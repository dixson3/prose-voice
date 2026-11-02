# blog-voice

An agent skill that keeps a writing repo's essays in a consistent house voice and runs a
multi-agent editorial pipeline across the essay lifecycle: voice and readability checks, claim
sourcing, Harper grammar, an adversarial red-team / cold-read / curmudgeon / steelman pass, and
illustration candidates. It installs into Claude Code, pi, Codex and opencode.

The voice itself is not in this repo. The skill reads `VOICE.md` and `AUDIENCE.md` from the git
root of the repo it runs in, so each writing repo owns its voice. This repo ships blank templates
for them.

## Layout

```text
skills/blog-voice/         the skill (source of truth)
  SKILL.md                 router, stage-gates, write authority
  agents/                  one prompt per editorial step
  harper/                  Harper dictionary + suppressed rules
  scripts/                 uv-run helpers (stdlib only)
  protocols/BLOG_VOICE.md  always-loaded companion rule (triggers + pre-surface rule)
templates/                 VOICE.md, AUDIENCE.md, ILLUSTRATIONS.md starters
install.sh                 multi-harness installer
```

## Install

```bash
# User scope, Claude Code (default harness)
./install.sh

# User scope, every supported harness
./install.sh --harness all

# Project scope into a writing repo, with starter voice files
./install.sh --scope project --project-root ~/path/to/writing --harness all --templates

# Development: symlink instead of copy
./install.sh --harness claude-code --link

# Preview or remove
./install.sh --harness all --dry-run
./install.sh --harness all --uninstall
```

| Harness | Skill destination | Companion rule |
| :-- | :-- | :-- |
| `claude-code` | `<base>/.claude/skills/blog-voice` | `<base>/.claude/rules/BLOG_VOICE.md` |
| `pi` | `<base>/.agents/skills/blog-voice` | managed block in `~/.pi/agent/AGENTS.md` (user) or `<root>/AGENTS.md` (project) |
| `codex` | `<base>/.agents/skills/blog-voice` | managed block in `~/.codex/AGENTS.md` (user) or `<root>/AGENTS.md` (project) |
| `opencode` | `<base>/.agents/skills/blog-voice` | managed block in `~/.config/opencode/AGENTS.md` (user) or `<root>/AGENTS.md` (project) |

`<base>` is `$HOME` at user scope and the project root at project scope. pi, Codex and opencode
share one `.agents/skills` copy. A copied install stamps its own path into the `SKILL_DIR`
resolver in `SKILL.md`; a `--link` install leaves the stamp empty and the resolver searches the
standard skill roots.

Install at one scope only. A repo that also carries its own copy under `.claude/skills/` will
show the skill twice.

## Requirements

- `uv` — runs the helper scripts.
- `harper-cli` (`brew install harper`) — grammar step; absent, it is skipped.
- `naba` — illustrator; absent, it is skipped.
- Web search/fetch tools — footnoter gap-filling; absent, claims are flagged `[needs-source]`.
- `blog-artifacts` (separate skill, optional) — offered at the READY gate when installed.

## Adopting in a writing repo

1. Install (project or user scope).
2. Fill in `VOICE.md` and `AUDIENCE.md` at the repo root from `templates/`. Until both are
   non-empty the skill does nothing.
3. Put essays at `Incubator/<slug>/ESSAY.md` (or `ESSAY-<n>.md`) with a frontmatter `status:` of
   `idea`, `draft`, `review` or `ready`, and optionally a `thesis:`.

See `skills/blog-voice/README.md` and `SKILL.md` for the pipeline itself.

## License

MIT — see [LICENSE](LICENSE).
