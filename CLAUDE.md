# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is (two truths, read both)

1. **Today it is the agent-first CLI scaffold** cloned from
   `culture-agent-template`. The shipping code is the *template* surface —
   identity/introspection verbs (`whoami`, `learn`, `explain`, `overview`,
   `doctor`), zero runtime dependencies, the vendored skill kit, and the
   build/CI baseline. None of it is Jetson-specific yet.
2. **Its intended domain** (per the seed and `pyproject.toml` description) is an
   *agent + CLI for operating NVIDIA Jetson Thor* — Blackwell-based
   robotics/edge-AI compute, Orin's successor: provisioning, inference, and
   on-device ops. That domain has **not been built**. When you add it, follow
   the noun-group pattern below (`register()` a new module under
   `jetson_thor/cli/_commands/`), don't bolt features onto the template verbs.

Treat the template verbs as the *contract* the agent-first rubric enforces, and
build the Jetson Thor surface as new noun groups beside them.

> The mesh resident prompt for this agent is **`AGENTS.colleague.md`**, not this
> file. `culture.yaml` declares `backend: colleague` (a Qwen served model), so
> the colleague backend reads `AGENTS.colleague.md`. `CLAUDE.md` is only
> guidance for Claude Code doing dev work here. `doctor`'s
> `prompt_file_present` check verifies `AGENTS.colleague.md` — editing this file
> does not affect that invariant.

## Commands

```bash
uv sync                                       # create .venv, install dev deps
uv run pytest -n auto                         # full suite (xdist parallel)
uv run pytest tests/test_cli.py::test_whoami_text -v   # a single test
uv run pytest --cov=jetson_thor --cov-report=term      # with coverage (fail_under=60)
```

Lint (each is a separate CI gate — run all before a PR):

```bash
uv run black --check jetson_thor tests
uv run isort --check-only jetson_thor tests
uv run flake8 jetson_thor tests
uv run bandit -c pyproject.toml -r jetson_thor
markdownlint-cli2 "**/*.md" "#node_modules" "#.local" "#.claude/skills" "#.teken"
uv run teken cli doctor . --strict            # the agent-first rubric gate
```

Run the CLI:

```bash
uv run thor whoami                    # console script (short command name)
uv run python -m jetson_thor whoami   # equivalent module entry point
```

## CLI naming invariant

The **console command is `thor`** — deliberately short, and *distinct* from both
the distribution/package name (`jetson-thor-cli` on PyPI, `jetson_thor` as the
import) and the mesh nick (`culture.yaml` `suffix: jetson-thor-cli`, which
`whoami` reports). Don't conflate them: `thor` is what you type, `jetson-thor-cli`
is who the agent is.

Three *command-surface* places must use the **same script name**, because the
`teken` rubric gate (the CI `afi rubric gate`) derives the binary name from
`[project.scripts]` and runs `explain <binary-name>`, which must resolve:

- `[project.scripts]` in `pyproject.toml` (`thor = "jetson_thor.cli:main"`),
- `prog=` in `jetson_thor/cli/__init__.py`,
- the root `ENTRIES` key in `jetson_thor/explain/catalog.py` (`("thor",)`).

Keep those three in sync — plus the command examples in `learn`, `overview`,
`doctor`, and the catalog bodies, which all show `thor <verb>`. The scaffold
originally shipped the script as `jetson-thor` while the catalog keyed
`jetson-thor-cli`, which broke `explain_self` in the rubric gate and made the
README quickstart fail; 0.4.1 renamed the command to `thor` and aligned all
three. The tests call `main([...])` directly rather than the installed script,
so they won't catch a script-name drift — the rubric gate is the only guard.

## Architecture

**Agent-first CLI** — the design goal is a CLI another *agent* can learn and
drive without docs. Every surface is introspectable (`learn`, `explain`,
`overview`), every command takes `--json`, and errors are structured.

- **Dispatch (`jetson_thor/cli/__init__.py`)** — `main(argv)` builds an argparse
  tree and routes through `_dispatch`. Handlers return `None`/`int` on success
  and **raise `CliError`** on failure; `_dispatch` catches it, and any stray
  exception is wrapped into a `CliError` so no traceback ever reaches stderr.
- **`_CliArgumentParser`** subclasses `ArgumentParser` so even *argparse-level*
  errors (unknown verb, bad flag) emit the structured `error:` / `hint:` format
  and exit 1, not argparse's default stderr/exit-2. Because parse errors happen
  before `args.json` exists, `main()` pre-scans raw argv for `--json` and stashes
  it on the class-level `_json_hint`. Subparsers are built with
  `parser_class=_CliArgumentParser` so the override propagates to every level.
- **Verb registration** — each command is a module under
  `jetson_thor/cli/_commands/` exposing `register(sub)`. To add a command,
  write the module and call its `register()` in `_build_parser()`. Noun groups
  (e.g. `cli`) add their own nested subparsers; pass `parser_class=type(p)` so
  the structured-error contract reaches nested verbs too.
- **Output contract (`_output.py`)** — `emit_result` → stdout, `emit_error` /
  `emit_diagnostic` → stderr, **never mixed**, so an agent can parse stdout
  blindly. `--json` routes structured payloads to the same streams.
- **Error contract (`_errors.py`)** — `CliError(code, message, remediation)`.
  Exit codes: `0` success, `1` user error, `2` environment error, `3+`
  reserved. The `hint:` line (from `remediation`) is required by the rubric.
- **`explain` catalog (`jetson_thor/explain/`)** — markdown keyed by
  command-path tuples in `catalog.py`; `resolve()` raises `CliError` on a miss.
  Every registered noun/verb should have a catalog entry, and
  `test_every_catalog_path_resolves` enforces that each key resolves.
- **Identity (`whoami.py`)** — parses `culture.yaml` *by hand* (no YAML dep, to
  keep `dependencies = []`) for `suffix`/`backend`/`model`. It walks up from
  `__file__` (not cwd) so identity is always the agent's own; in a wheel install
  with no `culture.yaml`, it falls back to literal defaults. `doctor.py` and
  `overview.py` both reuse `whoami`'s `report()`/`read_agent_fields()`.
- **`doctor.py`** mirrors `steward doctor`'s invariants: `backend-consistency`
  (the `_PROMPT_FILE` map: `claude`→`CLAUDE.md`, `colleague`→`AGENTS.colleague.md`,
  `acp`→`AGENTS.md`, `gemini`→`GEMINI.md`) plus a `skills-present` check. It
  emits the rubric-shaped `{healthy, checks:[{id,passed,severity,message,
  remediation}]}` and exits 1 when unhealthy.
- **Machine-telemetry verbs sit at top level** (`status`, `memory`, `gpu`,
  `disk`, `thermal`, `containers`, `network`, `processes`, `power`), alongside
  `whoami`/`doctor` rather than under a noun — the Thor *is* the system,
  mirroring `dgx-spark-cli`'s design (this surface was ported from there).
  `power` and `l4t` (folded into `status`) are the Jetson-specific additions
  over the DGX Spark original: nvpmodel mode, jetson_clocks state, and INA
  hwmon power rails have no DGX Spark equivalent, and the L4T release comes
  from `/etc/nv_tegra_release`, a Tegra-only file.
- **`jetson_thor/probe/`** — the collector package backing the machine verbs.
  Each domain module (`memory`, `disk`, `gpu`, `thermal`, `network`,
  `containers`, `processes`, `power`, `l4t`, `host`, `contention`) exposes a
  `collect()` returning a JSON-friendly report dict (`_report.py`:
  `subject`/`available`/`source`/`warnings`/`sections`/`data`/`remediation`);
  `status.py` aggregates them into an anomalies-first headline. Collectors
  **never raise** — a missing tool or unreadable `/proc`/`/sys` node degrades
  to `available: false` plus a remediation hint, so descriptive verbs always
  exit 0 (`doctor` stays the only health gate). Every collector takes an
  injectable command `Runner` and/or file root (`_run.py`) so the suite runs
  off-Thor on x86 CI with no GPU, docker, or aarch64.
- **`jetson_thor/swap/`** — domain logic for the `swap` noun group: `state.py`
  reads `/proc/swaps` + `/proc/meminfo` + swappiness for a point-in-time
  snapshot, `sar.py` reads recent trend via `sadf -j` (sysstat), `history.py`
  is a bounded JSONL per-process sampler/store under
  `$XDG_STATE_HOME/jetson-thor`, and `grow.py`/`apply.py` split the resize
  workflow into a pure planner (`GrowPlan`, never touches the host) and a
  privileged executor gated on `apply=True` + root. `swap grow` is
  **dry-run by default** — plan-only until both gates are satisfied.
- **`jetson_thor/monitor/`** — the webhook watchdog behind `monitor`:
  `config.py` (JSON at `~/.config/jetson-thor/monitor.json`, env override
  `JETSON_THOR_WEBHOOK_URL`), `rules.py` (`evaluate(snapshot, thresholds) ->
  [Alert]`, pure), `engine.py` (snapshot → evaluate → diff → notify → persist,
  `run_once`/`run_loop`), `notify.py` (stdlib `urllib` POST, generic/Slack/
  Discord presets, never raises into the loop), `state.py` (edge-triggered:
  fires on transition, resolves on recovery, re-notifies only after
  `renotify_cycles`), and `systemd.py` (generates/manages the `--user` unit
  `jetson-thor-monitor.service`). No model, no inference — pure threshold
  comparison.

**No runtime dependencies** is a hard invariant — `dependencies = []`. Anything
new the CLI needs at runtime must be hand-rolled or deferred; third-party libs
belong in `[dependency-groups].dev` only.

## Conventions

- **Version-bump every PR.** CI's `version-check` job fails any PR whose
  `pyproject.toml` version equals `main`'s — even docs/CI-only PRs. Use the
  `version-bump` skill (updates `pyproject.toml` + prepends a Keep-a-Changelog
  entry to `CHANGELOG.md`). Version is single-sourced from `pyproject.toml`;
  `jetson_thor.__version__` reads it via `importlib.metadata`.
- **Skills are cite-don't-import.** `.claude/skills/` is vendored from
  `guildmaster` (and a few from `devague`/`colleague`) — see
  `docs/skill-sources.md` for provenance and the re-sync procedure. Don't edit
  skill script bodies in place; adapt only consumer-identifying prose in
  `SKILL.md` and lift real changes upstream first. Every vendored `SKILL.md`
  must carry `type: command` or the loader silently skips it.
- **PR lifecycle** uses the `cicd` skill (delegates to `devex pr`, adds Sonar
  gating via `status`/`await`). Cross-repo/mesh comms use `communicate`.
- **Renaming the package** (`jetson_thor` / `jetson-thor-cli`): the name is
  hard-coded in ~100 places. Discover them first:
  `git grep -n -E 'jetson[_-]thor'` and update `pyproject.toml`, the package
  dir, `tests/`, `sonar-project.properties`, `README.md`, and the explain
  catalog together — keeping the four names in the CLI naming invariant in sync.

## CI

`.github/workflows/tests.yml` runs three jobs on PRs: **test** (pytest +
SonarCloud, gated on `SONAR_TOKEN` so forks skip it), **lint** (the six gates
above, including the `afi rubric gate`), and **version-check**.
`publish.yml` publishes to TestPyPI on PRs and PyPI on push-to-main via Trusted
Publishing (no stored token), triggered only by changes to `pyproject.toml` or
`jetson_thor/**`.
