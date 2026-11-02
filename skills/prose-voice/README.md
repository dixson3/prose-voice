# prose-voice

A skill that keeps written prose — blog posts, documents, slide decks and emails — in a
consistent house voice and runs a multi-agent editorial pipeline over it. The voice and audience
are owned by the writer, not the skill: it reads `VOICE.md` and `AUDIENCE.md` (document directory
→ git root → `~/.config/prose-voice/`) rather than hard-coding them.

Two axes classify a document. **Form** (`post` / `document` / `slides` / `email`) selects
form-specific checks. **Intent** selects how deep the review goes:

- **`persuasive`** — an argument, proposal, opinion, pitch. REVIEW and READY run the full suite:
  fact-checker, provenance, red-team, cold-read, and a gated curmudgeon → steelman pair.
- **`informational`** — a status update, how-to, reference page, minutes, FYI. REVIEW and READY
  run a lean set: fact-checker and provenance. Nothing has a premise to attack, so nothing attacks.

The checks are mapped onto an optional frontmatter `status:` as **stage-gates**. A document with
no `status:` is treated as `draft`:

- **`draft` → DRAFT gate** (both intents) — voice (`VOICE.md` Do / Don't, generative-cadence
  tells, form rules) and readability, then the footnoter, then the copy-editor. Fires
  **report-only on edit** and as a **pre-surface auto-clean** before an agent shows prose it
  wrote — including an email or slide text drafted in chat.
- **`review` → REVIEW gate** — the intent's agent set.
- **`ready` → READY gate** — no unresolved `[needs-source]`, then the DRAFT evaluators plus the
  intent's REVIEW set; for posts, an offer to run `blog-artifacts` when installed.
- **`idea`** — silent no-op.

`/prose-voice review <path>` and `/prose-voice ready <path>` run those gates regardless of
frontmatter; `--persuasive` / `--informational` override the intent for one run.

## Artifacts

Everything the skill writes goes under `<git-root>/.prosevoice/<doc-key>/`, where `<doc-key>` is
the document's path relative to the root without its extension (`posts/why.md` →
`.prosevoice/posts/why/`; chat drafts → `.prosevoice/_chat/<slug>/`). Fixed names, overwritten
per run:

```text
draft.md  review.md  ready.md      collected gate reports
footnoter.md                       citation proposals for operator prose
fact-check.md  provenance.md       lean set (every document)
red-team.md  cold-read.md          persuasive additions
curmudgeon.md  steelman.md         gated pair (carry premise_fingerprint:)
```

Nothing is written beside the document. Whether to commit `.prosevoice/` is the project's call.

## Layout

```text
SKILL.md                         router: forms, intent, gates, workdir, write authority
README.md                        this file
agents/
  voice-stylist.md               DRAFT — voice, register, de-jargon, AI-slop, form rules
  readability-critic.md          DRAFT — mechanical readability, per-form load
  footnoter.md                   DRAFT — sources load-bearing claims (form-shaped citations)
  copy-editor.md                 DRAFT — spelling, agreement, punctuation, consistency
  fact-checker.md                REVIEW lean — verifies citations and claims
  provenance.md                  REVIEW lean — claim origins, internal-material safety, reproducibility
  red-team.md                    REVIEW persuasive — the argument
  cold-read.md                   REVIEW persuasive — first-time-reader experience
  curmudgeon.md                  REVIEW persuasive — counter-essay (gated)
  steelman-response.md           REVIEW persuasive — adjudication (gated)
protocols/
  PROSE_VOICE.md                 always-loaded companion rule (deployed by the repo's install.sh)
scripts/
  workdir.py                     resolve .prosevoice/<doc-key>/ for a document or chat draft
  premise_fingerprint.py         deterministic premise hash (gates the curmudgeon/steelman pair)
  ready_preconditions.py         READY-gate [needs-source] residue check
```

Writer-owned content (read, not vendored): `VOICE.md`, `AUDIENCE.md`, and optionally `QUOTES.md`,
`RENDER.md`, and a sibling `research/` or `sources/` directory. Add a step by writing
`agents/<step>.md` and listing it in `SKILL.md` under the gate and intent it belongs to.

## Requirements

`uv` for the helper scripts. No other CLI. Web search/fetch tools improve the footnoter,
fact-checker and provenance agents; without them, external claims are flagged `[needs-source]`.
