---
name: prose-voice
description: >-
  House voice and editorial review for written prose — blog posts, documents, slide decks and
  emails — judged against VOICE.md and AUDIENCE.md (document dir → git root →
  ~/.config/prose-voice). Three gates: DRAFT (voice Do/Don't, AI-slop scan, readability,
  footnoter, copy-edit), REVIEW and READY. The REVIEW/READY agent set follows the document's
  intent: persuasive pieces get the full suite (red-team, cold-read, fact-checker, provenance,
  gated curmudgeon/steelman pair); informational pieces get fact-checker + provenance only. All
  generated artifacts go under .prosevoice/<doc-key>/, never beside the document. TRIGGER on
  /prose-voice; on a prose-document edit, run the gate for its frontmatter status (absent =
  draft; the draft gate is report-only); before presenting prose you authored or rewrote this
  turn — a file or a chat-drafted email/slide text — run the DRAFT gate and auto-clean your own
  violations. SKIP (silent no-op) when no VOICE.md or AUDIENCE.md resolves; status idea; anything
  under .prosevoice/; code, commit messages, config, agent-instruction files (AGENTS.md,
  CLAUDE.md, SKILL.md, rules), chat replies.
---

# prose-voice

Voice consistency and editorial review for **prose a human will read**: blog posts, documents
(memos, reports, proposals, READMEs written for people), slide decks (Markdown slide sources or
slide text drafted in chat), and emails (files or chat drafts). Not tied to any directory layout.

## SKILL_DIR

This skill installs into several harness skill roots (claude-code, pi, codex, opencode). Every
`agents/` and `scripts/` path below is relative to the **copy being read**. Resolve it once before
running a script:

```bash
# Stamped by install.sh with this copy's destination; empty in the repo source.
SKILL_DIR_INSTALLED_AT=""
SKILL_DIR="${SKILL_DIR:-}"
if [ -z "$SKILL_DIR" ] && [ -n "$SKILL_DIR_INSTALLED_AT" ] && [ -d "$SKILL_DIR_INSTALLED_AT" ]; then
  SKILL_DIR="$SKILL_DIR_INSTALLED_AT"
fi
if [ -z "$SKILL_DIR" ]; then
  GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo .)
  for _root in \
    "$GIT_ROOT/.claude/skills" "$GIT_ROOT/.agents/skills" "$GIT_ROOT/.opencode/skills" "$GIT_ROOT/.pi/skills" \
    "$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.config/opencode/skills" "$HOME/.pi/agent/skills"
  do
    if [ -d "$_root/prose-voice" ]; then SKILL_DIR="$_root/prose-voice"; break; fi
  done
  unset _root
fi
[ -z "$SKILL_DIR" ] && { echo "ERROR: prose-voice skill directory not found" >&2; exit 1; }
```

When the harness states the skill's base directory (pi, opencode), that directory wins: export it
as `SKILL_DIR` first.

## Scope: what counts as a document

A **document** is a prose deliverable for a human reader. Two axes classify it: **form** (what
it looks like) and **intent** (what it is trying to do). Form selects form-specific checks; intent
selects how many agents the REVIEW and READY gates run.

### Form

| `form:`    | Typical sources                                          | Form-specific checks                                                                                   |
| :--------- | :------------------------------------------------------- | :----------------------------------------------------------------------------------------------------- |
| `post`     | blog Markdown                                            | footnotes on load-bearing claims; `blog-artifacts` offer at READY                                      |
| `document` | memo, report, proposal, spec prose, people-facing README | footnotes or an inline sources section                                                                 |
| `slides`   | Marp / reveal / Slidev Markdown, slide text in chat      | per-slide word budget, one idea per slide, title says the point, speaker notes vs. on-slide text       |
| `email`    | `.md`/`.txt`/`.eml` drafts, chat-drafted mail            | subject line states the point, ask in the first lines, length, one request per mail, sign-off register |

Form resolution: frontmatter `form:` → file signals (`marp: true`, `---` slide separators, a
`Subject:` line, `.eml`) → path hints (`slides/`, `decks/`, `mail/`, `posts/`, `blog/`) → the
operator's stated intent ("draft an email to…") → default `document`.

### Intent

| `intent:`       | The piece is trying to…                                                               | REVIEW / READY agent set                                                                                    |
| :-------------- | :------------------------------------------------------------------------------------ | :---------------------------------------------------------------------------------------------------------- |
| `persuasive`    | change a belief or win a decision — an argument, opinion, proposal, pitch             | **full suite**: `fact-checker`, `provenance`, `red-team`, `cold-read`, gated `curmudgeon` → `steelman` pair |
| `informational` | report, explain, instruct, summarize — status update, how-to, reference, minutes, FYI | **lean set**: `fact-checker`, `provenance`                                                                  |

Intent resolution: frontmatter `intent:` → a `thesis:` field (present → `persuasive`) → content
signals (a recommendation or ask; "should", "we must", "I argue"; a counter-position engaged →
`persuasive`; procedural steps, a status table, a changelog, meeting notes → `informational`) →
form default (`post` → `persuasive`; `document`, `slides`, `email` → `informational`). When the
signals conflict, **ask** rather than guess — the choice decides whether four more agents run.
`/prose-voice review --persuasive` / `--informational` overrides for one run.

**State the resolved form and intent, and which `AUDIENCE.md` resolved, at the top of every
report.**

### Out of scope (silent no-op)

Source code and comments, commit messages, configuration, agent-instruction files (`AGENTS.md`,
`CLAUDE.md`, `SKILL.md`, `agents/*.md`, rule files), test fixtures, chat replies to the operator,
and **anything under `.prosevoice/`** (the skill's own artifacts).

### Multi-file documents

A series (`post-1.md`, `post-2.md`), a deck split by section, or an email thread may be passed
together; argument-level agents treat a point made in a sibling as present, not missing. The
caller decides what to pass; the skill does not infer siblings.

## Voice references

Two files define the voice. Both are **required**; neither ships with the skill.

- `VOICE.md` — how the author writes: patterns to preserve (protected), register, readability
  limits, Do / Don't, generative-cadence tells, and an optional `## Forms` section with per-form
  rules.
- `AUDIENCE.md` — the reader, register, density, de-jargon table, figure-text convention.

**Resolution order** (first hit wins, per file):

1. `AUDIENCE.md` only: the document's own directory (a per-folder audience wholly replaces the
   broader one).
2. The git root of the document (or of `cwd` for chat-drafted prose).
3. `~/.config/prose-voice/` — the operator's personal voice, so email and slide text drafted
   outside any writing repo still has a standard.

Frontmatter `audience:` (one line) overrides the reader persona only.

Optional references at the same locations: `QUOTES.md` (verbatim exemplars), `RENDER.md`
(image alt/title convention), a sibling `research/` or `sources/` directory (citation pool).

## Gate

- Both required files resolve and are non-empty → run.
- Either is missing on an **edit** or **pre-surface** → silent no-op.
- Either is missing on an explicit `/prose-voice` → offer to bootstrap it from the operator's
  existing writing plus the template's documented sections; get approval. Never review against a
  missing or assumed voice.
- An optional reference is absent → run; the dependent check degrades (skip and say so).
- Web search/fetch tools absent → `footnoter`, `fact-checker` and `provenance` run against local
  sources only and flag web-needed claims `[needs-source]`.

No external CLI is required. `uv` runs the three helper scripts.

## Working directory: `.prosevoice/<doc-key>/`

Every artifact the skill generates lives in one project-local tree, **never beside the
document**. Resolve it with:

```bash
WD=$(uv run "$SKILL_DIR/scripts/workdir.py" <doc.md> --ensure)          # <root>/.prosevoice/<rel-path-sans-ext>/
WD=$(uv run "$SKILL_DIR/scripts/workdir.py" --chat "<slug>" --ensure)   # chat-drafted prose: .prosevoice/_chat/<slug>/
```

Fixed artifact names (a re-run overwrites; nothing accumulates):

| Artifact                            | Written by                                    | When                                   |
| :---------------------------------- | :-------------------------------------------- | :------------------------------------- |
| `draft.md`, `review.md`, `ready.md` | the caller — the collected gate report        | every explicit or pre-surface gate run |
| `footnoter.md`                      | `footnoter` — the propose-on-confirm list     | DRAFT, READY                           |
| `fact-check.md`, `provenance.md`    | `fact-checker`, `provenance`                  | REVIEW, READY (both intents)           |
| `red-team.md`, `cold-read.md`       | `red-team`, `cold-read`                       | REVIEW, READY (`persuasive`)           |
| `curmudgeon.md`, `steelman.md`      | the gated pair (carry `premise_fingerprint:`) | REVIEW, READY (`persuasive`, gated)    |

The on-edit report-only DRAFT trigger writes **nothing** to the workdir — it only surfaces in
chat, so a keystroke never produces a file. Whether `.prosevoice/` is committed is the project's
call; the skill neither adds it to `.gitignore` nor stages it. Suggest committing it for
persuasive pieces (the pair's reports are author-review artifacts worth keeping) and ignoring it
otherwise.

## Bounded write authority

Reviews **report**; the caller applies. The limits keep the caller from homogenizing the voice it
exists to protect.

- **Auto-apply is string-matched, not judged.** Apply a change without asking only when it is an
  exact match against a row of `AUDIENCE.md`'s de-jargon table **and** the replacement is
  grammatical in that sentence. Everything else is surfaced.
- **Preserve wins — every gate.** Any change touching a `VOICE.md` pattern to preserve (a blunt
  verdict, an analogy, an owned hedge) is surfaced, never auto-applied. When in doubt, surface.
  This binds `cold-read`'s conviction findings too.
- **DRAFT-gate auto-clean is scoped by authorship and region.** The DRAFT gate is the one place
  the caller may auto-apply voice, readability and copy-edit fixes — **only to prose an agent
  authored or rewrote in the current turn**, and **only at the pre-surface moment**. Three bounds:
  (1) authorship — pre-existing and operator-written prose is surface-only; (2) region, not file —
  a mixed file is cleaned only in the agent-written regions; uncertain origin → surface;
  (3) preserve still wins inside agent regions. The report-only on-edit trigger never applies.
- **One additive body write: citations.** `footnoter` may insert a GFM marker `[^id]` at a
  load-bearing claim plus its `[^id]:` definition under a `## Notes` heading (for `slides`, a
  final *Sources* slide; for `email`, an inline link). Additive only, never a rewrite of the
  sentence, bounded by the same authorship/region rule — on operator prose it is
  **propose-on-confirm**, with the list written to `<WD>/footnoter.md`.
- **Copy-edit is surface-only** except unambiguous spelling/agreement fixes inside the
  pre-surface auto-clean of agent-authored regions.
- **Agents write only into the workdir.** `curmudgeon`, `steelman-response`, `fact-checker`,
  `provenance`, `red-team`, `cold-read` each write exactly one named file under
  `.prosevoice/<doc-key>/` and never touch the document or each other's file.

## Stage gates

Lifecycle lives in optional frontmatter `status:` — `idea` / `draft` / `review` / `ready`. **A
document with no `status:` is treated as `draft`.** Gates are cumulative in rigor; REVIEW and
READY scale with intent.

| `status:`           | Gate                                                                                                                     | Fires on                                                    |
| :------------------ | :----------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------- |
| `idea`              | none (silent no-op)                                                                                                      | —                                                           |
| `draft` (or absent) | **DRAFT** — `voice-stylist` ‖ `readability-critic` → `footnoter` → `copy-editor`                                         | report-only on edit; pre-surface auto-clean; `/prose-voice` |
| `review`            | **REVIEW** — the intent's agent set (lean: `fact-checker` + `provenance`; full: + `red-team` + `cold-read` + gated pair) | on edit; `/prose-voice`                                     |
| `ready`             | **READY** — source precondition, DRAFT evaluators + the intent's REVIEW set, `blog-artifacts` offer for `post`           | on edit; `/prose-voice`; before sending/publishing          |

`/prose-voice review <path>` and `/prose-voice ready <path>` run that gate regardless of the
file's `status:` — the normal path for emails and decks, which rarely carry frontmatter.

### DRAFT gate — both intents, two triggers

`voice-stylist` and `readability-critic` run first (parallel; neither touches footnotes), then
`footnoter` (so citations exist before the copy-edit), then `copy-editor` last. `voice-stylist` is
scoped to `VOICE.md`'s **Do / Don't**, the **generative-cadence tells** scan, register, and the
resolved form's rules from `VOICE.md` §Forms.

1. **Report-only on edit** (mechanical). On a document edit at `status: draft` (or absent),
   surface every finding in chat; **never rewrite under a writer mid-thought**; write nothing to
   the workdir. Once per operator edit. Cost-scoped: `footnoter` runs local-only and
   `copy-editor` is skipped.
2. **Pre-surface auto-clean** (behavioral). **Before presenting prose you authored or rewrote
   this turn** — a file, or an email/slide text drafted in chat — run the gate through a
   fresh-eyes subagent and clean your own violations within the bounds above, then surface the
   rest. The operator never receives a raw agent draft. Write the report to `<WD>/draft.md`.

Why a dispatched gate and not a checklist: authors are blind to their own meta-narration and
cadence; a separate fresh-eyes read catches what self-monitoring does not.

### REVIEW gate — scaled by intent

**Informational (lean).** Two agents, parallel, read-only:

1. `fact-checker` → `<WD>/fact-check.md` — every figure, date, named source and quote verified or
   flagged.
2. `provenance` → `<WD>/provenance.md` — where each claim comes from, whether internal material is
   safe for this audience, what the reader would need to reproduce or verify it.

Collect both into `<WD>/review.md`; surface the findings. No argument-level agents: an FYI, a
how-to or a status report has no premise to attack, and running the suite on it is noise.

**Persuasive (full).**

1. **Parallel group.** `fact-checker`, `provenance`, `red-team`, `cold-read` (read-only; each
   writes its own `<WD>/<agent>.md`). `cold-read` gets the document plus the reader persona only.
2. **Gated adversarial pair** — see *Premise-gated pair*. Writes `<WD>/curmudgeon.md` and
   `<WD>/steelman.md`.
3. Collect into `<WD>/review.md`; surface everything meaning-level or `VOICE.md`-protected.
   `red-team` and `cold-read` flag structure on different axes (argument vs. experience); when
   they hit the same span, surface both — do not auto-resolve.

### READY gate

0. **Source precondition** (mechanical, both intents):

   ```bash
   uv run "$SKILL_DIR/scripts/ready_preconditions.py" <paths.md> --json   # exit 3 = BLOCKED, 0 = clear
   ```

   No unresolved `[needs-source]` may remain. The full pass runs the web-enabled `footnoter`, so
   a never-cited document cannot pass vacuously. The author resolves each flag (adds a source or
   downgrades the claim) or applies an explicit, logged override (note it in `<WD>/ready.md`).
1. **Full parallel group.** The DRAFT evaluators (`voice-stylist`, `readability-critic`,
   `copy-editor`, web-enabled `footnoter`) plus the intent's REVIEW set. Re-check the source
   precondition after.
2. **Gated adversarial pair** (`persuasive` only).
3. Collect into `<WD>/ready.md`; apply within the bounded write authority; surface the rest. A
   clean pass clears the prose — it does not send the email or publish the post.
4. **`post` only — offer `blog-artifacts`** when that skill is installed and an `artifacts.yaml`
   sits beside the post. Offer, never auto-run.

### Premise-gated pair (`persuasive`, REVIEW and READY)

```bash
FP=$(uv run "$SKILL_DIR/scripts/premise_fingerprint.py" <document.md>)   # title + thesis: (or first body paragraph)
```

Read `premise_fingerprint:` from an existing `<WD>/curmudgeon.md`. **Reuse** when it equals `$FP`
("premise unchanged; reusing curmudgeon/steelman"). **Regenerate** otherwise: dispatch
`curmudgeon` with `$FP` as `PREMISE_FINGERPRINT` and `$WD`, then `steelman-response`. The steelman
is always regenerated with the curmudgeon. Per file for multi-file documents (each has its own
workdir). For chat-drafted prose use the `--chat <slug>` workdir; the fingerprint is computed from
the drafted text written to `<WD>/source.md`.

## Modes

| Invocation                                                      | Runs                                                                                     |
| :-------------------------------------------------------------- | :--------------------------------------------------------------------------------------- |
| document edit, `status` draft/absent                            | DRAFT, report-only in chat (no `copy-editor`, `footnoter` local-only, no workdir writes) |
| pre-surface of agent-authored prose                             | DRAFT, auto-clean agent regions, web-enabled `footnoter`, report → `<WD>/draft.md`       |
| `/prose-voice [<path>...]`                                      | the gate for the document's `status:` (absent = DRAFT, web-enabled)                      |
| `/prose-voice review [--persuasive\|--informational] <path>...` | REVIEW regardless of `status:`; the flag overrides intent for this run                   |
| `/prose-voice ready [--persuasive\|--informational] <path>...`  | READY regardless of `status:`                                                            |
| `/prose-voice clean <path>...`                                  | DRAFT with auto-clean over **operator** prose too. Protected patterns still surfaced.    |
| `/prose-voice` with no path                                     | the prose most recently drafted or discussed in this conversation; refuse if none        |

`/prose-voice <path>` refuses out-of-scope files and says why.

## Steps (extensible)

Agents dispatched via the Agent tool; the caller applies within the bounds above. Add a step by
writing `agents/<step>.md` and listing it here under the gate and intent it belongs to. Every
agent receives the resolved `form`, `intent`, and `WD`.

**DRAFT (both intents)**

1. [`agents/voice-stylist.md`](agents/voice-stylist.md) — voice, register, de-jargon, AI-slop scan,
   form rules.
2. [`agents/readability-critic.md`](agents/readability-critic.md) — mechanical readability,
   per-form load.
3. [`agents/footnoter.md`](agents/footnoter.md) — sources load-bearing claims; proposal list →
   `footnoter.md`.
4. [`agents/copy-editor.md`](agents/copy-editor.md) — spelling, agreement, punctuation, consistency.

**REVIEW / READY — lean set (both intents)**

5. [`agents/fact-checker.md`](agents/fact-checker.md) — verifies citations and claims →
   `fact-check.md`.
6. [`agents/provenance.md`](agents/provenance.md) — claim origins, internal-material safety,
   reproducibility → `provenance.md`.

**REVIEW / READY — persuasive additions**

7. [`agents/red-team.md`](agents/red-team.md) — the argument → `red-team.md`.
8. [`agents/cold-read.md`](agents/cold-read.md) — the reader experience → `cold-read.md`.
9. [`agents/curmudgeon.md`](agents/curmudgeon.md) — counter-essay → `curmudgeon.md` (gated).
10. [`agents/steelman-response.md`](agents/steelman-response.md) — adjudication → `steelman.md`
    (gated).

## Rules

- Prose deliverables only; everything in *Out of scope* is a silent no-op.
- Intent decides the agent set; when it is ambiguous, ask — do not default a borderline piece to
  the full suite silently, and do not downgrade an argument to `informational` to save cost.
- Nothing is written beside the document. If a legacy `<stem>.curmudgeon.md` / `<stem>.steelman.md`
  sidecar exists next to a document, read its `premise_fingerprint:` once, then regenerate into
  the workdir and tell the operator the sidecar can be deleted.
- Editing `AUDIENCE.md`'s de-jargon table changes what gets auto-written — treat table edits as
  load-bearing.
