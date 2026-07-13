"""CLI integration tests for the machine-scope verbs.

These run the real collectors against whatever host the suite executes on.
Tool-backed subsystems (gpu/containers/power) may be unavailable on CI — that
is the point: the verbs must still exit 0 with a well-formed report.
"""

from __future__ import annotations

import json

import pytest

from jetson_thor.cli import main

VERBS = [
    "status",
    "memory",
    "gpu",
    "disk",
    "thermal",
    "containers",
    "network",
    "processes",
    "power",
]


@pytest.mark.parametrize("verb", VERBS)
def test_verb_text_exits_zero(verb: str, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([verb])
    assert rc == 0, f"{verb} should exit 0 even when its subsystem is absent"
    out = capsys.readouterr().out
    assert out.startswith("#")  # sectioned markdown


@pytest.mark.parametrize("verb", VERBS)
def test_verb_json_shape(verb: str, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([verb, "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["subject"] == verb
    assert isinstance(payload["available"], bool)
    assert isinstance(payload["sections"], list)
    assert isinstance(payload["warnings"], list)
    assert "data" in payload


def test_verbs_listed_in_help(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([])
    assert rc == 0
    out = capsys.readouterr().out
    for verb in VERBS:
        assert verb in out


@pytest.mark.parametrize("verb", VERBS)
def test_verb_tolerates_stray_positional(verb: str, capsys: pytest.CaptureFixture[str]) -> None:
    # Descriptive verbs must not hard-fail on an extra positional (overview's
    # contract). A stray arg is accepted and ignored -> exit 0.
    rc = main([verb, "some-stray-arg"])
    assert rc == 0
    assert capsys.readouterr().out.startswith("#")


def test_probe_unknown_flag_routes_structured_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Parse errors on a probe verb must use the error:/hint: contract + exit 1,
    # not argparse's default stderr/exit 2.
    with pytest.raises(SystemExit) as exc:
        main(["memory", "--bogus"])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "hint:" in err


def test_status_json_carries_subsystem_data(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["status", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "host" in payload["data"]
    assert "subsystems" in payload["data"]


def test_status_json_carries_l4t_field(capsys: pytest.CaptureFixture[str]) -> None:
    # l4t is folded into the host facts; on non-Jetson hosts it degrades to
    # None rather than being absent or raising.
    rc = main(["status", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "l4t" in payload["data"]["host"]


def test_status_text_mentions_l4t(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "l4t:" in out
