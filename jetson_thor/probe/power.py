"""``thor power`` — nvpmodel mode, jetson_clocks state, and per-rail power draw.

Jetson Thor exposes power posture through three independent, often
root-gated sources:

* ``nvpmodel -q`` — the active power mode profile (e.g. ``MAXN``). Readable
  without root on stock images, but the binary or the mode file it reads may
  not be, so this degrades gracefully rather than assuming access.
* ``jetson_clocks --show`` — whether CPU/GPU clocks are pinned to max.
  Requires root on Thor (``Error: Run this script(...) as a root user``,
  exit 1); a permission failure surfaces as absent data, never a crash.
* INA3221/INA238-family power monitor chips under ``/sys/class/hwmon`` —
  read-only rail telemetry (e.g. ``VDD_GPU``, ``VDD_CPU_SOC_MSS``,
  ``VIN_SYS_5V0``, ``VIN``) that needs no privilege at all.

Each source is read independently and reported on its own; the overall
report is only ``unavailable`` when none of the three yielded anything.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from jetson_thor.probe import _run
from jetson_thor.probe._report import report, unavailable
from jetson_thor.probe._run import Runner, default_runner

# hwmon chip driver names treated as power monitors (INA3221, INA238, INA226, ...).
_INA_PREFIX = "ina"


def _parse_nvpmodel(out: Optional[str]) -> dict:
    """Parse ``nvpmodel -q`` output, e.g. ``"NV Power Mode: MAXN\\n0\\n"``."""
    if not out or not out.strip():
        return {"mode": None, "mode_id": None, "raw": None}
    mode: Optional[str] = None
    mode_id: Optional[str] = None
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("nv power mode"):
            mode = stripped.partition(":")[2].strip()
        elif stripped.isdigit():
            mode_id = stripped
    return {"mode": mode, "mode_id": mode_id, "raw": out.strip()}


def _parse_jetson_clocks(out: Optional[str]) -> dict:
    """``jetson_clocks --show`` output is kept raw (long, host-specific)."""
    if not out or not out.strip():
        return {"raw": None}
    return {"raw": out.strip()}


def _rail_power_mw(hdir: Path, idx: str) -> Optional[float]:
    """Power for hwmon channel ``idx``: prefer ``power{idx}_input`` (uW -> mW)."""
    raw = _run.read_first_line(hdir / f"power{idx}_input")
    if raw:
        try:
            return int(raw) / 1000.0
        except ValueError:
            pass
    volt = _run.read_first_line(hdir / f"in{idx}_input")
    curr = _run.read_first_line(hdir / f"curr{idx}_input")
    if volt and curr:
        try:
            return int(volt) * int(curr) / 1000.0  # mV * mA / 1000 -> mW
        except ValueError:
            pass
    return None


def _chip_rails(hdir: Path) -> list[dict]:
    """Rails for one hwmon chip: multi-channel (``in{n}_label``) or single (``label``)."""
    rails: list[dict] = []
    label_files = sorted(hdir.glob("in*_label"))
    if label_files:
        for label_path in label_files:
            idx = label_path.name[len("in") : -len("_label")]
            label = _run.read_first_line(label_path)
            if not label:
                continue
            # Channels without a matching current node (e.g. INA3221's "sum of
            # shunt voltages" diagnostic entry) aren't a real power rail.
            if _run.read_first_line(hdir / f"curr{idx}_input") is None:
                continue
            rails.append({"label": label, "power_mw": _rail_power_mw(hdir, idx)})
        return rails

    label = _run.read_first_line(hdir / "label")
    if label:
        rails.append({"label": label, "power_mw": _rail_power_mw(hdir, "1")})
    return rails


def _rails(hwmon_root: Path) -> list[dict]:
    if not hwmon_root.is_dir():
        return []
    rails: list[dict] = []
    for hdir in sorted(hwmon_root.glob("hwmon*")):
        name = (_run.read_first_line(hdir / "name") or "").lower()
        if not name.startswith(_INA_PREFIX):
            continue
        rails.extend(_chip_rails(hdir))
    return rails


def collect(runner: Optional[Runner] = None, hwmon_root: str = "/sys/class/hwmon") -> dict:
    """Return a power report (nvpmodel + jetson_clocks + hwmon rails).

    ``hwmon_root`` is injectable for tests; ``runner`` is the same
    :data:`~jetson_thor.probe._run.Runner` convention as the other probes.
    """
    run = runner or default_runner

    nvpmodel = _parse_nvpmodel(run("nvpmodel", ["-q"]))
    jetson_clocks = _parse_jetson_clocks(run("jetson_clocks", ["--show"]))
    rails = _rails(Path(hwmon_root))

    if nvpmodel["mode"] is None and jetson_clocks["raw"] is None and not rails:
        return unavailable(
            "power",
            "nvpmodel, jetson_clocks, hwmon",
            "run on Jetson Thor; nvpmodel/jetson_clocks may need root, "
            "and rail telemetry needs an INA3221/INA238 hwmon node",
        )

    sections = []

    if nvpmodel["mode"] is not None:
        mode_item = f"mode: {nvpmodel['mode']}"
        if nvpmodel["mode_id"] is not None:
            mode_item += f" (id {nvpmodel['mode_id']})"
        sections.append({"title": "Power mode", "items": [mode_item]})
    else:
        sections.append(
            {"title": "Power mode", "items": ["unavailable (nvpmodel absent or needs root)"]}
        )

    if jetson_clocks["raw"] is not None:
        sections.append({"title": "jetson_clocks", "items": [jetson_clocks["raw"].splitlines()[0]]})
    else:
        sections.append(
            {
                "title": "jetson_clocks",
                "items": ["unavailable (jetson_clocks absent or needs root)"],
            }
        )

    if rails:
        rail_items = [
            (
                f"{r['label']}: {r['power_mw']:.0f} mW"
                if r["power_mw"] is not None
                else f"{r['label']}: n/a"
            )
            for r in rails
        ]
        sections.append({"title": "Power rails", "items": rail_items})

    data = {"nvpmodel": nvpmodel, "jetson_clocks": jetson_clocks, "rails": rails}
    return report(
        "power",
        source="nvpmodel, jetson_clocks, hwmon",
        sections=sections,
        data=data,
    )
