"""Markdown catalog for ``thor explain <path>``.

Each entry is verbatim markdown. Keys are command-path tuples. The empty tuple
and ``("thor",)`` both resolve to the root entry.

Keep bodies self-contained: an agent reading one entry should get enough
context without chaining reads.
"""

from __future__ import annotations

_ROOT = """\
# thor

A clonable template for AgentCulture mesh agents. It carries an agent-first CLI
(cited from the teken `python-cli` reference), a mesh identity (`culture.yaml` +
`CLAUDE.md`), the canonical guildmaster skill kit under `.claude/skills/`, and a
buildable/deployable package baseline. Clone it, rename the package, edit
`culture.yaml`, and you have a new agent.

## Verbs

- `thor whoami` — identity probe from `culture.yaml`.
- `thor learn` — structured self-teaching prompt.
- `thor explain <path>` — markdown docs for any noun/verb.
- `thor overview` — descriptive snapshot of the agent.
- `thor doctor` — check the agent-identity invariants.
- `thor cli overview` — describe the CLI surface.
- `thor monitor` — deterministic, AI-free threshold watchdog that webhooks on
  catastrophes.

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
verb surface, and the sibling-pattern artifacts the template carries. Accepts an
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
- `monitor config [--init]` — show resolved config / write a scaffold.
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
is valid. `--init` writes a scaffold config file you can edit. `--json`,
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

The guarded mutator: resize the file-backed swapfile in place
(`swapoff -> fallocate -> chmod -> mkswap -> swapon`, plus an fstab ensure on the
persistent path). `SIZE` is a **placeholder** — replace it with a human-readable
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
