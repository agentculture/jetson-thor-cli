"""Unit tests for the Jetson-specific probes: gpu's sysfs fallback, power, l4t.

Every collector takes an injectable runner and/or file root, so these tests
run deterministically off real Jetson Thor hardware (fixtures built in
``tmp_path`` mirror what was observed live on a Thor devkit: thin
``nvidia-smi`` NVML fields, ``/sys/class/devfreq`` GPU clocks, INA3221/INA238
hwmon rails, and ``/etc/nv_tegra_release``).
"""

from __future__ import annotations

from jetson_thor.probe import gpu, l4t, power, status

# --- gpu: sysfs fixture builder --------------------------------------------


def _write_gpu_sysfs(tmp_path, *, cur_hz="315000000", max_hz="1575000000"):
    """Build devfreq/thermal/hwmon fixtures matching what Thor exposes live."""
    devfreq = tmp_path / "devfreq"
    (devfreq / "gpu-gpc-0").mkdir(parents=True)
    (devfreq / "gpu-gpc-0" / "cur_freq").write_text(cur_hz + "\n")
    (devfreq / "gpu-gpc-0" / "max_freq").write_text(max_hz + "\n")

    thermal = tmp_path / "thermal"
    (thermal / "thermal_zone1").mkdir(parents=True)
    (thermal / "thermal_zone1" / "type").write_text("gpu-thermal\n")
    (thermal / "thermal_zone1" / "temp").write_text("48406\n")

    hwmon = tmp_path / "hwmon"
    (hwmon / "hwmon5").mkdir(parents=True)
    (hwmon / "hwmon5" / "name").write_text("ina3221\n")
    (hwmon / "hwmon5" / "in1_label").write_text("VDD_GPU\n")
    (hwmon / "hwmon5" / "in1_input").write_text("19864\n")
    (hwmon / "hwmon5" / "curr1_input").write_text("20\n")

    return str(devfreq), str(thermal), str(hwmon)


# --- gpu: nvidia-smi is thin on Thor (name+utilization only) --------------

# Real line captured on a Jetson Thor devkit: only name/utilization.* are
# populated; temperature/power/memory/clocks/fan all come back [N/A].
_THIN_SMI_LINE = "NVIDIA Thor, 0, 0, [N/A], [N/A], [N/A], [N/A], [N/A], [N/A], [N/A]\n"
_FULL_SMI_LINE = "NVIDIA Thor, 12, 3, 55, 20.5, 60, [N/A], [N/A], 900, [N/A]\n"


def _smi_runner(line: str):
    def _run(name: str, args) -> str:
        assert name == "nvidia-smi"
        if "--query-gpu" in " ".join(args):
            return line
        if "--query-compute-apps" in " ".join(args):
            return ""
        return ""

    return _run


def test_gpu_full_nvidia_smi_needs_no_sysfs_fallback(tmp_path) -> None:
    devfreq, thermal, hwmon = _write_gpu_sysfs(tmp_path)
    rep = gpu.collect(
        runner=_smi_runner(_FULL_SMI_LINE),
        devfreq_root=devfreq,
        thermal_root=thermal,
        hwmon_root=hwmon,
    )
    assert rep["available"] is True
    assert rep["source"] == "nvidia-smi"
    assert rep["data"]["sysfs_augmented_fields"] == []
    assert rep["data"]["gpu"]["temperature.gpu"] == "55"


def test_gpu_thin_nvidia_smi_falls_back_to_sysfs_for_missing_fields(tmp_path) -> None:
    devfreq, thermal, hwmon = _write_gpu_sysfs(tmp_path)
    rep = gpu.collect(
        runner=_smi_runner(_THIN_SMI_LINE),
        devfreq_root=devfreq,
        thermal_root=thermal,
        hwmon_root=hwmon,
    )
    assert rep["available"] is True
    assert rep["source"] == "nvidia-smi+sysfs"
    filled = set(rep["data"]["sysfs_augmented_fields"])
    assert filled == {"temperature.gpu", "power.draw", "clocks.sm"}
    vals = rep["data"]["gpu"]
    assert vals["temperature.gpu"] == "48.4"
    assert vals["clocks.sm"] == "315"
    assert float(vals["power.draw"]) > 0
    # utilization came straight from nvidia-smi and must be left untouched.
    assert vals["utilization.gpu"] == "0"
    # A GPU report at 48.4 C is nowhere near the hot threshold.
    assert rep["warnings"] == []


def test_gpu_thin_nvidia_smi_without_any_sysfs_stays_nvidia_smi_only(tmp_path) -> None:
    rep = gpu.collect(
        runner=_smi_runner(_THIN_SMI_LINE),
        devfreq_root=str(tmp_path / "no-devfreq"),
        thermal_root=str(tmp_path / "no-thermal"),
        hwmon_root=str(tmp_path / "no-hwmon"),
    )
    assert rep["available"] is True
    assert rep["source"] == "nvidia-smi"
    assert rep["data"]["sysfs_augmented_fields"] == []
    assert rep["data"]["gpu"]["temperature.gpu"] is None


def test_gpu_absent_nvidia_smi_uses_sysfs(tmp_path) -> None:
    devfreq, thermal, hwmon = _write_gpu_sysfs(tmp_path)
    rep = gpu.collect(
        runner=lambda _n, _a: None,
        devfreq_root=devfreq,
        thermal_root=thermal,
        hwmon_root=hwmon,
    )
    assert rep["available"] is True
    assert rep["source"] == "sysfs"
    data = rep["data"]["gpu"]
    assert data["clock_mhz"] == 315.0
    assert data["clock_pct_of_max"] == 20.0
    assert data["temperature_c"] == 48.406
    assert data["power_w"] is not None
    titles = [s["title"] for s in rep["sections"]]
    assert "GPU (sysfs)" in titles


def test_gpu_fully_degraded_when_neither_available(tmp_path) -> None:
    rep = gpu.collect(
        runner=lambda _n, _a: None,
        devfreq_root=str(tmp_path / "no-devfreq"),
        thermal_root=str(tmp_path / "no-thermal"),
        hwmon_root=str(tmp_path / "no-hwmon"),
    )
    assert rep["available"] is False
    assert rep["remediation"]
    assert "nvidia-smi" in rep["source"]
    assert "sysfs" in rep["source"]


# --- gpu: sysfs-built reports speak the nvidia-smi keys monitor/status read


def _hot_gpu_collect(tmp_path, monkeypatch):
    """Patch ``gpu.collect`` to read a 95 C gpu-thermal fixture (no nvidia-smi)."""
    devfreq, thermal, hwmon = _write_gpu_sysfs(tmp_path)
    (tmp_path / "thermal" / "thermal_zone1" / "temp").write_text("95000\n")
    real = gpu.collect

    def _collect(runner=None, **_kw):
        return real(
            runner=lambda _n, _a: None,
            devfreq_root=devfreq,
            thermal_root=thermal,
            hwmon_root=hwmon,
        )

    monkeypatch.setattr(gpu, "collect", _collect)


def test_gpu_sysfs_report_carries_nvidia_smi_shaped_keys(tmp_path) -> None:
    devfreq, thermal, hwmon = _write_gpu_sysfs(tmp_path)
    rep = gpu.collect(
        runner=lambda _n, _a: None, devfreq_root=devfreq, thermal_root=thermal, hwmon_root=hwmon
    )
    assert rep["source"] == "sysfs"
    g = rep["data"]["gpu"]
    assert g["temperature.gpu"] == "48.4"
    assert g["power.draw"] == f"{g['power_w']:.2f}"
    assert g["clocks.sm"] == "315"
    assert g["utilization.gpu"] is None  # sysfs has no utilization source
    # the sysfs-native keys stay for compatibility
    assert g["temperature_c"] == 48.406
    assert g["clock_mhz"] == 315.0


def test_gpu_sysfs_report_smi_keys_none_when_unknown(tmp_path) -> None:
    devfreq, _thermal, _hwmon = _write_gpu_sysfs(tmp_path)
    rep = gpu.collect(
        runner=lambda _n, _a: None,
        devfreq_root=devfreq,
        thermal_root=str(tmp_path / "no-thermal"),
        hwmon_root=str(tmp_path / "no-hwmon"),
    )
    g = rep["data"]["gpu"]
    assert g["clocks.sm"] == "315"
    assert g["temperature.gpu"] is None
    assert g["power.draw"] is None


def test_monitor_gpu_temp_alert_fires_from_sysfs_only_gpu(tmp_path, monkeypatch) -> None:
    from jetson_thor.monitor import engine
    from jetson_thor.monitor.config import DEFAULT_THRESHOLDS
    from jetson_thor.monitor.rules import evaluate

    _hot_gpu_collect(tmp_path, monkeypatch)
    snap = engine.snapshot(runner=lambda _n, _a: None)
    assert DEFAULT_THRESHOLDS["gpu_temp_c"] == 87.0
    alerts = [a for a in evaluate(snap, {"gpu_temp_c": 87.0}) if a.key == "gpu_temp_c"]
    assert len(alerts) == 1
    assert alerts[0].value == 95.0
    assert alerts[0].severity == "critical"


def test_status_gpu_line_shows_sysfs_temperature(tmp_path, monkeypatch) -> None:
    _hot_gpu_collect(tmp_path, monkeypatch)
    rep = status.collect(
        runner=lambda _n, _a: None, l4t_path=str(tmp_path / "no-such-nv_tegra_release")
    )
    items = next(s for s in rep["sections"] if s["title"] == "Subsystems")["items"]
    line = next(i for i in items if i.startswith("gpu:"))
    assert "95.0 C" in line
    assert "n/a C" not in line


# --- power ------------------------------------------------------------------


def _write_power_hwmon(tmp_path):
    hwmon = tmp_path / "hwmon"
    # ina3221: 3-channel rail monitor, matches what tegrastats also reports
    # (VDD_GPU / VDD_CPU_SOC_MSS / VIN_SYS_5V0), plus a non-rail diagnostic
    # channel (in7, "sum of shunt voltages") that has no matching curr node.
    chip = hwmon / "hwmon5"
    chip.mkdir(parents=True)
    (chip / "name").write_text("ina3221\n")
    (chip / "in1_label").write_text("VDD_GPU\n")
    (chip / "in1_input").write_text("19864\n")
    (chip / "curr1_input").write_text("20\n")
    (chip / "in2_label").write_text("VDD_CPU_SOC_MSS\n")
    (chip / "in2_input").write_text("19856\n")
    (chip / "curr2_input").write_text("300\n")
    (chip / "in7_label").write_text("sum of shunt voltages\n")
    (chip / "in7_input").write_text("680\n")  # no curr7_input -> must be skipped

    # ina238: single-channel VIN monitor with a direct power1_input (uW).
    chip2 = hwmon / "hwmon4"
    chip2.mkdir(parents=True)
    (chip2 / "name").write_text("ina238\n")
    (chip2 / "label").write_text("VIN\n")
    (chip2 / "power1_input").write_text("20986000\n")

    # A non-INA chip must be ignored entirely.
    chip3 = hwmon / "hwmon1"
    chip3.mkdir(parents=True)
    (chip3 / "name").write_text("pwmfan\n")

    return str(hwmon)


_NVPMODEL_OUT = "NV Power Mode: MAXN\n0\n"
_JETSON_CLOCKS_OUT = (
    "SOC family:tegra264  Machine:NVIDIA Jetson AGX Thor Developer Kit\n" "Online CPUs: 0-13\n"
)


def _power_runner(nvpmodel_out, jetson_clocks_out):
    def _run(name: str, args):
        if name == "nvpmodel":
            assert list(args) == ["-q"]
            return nvpmodel_out
        if name == "jetson_clocks":
            assert list(args) == ["--show"]
            return jetson_clocks_out
        raise AssertionError(f"unexpected tool {name}")

    return _run


def test_power_reports_mode_clocks_and_rails(tmp_path) -> None:
    hwmon = _write_power_hwmon(tmp_path)
    rep = power.collect(runner=_power_runner(_NVPMODEL_OUT, _JETSON_CLOCKS_OUT), hwmon_root=hwmon)
    assert rep["available"] is True
    data = rep["data"]
    assert data["nvpmodel"] == {"mode": "MAXN", "mode_id": "0", "raw": _NVPMODEL_OUT.strip()}
    assert data["jetson_clocks"]["raw"] == _JETSON_CLOCKS_OUT.strip()

    rails = {r["label"]: r["power_mw"] for r in data["rails"]}
    assert set(rails) == {"VDD_GPU", "VDD_CPU_SOC_MSS", "VIN"}  # in7 diagnostic entry skipped
    assert rails["VDD_GPU"] == 19864 * 20 / 1000.0
    assert rails["VIN"] == 20986000 / 1000.0

    titles = [s["title"] for s in rep["sections"]]
    assert titles == ["Power mode", "jetson_clocks", "Power rails"]


def test_power_degrades_gracefully_without_root(tmp_path) -> None:
    # nvpmodel/jetson_clocks unreachable (e.g. permission denied -> the
    # injected runner mirrors run_tool's None-on-nonzero-exit contract), but
    # hwmon rails are still readable without any privilege.
    hwmon = _write_power_hwmon(tmp_path)
    rep = power.collect(runner=lambda _n, _a: None, hwmon_root=hwmon)
    assert rep["available"] is True
    mode_items = next(s["items"] for s in rep["sections"] if s["title"] == "Power mode")
    assert "unavailable" in mode_items[0]
    jc_items = next(s["items"] for s in rep["sections"] if s["title"] == "jetson_clocks")
    assert "unavailable" in jc_items[0]
    assert rep["data"]["rails"]  # still populated


def test_power_unavailable_when_nothing_is_readable(tmp_path) -> None:
    rep = power.collect(runner=lambda _n, _a: None, hwmon_root=str(tmp_path / "no-hwmon"))
    assert rep["available"] is False
    assert rep["remediation"]


# --- l4t ---------------------------------------------------------------

# Real first line captured on a Jetson Thor devkit (/etc/nv_tegra_release).
_NV_TEGRA_RELEASE = (
    "# R38 (release), REVISION: 2.2, GCID: 42205042, BOARD: generic, "
    "EABI: aarch64, DATE: Thu Sep 25 22:47:11 UTC 2025\n"
    "# KERNEL_VARIANT: oot\n"
    "TARGET_USERSPACE_LIB_DIR=nvidia\n"
)


def test_l4t_parses_real_release_line(tmp_path) -> None:
    path = tmp_path / "nv_tegra_release"
    path.write_text(_NV_TEGRA_RELEASE)
    rep = l4t.collect(str(path))
    assert rep["available"] is True
    data = rep["data"]
    assert data["l4t"] == "R38.2.2"
    assert data["release"] == "R38"
    assert data["revision"] == "2.2"
    assert data["gcid"] == "42205042"
    assert data["board"] == "generic"
    assert data["eabi"] == "aarch64"
    assert data["date"] == "Thu Sep 25 22:47:11 UTC 2025"
    assert "R38.2.2" in " ".join(rep["sections"][0]["items"])


def test_l4t_unavailable_when_file_absent(tmp_path) -> None:
    rep = l4t.collect(str(tmp_path / "no-such-nv_tegra_release"))
    assert rep["available"] is False
    assert rep["remediation"]


def test_l4t_unavailable_on_malformed_content(tmp_path) -> None:
    path = tmp_path / "nv_tegra_release"
    path.write_text("not a tegra release file\n")
    rep = l4t.collect(str(path))
    assert rep["available"] is False
    assert rep["remediation"]


# --- l4t folded into status ------------------------------------------------


def test_status_includes_l4t_when_present(tmp_path) -> None:
    path = tmp_path / "nv_tegra_release"
    path.write_text(_NV_TEGRA_RELEASE)
    rep = status.collect(runner=lambda _n, _a: None, l4t_path=str(path))
    assert rep["data"]["host"]["l4t"] == "R38.2.2"


def test_status_l4t_is_none_off_jetson(tmp_path) -> None:
    rep = status.collect(
        runner=lambda _n, _a: None, l4t_path=str(tmp_path / "no-such-nv_tegra_release")
    )
    assert rep["data"]["host"]["l4t"] is None
