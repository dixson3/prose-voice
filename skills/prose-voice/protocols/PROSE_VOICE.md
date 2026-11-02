# Prose Voice Protocol

Always-loaded trigger contract for the `prose-voice` skill. The procedure (agents, gates, bounded
write authority, workdir) lives in the skill's `SKILL.md`; this rule binds only the triggers a
skill description cannot reliably catch.

**Inert unless a voice resolves.** Every trigger below is a silent no-op when no non-empty
`VOICE.md` **and** `AUDIENCE.md` resolve for the prose in question (document directory for
`AUDIENCE.md` → git root → `~/.config/prose-voice/`).

## What the skill reviews

Prose a human will read — the four forms `post`, `document`, `slides`, `email` — whether in a
file or drafted in chat. Lifecycle is optional frontmatter `status:` (`idea` / `draft` / `review` /
`ready`); **absent means `draft`**. Intent (`persuasive` / `informational`, resolved per SKILL.md)
sets how many agents REVIEW and READY run.

**Never reviewed:** code and comments, commit messages, configuration, agent-instruction files
(`AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `agents/*.md`, rule files), test fixtures, chat replies to
the operator, and anything under `.prosevoice/`.

## Stage-gate triggers

On a create or modify of an in-scope document, run the gate for its `status:`:

- **`draft` or absent** → DRAFT gate, **report-only** (voice, AI-slop, readability, sourcing
  findings in chat; never rewrites; no copy-editor; no workdir writes).
- **`review`** → REVIEW gate: `fact-checker` + `provenance` for every document; `persuasive`
  pieces add `red-team`, `cold-read` and the gated curmudgeon → steelman pair.
- **`ready`** → READY gate (`[needs-source]` precondition, DRAFT evaluators + the intent's REVIEW
  set, `blog-artifacts` offer for `post` when installed and an `artifacts.yaml` exists).
- **`idea`** → silent no-op.

## Artifacts

Everything the skill writes goes under `<git-root>/.prosevoice/<doc-key>/` (resolve with
`scripts/workdir.py`), never beside the document. Legacy `<stem>.curmudgeon.md` /
`<stem>.steelman.md` sidecars are read once for their fingerprint, then superseded.

## Pre-surface rule (hard)

Before presenting prose **you authored or rewrote this turn** — a document file, or an email,
slide text or post drafted in chat — run the DRAFT gate through a fresh-eyes sub-agent and
auto-clean your own violations first. The operator never receives a raw agent draft. Bounds: only
agent-authored regions of the current turn; `VOICE.md`-protected verdicts, analogies and hedges are
surfaced, not cut; operator prose is surface-only; uncertain origin → surface.
