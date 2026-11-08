# Agent Instructions

Primary instruction source for all agents (Claude Code, pi, Codex, opencode) working in this repository. `CLAUDE.md` is a thin `@`-include of this file; put no content there.

## What this repo is

The source of truth for the `pv-prosevoice` and `pv-preflight` skills for Markdown-first narrative essays, installed into agent harnesses with `npx skills add dixson3/prose-voice`. It is not a writing repo: there are no essays here, and the skills' triggers do not apply to files in this repo.

## Layout

- `skills/pv-prosevoice/` — the editorial pipeline. Edit here; never edit an installed copy.
- `skills/pv-preflight/` — dependency checks, voice-file resolution and seeding, rule install.
  - `PV-PROTOCOL.md` — the always-loaded companion rule. `scripts/preflight.py rule` deploys it as `.claude/rules/PV-PROTOCOL.md` or as a managed block in an `AGENTS.md`.
  - `templates/` — blank `VOICE.md` / `AUDIENCE.md` / optional `ILLUSTRATIONS.md`. Keep their section headings in sync with the names the agents look up (`Register`, `Readability`, `Do / Don't`, `Generative-cadence tells`, `The reader`, `De-jargon table`, `Figure text`, `Style block`, `Aspect`), and keep the `pv-template: unfilled` marker line.
- `examples/` — filled, generic guidance examples; no company or personal names. These are reference material, not active guidance or automatic seed content.

## Conventions

- Markdown prose uses one source line per paragraph; rely on editor soft wrapping, never a fixed column width. Preserve structural line breaks in lists, tables, code blocks, frontmatter and intentional Markdown hard breaks. Reflow wrapped prose within a list item without merging separate items.

- Guidance resolves per file: optional configured `.prose-voice/config.json` paths → project `.prose-voice/` → `~/.prose-voice/`. `pv-preflight/scripts/pv_config.py` owns configuration and artifact paths; agents receive resolved content and output paths. Intermediate files default to gitignored `.prose-voice/cache/`, with optional adjacent placement. Final assets stay with the Markdown essay.
- Paths inside a skill are relative to that skill's directory, resolved through the `SKILL_DIR` block in its `SKILL.md`. `pv-prosevoice` reaches `pv-preflight` as the sibling directory. Do not hard-code `.claude/skills/...` paths.
- Helper scripts are stdlib-only PEP 723 scripts run with `uv run`.
- The skills must stay harness-neutral: no Claude-only frontmatter is relied on for behaviour.
- After changing a skill, install both skills from the absolute source repo path into a scratch git repo with `npx skills add <source-repo> -s pv-prosevoice -s pv-preflight -a claude-code -a pi -y`. Run the installed preflight and `uv run python -m unittest discover -s tests` in the source repo.
- All markdown is valid GFM.
- Task tracking uses `bd` (beads). Never markdown TODOs.
