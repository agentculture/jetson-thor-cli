# jetson-thor-cli

Agent and CLI for operating NVIDIA Jetson Thor (Blackwell-based robotics/edge-AI compute, Orin's successor) — provisioning, inference, and on-device ops.

## What you get

- **An agent-first CLI** cited from [teken](https://github.com/agentculture/teken)'s
  `python-cli` reference — the runtime package has no third-party dependencies.
- **A mesh identity** — `culture.yaml` (`suffix` + `backend`) and the matching
  resident prompt file (`AGENTS.colleague.md`, since this template runs
  `backend: colleague`).
- **The canonical guildmaster skill kit** (14 skills) under `.claude/skills/`,
  vendored cite-don't-import. See [`docs/skill-sources.md`](docs/skill-sources.md).
- **A build + deploy baseline** — pytest, lint, the agent-first rubric gate, and
  PyPI Trusted Publishing wired into GitHub Actions.

## Quickstart

```bash
uv sync
uv run pytest -n auto                 # run the test suite
uv run thor whoami             # identity from culture.yaml
uv run thor learn              # self-teaching prompt (add --json)
uv run thor status             # machine-wide scope, anomalies first
uv run teken cli doctor . --strict    # the agent-first rubric gate CI runs
```

## CLI

| Verb | What it does |
|------|--------------|
| `whoami` | Report this agent's nick, version, backend, and model from `culture.yaml`. |
| `learn` | Print a structured self-teaching prompt. |
| `explain <path>` | Markdown docs for any noun/verb path. |
| `overview` | Read-only descriptive snapshot of the agent. |
| `doctor` | Check the agent-identity invariants (prompt-file-present, backend-consistency). |
| `cli overview` | Describe the CLI surface itself. |

Every command supports `--json`. Results go to stdout, errors/diagnostics to
stderr (never mixed). Exit codes: `0` success, `1` user error, `2` environment
error, `3+` reserved.

### Machine scope (Jetson Thor host telemetry)

Jetson Thor *is* the system, so these read-only verbs sit at the top level:

| Verb | What it does |
|------|--------------|
| `status` | Machine-wide scope, anomalies first — the headline (includes the L4T version). |
| `memory` | Unified RAM + swap (CPU and iGPU share one pool). |
| `gpu` | Blackwell iGPU: utilization, temp, power, clocks, and GPU processes. |
| `disk` | Filesystem usage for real block devices (via `/proc/mounts` + `statvfs`). |
| `thermal` | SoC thermal zones and hwmon sensors (no `lm-sensors` needed). |
| `containers` | Running Docker containers and their health. |
| `network` | Interfaces, default route, and reachable addresses. |
| `processes` | Top processes by resident memory (via `/proc`). |
| `power` | nvpmodel mode, jetson_clocks state, and per-rail power draw (Jetson-only — no discrete-GPU equivalent). |

They have zero runtime dependencies — kernel telemetry is read from `/proc`
and `/sys`, while `nvidia-smi`, `docker`, and `ip` are shelled out and degrade
gracefully (a missing tool reports `available: false` and still exits 0).
`doctor` remains the health gate.

On real Thor hardware `nvidia-smi` is present but *thin*: it reports
`name`/`utilization.gpu`/`utilization.memory` but `temperature.gpu`,
`power.draw`, and `clocks.sm` all come back `[N/A]` — the iGPU doesn't expose
those counters through NVML the way a discrete card does. `gpu` backfills
those three fields from stable sysfs nodes instead (devfreq for clock, the
`*gpu*` thermal zone for temperature, the `VDD_GPU` hwmon rail for power), and
records which fields it backfilled in `source` (`nvidia-smi+sysfs`). Because
Thor's GPU shares one **unified memory pool** with the CPU — no discrete
VRAM — `nvidia-smi` reports `memory.total`/`memory.used` as `[N/A]` too; `gpu`
instead sums per-process compute-app memory and points at `thor memory` for
the shared pool rather than inventing a VRAM number:

```bash
uv run thor gpu
uv run thor power
```

### Swap management

Swap inspection is read-only; the `grow` command is a dry-run by default —
re-run with `--apply` to mutate. All commands support `--json`.

| Verb | What it does |
|------|--------------|
| `thor swap overview` | Comprehensive read of the swap noun: the descriptive summary **plus** the live snapshot (memory, swap, devices, sar trend). The superset of `status`. |
| `thor swap status` | The quick snapshot only: read-only swap + memory pressure with a recent sar trend. No root needed. (Also shown, with the verb list, by `thor swap overview`.) |
| `thor swap grow SIZE [--apply] [--ephemeral]` | Grow swap. DEFAULT is a DRY RUN: prints a warning and the exact command plan but changes nothing. Re-run with `--apply` to actually perform it (needs root — without root it prints the plan and a `sudo ... --apply` hint). `--ephemeral` activates the new size for this boot only (no `/etc/fstab` change); the default is permanent (survives reboot). `SIZE` is a placeholder — replace it with a value like `64G`, `32GiB`, or a raw byte count (e.g. `thor swap grow 64G`; don't type the literal word `size`). |
| `thor swap history [--window DUR] [--top N]` | Top per-process memory/swap consumers over a time window (e.g. `--window 1h --top 10`). |
| `thor swap sample` | Record one per-process telemetry snapshot (this is what a scheduled timer calls). |

```bash
uv run thor swap status
uv run thor swap grow 64G      # dry-run: prints the plan, changes nothing
uv run thor swap history --window 1h --top 5
uv run thor swap sample
```

#### Per-process history collection via systemd timer

Per-process memory and swap history accrues only when `thor swap sample` runs
on a schedule. Here's a systemd service and timer pair:

```ini
# /etc/systemd/system/jetson-thor-swap-sample.service
[Unit]
Description=Sample per-process swap/memory for jetson-thor-cli
[Service]
Type=oneshot
ExecStart=/usr/bin/env thor swap sample

# /etc/systemd/system/jetson-thor-swap-sample.timer
[Unit]
Description=Periodic thor swap sample
[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
Persistent=true
[Install]
WantedBy=timers.target
```

Enable with `sudo systemctl enable --now jetson-thor-swap-sample.timer`. Note
that system-level CPU/mem/swap trend already comes from sysstat/sar; this
timer only adds the per-process layer.

### Monitoring (`monitor`) — AI-free webhook watchdog

`monitor` turns the collectors into a deterministic, always-on watchdog. It
evaluates the same numbers against configurable thresholds and POSTs to a
**generic webhook** when a catastrophe condition crosses — and again when it
clears (edge-triggered, so a standing condition doesn't spam). No AI, no new
dependencies (`urllib` does the POST).

```bash
uv run thor monitor config --init     # scaffold ~/.config/jetson-thor/monitor.json
export JETSON_THOR_WEBHOOK_URL=https://…  # or put webhook_url in the config
uv run thor monitor check             # dry run: what's firing right now
uv run thor monitor config            # show resolved config + thresholds
```

| Verb | What it does |
|------|--------------|
| `monitor check` | Evaluate thresholds now (no webhook, no state change). |
| `monitor once` | One cycle: evaluate, deliver transitions, update state. |
| `monitor run` | Foreground watch loop (the systemd `ExecStart`). |
| `monitor test` | POST a synthetic alert to verify the webhook. |
| `monitor config [--init]` | Show resolved config / write a scaffold. |
| `monitor install\|enable\|disable\|status\|uninstall` | Manage the systemd `--user` service (unit: `jetson-thor-monitor.service`). |

Watches memory %, swap %, disk %, hottest sensor, GPU temp, load-per-core,
I/O contention (iowait % + blocked processes), container health, and
subsystem availability. Thresholds live in the config
(`~/.config/jetson-thor/monitor.json`; `null` disables a check);
`webhook_format` is `generic` (default), `slack`, or `discord`.

When `monitor run` starts (the systemd `ExecStart`), it POSTs a one-shot
**"started watching"** liveness alert — so a watchdog that silently fails to
come up is noticed by the absence of its heartbeat, not just the absence of
an alert. A failed startup POST is logged, never fatal. Set
`notify_on_start: false` in the config to disable it.

## Make it your own

1. Rename the package `jetson_thor/` and the `jetson-thor-cli`
   CLI/dist name throughout `pyproject.toml`, the package, `tests/`,
   `sonar-project.properties`, and this `README.md`. The name is hard-coded in
   ~100 places, so list every occurrence first — see the `git grep` discovery
   command in [`CLAUDE.md`](CLAUDE.md), the authoritative rename procedure.
2. Edit `culture.yaml` with your `suffix` and `backend`.
3. Rewrite `CLAUDE.md` for your agent and run `/init`.
4. Re-vendor only the skills you need from guildmaster (see
   [`docs/skill-sources.md`](docs/skill-sources.md)).

See [`CLAUDE.md`](CLAUDE.md) for the full conventions (version-bump-every-PR,
the `cicd` PR lane, deploy setup).

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
