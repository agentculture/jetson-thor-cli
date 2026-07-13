"""Repo-wide guard tests: the hard invariants behind the 0.5.0 machine-scope front.

These pin the boundary claims of the spec (docs/specs/2026-07-13-…machine-scope…):
zero runtime dependencies (stdlib-only imports everywhere under ``jetson_thor``),
and the agent-first output contract (results to stdout, stderr clean on success,
``--json`` payloads parse) for every read-only verb of the new surface.
"""

from __future__ import annotations

import ast
import json
import sys
import tomllib
from pathlib import Path

import pytest

from jetson_thor.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "jetson_thor"

# Everything importable at runtime must be stdlib or first-party.
_ALLOWED_TOP_LEVEL = set(sys.stdlib_module_names) | {"jetson_thor"}


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return found


def test_no_third_party_imports_anywhere() -> None:
    offenders: dict[str, set[str]] = {}
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        extra = _top_level_imports(path) - _ALLOWED_TOP_LEVEL
        if extra:
            offenders[str(path.relative_to(REPO_ROOT))] = extra
    assert not offenders, f"non-stdlib imports found: {offenders}"


def test_runtime_dependencies_stay_empty() -> None:
    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)
    assert pyproject["project"]["dependencies"] == []


# The read-only surface: every one of these must succeed on any Linux host,
# emit its result on stdout only, and produce parseable --json.
_READ_ONLY_ARGS = [
    ["status"],
    ["memory"],
    ["gpu"],
    ["disk"],
    ["thermal"],
    ["containers"],
    ["network"],
    ["processes"],
    ["power"],
    ["swap", "status"],
    ["monitor", "check"],
    ["whoami"],
    ["learn"],
    ["overview"],
]


@pytest.mark.parametrize("argv", _READ_ONLY_ARGS, ids=lambda a: " ".join(a))
def test_read_only_verbs_keep_output_contract(argv, capsys) -> None:
    rc = main(argv)
    out, err = capsys.readouterr()
    assert rc == 0
    assert out.strip()
    assert err == ""

    rc = main([*argv, "--json"])
    out, err = capsys.readouterr()
    assert rc == 0
    assert err == ""
    json.loads(out)
