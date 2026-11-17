# Agent Instructions

Primary instruction source for all agents (Claude Code, pi, Codex, opencode) working in this repository. `CLAUDE.md` is a thin `@`-include of this file; put no content there.

## What this repo is

The source of truth for the `prosevoice` skill for Markdown-first narrative essays, installed into agent harnesses with `npx skills add dixson3/prose-voice -s prosevoice`, and for the `prosevoice` Python support package built from the same tree. It is not a writing repo: there are no essays here, and the skill's triggers do not apply to files in this repo.

## Layout

- `skills/prosevoice/` — the single skill. Edit here; never edit an installed copy.
  - `SKILL.md` — editorial pipeline, gates, setup flow and write authority. `README.md` is the maintainer reference for its layout and CLI.
  - `agents/` — reviewer and illustrator prompts. They call the helper only through the `pv` command defined in `SKILL.md`.
  - `scripts/prosevoice.py` — thin PEP 723 launcher for `scripts/prosevoice_lib/` (config, rules, policy, essay checks, migration, CLI).
  - `PROSEVOICE-PROTOCOL.md` — the always-loaded companion rule. `pv rule --apply` deploys it as `.claude/rules/PROSEVOICE-PROTOCOL.md` or as a `prosevoice` managed block in an `AGENTS.md`.
  - `harper/` — bundled Harper dictionary and ignore policy.
  - `templates/` — blank `VOICE.md` / `AUDIENCE.md` / optional `ILLUSTRATIONS.md`. Keep their section headings in sync with the names the agents look up (`Register`, `Readability`, `Do / Don't`, `Generative-cadence tells`, `The reader`, `De-jargon table`, `Figure text`, `Style block`, `Aspect`), and keep the `pv-template: unfilled` marker line.
- `pyproject.toml` — Hatchling build of `prosevoice_lib` with the skill resources under `prosevoice_lib/_skill/`; console command `prosevoice`.
- `examples/` — filled, generic guidance examples; no company or personal names. These are reference material, not active guidance or automatic seed content.
- `tests/` — unittest suite, plus `check_distribution.py` for wheel and installer validation.

## Conventions

- Markdown prose uses one source line per paragraph; rely on editor soft wrapping, never a fixed column width. Preserve structural line breaks in lists, tables, code blocks, frontmatter and intentional Markdown hard breaks. Reflow wrapped prose within a list item without merging separate items.
- Configuration is strict JSON `schema_version: 1` at `$XDG_CONFIG_HOME/prosevoice/config.json` (else `~/.config/prosevoice/config.json`) and `<project>/.prosevoice/config.json`, with precedence builtin < user < project < `--set`. Guidance resolves per file: configured paths → project `.prosevoice/<file>` → user prosevoice directory. `prosevoice_lib/config.py` owns configuration and artifact paths; agents receive resolved content and output paths. Intermediate files default to gitignored `.prosevoice/cache/`, with optional adjacent placement. Final assets stay with the Markdown essay.
- Ordinary commands never read `.prose-voice/` or the retired `pv-prosevoice` / `pv-preflight` / `PV-PROTOCOL` identities. Only `prosevoice_lib/migration.py`, its tests and fixtures may name them.
- Paths inside the skill are relative to its directory, resolved through the `SKILL_DIR` block in `SKILL.md`. Do not hard-code `.claude/skills/...` paths. Resource lookup goes through `prosevoice_lib.skill_root()`, never the current directory.
- The runtime is stdlib-only Python >= 3.11, run with `uv run`; the launcher carries PEP 723 metadata.
- The skill must stay harness-neutral: no Claude-only frontmatter is relied on for behaviour.
- After changing the skill, run `uv run python -m unittest discover -s tests` and `uv run tests/check_distribution.py` in the source repo. The distribution check builds and installs the wheel in isolation, exercises a copied skill tree, and installs the skill from the absolute source repo path into a scratch git repo with `npx skills add <source-repo> -s prosevoice -a claude-code -a pi -y` under an isolated `HOME`.
- All markdown is valid GFM.
- Task tracking uses `bd` (beads). Never markdown TODOs.
