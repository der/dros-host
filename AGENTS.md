# IMPORTANT! General principles

1. Don't assume. Don't hide confusion. Surface tradeoffs.
2. Minimum code that solves the problem. Nothing speculative.
3. Touch only what you must. Clean up only your own mess.
4. Define success criteria. Loop until verified.

# Project specific

- Use pyproject.toml with src directory style of layout.
- Python >= 3.12 required.
- No CI, Docker, Makefile, or pre-commit. Lint/typecheck/test are manual.

## Dev commands

```bash
uv pip install -e ".[dev]"
uv run ruff check src/       # E, F, I, UP, B, SIM; ignore E501
uv run pyright src/          # standard strictness
uv run pytest                # run all tests, expect ~4s
```

Run lint + typecheck + tests before committing.

## DROS

Builds on a local (../dros) software library which provides a lightweight ROS2-like framework.

See docs/DROS.md for details.

## Agent skills

### Issue tracker

Issues live as GitHub issues in this repo (`der/dros-host`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — one `CONTEXT.md` at repo root + `docs/adr/`. See `docs/agents/domain.md`. 