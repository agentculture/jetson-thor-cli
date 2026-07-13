"""systemd ``--user`` supervision for the monitor.

Generates and manages a user-level unit so the watchdog runs always-on with
auto-restart and journald logs — the way persistent services run on Jetson
Thor. The unit text is pure (testable); every ``systemctl``/``loginctl`` call
goes through :mod:`jetson_thor.probe._run` (``shutil.which`` — graceful when
absent, and no bandit B607 partial-path).
"""

from __future__ import annotations

import getpass
import shutil
import sys
from pathlib import Path
from typing import Optional

from jetson_thor.monitor.config import config_home, default_config_path
from jetson_thor.probe._run import run_capture, run_tool

UNIT_NAME = "jetson-thor-monitor.service"


def unit_dir() -> Path:
    return config_home() / "systemd" / "user"


def unit_path() -> Path:
    return unit_dir() / UNIT_NAME


def _unit_arg(value: str) -> str:
    """Quote/escape one ExecStart argument for the systemd unit grammar.

    systemd splits ExecStart into argv on whitespace and treats ``%`` as a
    specifier, so a path with spaces or ``%`` would corrupt the command. Double
    quotes preserve spaces; ``%`` is escaped to ``%%`` and ``"``/``\\`` are
    backslash-escaped.
    """
    escaped = value.replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _thor_executable() -> str:
    """Resolve the ``thor`` console script for the ExecStart line.

    Prefers PATH resolution (:func:`shutil.which`) since that's how a systemd
    ``--user`` unit normally finds it. Falls back to the script installed
    alongside the running interpreter (venvs/``uv`` installs put
    ``console_scripts`` next to ``python`` in the same ``bin/`` dir), and
    finally to the bare name so a unit is always written — systemd will report
    "not found" clearly if PATH lacks it at run time.
    """
    found = shutil.which("thor")
    if found:
        return found
    candidate = Path(sys.executable).with_name("thor")
    if candidate.is_file():
        return str(candidate)
    return "thor"


def exec_start(config_path: Optional[str] = None) -> str:
    """ExecStart line: the ``thor`` console script's ``monitor run``."""
    cfg = config_path or str(default_config_path())
    return f"{_unit_arg(_thor_executable())} monitor run --config {_unit_arg(cfg)}"


def unit_text(config_path: Optional[str] = None) -> str:
    return (
        "[Unit]\n"
        "Description=Jetson Thor monitor (jetson-thor-cli watchdog)\n"
        "After=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={exec_start(config_path)}\n"
        "Restart=on-failure\n"
        "RestartSec=10\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def install(config_path: Optional[str] = None) -> Path:
    """Write the unit file and reload the user manager. Returns the unit path."""
    path = unit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(unit_text(config_path), encoding="utf-8")
    run_tool("systemctl", ["--user", "daemon-reload"])
    return path


def enable(*, linger: bool = True) -> tuple[bool, Optional[str]]:
    out = run_tool("systemctl", ["--user", "enable", "--now", UNIT_NAME])
    if out is None:
        return False, "systemctl --user enable failed (is the user manager running?)"
    if linger:
        # Lets the user service keep running after logout / across reboots.
        # `run_capture` distinguishes "worked" from "absent/failed"; a linger
        # failure must not report silent success — the service would silently
        # stop at logout. Surfaced as a warning: the unit itself IS enabled.
        linger_out = run_capture("loginctl", ["enable-linger", getpass.getuser()])
        if linger_out is None or linger_out[0] != 0:
            return True, (
                "warning: could not enable login-linger (loginctl absent or failed) — "
                "the service stops at logout; run 'loginctl enable-linger' manually"
            )
    return True, None


def disable() -> tuple[bool, Optional[str]]:
    out = run_tool("systemctl", ["--user", "disable", "--now", UNIT_NAME])
    if out is None:
        return False, "systemctl --user disable failed"
    return True, None


def _query(args: list[str]) -> str:
    result = run_capture("systemctl", args)
    if result is None:
        return "unknown"
    return (result[1] or "").strip() or "unknown"


def status() -> dict:
    """Report unit presence + active/enabled state (via is-active/is-enabled)."""
    return {
        "unit": UNIT_NAME,
        "unit_path": str(unit_path()),
        "installed": unit_path().is_file(),
        "active": _query(["--user", "is-active", UNIT_NAME]),
        "enabled": _query(["--user", "is-enabled", UNIT_NAME]),
    }


def uninstall() -> Path:
    disable()
    path = unit_path()
    if path.is_file():
        path.unlink()
    run_tool("systemctl", ["--user", "daemon-reload"])
    return path
