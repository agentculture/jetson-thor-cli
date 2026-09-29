"""Markdown catalog for ``thor explain <path>``.

Each entry is verbatim markdown. Keys are command-path tuples. The empty tuple
and ``("thor",)`` both resolve to the root entry.

Keep bodies self-contained: an agent reading one entry should get enough
context without chaining reads.
"""

from __future__ import annotations

_ROOT = """\
# thor

Agent-first CLI for the NVIDIA Jetson Thor device: machine telemetry (`status`,
`memory`, `gpu`, `disk`, `thermal`, ...), `swap` inspection and planning, and a
`monitor` webhook watchdog. It also carries a mesh identity (`culture.yaml` +
`CLAUDE.md`) and the canonical guildmaster skill kit under `.claude/skills/`.

## Agent verbs

- `thor whoami` — identity probe from `culture.yaml`.
- `thor learn` — structured self-teaching prompt.
- `thor explain <path>` — markdown docs for any noun/verb.
- `thor overview` — descriptive snapshot of the agent.
- `thor doctor` — check the agent-identity invariants.
- `thor cli overview` — describe the CLI surface.
- `thor monitor` — deterministic, AI-free threshold watchdog that webhooks on
  catastrophes.

## Machine-scope verbs (Jetson Thor host telemetry)

- `thor status` — machine-wide scope, anomalies first (the headline); includes
  the flashed L4T release.
- `thor memory` — unified RAM + swap (CPU and iGPU share one pool).
- `thor gpu` — Jetson Thor iGPU: utilization, temp, power, GPU processes.
- `thor disk` — filesystem usage for real block devices.
- `thor thermal` — SoC thermal zones and hwmon sensors.
- `thor containers` — running Docker containers and health.
- `thor network` — interfaces, default route, reachable addresses.
- `thor processes` — top processes by resident memory.
- `thor power` — nvpmodel mode, jetson_clocks state, per-rail power draw.

All machine-scope verbs are read-only, support `--json`, and exit 0 even when a
subsystem is absent (it reports `available: false`). `doctor` is the health gate.

## Exit-code policy

- `0` success
- `1` user-input error
- `2` environment / setup error
- `3+` reserved

## See also

- `thor explain whoami`
- `thor explain doctor`
"""

_WHOAMI = """\
# thor whoami

Reports the agent's identity from `culture.yaml`: nick (`suffix`), backend,
served model, and the package version. Read-only.

## Usage

    thor whoami
    thor whoami --json
"""

_LEARN = """\
# thor learn

Prints a structured self-teaching prompt covering purpose, command map,
exit-code policy, `--json` support, and the `explain` pointer.

## Usage

    thor learn
    thor learn --json
"""

_EXPLAIN = """\
# thor explain <path>

Prints markdown documentation for any noun/verb path. Unlike `--help` (terse,
positional), `explain` is global and addressable by path.

## Usage

    thor explain thor
    thor explain whoami
    thor explain --json <path>
"""

_OVERVIEW = """\
# thor overview

Read-only descriptive snapshot of the agent: identity (from `culture.yaml`), the
verb surface, and the sibling-pattern artifacts the agent carries. Accepts an
ignored `target` so a stray path never hard-fails.

## Usage

    thor overview
    thor overview --json
"""

_DOCTOR = """\
# thor doctor

Checks the agent-identity invariants `steward doctor` verifies:
prompt-file-present and backend-consistency (`colleague` → `AGENTS.colleague.md`), plus a
skills-present check. Exits 1 when unhealthy.

## Usage

    thor doctor
    thor doctor --json
"""

_CLI = """\
# thor cli

Noun group for CLI-surface introspection. `cli overview` describes the CLI
itself (distinct from the global `overview`, which describes the agent).

## Usage

    thor cli overview
    thor cli overview --json
"""

_STATUS = """\
# thor status

Machine-wide scope of Jetson Thor, anomalies first. Calls every domain
collector once and prints a Host header (including the flashed L4T release,
e.g. `R38.2.2`, read from `/etc/nv_tegra_release`), an Attention block (merged
warnings from all subsystems), and a compact one-liner per subsystem. The
headline entry point — drill into any line with its verb (`memory`, `gpu`, …).

The L4T field degrades to `n/a` off-Jetson (the release file only exists on a
flashed Jetson board) rather than raising.

Read-only; exits 0 even if a subsystem is unavailable.

## Usage

    thor status
    thor status --json
"""

_MEMORY = """\
# thor memory

Unified memory + swap snapshot from `/proc/meminfo`. On Jetson Thor the CPU
cores and Blackwell iGPU share ONE memory pool — there is no separate VRAM —
so memory pressure here is a GPU-workload signal too. Warns on low available
memory or heavy swap use.

## Usage

    thor memory
    thor memory --json
"""

_GPU = """\
# thor gpu

Jetson Thor iGPU snapshot via `nvidia-smi`, with a sysfs fallback. Because
memory is unified, `nvidia-smi` reports aggregate `memory.total/used` as
`[N/A]`; this verb instead sums the per-process compute-app memory to report
how much of the shared pool is attributed to the GPU.

On real Thor hardware `nvidia-smi` is present but *thin*: it reports
`name`/`utilization.gpu`/`utilization.memory`, but `temperature.gpu`,
`power.draw`, and `clocks.sm` come back `[N/A]` — the iGPU doesn't expose those
counters through NVML the way a discrete card does. When nvidia-smi is
unhelpful like this (or entirely absent), those fields are backfilled from
stable sysfs nodes instead: `/sys/class/devfreq` (clock), `/sys/class/thermal`
(GPU thermal zone), and the `VDD_GPU` rail under `/sys/class/hwmon` (power).
Whichever fields were backfilled are recorded in
`data["sysfs_augmented_fields"]` and reflected in `source`
(`nvidia-smi`, `nvidia-smi+sysfs`, or plain `sysfs`). Unavailable (exit 0) only
when neither nvidia-smi nor any sysfs node yields anything.

## Usage

    thor gpu
    thor gpu --json
"""

_DISK = """\
# thor disk

Filesystem usage for real (non-virtual) block devices, read via `/proc/mounts`
and `os.statvfs` — no `df` dependency. Virtual filesystems and snap `loop`
mounts are filtered out. Warns when a filesystem is >=85% full.

## Usage

    thor disk
    thor disk --json
"""

_THERMAL = """\
# thor thermal

SoC thermal zones (`/sys/class/thermal`) and hwmon sensors
(`/sys/class/hwmon`: nvme, wifi PHY, INA3221/INA238 power monitors, …) in
Celsius. No `lm-sensors` dependency. GPU die temperature comes from
`nvidia-smi`/sysfs (see `gpu`). Warns on any sensor at or above 85 C.

## Usage

    thor thermal
    thor thermal --json
"""

_CONTAINERS = """\
# thor containers

Running Docker containers via `docker ps`, with health. Images served from
`nvcr.io` are tagged GPU-likely (heuristic). Warns on any container reporting
`(unhealthy)`. Unavailable (exit 0) when docker is absent or the daemon is
down.

## Usage

    thor containers
    thor containers --json
"""

_NETWORK = """\
# thor network

Interfaces, default route, and reachable addresses, summarized from `ip -br
addr` and `ip route show default`. Named interfaces (wifi/ethernet/tailscale/
bridges) are listed with their IPv4; the many container `veth` pairs are rolled
up to a count. "Reachable" excludes docker bridge gateways and link-local.

## Usage

    thor network
    thor network --json
"""

_PROCESSES = """\
# thor processes

Top processes by resident memory (`VmRSS`), read straight from `/proc` — no
`ps` dependency. RSS is the right lens on a unified-memory board: the share of
the one shared pool a process holds resident. Kernel threads (no `VmRSS`) are
skipped.

## Usage

    thor processes
    thor processes --json
"""

_POWER = """\
# thor power

Jetson Thor power posture from three independent, often root-gated sources:

- `nvpmodel -q` — the active power mode profile (e.g. `MAXN`). Usually
  readable without root, but degrades to absent rather than assuming access.
- `jetson_clocks --show` — whether CPU/GPU clocks are pinned to max. Requires
  root on Thor; a permission failure surfaces as absent data, never a crash.
- INA3221/INA238-family power monitor chips under `/sys/class/hwmon` —
  read-only per-rail telemetry (e.g. `VDD_GPU`, `VDD_CPU_SOC_MSS`, `VIN`) that
  needs no privilege at all.

Each source is read independently and reported on its own; the overall report
is only `unavailable` when none of the three yielded anything. Read-only;
exits 0 even when `nvpmodel`/`jetson_clocks` need root you don't have.

## Usage

    thor power
    thor power --json
"""

_MONITOR = """\
# thor monitor

A deterministic, **AI-free** watchdog. It periodically runs the
`jetson_thor.probe` collectors, compares their numbers against configured
thresholds, and POSTs to a generic webhook when a catastrophe condition
crosses — and again when it clears (edge-triggered, so a standing condition
doesn't spam). Designed to run always-on as a systemd `--user` service this
CLI installs and manages.

Watches: memory %, swap %, disk %, hottest sensor, GPU temp, load-per-core,
I/O contention (iowait + blocked procs), container health, and subsystem
availability (nvidia-smi / docker going dark).

## Verbs

- `monitor check` — evaluate now, print firing alerts (no webhook, no state).
- `monitor once` — one cycle: evaluate, deliver transitions, update state.
- `monitor run` — foreground watch loop (the systemd ExecStart).
- `monitor test` — POST a synthetic alert to verify the webhook.
- `monitor config [--init [--force]]` — show resolved config / write a scaffold.
- `monitor install | enable | disable | status | uninstall` — systemd `--user`.

## Config

JSON at `~/.config/jetson-thor/monitor.json` (`JETSON_THOR_WEBHOOK_URL`
overrides the webhook). `webhook_format` is `generic` (default), `slack`, or
`discord`. A numeric threshold of `null` disables that check. `notify_on_start`
(default `true`) sends a one-shot "started watching" alert when `run` comes
up. Zero runtime dependencies — `urllib` does the POST, never raising into
the loop.

## Usage

    thor monitor check
    thor monitor config
"""

_MONITOR_CHECK = """\
# thor monitor check

Evaluate the thresholds against a fresh snapshot and print the alerts that are
currently firing. Does **not** POST to the webhook and does **not** touch the
alert state — a safe dry run. Supports `--json` and `--config PATH`.

## Usage

    thor monitor check
    thor monitor check --json
"""

_MONITOR_ONCE = """\
# thor monitor once

Run a single monitor cycle: snapshot, evaluate, and deliver any edge-triggered
events (new alerts + recoveries) to the webhook, then persist the alert state.
Cron-friendly. Exits 0; reports whether delivery happened. `--json`, `--config`.

## Usage

    thor monitor once
"""

_MONITOR_RUN = """\
# thor monitor run

The foreground watch loop — what the systemd unit runs as its `ExecStart`.
Polls every `interval_seconds`, delivering transitions to the webhook; stops
cleanly on SIGTERM/SIGINT. Requires a valid webhook (errors with exit 2
otherwise). `--interval N` overrides the poll period; `--config PATH` selects
the config.

On start it POSTs a one-shot **"started watching"** liveness alert (so a
watchdog that silently fails to come up is noticed). A failed startup POST is
logged but never blocks the loop. Disable it with `notify_on_start: false` in
the config.

## Usage

    thor monitor run
    thor monitor run --interval 30
"""

_MONITOR_TEST = """\
# thor monitor test

POST a synthetic alert to the configured webhook to verify connectivity and
formatting. Exits 2 if no webhook is configured or the POST fails. `--config`.

## Usage

    thor monitor test
"""

_MONITOR_CONFIG = """\
# thor monitor config

Show the resolved configuration (thresholds, webhook, interval) and whether it
is valid. `--init` writes a scaffold config file you can edit; it refuses
(exit 1) when the file already exists, unless `--force` is also given. The
file is written mode 0600 (and a directory it creates 0700), since the webhook
URL is often a bearer secret. `--json`,
`--config PATH`. The webhook may also come from `JETSON_THOR_WEBHOOK_URL`.
`notify_on_start` (default `true`) toggles the startup liveness alert.

## Usage

    thor monitor config
    thor monitor config --init
"""

_MONITOR_SYSTEMD = """\
# thor monitor (systemd management)

Manage the monitor as a systemd `--user` service:

- `monitor install` — write `~/.config/systemd/user/jetson-thor-monitor.service`.
- `monitor enable` — `systemctl --user enable --now` (+ `loginctl enable-linger`
  so it survives logout/reboot; `--no-linger` to skip).
- `monitor disable` — stop and disable the service.
- `monitor status` — unit installed/active/enabled state + currently firing keys.
- `monitor uninstall` — disable and remove the unit file.

All `systemctl`/`loginctl` calls degrade gracefully when systemd is absent.

## Usage

    thor monitor install
    thor monitor enable
    thor monitor status
"""


_SWAP = """\
# thor swap

Swap inspection, per-process history, and the guarded swap grow. Read verbs are
descriptive (exit 0 even when a subsystem is absent); `grow` is the only mutator
and is **dry-run unless `--apply` is passed**.

## Verbs

- `thor swap overview` — describe the swap surface **and** show the
  live snapshot (the superset of `status`).
- `thor swap status` — the quick snapshot only: swap/memory + a short sar trend
  summary.
- `thor swap grow SIZE [--apply] [--ephemeral]` — resize the swapfile
  (`SIZE` is a placeholder, e.g. `64G`).
- `thor swap history [--window DUR] [--top N]` — top per-process swap/RSS.
- `thor swap sample` — take one snapshot for the history store.

All verbs support `--json`. Sizes are binary (1024-based): `32G` == `32GiB` ==
`32GB`; a bare number is bytes.
"""

_SWAP_STATUS = """\
# thor swap status

Read-only swap + memory snapshot, composed from `/proc` (devices, used%, unified
memory, swappiness) plus a short trend summary read from the existing
sysstat/`sar` history (recent and average swap-used %). Works without root and
exits 0 even when a subsystem is unavailable (it reports `available: false`).

`status` is the quick snapshot-only view. For the same snapshot *plus* the verb
surface in one read, use `thor swap overview` (the superset).

## Usage

    thor swap status
    thor swap status --json
"""

_SWAP_GROW = """\
# thor swap grow SIZE

The guarded mutator: resize the file-backed swapfile detected in `/proc/swaps`
(e.g. `/swap.img` or `/swapfile`) in place
(`swapoff -> fallocate -> chmod -> mkswap -> swapon`, plus an fstab ensure on the
persistent path). A host with no file-backed swap is refused (exit 1).
`SIZE` is a **placeholder** — replace it with a human-readable
size (`64G`, `32GiB`, `16g`, or a raw byte count; binary 1024-based). Don't type
the literal word `size`: `swap grow 64G`, not `swap grow size 64G`.

**Dry-run by default**: without `--apply` it previews the exact step plan on
stderr, emits the structured plan on stdout, and changes nothing (exit 0).
`--apply` executes it and **requires root** — the executor raises an error
(exit 2) with a `sudo … --apply` hint otherwise. `--ephemeral` skips the
persistent fstab entry (this boot only). Hazard warnings (e.g. the swapoff
ENOMEM risk) are always surfaced on stderr.

## Usage

    thor swap grow 32G                 # dry-run preview
    thor swap grow 32G --json
    sudo thor swap grow 32G --apply
"""

_SWAP_HISTORY = """\
# thor swap history

Top per-process swap/RSS consumers over a recent window, aggregated from the
bounded history store the `sample` verb feeds. `--window` accepts a duration
(`1h`, `30m`, `2d`, or a raw second count; default `1h`); `--top N` caps the
ranking (default 10). An empty store prints "no history recorded yet" (and `[]`
under `--json`) and exits 0.

## Usage

    thor swap history
    thor swap history --window 6h --top 20
    thor swap history --json
"""

_SWAP_SAMPLE = """\
# thor swap sample

Take one snapshot of per-process memory/swap from `/proc` and append it to the
bounded history store (which `swap history` later queries). Reports how many
process samples were written. This is the verb an operator's systemd timer /
cron invokes periodically to build up history.

## Usage

    thor swap sample
    thor swap sample --json
"""

_SWAP_OVERVIEW = """\
# thor swap overview

The comprehensive read of the swap noun: the descriptive surface (its verbs and
one-liners) **plus** the live snapshot `thor swap status` shows on its
own — unified memory, swap devices, swappiness, and the short sar trend. `status`
remains the quick snapshot-only view (same input); `overview` is the superset.

Accepts and ignores a stray `target` positional and always exits 0 (the
descriptive-verb contract): the underlying collectors degrade to
`available: false` rather than raise, so overview never hard-fails.

## Usage

    thor swap overview
    thor swap overview --json
"""

ENTRIES: dict[tuple[str, ...], str] = {
    (): _ROOT,
    ("thor",): _ROOT,
    ("whoami",): _WHOAMI,
    ("learn",): _LEARN,
    ("explain",): _EXPLAIN,
    ("overview",): _OVERVIEW,
    ("doctor",): _DOCTOR,
    ("cli",): _CLI,
    ("cli", "overview"): _CLI,
    ("status",): _STATUS,
    ("memory",): _MEMORY,
    ("gpu",): _GPU,
    ("disk",): _DISK,
    ("thermal",): _THERMAL,
    ("containers",): _CONTAINERS,
    ("network",): _NETWORK,
    ("processes",): _PROCESSES,
    ("power",): _POWER,
    ("monitor",): _MONITOR,
    ("monitor", "overview"): _MONITOR,
    ("monitor", "check"): _MONITOR_CHECK,
    ("monitor", "once"): _MONITOR_ONCE,
    ("monitor", "run"): _MONITOR_RUN,
    ("monitor", "test"): _MONITOR_TEST,
    ("monitor", "config"): _MONITOR_CONFIG,
    ("monitor", "install"): _MONITOR_SYSTEMD,
    ("monitor", "enable"): _MONITOR_SYSTEMD,
    ("monitor", "disable"): _MONITOR_SYSTEMD,
    ("monitor", "status"): _MONITOR_SYSTEMD,
    ("monitor", "uninstall"): _MONITOR_SYSTEMD,
    ("swap",): _SWAP,
    ("swap", "overview"): _SWAP_OVERVIEW,
    ("swap", "status"): _SWAP_STATUS,
    ("swap", "grow"): _SWAP_GROW,
    ("swap", "history"): _SWAP_HISTORY,
    ("swap", "sample"): _SWAP_SAMPLE,
}
