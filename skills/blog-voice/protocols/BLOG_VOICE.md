# Blog Voice Protocol

Always-loaded trigger contract for the `blog-voice` skill. The procedure (agents, gates, bounded
write authority, illustrator flow) lives in the skill's `SKILL.md`; this rule binds only the
triggers a skill description cannot reliably catch.

**Inert unless the repo opts in.** Every trigger below is a silent no-op in a repository whose git
root lacks a non-empty `VOICE.md` **and** `AUDIENCE.md`.

## Essay layout the skill assumes

- Each essay topic is an incubator under `Incubator/<slug>/`.
- Its publication prose is **either** `ESSAY.md` (single post) **or** `ESSAY-<n>.md` (one file
  per part). Never both in one incubator.
- Lifecycle lives in the essay frontmatter `status:` — `idea` / `draft` / `review` / `ready`.
- Optional, recommended frontmatter `thesis:` — one to a few sentences stating the claim. It is
  the region the curmudgeon/steelman premise fingerprint hashes; absent, the first body paragraph
  is used.
- Generated companions match `^ESSAY(-\d+)?\.[\w-]+\.md$` (`.curmudgeon.md`, `.steelman.md`,
  `.illustrations.md`, …) and are never reviewed as essays.

## Repo-owned references

Read from the git root: `VOICE.md` (required), `AUDIENCE.md` (required; an
`Incubator/<slug>/AUDIENCE.md` wholly replaces it for that incubator), `ILLUSTRATIONS.md`
(per-incubator → root), `RENDER.md` and `QUOTES.md` (optional).

## Stage-gate triggers

On an `ESSAY*.md` create or modify, run the gate for its `status:`:

- **`draft`** → DRAFT gate, **report-only** (surfaces voice, readability, sourcing and grammar
  findings; never rewrites).
- **`review`** → REVIEW gate (red-team, cold-read, reference check, gated curmudgeon → steelman
  pair).
- **`ready`** → READY gate (image + `[needs-source]` preconditions, full pass, offer
  `blog-artifacts` when installed and an `artifacts.yaml` exists).
- **`idea`** → silent no-op.

## Pre-surface rule (hard)

Before presenting an `ESSAY*.md` draft **you authored or rewrote this turn**, run the DRAFT gate
through a fresh-eyes sub-agent and auto-clean your own violations first. The operator never
receives a raw agent draft. Bounds: only agent-authored regions of the current turn;
`VOICE.md`-protected verdicts, analogies and hedges are surfaced, not cut; operator prose is
surface-only; uncertain origin → surface.

## Illustration

The illustrator (`naba`, paid and networked) runs only as a **confirmed, explicit** first-draft
step — never as an on-edit side effect.
