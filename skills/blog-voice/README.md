# blog-voice

Project-scoped skill that keeps this repo's essays (`Incubator/<slug>/ESSAY*.md`) in a
consistent house voice and runs a multi-agent editorial pipeline (voice, reference check, mechanical
readability, red-team of the argument, cold-read of the reader experience, grammar/spelling via
Harper, plus a gated `curmudgeon` → `steelman-response` adversarial pair) across the essay lifecycle.
The voice and audience are repo-owned: the skill reads git-root `VOICE.md` and `AUDIENCE.md` (like
yf-drift-check reads its manifest) rather than hard-coding them.

The checks are mapped onto the essay `status:` as **stage-gates**, cumulative in rigor:

- **`draft` → DRAFT gate** — voice (`VOICE.md` Do/Don't) + readability, then the **footnoter**
  (sources load-bearing claims), then inline `harper-cli` grammar. Fires **report-only on edit**
  (surfaces, never rewrites) and as a **pre-surface auto-clean** before an agent shows a draft it
  wrote. This is the gate that keeps meta-narration out of a surfaced draft.
- **`review` → REVIEW gate** — the adversarial pressure-test: red-team, cold-read, reference check
  (which verifies the footnoter's citations), and the gated `curmudgeon` → `steelman-response` pair.
- **`ready` → READY gate** — **image + source preconditions** (every section + hero has a resolved
  illustration; no unresolved `[needs-source]`), then a full pass over all evaluators, plus an
  **offer to run `blog-artifacts`** (social/newsletter/SEO sidecars) on confirmation when an
  `artifacts.yaml` exists.
- **`idea`** — silent no-op.

The **illustrator** (candidate art via `naba`, into `ESSAY*.illustrations.md`) is a confirmed,
explicit first-draft step — never an on-edit trigger. Style comes from `ILLUSTRATIONS.md`
(per-incubator → project-root).

See `SKILL.md` for the gates, the Preflight, the bounded write authority, and the two DRAFT-gate
triggers.

## When to use

- Drafting an `ESSAY*.md` — the DRAFT gate fires on edit (report-only) and, for an agent, before it
  surfaces a draft it wrote (pre-surface auto-clean).
- Promoting to `review` (adversarial pressure-test) or `ready` (full pass + artifacts offer).
- `/blog-voice [path]` to run the gate for the essay's current status on demand.

Not for: non-essay markdown, research artifacts, skill or instruction files.

## Layout

```text
SKILL.md                         router + workflow + repo-owned references
README.md                        this file
agents/
  voice-stylist.md               EVALUATE/reviewer — voice + accessibility
  fact-checker.md                EVALUATE/reviewer — references/claims
  readability-critic.md          EVALUATE/reviewer — mechanical readability (fast + full)
  red-team.md                    EVALUATE/red-team — ideas, argument, flow
  cold-read.md                   EVALUATE/reviewer — first-time-reader experience
  grammar-check.md               EVALUATE/reviewer — grammar/spelling via Harper (runs harper-cli)
  footnoter.md                   EVALUATE/writer — sources load-bearing claims (GFM footnotes); DRAFT gate, after voice, before grammar
  illustrator.md                 GENERATE/writer — candidate art via naba + ESSAY*.illustrations.md sidecar (confirmed explicit step)
  curmudgeon.md                  GENERATE/red-team — writes ESSAY*.curmudgeon.md counter-essay (gated)
  steelman-response.md           GENERATE/reviewer — writes ESSAY*.steelman.md recommendations (gated)
protocols/
  BLOG_VOICE.md                  always-loaded companion rule (deployed by the repo's install.sh)
harper/
  dictionary.txt                 global custom words (coinages, recurring proper nouns)
  ignore-rules.txt               permanently suppressed Harper rule names (house style)
scripts/
  build_user_dict.py             union the global dict + per-incubator .harper-words sidecar
  extract_prose.py               supplemental pass: recover Harper-skipped reader-facing prose
  premise_fingerprint.py         deterministic premise hash (gates the curmudgeon/steelman pair)
  ready_preconditions.py         mechanical READY-gate checks (image selection + [needs-source] residue)
```

Repo-owned content (read, not vendored): project-root `VOICE.md`, `AUDIENCE.md`, `QUOTES.md`,
`RENDER.md`, and `ILLUSTRATIONS.md` (illustration house style; resolves per-incubator →
project-root). The steps are independent and extensible — add `agents/<step>.md` and list it in
`SKILL.md` to grow the pipeline over time.

## Harper grammar policy

`grammar-check` runs `harper-cli` under a **repo-committed filter policy** so it surfaces genuine
defects, not house-style conflicts:

- `harper/dictionary.txt` — global custom words (e.g. coinages like `accelerant`).
- `harper/ignore-rules.txt` — Harper rule names permanently suppressed as house style (e.g.
  `UseTitleCase` — sentence-case headings). `LongSentences`/`DisjointPrefixes` are **not** suppressed;
  the agent reclassifies them to *advisory* (surfaced, never auto-fixed).
- **Per-incubator proper nouns** live in an optional `Incubator/<slug>/.harper-words` sidecar — one
  word per line (citation author names, essay-local names). `build_user_dict.py` merges it with the
  global dictionary at runtime; a missing sidecar falls back to the global dict alone. The agent
  *proposes* additions (a `proper-noun` finding); the operator appends on approval. `.harper-words` is
  committed (editorial policy, not a build artifact).

**Requires `harper-cli`** (`brew install harper`). Absent → the grammar step is reported skipped and
the other agents run (see SKILL.md Preflight).

### Optional: same dictionary in emacs `harper-ls`

The repo policy is the source of truth, but an author who runs Harper as an LSP in emacs can point
`harper-ls.userDictPath` (or a symlink) at the repo's `harper/dictionary.txt` so the interactive
editor and the editorial gate share the same custom words. This is **optional** — not a build step,
and the repo config remains authoritative.
