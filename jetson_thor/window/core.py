"""``window`` and ``drop-caches`` logic. Results are plain dicts shaped per
the machine-CLI contract: ``ok``, ``reason``, plus verb fields. Exit codes are
carried in the ``_exit`` key, which the CLI layer strips before printing.

State (stock clocks + saved fan profile) lives under
``${XDG_STATE_HOME:-~/.local/state}/thor/``:

* ``jetson_clocks.state`` - written by ``jetson_clocks --store``;
* ``window.json`` - ``{locked, stored_at}``.

Fan handling (validated on a real Thor, 2026-10-17): ``nvfancontrol`` has no
runtime profile switch. ``lock`` is ``jetson_clocks`` then ``jetson_clocks
--fan`` (PWM to max); ``restore`` is ``jetson_clocks --restore <file>``, whose
stored file carries the fan PWM state. ``fan_profile`` is read from
``FAN_DEFAULT_PROFILE`` in ``/etc/nvfancontrol.conf``.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

from jetson_thor.probe import power, thermal
from jetson_thor.window import sudoers
from jetson_thor.window.env import Env

_FAN_CONF_RE = re.compile(r"^\s*FAN_DEFAULT_PROFILE\s+(\S+)", re.MULTILINE)
_EMC_RE = re.compile(r"^EMC\s+.*?CurrentFreq=(?P<cur>\d+)", re.MULTILINE)
_PWM_RE = re.compile(r"hwmon\d+_pwm1=(?P<pwm>\d+)")
GPU_DEVFREQ = "gpu-gpc-0"


def state_paths(env: Env) -> tuple:
    return env.state_dir / "jetson_clocks.state", env.state_dir / "jetson_clocks.state"


def _window_file(env: Env) -> Path:
    return env.state_dir / "window.json"


def _read_state(env: Env) -> Optional[dict]:
    try:
        data = json.loads(_window_file(env).read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_state(env: Env, data: dict) -> None:
    env.state_dir.mkdir(parents=True, exist_ok=True)
    _window_file(env).write_text(json.dumps(data))


def _sudo(env: Env, argv: list) -> list:
    return list(argv) if env.euid() == 0 else ["sudo", "-n", *argv]


def _fail(reason: str, code: int, message: str, **extra) -> dict:
    return {"ok": False, "reason": reason, "message": message, "_exit": code, **extra}


def _priv(env: Env, argv: list, stdin: Optional[str] = None):
    """Run ``argv`` privileged. -> (result_tuple, None) or (None, failure_dict)."""
    res = env.exec(_sudo(env, argv), stdin)
    if res is None:
        return None, _fail("tool_missing", 2, "sudo (or the tool) not found")
    if res[0] != 0:
        if sudoers.is_denied(res[2]):
            return None, _fail("not_granted", 2, "passwordless sudo rule missing")
        return None, _fail("failed", 2, (res[2] or res[1]).strip() or f"exit {res[0]}")
    return res, None


def _read_int(path: Path) -> Optional[int]:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _mhz(hz: Optional[int]) -> Optional[int]:
    return None if hz is None else hz // 10**6


def _gpu_freqs(env: Env) -> dict:
    """GPU cur/min/max in Hz from world-readable devfreq sysfs (no root)."""
    base = Path(env.devfreq_root) / GPU_DEVFREQ
    return {k: _read_int(base / f"{k}_freq") for k in ("cur", "min", "max")}


def _clocks_locked(gpu: dict) -> Optional[bool]:
    lo, hi = gpu["min"], gpu["max"]
    return None if lo is None or hi is None else lo == hi


def _privileged_show(env: Env) -> Optional[str]:
    """``jetson_clocks --show`` as root or via non-interactive sudo, else None."""
    clocks = env.which("jetson_clocks")
    if not clocks:
        return None
    res = env.exec(_sudo(env, [clocks, "--show"]), None)
    return res[1] if res is not None and res[0] == 0 else None


def _emc_mhz(raw: Optional[str]) -> Optional[int]:
    m = _EMC_RE.search(raw or "")
    return int(m["cur"]) // 10**6 if m else None


def _fan_max(raw: Optional[str]) -> Optional[bool]:
    m = _PWM_RE.search(raw or "")
    return int(m["pwm"]) >= 255 if m else None


def _fan_profile(env: Env) -> Optional[str]:
    try:
        text = Path(env.fan_conf).read_text()
    except OSError:
        return None
    m = _FAN_CONF_RE.search(text)
    return m.group(1) if m else None


def _fan_max_on(env: Env) -> Optional[str]:
    """``jetson_clocks --fan``; return an error string, or None on success."""
    clocks = env.which("jetson_clocks")
    if not clocks:
        return "jetson_clocks not found"
    _, fail = _priv(env, [clocks, "--fan"])
    return fail["message"] if fail else None


def _unprivileged(env: Env):
    def run(name, args):
        res = env.exec([name, *args], None)
        return res[1] if res and res[0] == 0 else None

    return run


def show(env: Env, runner=None) -> dict:
    """Current state; read-only, never needs root."""
    pw = power.collect(runner or _unprivileged(env))
    data = pw.get("data") or {}
    temps = {}
    th = thermal.collect(env.thermal_root, env.hwmon_root)
    for s in (th.get("data") or {}).get("sensors", []):
        if s.get("kind") == "zone":
            temps[s["name"]] = s["temp_c"]
    st = _read_state(env)
    gpu = _gpu_freqs(env)
    raw = _privileged_show(env)
    return {
        "ok": True,
        "reason": None,
        "active": bool(st and st.get("locked")),
        "stored": st is not None,
        "supported": env.which("jetson_clocks") is not None,
        "power_mode": (data.get("nvpmodel") or {}).get("mode"),
        "clocks": {
            "gpu_mhz": _mhz(gpu["cur"]),
            "gpu_min_mhz": _mhz(gpu["min"]),
            "gpu_max_mhz": _mhz(gpu["max"]),
            "emc_mhz": _emc_mhz(raw),
        },
        "clocks_locked": _clocks_locked(gpu),
        "fan_profile": _fan_profile(env),
        "temps_c": temps,
        "detail": {"fan_max": _fan_max(raw)},
    }


def _after(env: Env, action: str, **extra) -> dict:
    out = show(env)
    out.update(action=action, **extra)
    return out


def _need_tool(env: Env) -> Optional[dict]:
    if env.which("jetson_clocks") is None:
        return _fail("tool_missing", 2, "jetson_clocks not found")
    return None


def store(env: Env) -> dict:
    st = _read_state(env)
    if st and st.get("locked"):
        return _fail("window_active", 1, "a window is active; restore it first", action="store")
    missing = _need_tool(env)
    if missing:
        return {**missing, "action": "store"}
    clocks = env.which("jetson_clocks")
    path, _ = state_paths(env)
    env.state_dir.mkdir(parents=True, exist_ok=True)
    _, fail = _priv(env, [clocks, "--store", str(path)])
    if fail:
        return {**fail, "action": "store"}
    _write_state(
        env,
        {"locked": False, "stored_at": int(time.time())},
    )
    return _after(env, "store")


def lock(env: Env) -> dict:
    st = _read_state(env)
    if st is None:
        return _fail("no_stored_state", 1, "run 'thor window store' first", action="lock")
    missing = _need_tool(env)
    if missing:
        return {**missing, "action": "lock"}
    if st.get("locked"):
        return _after(env, "lock")
    _, fail = _priv(env, [env.which("jetson_clocks")])
    if fail:
        return {**fail, "action": "lock"}
    st["locked"] = True
    _write_state(env, st)
    fan_err = _fan_max_on(env)
    out = _after(env, "lock")
    if fan_err:
        out["detail"]["fan_error"] = fan_err
    return out


def restore(env: Env) -> dict:
    st = _read_state(env)
    if st is None:
        return _after(env, "restore", restored=False)
    missing = _need_tool(env)
    if missing:
        return {**missing, "action": "restore"}
    path, _ = state_paths(env)
    _, fail = _priv(env, [env.which("jetson_clocks"), "--restore", str(path)])
    if fail:
        return {**fail, "action": "restore"}
    for f in (_window_file(env), path):
        try:
            f.unlink()
        except OSError:
            pass
    return _after(env, "restore", restored=True)


def drop_caches(env: Env) -> dict:
    """``sync`` then clear the page cache via the granted rule."""
    rule = sudoers.drop_caches_rule(sudoers.sudo_listing(env))
    if rule is None:
        return _fail("not_granted", 2, "no passwordless drop-caches rule", cleared=False, rule=None)
    env.exec(["sync"], None)
    if rule == "tee":
        res = env.exec(sudoers.DROP_TEE_ARGV, "3")
    else:
        res = env.exec(sudoers.DROP_SYSCTL_ARGV, None)
    if res is None:
        return _fail("tool_missing", 2, "sudo not found", cleared=False, rule=rule)
    if res[0] != 0:
        return _fail("failed", 2, (res[2] or res[1]).strip(), cleared=False, rule=rule)
    return {"ok": True, "reason": None, "cleared": True, "rule": rule}


def check_grants(env: Env) -> dict:
    listing = sudoers.sudo_listing(env)
    drop = sudoers.drop_caches_rule(listing)
    win = sudoers.window_rule(env, listing, state_paths(env))
    ok = drop is not None
    return {
        "ok": ok,
        "reason": None if ok else "not_granted",
        "drop_caches": {"granted": ok, "rule": drop, "source": "sudo -n -l"},
        "window": {"granted": win is not None, "rule": win},
        "_exit": 0 if ok else 2,
    }


def grant(env: Env, assume_yes: bool, diag) -> dict:
    """Install missing rules (consent unless ``assume_yes``). Reuses equivalents."""
    state = check_grants(env)
    need_drop = not state["drop_caches"]["granted"]
    need_win = not state["window"]["granted"]
    out = {k: v for k, v in state.items() if not k.startswith("_")}
    out["installed"] = False
    if not (need_drop or need_win):
        return {**out, "ok": True, "reason": None}
    commands = []
    if need_drop:
        commands.append(f"{sudoers.SYSCTL} -w vm.drop_caches=3")
    if need_win:
        commands.extend(sudoers.window_commands(env, state_paths(env)))
    user = env.user()
    rules = sudoers.render_rules(user, commands)
    diag(f"thor grant-permissions will install {env.sudoers_dropin}:\n{rules}")
    if not assume_yes:
        try:
            ans = env.ask("Install these rules (not full sudo)? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans not in ("y", "yes"):
            return {**out, **_fail("declined", 1, "declined; nothing installed")}
    ok, reason, msg = sudoers.install(env, rules)
    if not ok:
        return {**out, **_fail(reason, 2, msg)}
    after = check_grants(env)
    return {
        **{k: v for k, v in after.items() if not k.startswith("_")},
        "ok": True,
        "reason": None,
        "installed": True,
        "rules": commands,
    }
