---
name: blog-voice
description: >-
  House voice and editorial review for a writing repo's essays (Incubator/<slug>/ESSAY*.md),
  read from git-root VOICE.md and AUDIENCE.md. A multi-agent pipeline mapped onto the essay
  status stage-gates: DRAFT (voice Do/Don't, readability, footnoter, Harper grammar), REVIEW
  (red-team, cold-read, reference check, curmudgeon/steelman pair), READY (image + source
  preconditions, full pass, blog-artifacts offer). TRIGGER on /blog-voice; on an ESSAY*.md edit,
  run the gate for its frontmatter status (draft gate is report-only); before presenting an
  ESSAY*.md draft you wrote or rewrote this turn, run the DRAFT gate and auto-clean your own
  violations. SKIP (silent no-op) when VOICE.md or AUDIENCE.md is absent or empty; status idea;
  generated sidecars matching ^ESSAY(-\d+)?\.[\w-]+\.md$; non-essay markdown, render siblings,
  research and instruction files.
---

# blog-voice

Voice consistency and editorial review for `Incubator/<slug>/ESSAY*.md` — the `.md` only; ignore
co-located `.pdf`/`.html` render artifacts.

## SKILL_DIR

This skill installs into several harness skill roots (claude-code, pi, codex, opencode). Every
`agents/`, `scripts/` and `harper/` path below is relative to the **copy being read**. Resolve it
once before running a script:

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
    if [ -d "$_root/blog-voice" ]; then SKILL_DIR="$_root/blog-voice"; break; fi
  done
  unset _root
fi
[ -z "$SKILL_DIR" ] && { echo "ERROR: blog-voice skill directory not found" >&2; exit 1; }
```

When the harness states the skill's base directory (pi, opencode), that directory wins: export it
as `SKILL_DIR` first.

## Repo-owned references

Read at trigger time from the **git repository root** (project-scoped):

- `VOICE.md` — patterns to preserve. **Required.**
- `AUDIENCE.md` — reader, register, de-jargon table, figure-text convention. **Required.**
  **Resolved per-incubator → project-root:** if `Incubator/<slug>/AUDIENCE.md` exists (where
  `<slug>` is the edited essay's incubator), it **wholly replaces** the repo-root `AUDIENCE.md`
  for that essay; otherwise the repo-root file is used (same resolution `ILLUSTRATIONS.md` uses).
  A per-incubator file carries a full audience (reader + register + de-jargon + figure text), so it
  overrides more than the frontmatter `audience:` line, which sets only the reader persona. Whatever
  resolves is "the AUDIENCE.md" every agent below reads.
- `RENDER.md` — image alt/title convention. Optional.
- `QUOTES.md` + the incubator's `research/voice-quotes.md` — verbatim exemplars. Optional.

## Gate

- Required refs present and non-empty → run. (Absent/empty on an edit → silent no-op, per the description.)
- Absent/empty on explicit `/blog-voice` → offer to bootstrap the missing file(s) from the repo's
  existing essays + each file's documented sections, get operator approval. Never review against a
  missing reference.
- Optional ref absent → run; the dependent check degrades (skip + say so), never errors.

## Preflight

`grammar-check` (and the inline fast-check grammar pass) is the skill's one hard external CLI
dependency: **`harper-cli`**. Before running the grammar step, verify it is resolvable:

```bash
command -v harper-cli
```

- **Present** → run the grammar step normally.
- **Absent** → **graceful degradation**, not an error: the other agents (and `voice-stylist`
  in the fast check) run as usual, and the grammar step is reported
  **`grammar-check skipped (harper-cli not found — brew install harper)`**. This mirrors the
  optional-ref contract above (degrade + say so).

Two **further soft dependencies**, both degrade the same way (skip + say so, never an error):

- **`naba`** (Gemini API + key) — the `illustrator` step's image generator. Verify with
  `command -v naba && naba doctor --json`; absent/unhealthy → the illustrator is reported
  skipped and the rest of the DRAFT gate runs (the essay still reaches `ready` via the
  **decline-without-generate** path — see *Selection flow*).
- **Web search/fetch tools** — the `footnoter`'s gap-filling source pass. Absent → the
  footnoter runs **research-only** and flags web-needed claims `[needs-source]` (web pass
  required).

Scope is deliberately minimal: `harper-cli` is the only tool the grammar step verifies, and
`naba` is checked only when the illustrator runs. JSON is parsed with `uv`-run Python (a
yoshiko-flow baseline tool), **not** `jq`, so no second dependency is introduced. Tools already
guaranteed by yoshiko-flow (`uv`, `git`, `bd`) are not re-checked.

## Bounded write authority

Reviews **report**; the caller applies. Two hard limits keep the caller from quietly homogenizing
the voice it exists to protect:

- **Auto-apply is string-matched, not judged.** Apply a change automatically only when it is an
  exact match against a row of `AUDIENCE.md`'s de-jargon table **and** the replacement is grammatical
  in that sentence. Everything else — including a table row that reads wrong in context — is surfaced.
- **Preserve wins — every gate alike.** Any change touching a `VOICE.md` pattern to
  preserve (a blunt verdict, an analogy, **a self-aware/owned hedge**) is surfaced, never
  auto-applied. **When in doubt, surface.** This binds `cold-read`'s conviction findings too: a hedge
  `VOICE.md` protects is not cut on the strength of a "mushy" verdict without operator sign-off.
- **DRAFT-gate auto-clean is scoped by authorship and region.** The DRAFT gate is the one place the
  caller may auto-apply voice/readability fixes — but **only to prose an agent authored or rewrote in
  the current turn/session**, and **only at the pre-surface moment** (before showing the operator the
  draft). This is the carve-out that lets an agent hand the operator a clean draft instead of a
  violation list. It is bounded three ways: (1) **authorship** — pre-existing prose and any prose the
  operator wrote stay surface-only, the existing preserve-wins rule unchanged; (2) **region, not
  file** — a file mixing agent and operator prose is auto-cleaned only in the agent-written regions;
  when a region's origin is uncertain, **surface, never auto-apply**; (3) **preserve still wins** — a
  `VOICE.md`-protected verdict/analogy/owned-hedge inside an agent region is still surfaced, not
  rewritten (cut the announcement, keep the verdict). The **report-only on-edit** draft trigger (below)
  never auto-applies at all — it only surfaces.
- **Three sanctioned additive body-write classes (footnotes, image insertion, section
  anchors).** The plan-009 rule "no agent writes the `ESSAY*.md` body" now has **exactly three
  additive exceptions**, all introduced by the footnoter/illustrator cycle. Each is
  **additive only — never a rewrite of the author's sentence** — and each is bounded by the
  same DRAFT-gate authorship/region rule below (agent-authored current-turn regions
  auto-insert; operator prose is propose-only; uncertain origin → surface):
  1. **Footnotes** — `footnoter` inserts a GFM marker `[^id]` at a load-bearing claim plus its
     `[^id]:` definition under a `## Notes` heading. On operator prose this is the *primary*
     path and is **propose-on-confirm** (batch-apply list), not silent insertion.
  2. **Image insertion** — the *Selection flow* inserts a chosen `![alt](images/<id>.png
     "title")` line (per `RENDER.md`) at a defined location (hero after frontmatter, section
     after its `##` heading). The image is the illustrator's own generated asset.
  3. **Section anchors** — `illustrator` inserts a hidden `<!-- illus:<id> -->` comment above
     each `##` heading (and `<!-- illus:hero -->` after the frontmatter). A metadata comment,
     never prose; agent-authored by construction.

  These three are the **only** essay-body writes any agent makes; the `curmudgeon`/`steelman`
  sidecar exception (below) writes a *separate file*, not the body. No agent rewrites a
  sentence of the essay's prose.
- **Grammar auto-fix is the narrowest band of all.** `grammar-check`'s only write is an
  **unambiguous spelling typo** in **body prose**: `kind: Spelling`, exactly one suggestion, the
  token in no dictionary and matching no VOICE-protected pattern, **and** the `matched_text`
  write-guard passes (the computed source span must equal Harper's `matched_text` — a mismatch
  surfaces, never writes, because Harper has no confidence score and "single suggestion" is not one:
  `capshun`→`capstan`). House-style, readability/advisory, proper-noun, and every supplemental region
  (frontmatter, image alt/title, fenced prose) are **surface-only in v1** — never auto-fixed.
- **Sidecar exception — the adversarial pair writes its own file, never the essay.** `curmudgeon`
  and `steelman-response` are the **only** agents permitted to write, and each writes **exactly one**
  designated sidecar — `ESSAY*.curmudgeon.md` / `ESSAY*.steelman.md` respectively. They **never**
  edit the essay, never write each other's file, never write anything else. The essay-protection
  invariant is unchanged: no agent modifies `ESSAY*.md`. The sidecars are **committed** artifacts
  (tracked alongside the essay), and — because they match the `ESSAY*` prefix — every essay consumer
  excludes them via the companion discriminator (see *Fast check, gated* and *Full pass*).

## Stage gates

The editorial checks are mapped onto the essay lifecycle `status:` (`idea` / `draft` / `review` /
`ready`). Each stage runs a **gate**; the gates are cumulative in rigor as an essay advances. **Match
the essay proper only** (`^ESSAY(-\d+)?\.md$`) throughout; a companion sidecar edit
(`^ESSAY(-\d+)?\.[\w-]+\.md$` — `.curmudgeon.md` / `.steelman.md` / `.social.md` /
`.newsletter.md` / `.illustrations.md`) is **never** an essay edit and never triggers any gate.

| Stage (`status:`) | Gate | Fires on |
|:--|:--|:--|
| `idea` | none (silent no-op) | — |
| `draft` | **DRAFT gate** — `voice-stylist` (‖ `readability-critic`) → `footnoter` → inline `harper-cli` grammar | **report-only on edit** (surfaces, never rewrites) **and** the **pre-surface auto-clean** (an agent about to present a draft it authored) |
| `review` | **REVIEW gate** — the adversarial pressure-test: `red-team` + `cold-read` + `fact-checker`, then the gated `curmudgeon` → `steelman-response` pair | on edit / `/blog-voice` |
| `ready` | **READY gate** — image + source preconditions, full pass (all evaluators) **+ offer→run `blog-artifacts`** | on edit / `/blog-voice` / before publish |

The **illustrator** is not a stage-gate step — it is a **confirmed, explicit** first-draft
generation action (see *Illustrator trigger*), not an on-edit trigger.

### DRAFT gate — the two triggers (the fix for draft-time voice drift)

The DRAFT gate is `voice-stylist` **and `readability-critic`** (two subagents, parallel), **then
`footnoter`** (a subagent), **then an inline `harper-cli` grammar pass** — the grammar pass runs
directly in the main session (Bash), **no subagent**: Harper is cheap, but spawning an LLM
classification subagent per qualifying edit is not, so the draft gate does **not** dispatch the
`grammar-check` agent. `readability-critic` *is* a subagent — choppiness is a near-final problem the
gate exists to catch, so it earns its dispatch. `voice-stylist` is scoped here to `VOICE.md`'s
**Do/Don't** (anti-meta-narration: throat-clearing / "pay attention" leads, essay-as-object
self-narration, stage-direction openers), the **generative-cadence tells (AI slop)** scan
(binary flips, faux-insight openers, colon-reveal drumbeat, importance puffery, weasel attribution,
fake-strong/hub verbs, synonym-cycling, dramatic fragmentation — `VOICE.md` §*Generative-cadence
tells*), plus register.

**Ordering matters, so the DRAFT gate is sequential where it matters:** `voice-stylist`
(‖ `readability-critic`, which does not touch footnotes) runs **first** so it is not confused by
footnote syntax; then `footnoter` inserts/proposes its citations; then the inline grammar pass runs
**last** so it lints the footnote text too.

**The `footnoter` step** (`agents/footnoter.md`) sources the essay's **load-bearing** claims
(fact / stat / story / quote that carries the thesis — not ordinary assertion). Two things scope its
cost and its writes:

- **Cost-scoped by pass.** The cheap **report-only-on-edit** trigger runs the footnoter
  **research-only** (matches claims against the incubator's `research/`; **no web calls** per
  keystroke), surfacing everything. The **pre-surface / explicit** pass is **web-enabled** (fills
  gaps with a credible source, else `[needs-source]`).
- **Propose-on-operator-prose is the primary path.** Footnoting is most valuable on the author's own
  factual prose, which is exactly where the write rule is propose-only — so the *dominant* UX is a
  **batch-apply-on-confirm** proposal list (claim → proposed source; apply-all / pick). Auto-insert
  into current-turn **agent-authored** regions is the convenience path, not the main one (see the
  three additive body-write classes in *Bounded write authority*).

It fires on **two reinforcing triggers** (belt-and-suspenders — see the plan-009 rationale):

1. **Report-only on-edit trigger** (mechanical). On an `ESSAY*.md` edit at `status: draft`, run the
   gate and **surface** every violation — it **never rewrites** (the "don't rewrite under a writer
   mid-thought" guarantee is preserved). Once per operator edit; fix-application writes do not re-arm
   it. This is the mechanical safety net decoupled from an agent remembering to invoke.
2. **Pre-surface auto-clean** (behavioral). **Before an agent presents an `ESSAY*.md` draft it
   authored or rewrote this turn**, it MUST run the gate and **auto-clean its own violations first**
   (bounded by the DRAFT-gate authorship/region rule in *Bounded write authority*) so the operator
   receives clean prose, not a violation list. This is a hard behavioral contract on the authoring
   agent — the un-hookable "surfacing a draft in chat" moment has no filesystem event, so prose is
   the only lever there; the on-edit trigger above is its mechanical backstop.

*Why the DRAFT gate works when a passive `VOICE.md` checklist did not:* it replaces the author's
unreliable self-monitoring (authors are blind to their own meta-narration) with a discrete dispatch
to a **fresh-eyes sub-agent** that catches what the author cannot see in its own prose.

The inline grammar pass runs a **reduced rule scope** (`--only`) of cheap spelling + agreement
classes, excluding readability noise (`LongSentences` and the like), applies the
`harper/ignore-rules.txt` suppressions, and uses the merged `--user-dict-path`:

```bash
harper-cli lint --format json --dialect us \
  --user-dict-path "$DICT" --ignore "$IGNORE" \
  --only SpellCheck,SplitWords,RepeatedWords,PronounVerbAgreement,ThereIsAgreement,IAmAgreement,SubjectPronoun,TheirToThere,TheirToTheyre,ThenThan,ItsContraction \
  <essay-paths.md> 2>/dev/null
```

This `--only` set is a **curated, forward-safe** subset of cheap spelling + agreement + common-
confusable rules pinned to `harper-cli config`; an unknown rule name only warns on stderr (exit 0),
so the list survives Harper version drift. Excluding `LongSentences` here also **unmasks** spelling
lints the default overlap-removal would otherwise swallow. The report-only trigger **surfaces
everything** (no auto-fix). The pre-surface auto-clean applies the bounded DRAFT-gate fixes to
agent-authored regions (guarded single-suggestion body-prose spelling typos via the `matched_text`
guard for grammar; voice/readability per *Bounded write authority*); it surfaces the rest. If
`harper-cli` is absent, the inline pass is skipped (the Preflight contract) — `voice-stylist` still
runs.

**Consequence (intended):** `idea` stays a silent no-op; the DRAFT gate makes voice drift visible
**during** drafting instead of accruing silently until `review`. The REVIEW gate adds the argument
pressure-test; the READY gate is the final full sweep plus artifact generation.

## Modes

| Gate | Trigger | Run | Cost |
|:--|:--|:--|:--|
| DRAFT | `ESSAY*.md` edit at status `draft` (report-only), or pre-surface of an agent-authored draft | `voice-stylist` (‖ `readability-critic`) → `footnoter` → inline `harper-cli` grammar (no subagent) | 3 agents + inline |
| REVIEW | `ESSAY*.md` edit at status `review`, or `/blog-voice` | `red-team` + `cold-read` + `fact-checker` (parallel), **then** the gated `curmudgeon` → `steelman-response` pair | 3 agents + gated pair |
| READY | `ESSAY*.md` edit at status `ready`, `/blog-voice`, or before publish | **image + source preconditions** (mechanical), then the full pass — `voice-stylist` + `fact-checker` + `readability-critic` + `red-team` + `cold-read` + `grammar-check` + `footnoter` (web-enabled, parallel), **then** the gated pair — **plus** the `blog-artifacts` offer | preconditions + 7 agents + gated pair + artifacts |
| illustrator | **confirmed explicit step** at first-draft (behind the naba capability gate + cost confirm) — never on-edit | `illustrator` (generates 3/section + 3 hero via `naba`) | 1 agent + N naba calls |

`/blog-voice <path>` validates the path is an `ESSAY*.md` (refuse otherwise), auto-collects sibling
`ESSAY-NN.md` parts, and runs the gate for the essay's current `status:` (an explicit `/blog-voice`
on a `ready` essay runs the full READY gate; on a `review` essay, the REVIEW gate).

**`/blog-voice clean <path>`** is the explicit opt-in that lets the DRAFT gate auto-clean
**operator-authored** prose, not just current-turn agent regions. The default on-edit gate is
report-only on the author's own prose (never rewrites under a writer mid-thought — *Bounded write
authority*); `clean` is the author *asking* for a mechanics + AI-slop + readability pass over their
own edits. `VOICE.md`-protected verdicts, analogies, and owned hedges are still surfaced, not
rewritten (preserve wins); everything else in the named essay is fair game. Use it after a heavy
hand-edit to hand the essay back clean rather than as a violation list.

## Steps (extensible)

Read-only EVALUATE agents dispatched via the Agent tool; the caller applies within the bounds above.
Add steps by writing `agents/<step>.md` and listing it here.

1. [`agents/voice-stylist.md`](agents/voice-stylist.md) — voice + audience conformance.
2. [`agents/fact-checker.md`](agents/fact-checker.md) — claims cited and accurate. Needs web tools;
   with none, verifies against `research/` only and flags external claims unverifiable. Others are pure-read.
3. [`agents/red-team.md`](agents/red-team.md) — the **argument**: logic, evidence, dodged objections, argument-structure.
4. [`agents/cold-read.md`](agents/cold-read.md) — the **reader experience**: engagement, clarity,
   felt conviction, read **as the target reader** (persona from `AUDIENCE.md` §The reader, or the
   essay's `audience:` frontmatter override).
5. [`agents/grammar-check.md`](agents/grammar-check.md) — grammar/spelling via Harper
   (`harper-cli`) under a repo-owned filter policy (`harper/`). The one agent that **runs a tool**
   (needs Bash) and may apply a **bounded** auto-fix (guarded single-suggestion spelling typos only);
   everything else is surfaced. Requires `harper-cli` — degrades gracefully if absent (see Preflight).
6. [`agents/readability-critic.md`](agents/readability-critic.md) — **mechanical readability**:
   sentence length, punctuation-beat density, overpacked sentences, buried callouts / payoff
   position. Enforces `VOICE.md`'s Readability section. Read-only; runs in **both** the fast check
   and the full pass. Owns the *measurable* axis; `voice-stylist`'s "Density" stays register/voice-
   loss (surface both on overlap).
7. [`agents/footnoter.md`](agents/footnoter.md) — sources **load-bearing** claims with GFM
   footnotes (research-first → web → `[needs-source]`). Runs in the DRAFT gate **after
   `voice-stylist`, before grammar**, and again web-enabled in the READY full pass. A **bounded
   writer** (additive footnote class only — *Bounded write authority*); propose-on-operator-prose is
   its primary path.

The **image-generation step** (not a stage-gate evaluator — a confirmed, explicit action; see
*Illustrator trigger* and *Selection flow*). Like the pair below, it **writes** (its own generated
assets + a sidecar, plus the two additive body-write classes it owns):

- [`agents/illustrator.md`](agents/illustrator.md) — generates candidate illustrations (3/section +
  3 hero) via `naba` in the resolved `ILLUSTRATIONS.md` style, writes an append-only
  `ESSAY*.illustrations.md` history, and stamps hidden `<!-- illus:<id> -->` section anchors.

The **gated adversarial pair** (full pass only; sequential, and skipped when the premise is
unchanged — see *Full pass*). Unlike steps 1–6, these two **write** (their own sidecar only — see
*Bounded write authority*):

7. [`agents/curmudgeon.md`](agents/curmudgeon.md) — a bad-mood adversary: names the premise and
   writes a counter-essay to `ESSAY*.curmudgeon.md` attempting to falsify it or argue the opposite.
   Epistemically honest (no unsupported counter-claims); honest emotion allowed, no rabble-rousing.
8. [`agents/steelman-response.md`](agents/steelman-response.md) — runs **after** the curmudgeon;
   weighs the counter-essay against the original per point (strongest *surviving* objection even when
   ruling for the essay) and writes change/drop/revise/re-research recommendations to
   `ESSAY*.steelman.md` for the author.

`red-team` reads the essay only; `cold-read` reads the essay plus the **target-reader persona**
(`AUDIENCE.md` §The reader, or the essay's `audience:`) — never the register or de-jargon table
(fresh eyes). Both touch structure on different axes — argument vs. experience — so when they flag
the same span (often with opposite fixes), **surface both to the operator; do not auto-resolve.**

## Workflow

### DRAFT gate

Confirm the changed path is the **essay proper** (`^ESSAY(-\d+)?\.md$`) — a companion sidecar edit
is a no-op. Dispatch `voice-stylist` **and `readability-critic`** (parallel subagents) over the
changed `ESSAY*.md` with `VOICE.md`, `AUDIENCE.md`, and (if present) `RENDER.md`
(`readability-critic` needs `VOICE.md`'s Readability section; give it `AUDIENCE.md` for register
only; scope `voice-stylist` to the Do/Don't anti-meta-narration + register checks). **Also run the
inline `harper-cli` grammar pass** (the reduced `--only` scope above) directly in the main session —
no subagent; skip it if `harper-cli` is absent (Preflight).

Two invocation paths, same evaluators, different write behavior:

- **Report-only on-edit** (`status: draft` edit): **surface every finding**, apply nothing — never
  rewrite under a writer mid-thought.
- **Pre-surface** (an agent about to present a draft it authored/rewrote this turn): **auto-clean the
  agent-authored regions** within the bounded write authority (voice/readability per the DRAFT-gate
  authorship/region rule; for grammar, the `matched_text`-guarded single-suggestion body-prose
  spelling typo), then surface the rest. Hand the operator the cleaned draft.

The repo's `.markdown-lint-on-edit` marker handles GFM validity (if a clone lacks it, lint the
changed file).

### Illustrator trigger (confirmed, explicit — never on-edit)

The `illustrator` generates candidate art **only** as a deliberate step, because `naba` is paid,
networked, and multi-minute (3×(sections+1) generations is dozens of Gemini calls). It **never**
fires as an on-save side-effect. It runs when **both** hold:

1. **naba capability gate** — `command -v naba && naba doctor --json` reports healthy. Absent →
   skip (report `illustrator skipped (naba not available)`); the rest of the DRAFT gate runs.
2. **One-line cost confirmation** — e.g. *"generate N×3 + 3 hero candidates via naba? [y/N]"*.

**The sidecar is the once-guard.** An existing `ESSAY*.illustrations.md` means the full candidate
set was already generated; do not regenerate wholesale. After the first run the author **re-requests
per section** manually (the illustrator appends candidates to that section's block). See
`agents/illustrator.md` for generation, id assignment, and the anchor mechanism.

### Selection flow (author selects; the skill inserts)

The illustrator only generates and records — **selection is a separate, explicit step**:

1. The author names an **illustration-id** (choosing by the prompt shown in the sidecar).
2. The skill inserts the chosen image (`images/<id>.<ext>` — `naba` emits JPEG, not PNG; see
   `agents/illustrator.md`) into `ESSAY.md` (per the `RENDER.md` alt/title convention) at a
   **defined location** — the **hero** immediately after the frontmatter (before the first
   paragraph); a **section** image immediately after that section's `##` heading line (the author
   may move it). This is the *image insertion* additive body-write class (*Bounded write authority*):
   additive markdown only, never a prose rewrite.
3. The skill flips that block's selection line to the chosen `<id>`. **"No image for this section"**
   is an explicit decline — set `selected: no-image`.

**Decline-without-generate (naba-absent path).** An essay can reach `ready` **without** ever running
`naba`: stamp the section anchors (`<!-- illus:<id> -->`) and hero anchor and set every block
`selected: no-image` **without** generating candidates. This keeps a naba-absent (or
deliberately-unillustrated) essay READY-able rather than permanently blocked for lack of anchors.

### REVIEW gate (`status: review` or `/blog-voice`)

The adversarial pressure-test. The DRAFT-gate voice/readability/grammar checks have been firing on
edit throughout drafting; REVIEW adds the argument- and reader-level scrutiny.

1. **Parallel group.** Dispatch `red-team`, `cold-read`, and `fact-checker` in parallel (all
   read-only). Give `cold-read` the essay plus the target-reader persona only. For a multi-part essay,
   pass the sibling parts so `red-team`/`fact-checker` don't flag a point answered elsewhere; pass each
   agent the essay's `status`.
2. **Gated adversarial pair (sequential, after the group).** Compute the premise fingerprint and
   decide whether to run the pair (see *Premise-gated pair* below).
3. Collect findings; surface everything meaning-level or `VOICE.md`-protected to the operator. The
   curmudgeon/steelman sidecars are **author-review artifacts** — surfaced, never auto-applied; commit
   them alongside the essay.

### READY gate (`status: ready`, `/blog-voice`, or before publish)

The final full sweep plus artifact generation. **Two mechanical preconditions gate it first** —
neither is an LLM judgement; the judgement lives upstream (the illustrator placed the anchors, the
footnoter placed the flags):

0. **Image + source preconditions (mechanical — run before the full pass).**

   ```bash
   uv run "$SKILL_DIR/scripts/ready_preconditions.py" <essay-paths.md> --json   # exit 3 = BLOCKED, 0 = clear
   ```

   - **Image precondition** — every *current* section (each `## heading`, excluding the `## Notes`
     footnote apparatus) plus the hero must have a **resolved** selection in
     `ESSAY*.illustrations.md` (`selected: <id>` or `selected: no-image`). A current section with no
     `<!-- illus:<id> -->` anchor, or an `unresolved`/missing block, **blocks `ready`**. Stale blocks
     (an anchor no longer in the essay) are ignored. Resolve via the *Selection flow* (or the
     decline-without-generate path) before proceeding.
   - **Source precondition** — no unresolved `[needs-source]` token may remain. Because the full pass
     below runs the **web-enabled** `footnoter`, a never-footnoted essay cannot pass vacuously: the
     web pass runs, and any flag it leaves blocks the gate. The author resolves each flag (adds a
     source or downgrades the claim) **or** applies an **explicit override** (surfaced, logged) — the
     override is the author's escape hatch, symmetric with a `no-image` decline.

1. **Full parallel group.** Dispatch all seven read-only evaluators (`voice-stylist`,
   `fact-checker`, `readability-critic`, `red-team`, `cold-read`, `grammar-check`, and the
   **web-enabled `footnoter`**) in parallel. `grammar-check` runs `harper-cli` and may apply a
   bounded spelling auto-fix (skipped, not an error, if `harper-cli` is absent — see Preflight). Then
   **re-check the source precondition** (step 0) against any new `[needs-source]` the web pass left.
2. **Gated adversarial pair** (see *Premise-gated pair*).
3. Collect findings; apply within the bounded write authority, surfacing anything meaning-level or
   `VOICE.md`-protected. A clean pass clears the prose for the publish/sensitivity gate — it does not
   resolve that gate.
4. **Offer `blog-artifacts`.** On a clean full pass of a `ready` essay, **offer** to generate the
   social / newsletter / SEO sidecars and run `/blog-artifacts <incubator>` **on operator
   confirmation** — but **only when the incubator has an `artifacts.yaml`** (else note its absence and
   skip; do not auto-create it). `blog-artifacts` is a **separate skill** with a hard invariant (it
   writes committed sidecars next to the essay and **never contacts an external service**); this gate
   only *invokes* it, never duplicates or overrides it. Generation is a deliberate, confirmed step —
   the READY gate offers, it does not auto-run.

### Premise-gated pair (REVIEW and READY)

Compute the essay's premise fingerprint and decide whether to run the `curmudgeon` → `steelman`
pair:

```bash
FP=$(uv run "$SKILL_DIR/scripts/premise_fingerprint.py" <essay.md>)   # deterministic; title + thesis: (or
                                                          # fallback first body paragraph)
```

Read the `premise_fingerprint:` field from an existing `ESSAY*.curmudgeon.md` (if any).
- **Reuse** (skip regeneration) when the sidecar exists **and** its stored fingerprint **equals**
  `$FP` — report "premise unchanged; reusing existing curmudgeon/steelman."
- **Regenerate** otherwise (no sidecar, fingerprint mismatch, or a **missing/malformed**
  `premise_fingerprint:` header): dispatch `curmudgeon` (passing `$FP` as `PREMISE_FINGERPRINT`),
  then — after it writes `ESSAY*.curmudgeon.md` — dispatch `steelman-response`. The steelman is
  **always** regenerated whenever the curmudgeon is, so the two sidecars never drift apart. The pair
  is sequential (steelman consumes the curmudgeon output); it is **not** in the parallel group. For a
  multi-part essay the pair runs **per part** (per-part sidecars).

## Rules

- **Essays only.** Research artifacts, skill files, and instruction files are out of scope.
- Editing `AUDIENCE.md`'s de-jargon table changes what gets auto-written into essays — treat table
  edits as load-bearing.
