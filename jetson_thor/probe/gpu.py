"""``thor gpu`` — Blackwell GPU snapshot via nvidia-smi, with a sysfs fallback.

Jetson Thor's GPU shares one unified memory pool with the CPU cores — there is
no discrete VRAM — so ``nvidia-smi`` reports ``memory.total``/``memory.used``
as ``[N/A]``. This collector surfaces utilization, temperature, power and
clocks honestly and points at ``thor memory`` for the shared pool instead of
inventing a VRAM number.

On real Thor hardware ``nvidia-smi`` is present but *thin*: it reports
``name``/``utilization.gpu``/``utilization.memory`` but ``temperature.gpu``,
``power.draw`` and ``clocks.sm`` all come back ``[N/A]`` — the iGPU doesn't
expose those counters through NVML the way a discrete card does. When
nvidia-smi is "unhelpful" like this (or entirely absent), those specific
fields are backfilled from stable sysfs nodes instead of a streaming
``tegrastats`` (which never exits on its own and would need special-cased
process handling to bound):

* clock — the ``gpu-gpc-0`` (or similarly named) node under
  ``/sys/class/devfreq``.
* temperature — the ``thermal_zone*`` whose ``type`` contains ``gpu``.
* power — the ``VDD_GPU`` rail on the INA3221/INA238 power monitors under
  ``/sys/class/hwmon``.

Whichever fields were filled from sysfs are recorded in
``data["sysfs_augmented_fields"]`` and reflected in ``source``
(``"nvidia-smi"``, ``"nvidia-smi+sysfs"``, or plain ``"sysfs"`` when
nvidia-smi produced nothing at all).
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Optional

from jetson_thor.probe import _run
from jetson_thor.probe._report import (
    REASON_FAILED,
    REASON_NOT_INSTALLED,
    human_bytes,
    report,
    unavailable,
)
from jetson_thor.probe._run import Runner, default_runner

_HOT_C = 80.0

# nvidia-smi query-field names shared by the query list, the thin-response
# detection, the sysfs backfill, and the renderers.
_F_TEMP = "temperature.gpu"
_F_POWER = "power.draw"
_F_CLOCK = "clocks.sm"

_QUERY_FIELDS = [
    "name",
    "utilization.gpu",
    "utilization.memory",
    _F_TEMP,
    _F_POWER,
    "power.limit",
    "memory.total",
    "memory.used",
    _F_CLOCK,
    "fan.speed",
]

_GPU_RAIL_LABEL = "VDD_GPU"


def _na(value: str) -> Optional[str]:
    """Return a cleaned value, or ``None`` for nvidia-smi's ``[N/A]`` tokens."""
    cleaned = value.strip()
    if not cleaned or cleaned.upper().startswith("[N/A") or cleaned.upper() == "N/A":
        return None
    return cleaned


def _fmt(value: Optional[str], unit: str = "") -> str:
    return f"{value}{unit}" if value is not None else "n/a"


def _fmt_num(value: Optional[float], unit: str = "", digits: int = 1) -> str:
    return f"{value:.{digits}f}{unit}" if value is not None else "n/a"


def _split_csv(line: str) -> list[str]:
    """Split one nvidia-smi CSV line honouring quoting (process names can
    contain commas); ``str.split(",")`` would shift the columns."""
    try:
        # nvidia-smi separates with ", " — skipinitialspace so a quoted field
        # after the space is still recognised as quoted.
        return [field.strip() for field in next(csv.reader([line], skipinitialspace=True))]
    except (csv.Error, StopIteration):
        return [field.strip() for field in line.split(",")]


def _compute_apps(run: Runner) -> list[dict]:
    out = run(
        "nvidia-smi",
        ["--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
    )
    apps: list[dict] = []
    if not out:
        return apps
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = _split_csv(line)
        apps.append(
            {
                "pid": parts[0] if parts else "?",
                "name": parts[1] if len(parts) > 1 else "?",
                "used_mib": _na(parts[2]) if len(parts) > 2 else None,
            }
        )
    return apps


def _warn_hot(temp: Optional[str]) -> list[str]:
    if temp is None:
        return []
    try:
        return [f"GPU at {temp} C"] if float(temp) >= _HOT_C else []
    except ValueError:
        return []


def _memory_line(vals: dict, apps: list, gpu_mem_mib: int) -> str:
    if vals["memory.total"] is not None:
        return f"memory: {_fmt(vals['memory.used'])} / {vals['memory.total']} MiB"
    if apps and gpu_mem_mib:
        attributed = human_bytes(gpu_mem_mib * 1024 * 1024)
        return (
            f"memory: unified (no discrete VRAM); ~{attributed} attributed to "
            "GPU processes (see 'thor memory')"
        )
    return "memory: unified with system RAM (no discrete VRAM); see 'thor memory'"


def _app_items(apps: list) -> list[str]:
    if not apps:
        return ["none"]
    return [f"{a['pid']:>8} {a['name']} ({_fmt(a['used_mib'], ' MiB')})" for a in apps]


def _smi_unhelpful(vals: dict) -> bool:
    """True when nvidia-smi gave only name/utilization — no temp/power/clock.

    Real behavior on Thor: the iGPU's NVML surface reports these three as
    ``[N/A]`` even though nvidia-smi itself is present and working.
    """
    return vals[_F_TEMP] is None and vals[_F_POWER] is None and vals[_F_CLOCK] is None


def _sysfs_clock_mhz(devfreq_root: Path) -> tuple[Optional[float], Optional[float]]:
    """Return ``(cur_mhz, pct_of_max)`` from the GPU's devfreq node, if any.

    Prefers a node with "gpc" in its name (the 3D/graphics clock) over other
    GPU-adjacent devfreq nodes (e.g. the video decoder, "nvd").
    """
    if not devfreq_root.is_dir():
        return None, None
    candidates = sorted(devfreq_root.glob("*gpu*"), key=lambda p: 0 if "gpc" in p.name else 1)
    for node in candidates:
        cur = _run.read_first_line(node / "cur_freq")
        if not cur:
            continue
        try:
            cur_hz = int(cur)
        except ValueError:
            continue
        mx = _run.read_first_line(node / "max_freq")
        try:
            max_hz = int(mx) if mx else None
        except ValueError:
            max_hz = None
        pct = round(100.0 * cur_hz / max_hz, 1) if max_hz else None
        return cur_hz / 1_000_000.0, pct
    return None, None


def _sysfs_temp_c(thermal_root: Path) -> Optional[float]:
    """Read the first ``thermal_zone*`` whose type mentions "gpu"."""
    if not thermal_root.is_dir():
        return None
    for zdir in sorted(thermal_root.glob("thermal_zone*")):
        ztype = _run.read_first_line(zdir / "type") or ""
        if "gpu" not in ztype.lower():
            continue
        raw = _run.read_first_line(zdir / "temp")
        if not raw:
            continue
        try:
            return int(raw) / 1000.0
        except ValueError:
            continue
    return None


def _rail_power_w(hdir: Path, idx: str) -> Optional[float]:
    """Power for hwmon channel ``idx``: prefer ``power{idx}_input`` (uW)."""
    raw = _run.read_first_line(hdir / f"power{idx}_input")
    if raw:
        try:
            return int(raw) / 1_000_000.0
        except ValueError:
            pass
    volt = _run.read_first_line(hdir / f"in{idx}_input")
    curr = _run.read_first_line(hdir / f"curr{idx}_input")
    if volt and curr:
        try:
            return int(volt) * int(curr) / 1_000_000.0  # mV * mA -> mW, then /1000 -> W
        except ValueError:
            pass
    return None


def _sysfs_power_w(hwmon_root: Path, label: str = _GPU_RAIL_LABEL) -> Optional[float]:
    """Find the hwmon channel labeled ``label`` (e.g. "VDD_GPU") and read its power."""
    if not hwmon_root.is_dir():
        return None
    for hdir in sorted(hwmon_root.glob("hwmon*")):
        for label_path in sorted(hdir.glob("in*_label")):
            if _run.read_first_line(label_path) != label:
                continue
            idx = label_path.name[len("in") : -len("_label")]
            power = _rail_power_w(hdir, idx)
            if power is not None:
                return power
        if _run.read_first_line(hdir / "label") == label:
            power = _rail_power_w(hdir, "1")
            if power is not None:
                return power
    return None


def _sysfs_fallback(devfreq_root: Path, thermal_root: Path, hwmon_root: Path) -> dict:
    clock_mhz, clock_pct = _sysfs_clock_mhz(devfreq_root)
    return {
        "clock_mhz": clock_mhz,
        "clock_pct_of_max": clock_pct,
        "temperature_c": _sysfs_temp_c(thermal_root),
        "power_w": _sysfs_power_w(hwmon_root),
    }


def _sysfs_gpu_nodes_present(devfreq_root: Path, thermal_root: Path) -> bool:
    """True when a GPU sysfs node exists, readable or not.

    A node exists when ``devfreq_root`` has a ``*gpu*`` entry or any
    ``thermal_zone*`` type contains "gpu". Separates "no GPU here" (not
    installed) from "the GPU is there but its nodes yield nothing usable".
    """
    if devfreq_root.is_dir() and any(devfreq_root.glob("*gpu*")):
        return True
    if thermal_root.is_dir():
        for zdir in thermal_root.glob("thermal_zone*"):
            if "gpu" in (_run.read_first_line(zdir / "type") or "").lower():
                return True
    return False


def _unavailable_reason(devfreq_root: Path, thermal_root: Path) -> str:
    """Why neither nvidia-smi nor sysfs gave a GPU reading.

    ``not_installed`` only when nvidia-smi is not on PATH *and* no GPU sysfs
    node exists; otherwise the GPU is there and its probe is failing.
    """
    if shutil.which("nvidia-smi") is None and not _sysfs_gpu_nodes_present(
        devfreq_root, thermal_root
    ):
        return REASON_NOT_INSTALLED
    return REASON_FAILED


def _smi_shaped(sysfs: dict) -> dict:
    """The nvidia-smi-keyed view of a sysfs reading, formatted as the smi path is.

    ``monitor``'s gpu_temp rule and ``status``'s gpu line read these keys, so a
    sysfs-only report must carry them too; ``None`` when unknown (sysfs has no
    utilization source).
    """
    temp, power, clock = sysfs["temperature_c"], sysfs["power_w"], sysfs["clock_mhz"]
    return {
        _F_TEMP: f"{temp:.1f}" if temp is not None else None,
        _F_POWER: f"{power:.2f}" if power is not None else None,
        _F_CLOCK: f"{clock:.0f}" if clock is not None else None,
        "utilization.gpu": None,
    }


def _sysfs_report(sysfs: dict) -> dict:
    clock_item = f"clock: {_fmt_num(sysfs['clock_mhz'], ' MHz', 0)}"
    if sysfs["clock_pct_of_max"] is not None:
        clock_item += f" ({sysfs['clock_pct_of_max']:.0f}% of max)"
    items = [
        clock_item,
        f"temperature: {_fmt_num(sysfs['temperature_c'], ' C')}",
        f"power: {_fmt_num(sysfs['power_w'], ' W', 2)}",
        "memory: unified with system RAM (no discrete VRAM); see 'thor memory'",
    ]
    sections = [{"title": "GPU (sysfs)", "items": items}]
    warnings = _warn_hot(
        f"{sysfs['temperature_c']}" if sysfs["temperature_c"] is not None else None
    )
    # Keep the sysfs-native keys (temperature_c, ...) and add the smi-shaped ones.
    data = {"gpu": {**sysfs, **_smi_shaped(sysfs)}, "compute_apps": [], "gpu_attributed_mib": 0}
    return report("gpu", source="sysfs", sections=sections, warnings=warnings, data=data)


def _augment_from_sysfs(
    vals: dict, devfreq_root: Path, thermal_root: Path, hwmon_root: Path
) -> list[str]:
    """Backfill temp/power/clock into ``vals`` from sysfs; return filled field names."""
    sysfs = _sysfs_fallback(devfreq_root, thermal_root, hwmon_root)
    filled: list[str] = []
    if sysfs["temperature_c"] is not None:
        vals[_F_TEMP] = f"{sysfs['temperature_c']:.1f}"
        filled.append(_F_TEMP)
    if sysfs["power_w"] is not None:
        vals[_F_POWER] = f"{sysfs['power_w']:.2f}"
        filled.append(_F_POWER)
    if sysfs["clock_mhz"] is not None:
        vals[_F_CLOCK] = f"{sysfs['clock_mhz']:.0f}"
        filled.append(_F_CLOCK)
    return filled


def collect(
    runner: Optional[Runner] = None,
    devfreq_root: str = "/sys/class/devfreq",
    thermal_root: str = "/sys/class/thermal",
    hwmon_root: str = "/sys/class/hwmon",
) -> dict:
    """Return a GPU report using ``runner`` (injectable; defaults to nvidia-smi).

    ``devfreq_root``/``thermal_root``/``hwmon_root`` are injectable sysfs roots
    used only when nvidia-smi is absent or reports temp/power/clock as N/A.
    """
    run = runner or default_runner
    out = run(
        "nvidia-smi",
        ["--query-gpu=" + ",".join(_QUERY_FIELDS), "--format=csv,noheader,nounits"],
    )

    if out is None:
        sysfs = _sysfs_fallback(Path(devfreq_root), Path(thermal_root), Path(hwmon_root))
        if not any(v is not None for v in sysfs.values()):
            return unavailable(
                "gpu",
                "nvidia-smi, sysfs",
                "install NVIDIA drivers / run on Jetson Thor "
                "(with devfreq + hwmon nodes present)",
                reason=_unavailable_reason(Path(devfreq_root), Path(thermal_root)),
            )
        return _sysfs_report(sysfs)

    line = next((row for row in out.splitlines() if row.strip()), "")
    fields = _split_csv(line)
    fields += [""] * (len(_QUERY_FIELDS) - len(fields))
    vals = {key: _na(fields[i]) for i, key in enumerate(_QUERY_FIELDS)}

    # Compute apps DO report per-process memory even though the aggregate
    # memory.total/used is N/A on unified architecture. Summing them is the
    # closest honest answer to "GPU memory used" on Jetson Thor.
    apps = _compute_apps(run)
    gpu_mem_mib = sum(int(a["used_mib"]) for a in apps if a["used_mib"] and a["used_mib"].isdigit())

    source = "nvidia-smi"
    sysfs_fields: list[str] = []
    if _smi_unhelpful(vals):
        sysfs_fields = _augment_from_sysfs(
            vals, Path(devfreq_root), Path(thermal_root), Path(hwmon_root)
        )
        if sysfs_fields:
            source = "nvidia-smi+sysfs"

    sections = [
        {
            "title": vals["name"] or "NVIDIA GPU",
            "items": [
                f"utilization: {_fmt(vals['utilization.gpu'], '%')}"
                f" (mem ctrl {_fmt(vals['utilization.memory'], '%')})",
                f"temperature: {_fmt(vals[_F_TEMP], ' C')}",
                f"power: {_fmt(vals[_F_POWER], ' W')} / {_fmt(vals['power.limit'], ' W')}",
                f"sm clock: {_fmt(vals[_F_CLOCK], ' MHz')}",
                f"fan: {_fmt(vals['fan.speed'], '%')}",
                _memory_line(vals, apps, gpu_mem_mib),
            ],
        },
        {"title": "GPU compute processes", "items": _app_items(apps)},
    ]

    data = {
        "gpu": vals,
        "compute_apps": apps,
        "gpu_attributed_mib": gpu_mem_mib,
        "sysfs_augmented_fields": sysfs_fields,
    }
    return report(
        "gpu",
        source=source,
        sections=sections,
        warnings=_warn_hot(vals[_F_TEMP]),
        data=data,
    )
