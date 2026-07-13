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
}
