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

_SWAP = """\
# thor swap

Swap inspection, per-process history, and the guarded swap grow. Read verbs are
descriptive (exit 0 even when a subsystem is absent); `grow` is the only mutator
and is **dry-run unless `--apply` is passed**.

## Verbs

- `thor swap overview` — describe the swap surface **and** show the
  live snapshot (the superset of `status`).
- `thor swap status` — the quick snapshot only: swap/memory + a short sar trend
  summary.
- `thor swap grow SIZE [--apply] [--ephemeral]` — resize the swapfile
  (`SIZE` is a placeholder, e.g. `64G`).
- `thor swap history [--window DUR] [--top N]` — top per-process swap/RSS.
- `thor swap sample` — take one snapshot for the history store.

All verbs support `--json`. Sizes are binary (1024-based): `32G` == `32GiB` ==
`32GB`; a bare number is bytes.
"""

_SWAP_STATUS = """\
# thor swap status

Read-only swap + memory snapshot, composed from `/proc` (devices, used%, unified
memory, swappiness) plus a short trend summary read from the existing
sysstat/`sar` history (recent and average swap-used %). Works without root and
exits 0 even when a subsystem is unavailable (it reports `available: false`).

`status` is the quick snapshot-only view. For the same snapshot *plus* the verb
surface in one read, use `thor swap overview` (the superset).

## Usage

    thor swap status
    thor swap status --json
"""

_SWAP_GROW = """\
# thor swap grow SIZE

The guarded mutator: resize the file-backed swapfile in place
(`swapoff -> fallocate -> chmod -> mkswap -> swapon`, plus an fstab ensure on the
persistent path). `SIZE` is a **placeholder** — replace it with a human-readable
size (`64G`, `32GiB`, `16g`, or a raw byte count; binary 1024-based). Don't type
the literal word `size`: `swap grow 64G`, not `swap grow size 64G`.

**Dry-run by default**: without `--apply` it previews the exact step plan on
stderr, emits the structured plan on stdout, and changes nothing (exit 0).
`--apply` executes it and **requires root** — the executor raises an error
(exit 2) with a `sudo … --apply` hint otherwise. `--ephemeral` skips the
persistent fstab entry (this boot only). Hazard warnings (e.g. the swapoff
ENOMEM risk) are always surfaced on stderr.

## Usage

    thor swap grow 32G                 # dry-run preview
    thor swap grow 32G --json
    sudo thor swap grow 32G --apply
"""

_SWAP_HISTORY = """\
# thor swap history

Top per-process swap/RSS consumers over a recent window, aggregated from the
bounded history store the `sample` verb feeds. `--window` accepts a duration
(`1h`, `30m`, `2d`, or a raw second count; default `1h`); `--top N` caps the
ranking (default 10). An empty store prints "no history recorded yet" (and `[]`
under `--json`) and exits 0.

## Usage

    thor swap history
    thor swap history --window 6h --top 20
    thor swap history --json
"""

_SWAP_SAMPLE = """\
# thor swap sample

Take one snapshot of per-process memory/swap from `/proc` and append it to the
bounded history store (which `swap history` later queries). Reports how many
process samples were written. This is the verb an operator's systemd timer /
cron invokes periodically to build up history.

## Usage

    thor swap sample
    thor swap sample --json
"""

_SWAP_OVERVIEW = """\
# thor swap overview

The comprehensive read of the swap noun: the descriptive surface (its verbs and
one-liners) **plus** the live snapshot `thor swap status` shows on its
own — unified memory, swap devices, swappiness, and the short sar trend. `status`
remains the quick snapshot-only view (same input); `overview` is the superset.

Accepts and ignores a stray `target` positional and always exits 0 (the
descriptive-verb contract): the underlying collectors degrade to
`available: false` rather than raise, so overview never hard-fails.

## Usage

    thor swap overview
    thor swap overview --json
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
    ("swap",): _SWAP,
    ("swap", "overview"): _SWAP_OVERVIEW,
    ("swap", "status"): _SWAP_STATUS,
    ("swap", "grow"): _SWAP_GROW,
    ("swap", "history"): _SWAP_HISTORY,
    ("swap", "sample"): _SWAP_SAMPLE,
}
