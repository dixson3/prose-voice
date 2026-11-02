# Agent Instructions

Primary instruction source for all agents (Claude Code, pi, Codex, opencode) working in this
repository. `CLAUDE.md` is a thin `@`-include of this file; put no content there.

## What this repo is

The source of truth for the `blog-voice` skill, packaged for installation into several harnesses.
It is not a writing repo: there are no essays here, and the skill's triggers do not apply to files
in this repo.

## Layout

- `skills/blog-voice/` — the skill. Edit here; never edit an installed copy.
- `skills/blog-voice/protocols/BLOG_VOICE.md` — the always-loaded companion rule. `install.sh`
  deploys it as a rule file (Claude Code) or as a managed block in `AGENTS.md` (pi, Codex,
  opencode).
- `templates/` — blank `VOICE.md` / `AUDIENCE.md` / `ILLUSTRATIONS.md`. Keep their section
  headings in sync with the names the agents look up (`Register`, `Readability`, `Do / Don't`,
  `Generative-cadence tells`, `The reader`, `De-jargon table`, `Style block`, `Aspect`).
- `install.sh` — multi-harness installer. Must stay compatible with macOS `/bin/bash` 3.2.

## Conventions

- Paths inside the skill are relative to the skill directory and resolved through the
  `SKILL_DIR` block in `SKILL.md`. Do not hard-code `.claude/skills/...` paths.
- Helper scripts are stdlib-only PEP 723 scripts run with `uv run`.
- The skill must stay harness-neutral: no Claude-only frontmatter is relied on for behaviour.
- After changing the skill, smoke-test with
  `./install.sh --scope project --project-root "$(mktemp -d)" --harness all --dry-run`.
- All markdown is valid GFM.
- Task tracking uses `bd` (beads). Never markdown TODOs.
