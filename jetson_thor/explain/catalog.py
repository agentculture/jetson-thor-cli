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
}
