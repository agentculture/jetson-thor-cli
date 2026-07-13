# Build Plan — jetson-thor-cli 0.5.0 ships the machine-scope front ported from dgx-spark-cli: eight read-only host-telemetry verbs (status, memory, gpu, disk, thermal, containers, network, processes), a swap noun group (overview, status, grow, history, sample), and an AI-free webhook monitor watchdog — all adapted to Jetson Thor (Tegra/L4T), with Jetson-specific power-mode and clocks telemetry added, so an agent can track this Jetson Thor properly with zero runtime dependencies

slug: `jetson-thor-cli-0-5-0-ships-the-machine-scope-fron` · status: `exported` · from frame: `jetson-thor-cli-0-5-0-ships-the-machine-scope-fron`

> jetson-thor-cli 0.5.0 ships the machine-scope front ported from dgx-spark-cli: eight read-only host-telemetry verbs (status, memory, gpu, disk, thermal, containers, network, processes), a swap noun group (overview, status, grow, history, sample), and an AI-free webhook monitor watchdog — all adapted to Jetson Thor (Tegra/L4T), with Jetson-specific power-mode and clocks telemetry added, so an agent can track this Jetson Thor properly with zero runtime dependencies

## Tasks

### t1 — Port the probe collector package: jetson_thor/probe/ (_run, _report, host, memory, disk, thermal, network, processes, containers, status) from spark/probe — no CLI wiring yet

- covers: c8
- acceptance:
  - each collector returns a dict with an available flag; a missing external tool yields available:false with no exception
  - unit tests with faked /proc//sys reads and stubbed subprocess calls pass for every collector (tests/test_probe_*.py)

### t2 — Add Jetson-specific probes: probe/gpu.py (nvidia-smi with tegrastats/sysfs fallback), probe/power.py (nvpmodel -q, jetson_clocks --show, sysfs power rails), probe/l4t.py (/etc/nv_tegra_release parser)

- depends on: t1
- covers: c11
- acceptance:
  - gpu probe returns utilization/temp/power from whichever source is available and available:false when neither exists
  - power probe reports active nvpmodel mode and jetson_clocks state, degrading gracefully off-Jetson; l4t parser extracts release/revision from a sample nv_tegra_release line
  - unit tests cover both the nvidia-smi and tegrastats paths plus the degraded path

### t3 — Register the machine scope: _commands/machine.py exposing top-level thor verbs status/memory/gpu/disk/thermal/containers/network/processes/power, wired in _build_parser, with catalog entries for each

- depends on: t1, t2
- covers: c8, h1
- acceptance:
  - uv run thor <verb> and thor <verb> --json exit 0 for all nine verbs with stdout-only results
  - every new path resolves in test_every_catalog_path_resolves; status surfaces anomalies first and includes the l4t field

### t4 — Port the swap noun group: jetson_thor/swap/ (state, sar, history, grow, apply) plus _commands/swap.py (overview/status/grow/history/sample) with catalog entries

- depends on: t1, t3
- covers: c9, h2
- acceptance:
  - thor swap status works without root; thor swap grow 64G without --apply mutates nothing and prints the exact command plan with a sudo --apply hint
  - sample followed by history round-trips per-process state on disk (tested against a temp state dir); --ephemeral skips the fstab step in the plan

### t5 — Port the monitor watchdog: jetson_thor/monitor/ (config, rules, engine, notify, state, systemd) plus _commands/monitor.py (check/once/run/test/config/install/enable/disable/status/uninstall) with catalog entries

- depends on: t1, t4
- covers: c10, h3
- acceptance:
  - monitor check evaluates all thresholds against live collectors with zero state change; monitor test POSTs a synthetic alert via urllib to the configured webhook
  - edge-trigger tested: a standing over-threshold condition delivers exactly one alert and one clear across engine cycles
  - config resolves from ~/.config/jetson-thor/monitor.json with env-var webhook override; monitor run posts the startup liveness alert

### t6 — Teach the surface: extend learn.py and overview.py to cover machine/swap/monitor verbs, and rewrite README feature sections (telemetry table, swap table, monitor walkthrough, systemd timer) for thor

- depends on: t3, t4, t5
- covers: c2, h7
- acceptance:
  - thor learn --json names every new noun/verb with real flags; thor overview lists the machine scope
  - every README command example uses the thor script name and runs as written on this host

### t7 — Release assembly: version-bump to 0.5.0 with Keep-a-Changelog entry, CLAUDE.md architecture notes for the three new packages, naming-invariant check

- depends on: t6
- covers: c1, c12
- acceptance:
  - pyproject version is 0.5.0 and CHANGELOG has the 0.5.0 entry listing all three feature layers
  - [project.scripts], prog=, and the catalog root ENTRIES all still say thor

### t8 — Guard tests + on-device verification matrix: no-third-party-import scan test, output-contract tests (json parses, stderr empty on success), dependencies=[] assertion, baseline-main check, and the full on-device run recorded for the PR

- depends on: t7
- covers: c3, c4, c5, c6, c7, h4, h5, h6, h8, h9, h10, h11, h12
- acceptance:
  - a test imports every jetson_thor module and fails on any non-stdlib import; a test asserts pyproject dependencies == []
  - on this host: all nine machine verbs, swap status, doctor, monitor check return real data exit 0; thor status numbers cross-checked against free -b and /sys/class/thermal
  - uv run pytest -n auto (coverage >=60), all six lint gates, and uv run teken cli doctor . --strict pass; monitor test delivers a real webhook POST; outputs recorded in the PR description

## Risks

- [unknown_nonblocking] exact GPU metric source on the Thor iGPU (nvidia-smi vs tegrastats/sysfs) — collector handles both, decided empirically in t2 (task t2)
- [unknown_nonblocking] webhook env var + config dir naming (JETSON_THOR_WEBHOOK_URL vs THOR_WEBHOOK_URL; ~/.config/jetson-thor/) — settle in t5 (task t5)
- [follow_up] porting the iowait/blocked-process contention probe into monitor rules — include in t5 if mechanical, else follow-up (task t5)
