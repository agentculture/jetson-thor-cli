"""Tests for ``thor window`` / ``drop-caches`` / ``grant-permissions``.

Everything runs against a fake host: no sudo, jetson_clocks, nvpmodel,
visudo or drop_caches is ever executed. The fake records each
argv so tests assert exactly what *would* have run.
"""

from __future__ import annotations

import json

import pytest

from jetson_thor.cli import main
from jetson_thor.cli._commands import window as window_cmd
from jetson_thor.window.env import Env

# Verbatim shape of the real Thor's `sudo -n -l` (read 2026-10-17).
REAL_THOR_LISTING = """\
Matching Defaults entries for thor on thor:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\\:/usr/local/bin

User thor may run the following commands on thor:
    (ALL : ALL) ALL
    (ALL) NOPASSWD: /usr/sbin/sysctl -w vm.drop_caches\\=3
    (ALL) NOPASSWD: ALL
"""
SYSCTL_ONLY = REAL_THOR_LISTING.replace("    (ALL) NOPASSWD: ALL\n", "")
TEE_ONLY = SYSCTL_ONLY.replace(
    "/usr/sbin/sysctl -w vm.drop_caches\\=3", "/usr/bin/tee /proc/sys/vm/drop_caches"
)
NO_GRANT = "User thor may run the following commands on thor:\n    (ALL : ALL) ALL\n"

# Verbatim from a real `sudo jetson_clocks --show` on a Thor (2026-10-17).
CLOCKS_SHOW = """\
gpu-gpc-0 MinFreq=314000000 MaxFreq=1575000000 CurrentFreq=1575000000
gpu-nvd-0 MinFreq=314000000 MaxFreq=1692000000 CurrentFreq=1692000000
EMC MinFreq=665600000 MaxFreq=4266000000 CurrentFreq=665600000 FreqOverride=0
FAN Dynamic Speed Control=nvfancontrol hwmon1_pwm1=69
NV Power Mode: MAXN
"""
# Verbatim /etc/nvfancontrol.conf line (tab-indented).
FAN_CONF = "FAN_CONTROL_TYPE ...\n\tFAN_DEFAULT_PROFILE cool\n"
# gpu-gpc-0 devfreq on a real Thor: cur, min, max (Hz).
DEVFREQ_STOCK = ("1575000000", "314000000", "1575000000")


class FakeHost:
    def __init__(self, tmp_path, listing=REAL_THOR_LISTING, tools=("jetson_clocks",)):
        self.calls: list[tuple] = []
        self.listing = listing
        self.tools = set(tools)
        self.show_ok = True
        self.fail: dict[str, tuple] = {}  # substring of argv -> result
        self.sudoers_written: list[str] = []
        self.answers: list[str] = ["y"]
        (tmp_path / "state").mkdir()
        self.devfreq = tmp_path / "devfreq"
        self.set_devfreq(*DEVFREQ_STOCK)
        self.fan_conf = tmp_path / "nvfancontrol.conf"
        self.fan_conf.write_text(FAN_CONF)
        self.env = Env(
            exec=self.exec,
            which=lambda n: f"/usr/bin/{n}" if n in self.tools else None,
            state_dir=tmp_path / "state",
            euid=lambda: 1000,
            user=lambda: "thor",
            ask=self._ask,
            sudoers_dropin="/etc/sudoers.d/thor-lobes",
            mkstemp_dir=str(tmp_path),
            thermal_root=str(tmp_path / "nothermal"),
            hwmon_root=str(tmp_path / "nohwmon"),
            devfreq_root=str(self.devfreq),
            fan_conf=str(self.fan_conf),
        )

    def set_devfreq(self, cur, lo, hi):
        d = self.devfreq / "gpu-gpc-0"
        d.mkdir(parents=True, exist_ok=True)
        for name, val in (("cur", cur), ("min", lo), ("max", hi)):
            (d / f"{name}_freq").write_text(val + "\n")

    def _ask(self, prompt):
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)

    def exec(self, argv, stdin=None):
        argv = list(argv)
        self.calls.append((argv, stdin))
        joined = " ".join(argv)
        for key, res in self.fail.items():
            if key in joined:
                return res
        if argv[:3] == ["sudo", "-n", "-l"]:
            return (0, self.listing, "") if self.listing is not None else (1, "", "password")
        if argv[0] == "visudo":
            self.sudoers_written.append(open(argv[2]).read())
            return 0, "parsed OK", ""
        if argv[:2] == ["sudo", "install"]:
            return 0, "", ""
        if argv[0] == "nvpmodel":
            return 0, "NV Power Mode: MAXN\n0\n", ""
        if argv[0] == "jetson_clocks" and argv[1:] == ["--show"]:
            return 1, "", "run as root"  # unprivileged show fails on a real Thor
        if argv[:1] == ["/usr/bin/jetson_clocks"] and argv[1:] == ["--show"]:  # as root
            return 0, CLOCKS_SHOW, ""
        if argv[:2] == ["sudo", "-n"] and "jetson_clocks" in joined:
            if "--show" in argv:
                return (0, CLOCKS_SHOW, "") if self.show_ok else (1, "", "a password is required")
            if "--store" in argv:
                open(argv[-1], "w").write("stock-clocks")
            elif "--restore" in argv:
                self.set_devfreq(*DEVFREQ_STOCK)
            elif argv[-1].endswith("jetson_clocks"):  # bare lock: min pinned to max
                self.set_devfreq("1575000000", "1575000000", "1575000000")
            return 0, "", ""
        return 0, "", ""

    def ran(self, *needle):
        """Calls whose argv (as elements, not substrings of paths) contains each needle."""
        return [c for c, _ in self.calls if all(any(n in a for a in c) for n in needle)]

    def ran_prefix(self, *prefix):
        return [c for c, _ in self.calls if c[: len(prefix)] == list(prefix)]


@pytest.fixture
def host(tmp_path, monkeypatch):
    h = FakeHost(tmp_path)
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    return h


def run(capsys, *argv):
    rc = main(list(argv))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def js(capsys, *argv):
    rc, out, _ = run(capsys, *argv, "--json")
    return rc, json.loads(out)


# ---- window -----------------------------------------------------------------


def test_show_idle(host, capsys):
    rc, obj = js(capsys, "window", "show")
    assert rc == 0 and obj["ok"] is True and obj["reason"] is None
    assert obj["active"] is False and obj["stored"] is False and obj["supported"] is True
    assert obj["power_mode"] == "MAXN"
    assert obj["fan_profile"] == "cool"  # FAN_DEFAULT_PROFILE from the conf
    assert obj["clocks"] == {
        "gpu_mhz": 1575,
        "gpu_min_mhz": 314,
        "gpu_max_mhz": 1575,
        "emc_mhz": 665,
    }
    assert obj["clocks_locked"] is False  # min 314 != max 1575
    assert obj["detail"]["fan_max"] is False  # pwm 69
    assert not host.ran("--store") and not host.ran("--restore")


def test_show_clocks_come_from_sysfs_without_root(host, capsys):
    host.show_ok = False  # sudo -n would prompt: only emc is lost
    _, obj = js(capsys, "window", "show")
    assert obj["clocks"]["gpu_mhz"] == 1575 and obj["clocks"]["gpu_min_mhz"] == 314
    assert obj["clocks"]["emc_mhz"] is None
    assert obj["detail"]["fan_max"] is None


def test_show_emc_as_root_runs_show_without_sudo(host, capsys):
    host.env.euid = lambda: 0
    _, obj = js(capsys, "window", "show")
    assert obj["clocks"]["emc_mhz"] == 665
    assert ["/usr/bin/jetson_clocks", "--show"] in [c for c, _ in host.calls]


def test_clocks_locked_true_when_min_equals_max(host, capsys):
    host.set_devfreq("1575000000", "1575000000", "1575000000")
    _, obj = js(capsys, "window", "show")
    assert obj["clocks_locked"] is True


def test_clocks_locked_null_when_unreadable(host, capsys):
    (host.devfreq / "gpu-gpc-0" / "min_freq").unlink()
    _, obj = js(capsys, "window", "show")
    assert obj["clocks_locked"] is None
    assert obj["clocks"]["gpu_min_mhz"] is None and obj["clocks"]["gpu_mhz"] == 1575


def test_clocks_all_null_without_devfreq(host, capsys):
    host.env.devfreq_root = str(host.devfreq / "missing")
    _, obj = js(capsys, "window", "show")
    assert obj["clocks_locked"] is None
    assert obj["clocks"]["gpu_mhz"] is None and obj["clocks"]["gpu_max_mhz"] is None


def test_fan_profile_null_when_conf_unreadable(host, capsys):
    host.fan_conf.unlink()
    _, obj = js(capsys, "window", "show")
    assert obj["fan_profile"] is None


def test_fan_profile_null_when_conf_has_no_default(host, capsys):
    host.fan_conf.write_text("FAN_PROFILE quiet {\n}\n")
    _, obj = js(capsys, "window", "show")
    assert obj["fan_profile"] is None


def test_window_bare_noun_is_show(host, capsys):
    rc, obj = js(capsys, "window")
    assert rc == 0 and "active" in obj


def test_full_cycle_store_lock_restore(host, capsys):
    rc, obj = js(capsys, "window", "store")
    assert rc == 0 and obj["action"] == "store" and obj["stored"] is True and obj["active"] is False
    store_calls = host.ran("--store")
    assert len(store_calls) == 1
    assert store_calls[0][:3] == ["sudo", "-n", "/usr/bin/jetson_clocks"]
    assert (
        store_calls[0][-1].endswith("thor/jetson_clocks.state")
        or "jetson_clocks.state" in store_calls[0][-1]
    )

    rc, obj = js(capsys, "window", "lock")
    assert rc == 0 and obj["action"] == "lock" and obj["active"] is True
    assert obj["clocks_locked"] is True
    argvs = [c for c, _ in host.calls]
    assert argvs.index(["sudo", "-n", "/usr/bin/jetson_clocks"]) < argvs.index(
        ["sudo", "-n", "/usr/bin/jetson_clocks", "--fan"]
    )
    assert not host.ran("nvfancontrol") and "fan_error" not in obj["detail"]

    rc, obj = js(capsys, "window", "restore")
    assert rc == 0 and obj["restored"] is True and obj["active"] is False and obj["stored"] is False
    assert obj["clocks_locked"] is False  # stock min/max back
    restores = host.ran("--restore")
    assert len(restores) == 1
    assert restores[0][:4] == ["sudo", "-n", "/usr/bin/jetson_clocks", "--restore"]
    assert restores[0][-1].endswith("jetson_clocks.state")
    assert not host.ran("nvfancontrol")  # the restore file carries the fan state
    assert not list(host.env.state_dir.iterdir())


def test_store_refused_while_locked(host, capsys):
    js(capsys, "window", "store")
    js(capsys, "window", "lock")
    host.calls.clear()
    rc, obj = js(capsys, "window", "store")
    assert rc == 1 and obj["ok"] is False and obj["reason"] == "window_active"
    assert not host.ran("--store")  # the stock state is not overwritten


def test_store_twice_unlocked_is_allowed(host, capsys):
    js(capsys, "window", "store")
    rc, obj = js(capsys, "window", "store")
    assert rc == 0 and obj["ok"] is True


def test_lock_without_store(host, capsys):
    rc, obj = js(capsys, "window", "lock")
    assert rc == 1 and obj["reason"] == "no_stored_state"
    assert host.calls == []


def test_lock_is_idempotent(host, capsys):
    js(capsys, "window", "store")
    js(capsys, "window", "lock")
    host.calls.clear()
    rc, obj = js(capsys, "window", "lock")
    assert rc == 0 and obj["active"] is True
    assert not [
        c for c in host.ran_prefix("sudo", "-n", "/usr/bin/jetson_clocks") if "--show" not in c
    ]


def test_restore_without_state_is_ok(host, capsys):
    rc, obj = js(capsys, "window", "restore")
    assert rc == 0 and obj["ok"] is True and obj["restored"] is False
    assert not host.ran("--restore")


def test_not_granted_is_exit_2(host, capsys):
    host.fail["--store"] = (1, "", "sudo: a password is required")
    rc, obj = js(capsys, "window", "store")
    assert rc == 2 and obj["reason"] == "not_granted"
    assert not list(host.env.state_dir.iterdir())  # no half-written window state


def test_privileged_failure_is_failed(host, capsys):
    host.fail["--store"] = (1, "", "jetson_clocks: boom")
    rc, obj = js(capsys, "window", "store")
    assert rc == 2 and obj["reason"] == "failed" and "boom" in obj["message"]


def test_tool_missing(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, tools=())
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, obj = js(capsys, "window", "store")
    assert rc == 2 and obj["reason"] == "tool_missing"
    _, show = js(capsys, "window", "show")
    assert show["supported"] is False and show["clocks"]["emc_mhz"] is None


def test_restore_failure_keeps_state(host, capsys):
    js(capsys, "window", "store")
    js(capsys, "window", "lock")
    host.fail["--restore"] = (1, "", "boom")
    rc, obj = js(capsys, "window", "restore")
    assert rc == 2 and obj["reason"] == "failed"
    assert (host.env.state_dir / "window.json").exists()  # still restorable


def test_fan_failure_does_not_fail_the_window(host, capsys):
    js(capsys, "window", "store")
    host.fail["--fan"] = (1, "", "jetson_clocks: fan boom")
    rc, obj = js(capsys, "window", "lock")
    assert rc == 0 and obj["active"] is True
    assert "boom" in obj["detail"]["fan_error"]


def test_root_runs_without_sudo(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path)
    h.env.euid = lambda: 0
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    js(capsys, "window", "store")
    assert h.ran("--store")[0][0] == "/usr/bin/jetson_clocks"


def test_text_refusal_has_hint(host, capsys):
    rc, out, err = run(capsys, "window", "lock")
    assert rc == 1 and out == "" and "no_stored_state" in err and "hint:" in err


def test_text_success(host, capsys):
    rc, out, _ = run(capsys, "window", "show")
    assert rc == 0 and out.startswith("#")


# ---- drop-caches ------------------------------------------------------------


def test_drop_caches_sysctl_rule(host, capsys):
    rc, obj = js(capsys, "drop-caches")
    assert rc == 0 and obj == {"ok": True, "reason": None, "cleared": True, "rule": "sysctl"}
    argvs = [c for c, _ in host.calls]
    assert argvs.index(["sync"]) < argvs.index(
        ["sudo", "-n", "/usr/sbin/sysctl", "-w", "vm.drop_caches=3"]
    )


def test_drop_caches_tee_rule(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=TEE_ONLY)
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, obj = js(capsys, "drop-caches")
    assert rc == 0 and obj["rule"] == "tee"
    assert (["sudo", "-n", "tee", "/proc/sys/vm/drop_caches"], "3") in h.calls


def test_drop_caches_all_rule(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing="    (ALL) NOPASSWD: ALL\n")
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    _, obj = js(capsys, "drop-caches")
    assert obj["rule"] == "all" and obj["cleared"] is True


def test_drop_caches_not_granted(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=NO_GRANT)
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, obj = js(capsys, "drop-caches")
    assert rc == 2 and obj["reason"] == "not_granted" and obj["cleared"] is False
    assert not h.ran_prefix("sync") and not h.ran("drop_caches")


def test_drop_caches_sudo_would_prompt(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=None)
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, obj = js(capsys, "drop-caches")
    assert rc == 2 and obj["reason"] == "not_granted"


def test_drop_caches_failure(host, capsys):
    host.fail["vm.drop_caches=3"] = (1, "", "read-only")
    rc, obj = js(capsys, "drop-caches")
    assert rc == 2 and obj["reason"] == "failed" and obj["cleared"] is False


# ---- grant-permissions ------------------------------------------------------


def test_check_real_thor_listing_sysctl_is_equivalent(host, capsys):
    rc, obj = js(capsys, "grant-permissions", "--check")
    assert rc == 0 and obj["ok"] is True
    assert obj["drop_caches"] == {"granted": True, "rule": "sysctl", "source": "sudo -n -l"}
    assert obj["window"] == {"granted": True, "rule": "all"}


def test_grant_reuses_existing_rule_installs_nothing(host, capsys):
    rc, obj = js(capsys, "grant-permissions", "--yes")
    assert rc == 0 and obj["ok"] is True and obj["installed"] is False
    assert not host.ran_prefix("visudo") and not host.ran_prefix("sudo", "install")


def test_check_sysctl_only_window_missing(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=SYSCTL_ONLY)
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, obj = js(capsys, "grant-permissions", "--check")
    assert rc == 0 and obj["ok"] is True
    assert obj["window"] == {"granted": False, "rule": None}
    assert not h.ran_prefix("visudo")


def test_check_nothing_granted(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=NO_GRANT)
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, obj = js(capsys, "grant-permissions", "--check")
    assert rc == 2 and obj["ok"] is False and obj["reason"] == "not_granted"
    assert not h.ran_prefix("sudo", "install")


def test_install_window_only_when_sysctl_present(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=SYSCTL_ONLY)
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, obj = js(capsys, "grant-permissions", "--yes")
    assert rc == 0 and obj["installed"] is True
    rules = h.sudoers_written[0]
    assert "vm.drop_caches" not in rules  # not duplicated
    assert "NOPASSWD: ALL" not in rules  # never full sudo
    assert "thor ALL=(ALL) NOPASSWD: /usr/bin/jetson_clocks --store" in rules
    assert "--restore" in rules and "/usr/bin/jetson_clocks --fan" in rules
    assert "nvfancontrol" not in rules
    assert rules.count("\n") == len(obj["rules"])  # one rule per command
    visudo = h.ran_prefix("visudo")[0]
    assert visudo[:2] == ["visudo", "-cf"]
    installs = h.ran_prefix("sudo", "install")
    assert len(installs) == 1
    assert installs[0][:8] == ["sudo", "install", "-m", "0440", "-o", "root", "-g", "root"]
    assert installs[0][-1] == "/etc/sudoers.d/thor-lobes"
    assert h.calls.index((visudo, None)) < h.calls.index((installs[0], None))


def test_install_everything_when_nothing_granted(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=NO_GRANT)
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, out, err = run(capsys, "grant-permissions", "--yes", "--json")
    assert rc == 0
    rules = h.sudoers_written[0]
    assert "/usr/sbin/sysctl -w vm.drop_caches=3" in rules
    assert "will install /etc/sudoers.d/thor-lobes" in err  # rules printed before install
    assert json.loads(out)["installed"] is True


def test_install_declined(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=NO_GRANT)
    h.answers = ["n"]
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, obj = js(capsys, "grant-permissions")
    assert rc == 1 and obj["reason"] == "declined"
    assert not h.ran_prefix("visudo") and not h.ran_prefix("sudo", "install")


def test_install_no_tty_counts_as_declined(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=NO_GRANT)
    h.answers = []
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, obj = js(capsys, "grant-permissions")
    assert rc == 1 and obj["reason"] == "declined"


def test_visudo_rejection_installs_nothing(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=NO_GRANT)
    h.fail["visudo"] = (1, "", "syntax error")
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, obj = js(capsys, "grant-permissions", "--yes")
    assert rc == 2 and obj["reason"] == "failed"
    assert not h.ran_prefix("sudo", "install")


def test_install_failure(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=NO_GRANT)
    h.fail["sudo install"] = (1, "", "denied")
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    rc, obj = js(capsys, "grant-permissions", "--yes")
    assert rc == 2 and obj["reason"] == "failed"


def test_temp_rule_file_is_removed(tmp_path, monkeypatch, capsys):
    h = FakeHost(tmp_path, listing=NO_GRANT)
    monkeypatch.setattr(window_cmd, "_env", lambda: h.env)
    js(capsys, "grant-permissions", "--yes")
    assert not list(tmp_path.glob("thor-sudoers-*"))


def test_window_sudoers_rule_list(host):
    from jetson_thor.window import core, sudoers

    cmds = sudoers.window_commands(host.env, core.state_paths(host.env))
    state = str(host.env.state_dir / "jetson_clocks.state")
    assert cmds == [
        "/usr/bin/jetson_clocks",
        f"/usr/bin/jetson_clocks --store {state}",
        f"/usr/bin/jetson_clocks --restore {state}",
        "/usr/bin/jetson_clocks --fan",
        "/usr/bin/jetson_clocks --show",
    ]
    assert not any("nvfancontrol" in c for c in cmds)
