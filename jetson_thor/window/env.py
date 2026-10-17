"""Injectable host seam for the window verbs (exec, state dir, identity)."""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess  # nosec B404 - argv lists only, never a shell
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

# (argv, stdin) -> (returncode, stdout, stderr); None when argv[0] is absent.
Exec = Callable[[Sequence[str], Optional[str]], Optional[tuple]]


def default_exec(argv: Sequence[str], stdin: Optional[str] = None) -> Optional[tuple]:
    exe = shutil.which(argv[0])
    if exe is None:
        return None
    try:
        proc = subprocess.run(  # nosec B603 - argv list, resolved executable
            [exe, *argv[1:]],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as err:
        return 127, "", str(err)
    return proc.returncode, proc.stdout, proc.stderr


def default_state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "thor"


@dataclass
class Env:
    """Everything the verbs touch outside pure logic."""

    exec: Exec = default_exec
    which: Callable[[str], Optional[str]] = shutil.which
    state_dir: Path = field(default_factory=default_state_dir)
    euid: Callable[[], int] = os.geteuid
    user: Callable[[], str] = lambda: os.environ.get("SUDO_USER") or getpass.getuser()
    ask: Callable[[str], str] = input
    sudoers_dropin: str = "/etc/sudoers.d/thor-lobes"
    mkstemp_dir: Optional[str] = None
    thermal_root: str = "/sys/class/thermal"
    hwmon_root: str = "/sys/class/hwmon"
