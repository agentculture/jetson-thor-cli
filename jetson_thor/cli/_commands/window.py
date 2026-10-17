"""``thor window`` / ``thor drop-caches`` / ``thor grant-permissions``.

Machine-CLI contract (lobes ``docs/contracts/machine-cli-window.md``): with
``--json`` stdout is exactly one object carrying ``ok`` and ``reason``; exit
0 done, 1 refused by state, 2 environment. Without ``--json`` a refusal is the
usual ``error:`` / ``hint:`` on stderr. Mutators never prompt (``sudo -n``);
only ``grant-permissions`` asks, once, before installing.
"""

from __future__ import annotations

import argparse

from jetson_thor.cli._errors import CliError
from jetson_thor.cli._output import emit_diagnostic, emit_result, render_sections
from jetson_thor.window import core
from jetson_thor.window.env import Env

_HINTS = {
    "not_granted": "run 'thor grant-permissions' once (one sudo prompt)",
    "no_stored_state": "run 'thor window store' first",
    "window_active": "run 'thor window restore' first",
    "tool_missing": "run on a Jetson with jetson_clocks installed",
    "declined": "re-run with --yes to install without the prompt",
    "failed": "see the message above; nothing was left half-applied in the CLI state",
    "unsupported": "this card cannot do it",
}


def _env() -> Env:
    return Env()


def _strip(result: dict) -> tuple[dict, int]:
    code = result.get("_exit", 0)
    return {k: v for k, v in result.items() if not k.startswith("_")}, code


def _text(result: dict) -> str:
    items = [f"{k}: {v}" for k, v in result.items() if k not in ("detail", "message")]
    return render_sections("thor", [{"title": "Result", "items": items}])


def _finish(args: argparse.Namespace, result: dict) -> int:
    payload, code = _strip(result)
    if getattr(args, "json", False):
        emit_result(payload, json_mode=True)
        return code
    if not payload.get("ok"):
        reason = payload.get("reason") or "failed"
        raise CliError(
            code or 1,
            f"{reason}: {payload.get('message', '')}".rstrip(": "),
            _HINTS.get(reason, ""),
        )
    emit_result(_text(payload), json_mode=False)
    return code


def cmd_show(args: argparse.Namespace) -> int:
    return _finish(args, core.show(_env()))


def cmd_store(args: argparse.Namespace) -> int:
    return _finish(args, core.store(_env()))


def cmd_lock(args: argparse.Namespace) -> int:
    return _finish(args, core.lock(_env()))


def cmd_restore(args: argparse.Namespace) -> int:
    return _finish(args, core.restore(_env()))


def cmd_drop_caches(args: argparse.Namespace) -> int:
    return _finish(args, core.drop_caches(_env()))


def cmd_grant(args: argparse.Namespace) -> int:
    env = _env()
    if args.check:
        return _finish(args, core.check_grants(env))
    return _finish(args, core.grant(env, bool(args.yes), emit_diagnostic))


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Emit one JSON object.")


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("window", help="Benchmark window: lock clocks + fan, restore after.")
    _add_json(p)
    p.set_defaults(func=cmd_show, json=False)
    noun = p.add_subparsers(dest="window_command", parser_class=type(p))
    for name, func, text in (
        ("show", cmd_show, "Report clock/fan/power state and whether a window is active."),
        ("store", cmd_store, "Save the current clock + fan state (jetson_clocks --store)."),
        ("lock", cmd_lock, "Lock clocks and fan to max (needs a stored state)."),
        ("restore", cmd_restore, "Return to the stored state, then delete it."),
    ):
        v = noun.add_parser(name, help=text)
        _add_json(v)
        v.set_defaults(func=func)

    dc = sub.add_parser("drop-caches", help="sync + clear the page cache (needs the grant).")
    _add_json(dc)
    dc.set_defaults(func=cmd_drop_caches)

    gp = sub.add_parser(
        "grant-permissions", help="Install the passwordless sudo rules (never full sudo)."
    )
    _add_json(gp)
    gp.add_argument("--check", action="store_true", help="Only report; install nothing.")
    gp.add_argument("--yes", action="store_true", help="Skip the install confirmation.")
    gp.set_defaults(func=cmd_grant)
