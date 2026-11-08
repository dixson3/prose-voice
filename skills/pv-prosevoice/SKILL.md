---
name: pv-prosevoice
description: >-
  Write and review persuasive or explanatory narrative essays using VOICE.md and AUDIENCE.md.
  Work in Markdown, including ordered multi-file essays, until final export to HTML, DOCX,
  PowerPoint, PDF or another requested format. TRIGGER on /pv-prosevoice, essay writing or
  review requests, and edits to an identified essay. Calls pv-preflight first. SKIP unrelated
  notes, code, instruction files, generated review sidecars and exports; status idea; or
  unresolved required voice references. Optional visual aids follow ILLUSTRATIONS.md.
---

# pv-prosevoice

Write and review persuasive or explanatory narrative content. The document is an **essay**,
regardless of its intended publication channel. Blog posts are one possible use, not the default.
This skill owns prose development and editorial review, not marketing or distribution artifacts.

## Working format and essay selection

Always develop the essay in **Markdown**: one `.md` file or an explicitly ordered set of Markdown
parts. For a new essay, create the Markdown source before drafting. For an existing HTML, DOCX,
PowerPoint, PDF or other input, use an appropriate reader/converter to create Markdown first;
preserve the original, sources, asset references and intended reading order. Report extraction
losses or uncertain content. Review and revise the Markdown, not the binary or rendered output.

Use the user-selected paths and order. `ESSAY.md` and `ESSAY-2.md` are supported conventions, not
required names. For multiple parts, review both each part
and the whole argument, avoiding duplicated openings and conclusions. Retain source Markdown
after export so subsequent revisions start there.

An explicit request identifies the essay. Automatic edit triggers apply only to Markdown already
identified as an essay in the task, or conventional `ESSAY.md` / `ESSAY-<number>.md` sources.
Do not infer that every Markdown file is an essay. Exclude review and visual sidecars, research,
instructions and exported outputs. Sidecars use the configured intermediate paths (below);
never include them as essay parts. A missing `status:` defaults to `draft`; an explicit request
for review or final readiness selects that gate. `status: idea` is a silent no-op until the user
asks to develop it into a draft.

**Export is the final step**, after the READY checks and any remaining findings are resolved or
explicitly accepted. Use the relevant format skill/tool for the requested HTML, DOCX,
PowerPoint, PDF or other deliverable. For a deck, first settle the narrative and slide sequence
in Markdown. Do not perform ongoing prose revisions in the exported file: update Markdown and
regenerate. Check the final export for content completeness, reading order, headings, citations,
links, images, captions and layout. Report rendering limitations; do not claim an uninspected
export is verified. If Markdown is the requested deliverable, no conversion is needed.

## Review intent and requested form

Use the user's explicit intent first, then optional frontmatter `intent:`. `persuasive` means
changing a belief or winning a decision; `explanatory` (also accepted as `informational`) means
helping the reader understand an account or process. Infer from the actual narrative when neither
is stated, and report the chosen intent with the resolved audience. A `thesis:` field alone does
not imply advocacy. Ask only if ambiguity would materially change the review needed.

Both intents receive voice, readability, evidence, provenance and copy-editing checks.
Persuasive essays also receive red-team, cold-read and the curmudgeon/steelman pair by default.
Explanatory essays use the lean review set by default; include the argument/reader checks when
the user requests them or a contested explanation warrants them, without inventing an opposing
position. State which checks ran and why any were omitted.

Optional `VOICE.md` **Forms** guidance can tune the requested output while Markdown remains the
working source. For a slide narrative, check one idea per slide, point-first titles, appropriate
word budgets, and separation of speaker notes from on-slide text. Do not impose slide brevity
on prose essays or infer a publishing channel from a directory name.

## SKILL_DIR

Every `agents/`, `scripts/` and `harper/` path below is relative to this skill's directory. Use the
directory the harness states for this `SKILL.md`; when it states none, resolve:

```bash
SKILL_DIR="${SKILL_DIR:-}"
if [ -z "$SKILL_DIR" ]; then
  GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo .)
  for _root in \
    "$GIT_ROOT/.claude/skills" "$GIT_ROOT/.agents/skills" \
    "$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.config/opencode/skills"
  do
    if [ -d "$_root/pv-prosevoice" ]; then SKILL_DIR="$_root/pv-prosevoice"; break; fi
  done
  unset _root
fi
[ -z "$SKILL_DIR" ] && { echo "ERROR: pv-prosevoice skill directory not found" >&2; exit 1; }
```

`pv-preflight` is the sibling `$SKILL_DIR/../pv-preflight`; install both skills together.

## References and preflight

Before every gate, read the sibling `pv-preflight/SKILL.md` and run:

```bash
uv run "$SKILL_DIR/../pv-preflight/scripts/preflight.py" check
```

Configured additional paths are tried first, then each reference resolves independently from
`<git-root>/.prose-voice/<file>` and `~/.prose-voice/<file>`, taking the first usable file
(non-empty, no `pv-template: unfilled` marker). See *Project configuration*.

- **`VOICE.md` — required:** protected voice patterns, register, readability, Do/Don't and
  generative-cadence tells.
- **`AUDIENCE.md` — required:** reader, register, de-jargon table and figure-text conventions.
  Essay frontmatter `audience:` overrides only the reader persona.
- **`ILLUSTRATIONS.md` — optional:** user guidance for visual style, palette, typography,
  composition, accessibility, aspect ratios and tool preferences. Pass its resolved contents
  to the illustrator. Absence neither blocks prose review nor prevents useful visuals.

Pass resolved reference contents to agents; they do not search for references themselves.
`ready: false` on an edit is a silent no-op; on explicit invocation, report setup actions and
use the preflight setup flow. Never review against missing required references. Missing/stale
companion rules get a short setup note but do not block. `uv` and `git` are required.
`harper-cli` is optional: report `grammar-check skipped (harper-cli not found — brew install harper)`
when absent. Web tools are optional: unresolved source gaps remain `[needs-source]`. Visual tool
availability is assessed only when visuals are requested; no particular provider is required.

## Project configuration

Optional `.pv/config.json` at the git root is tool-agnostic. External workflows may seed it;
this skill has no dependency on them. `guidance` maps reference filenames to ordered file paths,
tried before standard project/global locations. Relative paths resolve from the git root;
absolute and `~` paths are accepted. Each file falls back independently. Invalid config is an
error, never silently ignored. See `pv-preflight/SKILL.md` for the JSON schema/example.

Before creating intermediate artifacts, run:

```bash
uv run "$SKILL_DIR/../pv-preflight/scripts/preflight.py" artifacts <essay.md> --apply
```

Pass the returned paths to agents. The resolver covers `curmudgeon`, `steelman`, `illustrations`,
`draft`, `review`, `ready`, `copyedit`, `provenance`, `fact-check`, `footnoter`, `red-team` and
`cold-read`. Save reports only for explicit or pre-surface work; on-edit reviews surface in chat
without writing report files. Default placement
is `.pv/cache/<essay-relative-directory>/<essay-stem>.<purpose>.md`; this avoids collisions
between same-named files in different directories. The command creates the directory and an
idempotent `.pv/.gitignore` entry for `/cache/`. Without a git root, use `.pv/cache/` beside the
essay. Set `artifacts.location` to `adjacent` for sidecars next to the source. No automatic move
or deletion of existing sidecars occurs when switching modes; use the new resolved paths and
regenerate or explicitly migrate existing artifacts. For a multi-part review, select a primary
source to key its pair's paths and record all parts in order.

Intermediate artifacts are disposable review/generation history, not export dependencies.
Final visual assets and editable diagram sources remain with the essay. Links in cached sidecars
must be relative to the sidecar directory; links in essay Markdown are relative to the essay.

## Bounded write authority

Reviews report findings; the caller applies changes within these limits:

- Automatically apply only an exact de-jargon table replacement that is grammatical in context.
  Meaning-level edits and ambiguous replacements are surfaced.
- **Preserve wins:** never silently change a VOICE-protected verdict, analogy or owned hedge,
  even in agent-authored prose. When uncertain, surface the finding.
- **Pre-surface DRAFT exception:** before showing prose authored or rewritten by an agent this
  turn, clean voice/readability violations only in those authored regions. Existing user prose
  and uncertain authorship remain report-only. An on-edit review never auto-cleans.
- Footnotes are additive: load-bearing claims get GFM markers and definitions under `## Notes`.
  Propose a batch for operator prose; current-turn agent prose may receive them automatically.
- Visual assets and their sidecars may be created when requested. Inserting an image, diagram
  or hidden visual anchor is additive, never a sentence rewrite; insertion into operator prose
  is proposed for confirmation. Follow AUDIENCE figure-text guidance when present, otherwise
  provide descriptive alt text and a useful caption when needed.
- Grammar auto-fix is limited to an unambiguous spelling typo in body prose: Harper
  `kind: Spelling`, exactly one suggestion, no dictionary or protected-pattern match, and an
  exact `matched_text` span match. All supplemental regions and other findings are report-only.
- `curmudgeon` and `steelman-response` write only their respective review sidecars. Other reviewers
  report findings; the caller may save them at resolved report paths. Keep these artifacts at the
  configured paths; this instruction does not authorize a git commit or publishing.

## Gates

| Stage | Work | Trigger |
| :-- | :-- | :-- |
| `idea` | No gate | Silent no-op |
| `draft` | Voice + readability → sources → grammar | Identified essay edit (report-only); before presenting agent-authored prose |
| `review` | Grammar + evidence/provenance; persuasive adds argument/reader checks and the premise-gated pair | Review request or edit at this stage |
| `ready` | Source and opted-in visual checks → full editorial pass → final export | Final-readiness/export request or edit at this stage |

Visual generation is optional and separate from gate execution. No hero, section image, visual
sidecar, or explicit image-decline record is required for an essay with no planned visuals.

### DRAFT gate

Run `agents/voice-stylist.md` and `agents/readability-critic.md` in parallel. Give both the resolved
references; focus voice review on Do/Don't, register, generative-cadence tells and protected
patterns. Readability covers sentence length, beat density, choppiness and buried payoff.
Then run `agents/footnoter.md`, then an inline Harper pass so newly added citations are checked.

On-edit footnoting is research-only: use supplied sources or an adjacent `research/` directory
when present; do not make web calls for every edit. Explicit/pre-surface passes may search for
credible sources. Never invent a citation; leave `[needs-source]` when a load-bearing factual
claim cannot be supported. Follow the agent's write rules.

Use the grammar policy in `agents/grammar-check.md`. Run `scripts/build_user_dict.py --cwd
<essay-dir> --sidecar <essay-dir>/.harper-words --json` to merge bundled policy, user
`~/.pv/dictionary.txt` and `~/.pv/ignore-rules.txt`, project `.pv/` equivalents, and optional
essay-local words. Both dictionary entries and ignore rules are additive unions. Use the returned
dictionary path and comma-separated ignore rules for every Harper pass; optional explicit
`--user-dict` / `--user-ignore` paths include policy stored elsewhere.
Use `scripts/harper_lint.py <essay.md> --dialect <dialect> --json` for the read-only primary pass;
it uses the same policy helper per essay and normalizes validated tool output. Honor VOICE dialect
(default `us`). A `fixable` flag is only a candidate and does not authorize a write.
`scripts/extract_prose.py` adds frontmatter, figure text and fenced prose that Harper may skip.
Run tools inline for on-edit draft review; on explicit/pre-surface drafts, follow the tool pass
with `agents/copy-editor.md` for agreement, punctuation, sentence boundaries and consistency.
The copy-editor still reads when Harper is absent. It reports proposals and never broadens
spelling auto-fix authority. Respect the matched-text guard and supplemental-region restrictions.
Check Markdown validity after changes.

For edits, surface findings without rewriting. Before presenting agent-authored prose, apply
only the scoped pre-surface cleanup and surface the rest. Report skipped checks accurately.

### REVIEW gate

Run a report-only Harper pass using the merged policy, then `agents/fact-checker.md` and
`agents/provenance.md` in parallel for both intents. Fact-checker tests accuracy and citations;
provenance tests claim origins, audience suitability of internal material, and whether the reader
can trace or reproduce the evidence. Neither silently changes the essay or publishes anything.

For persuasive essays, also run `agents/red-team.md` and `agents/cold-read.md` in parallel,
then the premise-gated pair below. Give the cold reader only the essay and target-reader persona,
not the voice/register rules. Supply all parts in order for whole-argument checks. Surface
conflicting recommendations without silently choosing one. Explanatory essays add these checks
only when requested or warranted by a contested account.

### Optional visual aids

Use `agents/illustrator.md` when the user asks for visuals or agrees to a concrete proposal for
visuals that improve explanation or persuasion. Identify the point each visual serves; avoid
mandatory decoration, heroes, or one-image-per-section quotas. Existing authorization to create
visuals is sufficient; do not ask repeatedly.

Choose the technology for the content: Mermaid for ordinary structural/sequence diagrams,
Pikchr for precise technical drawings, native SVG or other diagram tools when suitable, and
GPT-image, Nano Banana (`naba`) or another available image model for raster illustrations.
Follow relevant tool skills and resolved `ILLUSTRATIONS.md` guidance. Preserve editable sources
for diagrams and record raster prompts. Use supported rendered assets in exports, inspecting
legibility and accuracy. Missing one tool calls for a suitable available alternative or a clear
limitation, not a global skip of visual work.

For a proposed visual, use an alphanumeric `<!-- illus:<id> -->` anchor at the intended location
and a matching `## illus:<id>` block at the resolved `illustrations` artifact path. Record purpose, tool,
source/prompt, asset paths and `selected: unresolved`, a chosen asset id, or `selected: no-image`.
Only planned visuals get anchors; existing untracked visuals may stay as they are. After approval,
insert the selected asset with a relative path (or supported native diagram source), then record
its selected id. Do not generate a fixed number of alternatives. Regenerate only requested
visuals, retaining prior decisions. Remove obsolete anchors or resolve them as `no-image`.

### READY gate and final export

1. Run the mechanical checks on every essay part:

   ```bash
   uv run "$SKILL_DIR/scripts/ready_preconditions.py" <essay.md> [<part.md> ...] --json
   ```

   Exit 3 means blocked. Only explicitly anchored visuals need resolved sidecar selections;
   unillustrated essays pass the visual check. No `[needs-source]` may remain without an explicit,
   reported user override. Resolve missing sources or qualify/remove the claim with approval.
2. Run voice-stylist, readability-critic, fact-checker, provenance, grammar-check, copy-editor and
   web-enabled footnoter for both intents. Persuasive essays add red-team and cold-read; explanatory
   essays add those when warranted or requested. Avoid concurrent writes: collect parallel
   findings, apply allowed changes serially, then run grammar and copy-editing against the resulting
   text. Re-run mechanical
   checks after source/visual changes. A clean script result alone does not prove factual accuracy
   or visual quality; inspect visuals, links, citations and their fit with the argument.
3. For persuasive essays (or an explicitly requested explanatory pressure-test), run or reuse
   the premise-gated pair. Resolve or surface remaining findings under the bounded
   write authority. Report unavailable checks and outstanding issues.
4. Once editorial work is settled, export only to the requested format using its appropriate
   tools. Verify the output as described in *Working format and essay selection*. Keep the
   Markdown and editable visual sources. No automatic social, newsletter, SEO or promotional
   sidecars; distribution is outside this skill.

### Premise-gated pair

Run `scripts/premise_fingerprint.py <essay.md>` for the source under review. Compare the result
with `premise_fingerprint:` in the resolved `curmudgeon` and `steelman` artifact paths. Reuse only when
both sidecars exist with matching fingerprints and the same reviewed essay-part set. For a
multi-part essay, record each part's fingerprint in the review context; any changed part invalidates
reuse. Missing/malformed fingerprints or an explicit request to rerun also invalidate reuse.

Otherwise run `agents/curmudgeon.md`, then `agents/steelman-response.md` with the counter-essay.
The pair challenges the premise and offers recommendations; it never edits the essay. Distinguish
persuasive claims from explanatory accounts so an explanation is not forced into advocacy.
Pass both agents the status, ordered source paths, fingerprints and designated sidecar paths.
