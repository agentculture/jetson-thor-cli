"""Passwordless-sudo grant: detection (``sudo -n -l``) and install.

Cited from mjolnir ``cachectl.py`` (cite, don't import), extended with the
``tee`` form, the ``NOPASSWD: ALL`` pass-through and the window rules.
Detection is read-only and never prompts. An existing equivalent rule (for
example the Thor's ``/usr/sbin/sysctl -w vm.drop_caches\\=3``) is reused and
nothing is installed for it. Full sudo is never installed.
"""

from __future__ import annotations

import os
import re
import tempfile
from typing import Optional

from jetson_thor.window.env import Env

SYSCTL = "/usr/sbin/sysctl"
DROP_SYSCTL_ARGV = ["sudo", "-n", SYSCTL, "-w", "vm.drop_caches=3"]
DROP_TEE_ARGV = ["sudo", "-n", "tee", "/proc/sys/vm/drop_caches"]

_SYSCTL_RE = re.compile(r"sysctl.*vm\.drop_caches")
_TEE_RE = re.compile(r"tee /proc/sys/vm/drop_caches")
_ALL_RE = re.compile(r"NOPASSWD:\s*ALL\b")

_DENIED = ("password is required", "a terminal is required", "not allowed", "may not run")


def is_denied(stderr: str) -> bool:
    low = (stderr or "").lower()
    return any(tok in low for tok in _DENIED)


def sudo_listing(env: Env) -> Optional[str]:
    """``sudo -n -l`` stdout, or None when sudo is absent / would prompt."""
    res = env.exec(["sudo", "-n", "-l"], None)
    if res is None or res[0] != 0:
        return None
    return res[1]


def _rule_for(listing: Optional[str], sysctl_re, tee_re=None) -> Optional[str]:
    if not listing:
        return None
    if sysctl_re.search(listing):
        return "sysctl"
    if tee_re is not None and tee_re.search(listing):
        return "tee"
    return "all" if _ALL_RE.search(listing) else None


def drop_caches_rule(listing: Optional[str]) -> Optional[str]:
    """``sysctl`` | ``tee`` | ``all`` | None for the drop-caches grant."""
    return _rule_for(listing, _SYSCTL_RE, _TEE_RE)


def window_commands(env: Env, state_paths: tuple) -> list[str]:
    """The exact sudoers command specs the window verbs need (printed before install)."""
    clocks = env.which("jetson_clocks") or "/usr/bin/jetson_clocks"
    fan = env.which("nvfancontrol") or "/usr/sbin/nvfancontrol"
    store, restore = state_paths
    return [
        clocks,
        f"{clocks} --store {store}",
        f"{clocks} --restore {restore}",
        f"{fan} -q",
        f"{fan} -p *",
    ]


def listed_commands(listing: str) -> set:
    """Commands named on ``NOPASSWD:`` lines of a ``sudo -l`` listing (unescaped)."""
    out = set()
    for line in listing.splitlines():
        if "NOPASSWD:" not in line:
            continue
        for part in line.split("NOPASSWD:", 1)[1].split(", "):
            out.add(re.sub(r"\\(.)", r"\1", part.strip()))
    return out


def window_rule(env: Env, listing: Optional[str], state_paths: tuple) -> Optional[str]:
    """``sudoers`` | ``all`` | None; granted only when every command is listed."""
    if not listing:
        return None
    if _ALL_RE.search(listing):
        return "all"
    have = listed_commands(listing)
    return "sudoers" if all(c in have for c in window_commands(env, state_paths)) else None


def render_rules(user: str, commands: list[str]) -> str:
    return "".join(f"{user} ALL=(ALL) NOPASSWD: {c}\n" for c in commands)


def install(env: Env, rules: str) -> tuple:
    """Validate with ``visudo -cf`` then one ``sudo install``. -> (ok, reason, msg)."""
    fd, tmp = tempfile.mkstemp(prefix="thor-sudoers-", dir=env.mkstemp_dir)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(rules)
        chk = env.exec(["visudo", "-cf", tmp], None)
        if chk is None:
            return False, "tool_missing", "visudo not found"
        if chk[0] != 0:
            return False, "failed", f"visudo rejected the rule: {chk[1]}{chk[2]}".strip()
        argv = [
            "sudo",
            "install",
            "-m",
            "0440",
            "-o",
            "root",
            "-g",
            "root",
            tmp,
            env.sudoers_dropin,
        ]
        res = env.exec(argv, None)
        if res is None:
            return False, "tool_missing", "sudo not found"
        if res[0] != 0:
            return False, "failed", f"sudo install failed: {res[2]}".strip()
        return True, None, f"installed {env.sudoers_dropin}"
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
