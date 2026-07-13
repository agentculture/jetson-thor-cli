# jetson-thor-cli 0.5.0 ships the machine-scope front ported from dgx-spark-cli: eight read-only host-telemetry verbs (status, memory, gpu, disk, thermal, containers, network, processes), a swap noun group (overview, status, grow, history, sample), and an AI-free webhook monitor watchdog — all adapted to Jetson Thor (Tegra/L4T), with Jetson-specific power-mode and clocks telemetry added, so an agent can track this Jetson Thor properly with zero runtime dependencies

> jetson-thor-cli 0.5.0 ships the machine-scope front ported from dgx-spark-cli: eight read-only host-telemetry verbs (status, memory, gpu, disk, thermal, containers, network, processes), a swap noun group (overview, status, grow, history, sample), and an AI-free webhook monitor watchdog — all adapted to Jetson Thor (Tegra/L4T), with Jetson-specific power-mode and clocks telemetry added, so an agent can track this Jetson Thor properly with zero runtime dependencies
> instruction: implement as one PR series: probe port, swap port, monitor port, Jetson power/L4T additions, docs+catalog; bump to 0.5.0 via the version-bump skill

## Audience

- agents (Claude Code, the colleague backend, mesh peers) and the human operator driving this Jetson Thor host
  - instruction: verify by running thor learn --json and thor explain <path> for every new noun/verb and checking each output names the real flags

## Before → After

- Before: jetson-thor-cli is a bare template: only identity/introspection verbs (whoami, learn, explain, overview, doctor); zero Jetson-domain functionality — the device cannot be tracked through the CLI at all
  - instruction: verify with uv run thor overview on main before branching
- After: one CLI (thor) exposes live host telemetry, swap management with history, and an always-on webhook watchdog, all --json, structured errors, zero runtime dependencies — an agent can learn and drive the full surface without docs
  - instruction: add tests asserting --json parses, stderr is empty on success, and pyproject dependencies stays empty

## Why it matters

- the Thor runs heavy AI workloads in 122GiB unified CPU+GPU memory; memory pressure, thermals, and swap are the real failure modes, and today nothing tracks them
  - instruction: cross-check thor status --json numbers against free -b and /sys/class/thermal on this machine in the verify step

## Requirements

- Port the probe package (status, memory, gpu, disk, thermal, containers, network, processes) as top-level thor verbs, adapted to Tegra: /proc + /sys collectors unchanged; gpu collector prefers tegrastats/sysfs and falls back to nvidia-smi; every collector degrades gracefully (available: false, exit 0) when a tool is missing
  - instruction: create jetson_thor/probe/ mirroring spark/probe (_run, _report, host, memory, disk, thermal, network, processes, containers, gpu, status); adapt gpu.py to try nvidia-smi then tegrastats/sysfs; register a machine.py command module exposing the eight top-level verbs; port the corresponding tests
  - honesty: each of the eight verbs, run on this Jetson Thor, exits 0 and returns real values (or available:false for genuinely absent subsystems) in both text and --json modes
- Port the swap noun group (thor swap overview/status/grow/history/sample) including sar trend, per-process history state, dry-run-by-default grow with --apply and --ephemeral, and the documented systemd timer for sampling
  - instruction: create jetson_thor/swap/ from spark/swap (state, sar, history, grow, apply) and a swap.py command module with overview/status/grow/history/sample; keep grow dry-run default with --apply/--ephemeral; document the systemd sample timer in README
  - honesty: thor swap status works without root; thor swap grow 64G without --apply changes nothing and prints the exact command plan; history/sample round-trip per-process state on disk
- Port the monitor noun group (check/once/run/test/config/install/enable/disable/status/uninstall): threshold rules, edge-triggered generic/slack/discord webhooks, startup liveness ping, systemd --user unit; config at ~/.config/jetson-thor/monitor.json with THOR_WEBHOOK_URL-style env override
  - instruction: create jetson_thor/monitor/ from spark/monitor (config, rules, engine, notify, state, systemd) and a monitor.py command module with check/once/run/test/config/install/enable/disable/status/uninstall; config dir and env var use the jetson-thor name settled in v2
  - honesty: monitor check evaluates all thresholds against live collectors with no state change, and monitor test delivers a real POST to a configured webhook; a standing alert fires exactly once (edge-triggered)
- Add Jetson-specific telemetry beyond the Spark port: a power verb (nvpmodel mode, jetson_clocks state, per-rail power from sysfs/tegrastats) and L4T/JetPack identity (from /etc/nv_tegra_release) surfaced in status and overview
  - instruction: add a power probe reading nvpmodel -q, jetson_clocks --show, and sysfs power rails, exposed as thor power; parse /etc/nv_tegra_release into an l4t field surfaced in status and overview; both degrade gracefully off-Jetson
  - honesty: thor power reports the active nvpmodel mode and jetson_clocks state on this host, and gracefully degrades on a non-Jetson machine; L4T R38.2.2 appears in thor status
- Every new noun/verb gets an explain catalog entry, learn/overview mention, tests keeping coverage >= 60, and the three-way thor naming invariant stays intact; version-bump to 0.5.0 with changelog
  - instruction: add catalog entries for every new noun/verb path, extend learn/overview text, extend test_every_catalog_path_resolves coverage, run the full lint+rubric matrix, and use the version-bump skill for 0.5.0
  - honesty: uv run teken cli doctor . --strict passes and every catalog path resolves (test_every_catalog_path_resolves green) after the port

## Honesty conditions

- version 0.5.0 on main ships all three feature layers plus the Jetson additions in one release, verified by the success-signal checks
- an agent that has never seen the repo can drive the new surface from thor learn + explain alone
- on main today, thor exposes exactly the five template verbs and nothing Jetson-specific
- every new verb supports --json, keeps stdout/stderr split, and raises CliError (never a traceback); dependencies = [] is unchanged in pyproject.toml
- thor status surfaces memory/swap/thermal anomalies first, matching what free/swapon/thermal sysfs report on this host
- no third-party import appears anywhere under jetson_thor/ and the only mutating code paths are swap grow --apply and monitor install/enable/disable/uninstall
- each listed command has been run on this Jetson Thor and its real output recorded in the PR description

## Success signals

- on this host: uv run thor status/memory/gpu/thermal/swap status all return real numbers with exit 0; thor doctor and the teken rubric gate stay green; full pytest + lint suite passes; monitor test delivers a webhook POST
  - instruction: run the full check matrix (verbs, doctor, rubric gate, pytest, lint, monitor test) on-device before opening the PR

## Scope / boundaries

- no AI in the watchdog, no new runtime dependencies (dependencies = [] stays), no mutation verbs beyond swap grow --apply and monitor service management; not a jtop replacement UI — read-only JSON-first telemetry
  - instruction: enforce with a test that imports every module and scans for non-stdlib imports; audit mutation paths in review

## Non-goals

- No flashing/provisioning, no fan or power-mode mutation (nvpmodel -m), no container lifecycle management, no historical dashboards — read-only telemetry plus the two existing mutation surfaces (swap grow, monitor service) only

## Assumptions

- dgx-spark-cli's collectors are directly reusable because Thor is also aarch64 Linux with unified memory; verified on this host: tegrastats, nvidia-smi, nvpmodel, jetson_clocks, docker, ip, sar all present on L4T R38.2.2

## Decisions

- Follow the repo's noun-group pattern: new modules under jetson_thor/cli/_commands/ with register(), probe/swap/monitor as sibling packages under jetson_thor/ — mirror dgx-spark-cli's layout, do not bolt onto template verbs

## Open / follow-up

- whether to also port dgx-spark-cli's contention (iowait/blocked-process) probe into monitor rules — include if the port is mechanical
