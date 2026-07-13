"""``thor learn`` — the learnability affordance.

Prints a structured self-teaching prompt. Must satisfy the agent-first rubric:
>=200 chars and mention purpose, command map, exit codes, --json, and explain.
"""

from __future__ import annotations

import argparse

from jetson_thor import __version__
from jetson_thor.cli._output import emit_result

_TEXT = """\
thor — agent + CLI for operating NVIDIA Jetson Thor.

Purpose
-------
Agent-first CLI (cited from the teken `python-cli` reference), an identity
(culture.yaml + AGENTS.colleague.md), the canonical guildmaster skill kit
under .claude/skills/, a deploy/CI baseline, and a Jetson Thor operations
surface: host telemetry, swap management, and an AI-free webhook watchdog.

Command map
-----------
Commands by path:

  thor whoami             Identity from culture.yaml.
  thor learn              This self-teaching prompt.
  thor explain <path>...  Markdown docs for any noun/verb path.
  thor overview           Descriptive snapshot of the agent.
  thor doctor             Check the agent-identity invariants.
  thor cli overview       Describe the CLI surface itself.

Machine scope (Jetson Thor host telemetry)
--------------------------------------------
  thor status             Machine-wide scope, anomalies first (the headline;
                           includes the L4T version).
  thor memory             Unified RAM + swap (CPU and iGPU share it).
  thor gpu                Blackwell iGPU: util, temp, power, processes
                           (nvidia-smi backfilled from sysfs — see below).
  thor disk               Filesystem usage for real block devices.
  thor thermal            SoC thermal zones and hwmon sensors.
  thor containers         Running Docker containers and health.
  thor network            Interfaces, routes, reachable addresses.
  thor processes          Top processes by resident memory.
  thor power              nvpmodel mode, jetson_clocks state, per-rail power
                           draw (Jetson-only; no discrete-GPU equivalent).
These are read-only and exit 0 even when a subsystem is absent. On real Thor
hardware nvidia-smi is thin (temp/power/clock come back [N/A] via NVML), so
`gpu`/`power` backfill those fields from stable sysfs nodes (devfreq, thermal
zones, hwmon INA rails) instead of a streaming tegrastats.

Swap management
----------------
  thor swap overview       Describe the swap surface plus the live snapshot.
  thor swap status         Swap/memory snapshot + short sar trend.
  thor swap grow SIZE      Resize the swapfile (dry-run unless --apply).
  thor swap history        Top per-process swap/RSS consumers.
  thor swap sample         Take one snapshot for the history store.
grow is dry-run by default; --apply requires root. Sizes are 32G/32GiB/bytes.

Monitoring (AI-free background watchdog)
------------------------------------------
  thor monitor check      Evaluate thresholds now (no webhook).
  thor monitor once       One cycle: evaluate + webhook + state.
  thor monitor run        Foreground watch loop (systemd ExecStart).
  thor monitor test       POST a synthetic alert to the webhook.
  thor monitor config     Show/scaffold thresholds + webhook.
  thor monitor install    Manage a systemd --user service.
Webhooks on catastrophes (memory/disk/thermal/GPU/containers); no AI.
Config: ~/.config/jetson-thor/monitor.json (env override:
JETSON_THOR_WEBHOOK_URL). On 'run' it also POSTs a one-shot "started
watching" alert (notify_on_start).

Machine-readable output
-----------------------
Every command supports --json. Errors in JSON mode emit
{"code", "message", "remediation"} to stderr. Stdout and stderr never mix.

Exit-code policy
----------------
  0 success
  1 user-input error (bad flag, bad path, missing arg)
  2 environment / setup error
  3+ reserved

More detail
-----------
  thor explain thor
"""


def _as_json_payload() -> dict[str, object]:
    return {
        "tool": "thor",
        "version": __version__,
        "purpose": "Agent + CLI for operating NVIDIA Jetson Thor.",
        "commands": [
            {"path": ["whoami"], "summary": "Identity probe from culture.yaml."},
            {"path": ["learn"], "summary": "Self-teaching prompt."},
            {"path": ["explain"], "summary": "Markdown docs by path."},
            {"path": ["overview"], "summary": "Descriptive snapshot of the agent."},
            {"path": ["doctor"], "summary": "Check the agent-identity invariants."},
            {"path": ["cli", "overview"], "summary": "Describe the CLI surface."},
            {"path": ["status"], "summary": "Machine-wide scope, anomalies first (incl. L4T)."},
            {"path": ["memory"], "summary": "Unified RAM + swap snapshot."},
            {"path": ["gpu"], "summary": "Jetson Thor iGPU snapshot (nvidia-smi+sysfs)."},
            {"path": ["disk"], "summary": "Filesystem usage."},
            {"path": ["thermal"], "summary": "Thermal zones and hwmon sensors."},
            {"path": ["containers"], "summary": "Running Docker containers and health."},
            {"path": ["network"], "summary": "Interfaces, routes, reachable addresses."},
            {"path": ["processes"], "summary": "Top processes by resident memory."},
            {
                "path": ["power"],
                "summary": "nvpmodel mode, jetson_clocks state, per-rail power (Jetson-only).",
            },
            {"path": ["swap", "overview"], "summary": "Swap surface description + live snapshot."},
            {"path": ["swap", "status"], "summary": "Swap/memory snapshot + sar trend."},
            {"path": ["swap", "grow"], "summary": "Resize the swapfile (dry-run default)."},
            {"path": ["swap", "history"], "summary": "Top per-process swap/RSS consumers."},
            {"path": ["swap", "sample"], "summary": "Snapshot for the history store."},
            {"path": ["monitor", "check"], "summary": "Evaluate alert thresholds now."},
            {"path": ["monitor", "once"], "summary": "One monitor cycle + webhook delivery."},
            {"path": ["monitor", "run"], "summary": "Foreground watchdog loop."},
            {"path": ["monitor", "test"], "summary": "POST a synthetic alert to the webhook."},
            {"path": ["monitor", "config"], "summary": "Show/scaffold monitor config."},
            {"path": ["monitor", "install"], "summary": "Manage the systemd --user service."},
        ],
        "exit_codes": {
            "0": "success",
            "1": "user-input error",
            "2": "environment/setup error",
        },
        "json_support": True,
        "explain_pointer": "thor explain <path>",
    }


def cmd_learn(args: argparse.Namespace) -> int:
    if getattr(args, "json", False):
        emit_result(_as_json_payload(), json_mode=True)
    else:
        emit_result(_TEXT, json_mode=False)
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "learn",
        help="Print a structured self-teaching prompt for agent consumers.",
    )
    p.add_argument("--json", action="store_true", help="Emit structured JSON.")
    p.set_defaults(func=cmd_learn)
