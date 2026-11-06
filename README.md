# prose-voice

An agent skill that keeps written prose — blog posts, documents, slide decks and emails — in a
consistent house voice and runs a multi-agent editorial pipeline over it. Every document gets
voice and AI-slop checks, mechanical readability, claim sourcing and a copy-edit with a Harper
spelling/grammar pass (also run on edit and at review); review depth
then follows **intent**: persuasive pieces (arguments, proposals, pitches) get fact-check,
provenance, red-team, cold-read and a curmudgeon / steelman adversarial pair; informational
pieces (updates, how-tos, reference, minutes) get fact-check and provenance only. Generated
reports live under `.prosevoice/<doc>/`, never beside the document. It applies to files and to
prose an agent drafts in chat, and installs into Claude Code, pi, Codex and opencode.

The voice itself is not in this repo. The skill reads `VOICE.md` and `AUDIENCE.md` from the
document's directory, the git root, or `~/.config/prose-voice/`, so each writer owns their voice.
This repo ships blank templates for them.

## Layout

```text
skills/prose-voice/          the skill (source of truth)
  SKILL.md                   router: forms, intent, stage-gates, workdir, write authority
  agents/                    one prompt per editorial step
  scripts/                   uv-run helpers (stdlib only)
  protocols/PROSE_VOICE.md   always-loaded companion rule (triggers + pre-surface rule)
templates/                   VOICE.md, AUDIENCE.md starters
install.sh                   multi-harness installer
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

| Harness       | Skill destination                   | Companion rule                                                                         |
| :------------ | :---------------------------------- | :------------------------------------------------------------------------------------- |
| `claude-code` | `<base>/.claude/skills/prose-voice` | `<base>/.claude/rules/PROSE_VOICE.md`                                                  |
| `pi`          | `<base>/.agents/skills/prose-voice` | managed block in `~/.pi/agent/AGENTS.md` (user) or `<root>/AGENTS.md` (project)        |
| `codex`       | `<base>/.agents/skills/prose-voice` | managed block in `~/.codex/AGENTS.md` (user) or `<root>/AGENTS.md` (project)           |
| `opencode`    | `<base>/.agents/skills/prose-voice` | managed block in `~/.config/opencode/AGENTS.md` (user) or `<root>/AGENTS.md` (project) |

`<base>` is `$HOME` at user scope and the project root at project scope. pi, Codex and opencode
share one `.agents/skills` copy. A copied install stamps its own path into the `SKILL_DIR`
resolver in `SKILL.md`; a `--link` install leaves the stamp empty and the resolver searches the
standard skill roots.

Install at one scope only. A repo that also carries its own copy under `.claude/skills/` will
show the skill twice.

## Requirements

- `uv` — runs the helper scripts.
- `harper-cli` (`brew install harper`, optional) — the spelling/grammar pass; absent, it is
  skipped and the copy-editor's own read runs alone. Accepted words go in `harper-dictionary.txt`
  and suppressed rules in `harper-ignore.txt` (repo root, document dir or
  `~/.config/prose-voice/`).
- Web search/fetch tools — footnoter gap-filling and fact-checking; absent, claims are flagged
  `[needs-source]`.
- `blog-artifacts` (separate skill, optional) — offered at the READY gate for posts when installed.

## Adopting

1. Install (project or user scope).
2. Fill in `VOICE.md` and `AUDIENCE.md` from `templates/` — at the repo root for a writing repo,
   or in `~/.config/prose-voice/` for a personal voice that follows you into any directory (email,
   slide text, documents outside a repo). Until both are non-empty the skill does nothing.
3. Write. Any Markdown or text prose is in scope; an optional frontmatter `status:` (`idea` /
   `draft` / `review` / `ready`) selects the gate, `form:` (`post` / `document` / `slides` /
   `email`) selects the form rules, `intent:` (`persuasive` / `informational`) selects the review
   depth, and `thesis:` pins the premise for the adversarial pair. All are optional — absent, the
   skill infers form and intent and treats the piece as a draft.
4. Decide whether to commit `.prosevoice/` (the skill's reports). It is useful history for
   persuasive pieces and noise for most others; the skill does not touch `.gitignore`.

See `skills/prose-voice/README.md` and `SKILL.md` for the pipeline itself.

## License

MIT — see [LICENSE](LICENSE).
