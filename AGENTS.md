# Agent Instructions

Primary instruction source for all agents (Claude Code, pi, Codex, opencode) working in this
repository. `CLAUDE.md` is a thin `@`-include of this file; put no content there.

## What this repo is

The source of truth for the `prose-voice` skill — house-voice review for prose deliverables (posts,
documents, slides, emails) — packaged for installation into several harnesses. It is not a
writing repo: there is no `VOICE.md`/`AUDIENCE.md` here, so the skill's triggers are a no-op on
files in this repo.

## Layout

- `skills/prose-voice/` — the skill. Edit here; never edit an installed copy.
- `skills/prose-voice/protocols/PROSE_VOICE.md` — the always-loaded companion rule. `install.sh`
  deploys it as a rule file (Claude Code) or as a managed block in `AGENTS.md` (pi, Codex,
  opencode).
- `templates/` — blank `VOICE.md` / `AUDIENCE.md`. Keep their section headings in sync with the
  names the agents look up (`How the author argues`, `Register`, `Readability`, `Do / Don't`,
  `Generative-cadence tells`, `Forms`, `The reader`, `De-jargon table`).
- `install.sh` — multi-harness installer. Must stay compatible with macOS `/bin/bash` 3.2.

## Conventions

- Paths inside the skill are relative to the skill directory and resolved through the
  `SKILL_DIR` block in `SKILL.md`. Do not hard-code `.claude/skills/...` paths.
- Helper scripts are stdlib-only PEP 723 scripts run with `uv run`. `harper-cli` is the one
  external CLI, and it is optional: `scripts/harper_lint.py` exits 4 when it is absent and the
  gates degrade to the copy-editor's own read. Do not add a required CLI.
- The skill must stay harness-neutral: no Claude-only frontmatter is relied on for behaviour.
- The skill is form-neutral: nothing in it may assume a directory layout, filename pattern or
  single document kind.
- After changing the skill, smoke-test with
  `./install.sh --scope project --project-root "$(mktemp -d)" --harness all --dry-run`.
- All markdown is valid GFM.
- Task tracking uses `bd` (beads). Never markdown TODOs.
