---
name: prosevoice
description: >-
  Write and review persuasive or explanatory narrative essays in Markdown, with conversion
  to other formats as the final step. TRIGGER on /prosevoice; requests to draft, rewrite
  or review an essay; edits to an identified essay; and before presenting essay prose you
  authored or rewrote this turn. Load the skill and run its preflight check to resolve guidance or
  report setup needs. SKIP unrelated notes, code, instructions, generated sidecars and exports.
  An idea stays inactive until the user asks to develop it.
---

# prosevoice

Write and review persuasive or explanatory narrative content. The document is an **essay**, regardless of its intended publication channel. Blog posts are one possible use, not the default. This skill owns prose development and editorial review, not marketing or distribution artifacts.

## Working format and essay selection

Always develop the essay in **Markdown**: one `.md` file or an explicitly ordered set of Markdown parts. For a new essay, create the Markdown source before drafting. For an existing HTML, DOCX, PowerPoint, PDF or other input, use an appropriate reader/converter to create Markdown first; preserve the original, sources, asset references and intended reading order. Report extraction losses or uncertain content. Review and revise the Markdown, not the binary or rendered output.

Use the user-selected paths and order. `ESSAY.md` and `ESSAY-2.md` are supported conventions, not required names. For multiple parts, review both each part and the whole argument, avoiding duplicated openings and conclusions. Retain source Markdown after export so subsequent revisions start there.

An explicit request identifies the essay. Automatic edit triggers apply only to Markdown already identified as an essay in the task, or conventional `ESSAY.md` / `ESSAY-<number>.md` sources. Do not infer that every Markdown file is an essay. Exclude review and visual sidecars, research, instructions and exported outputs. Sidecars use the configured intermediate paths (below); never include them as essay parts. A missing `status:` defaults to `draft`; an explicit request for review or final readiness selects that gate. `status: idea` is a silent no-op until the user asks to develop it into a draft.

**Export is the final step**, after the READY checks and any remaining findings are resolved or explicitly accepted. Use the relevant format skill/tool for the requested HTML, DOCX, PowerPoint, PDF or other deliverable. For a deck, first settle the narrative and slide sequence in Markdown. Do not perform ongoing prose revisions in the exported file: update Markdown and regenerate. Check the final export for content completeness, reading order, headings, citations, links, images, captions and layout. Report rendering limitations; do not claim an uninspected export is verified. If Markdown is the requested deliverable, no conversion is needed.

## Review intent and requested form

Use the user's explicit intent first, then optional frontmatter `intent:`. `persuasive` means changing a belief or winning a decision; `explanatory` (also accepted as `informational`) means helping the reader understand an account or process. Infer from the actual narrative when neither is stated, and report the chosen intent with the resolved audience. A `thesis:` field alone does not imply advocacy. Ask only if ambiguity would materially change the review needed.

Both intents receive voice, readability, evidence, provenance and copy-editing checks. Persuasive essays also receive red-team, cold-read and the curmudgeon/steelman pair by default. Explanatory essays use the lean review set by default; include the argument/reader checks when the user requests them or a contested explanation warrants them, without inventing an opposing position. State which checks ran and why any were omitted.

Optional `VOICE.md` **Forms** guidance can tune the requested output while Markdown remains the working source. For a slide narrative, check one idea per slide, point-first titles, appropriate word budgets, and separation of speaker notes from on-slide text. Do not impose slide brevity on prose essays or infer a publishing channel from a directory name.

## SKILL_DIR and the helper command

Every `agents/`, `scripts/` and `harper/` path below is relative to this skill's directory. Use the directory the harness states for this `SKILL.md`; when it states none, resolve:

```bash
SKILL_DIR="${SKILL_DIR:-}"
if [ -z "$SKILL_DIR" ]; then
  GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo .)
  for _root in \
    "$GIT_ROOT/.claude/skills" "$GIT_ROOT/.agents/skills" \
    "$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.config/opencode/skills"
  do
    if [ -d "$_root/prosevoice" ]; then SKILL_DIR="$_root/prosevoice"; break; fi
  done
  unset _root
fi
[ -z "$SKILL_DIR" ] && { echo "ERROR: prosevoice skill directory not found" >&2; exit 1; }
pv() { env -u VIRTUAL_ENV uv run --script "$SKILL_DIR/scripts/prosevoice.py" "$@"; }
```

All runtime support is the single `pv` command (`scripts/prosevoice.py`, or the `prosevoice` console command when the package is installed). Every subcommand prints one JSON envelope `{schema_version, command, status, data, diagnostics}`. Exit 0 means `ok`, 1 means `blocked` (evaluated blockers such as unresolved guidance or READY failures), 2 means an invalid invocation, invalid configuration or operational error. Common options `--project PATH` and repeatable `--set KEY=JSON` work on every subcommand. Without `--project`, commands without an essay argument use the nearest Git root of the invocation directory, else the invocation directory; run them from inside the writing project or pass `--project`. Essay commands (`artifacts`, `ready`, `policy`, `lint`) without `--project` use each essay's nearest Git root, else the essay's own directory.

| Command | Writes | Purpose |
| :-- | :-- | :-- |
| `pv version` | nothing | package version and resource location |
| `pv check` | nothing | dependencies, resolved guidance, companion-rule state, `actions`, `ready` |
| `pv config` | nothing | effective configuration with per-leaf provenance and resolved paths |
| `pv resolve` | nothing | required VOICE/AUDIENCE and optional ILLUSTRATIONS guidance paths |
| `pv init [--scope project\|user] [--illustrations]` | missing config, blank guides, cache ignore | seed setup; never overwrites |
| `pv artifacts <essay.md> [--kind KIND] [--apply]` | with `--apply`: artifact directory and cache ignore rule | intermediate artifact paths |
| `pv rule [--remove] [--apply]` | with `--apply`: rule file, managed `AGENTS.md` blocks | install or remove `PROSEVOICE-PROTOCOL.md` |
| `pv policy [<essay.md>] [--user-dict P]... [--user-ignore P]... [--sidecar P] [--out P]` | merged dictionary (temp unless `--out`) | merged Harper dictionary and ignore rules |
| `pv lint <part.md>... [--dialect us\|uk\|au\|ca\|in] [--user-dict P]... [--user-ignore P]...` | nothing | read-only Harper pass |
| `pv extract <essay.md> [--out-md P]` | snippet file (temp unless `--out-md`) | Harper-skipped reader-facing prose with back-map |
| `pv premise <part.md>...` | nothing | 16-character premise fingerprint per part |
| `pv ready <part.md>...` | nothing | READY source and active-anchor visual checks |
| `pv migrate [--scope project\|user] [--apply]` | with `--apply`: new `.prosevoice` data, manifest, rules | operator-requested conversion of legacy prose-voice data; never automatic |

`rule`, `artifacts` and `migrate` preview unless `--apply` is given.

## References and preflight

Before every gate run:

```bash
pv check
```

Configured guidance paths are tried first, then each reference resolves independently from `<project>/.prosevoice/<file>` and the user prosevoice directory (`$XDG_CONFIG_HOME/prosevoice/<file>`, else `~/.config/prosevoice/<file>`), taking the first usable file (non-empty, no `pv-template: unfilled` marker). See *Project configuration*.

- **`VOICE.md` — required:** protected voice patterns, register, readability, Do/Don't and generative-cadence tells.
- **`AUDIENCE.md` — required:** reader, register, de-jargon table and figure-text conventions. Essay frontmatter `audience:` overrides only the reader persona.
- **`ILLUSTRATIONS.md` — optional:** user guidance for visual style, palette, typography, composition, accessibility, aspect ratios and tool preferences. Pass its resolved contents to the illustrator. Absence neither blocks prose review nor prevents useful visuals.

Pass resolved reference contents to agents; they do not search for references themselves. `ready: false` on an edit is a silent no-op; on explicit invocation, report setup actions and use the setup flow below. Never review against missing required references. Missing/stale companion rules get a short setup note but do not block. `uv` and `git` are required. `harper-cli` is optional: report `grammar-check skipped (harper-cli not found — brew install harper)` when absent. Web tools are optional: unresolved source gaps remain `[needs-source]`. Visual tool availability is assessed only when visuals are requested; no particular provider is required.

### Setup flow

Use it on an explicit `/prosevoice` invocation when `check` is not ready, or when the operator asks to set up prose voice.

1. Run `pv check` and show the report.
2. Guidance: ask project or user scope, then run `pv init --scope <scope>` (it seeds only missing VOICE/AUDIENCE templates and config, never overwriting; add `--illustrations` only when the operator wants optional visual guidance). Tell the operator to fill in each file and delete its `pv-template: unfilled` line. On request, draft the sections from the repo's existing essays for operator approval.
3. Companion rule: show `pv rule` (preview), then run `pv rule --apply` on confirmation.
4. Missing `uv` or `git` → report; the skill cannot run. Missing `harper-cli` skips grammar. `naba` is one optional raster tool; absence does not disable diagrams or other image tools.

To uninstall the rule before removing the skill, run `pv rule --remove --apply`. Legacy `.prose-voice/` data and older rule identities are never read by these commands; converting them is a separate, explicit migration.

### Companion rule targets

`rule` installs `PROSEVOICE-PROTOCOL.md` next to each `prosevoice` install it finds (project = selected project root, global = `$HOME`). Targets are deduplicated by path.

| Skill found at | Rule written to |
| :-- | :-- |
| `.claude/skills/prosevoice` | `.claude/rules/PROSEVOICE-PROTOCOL.md` |
| `<project>/.agents/skills/prosevoice` | managed block in `<project>/AGENTS.md` |
| `~/.agents/skills/prosevoice` | managed block in `~/.pi/agent/AGENTS.md`, `~/.codex/AGENTS.md` and `~/.config/opencode/AGENTS.md` (each only if that harness dir exists) |
| `~/.config/opencode/skills/prosevoice` | managed block in `~/.config/opencode/AGENTS.md` |

The managed block is delimited by `<!-- BEGIN prosevoice (managed by prosevoice rule; edits are overwritten) -->` and `<!-- END prosevoice -->`; every byte outside it is preserved. A malformed, nested or duplicate block makes `rule` report `blocked` and write nothing.

## Project configuration

Optional strict JSON at `<project>/.prosevoice/config.json` and the user directory's `config.json`. Precedence is builtin < user < project < `--set`. Supported keys are `schema_version` (must be `1`), `guidance` and `artifacts`; unknown keys, duplicate keys, malformed JSON or invalid types are errors, never silently skipped.

```json
{
  "schema_version": 1,
  "guidance": {
    "VOICE.md": ["guides/voice.md"],
    "AUDIENCE.md": ["guides/audience.md"],
    "ILLUSTRATIONS.md": ["guides/visuals.md"]
  },
  "artifacts": {
    "location": "cache"
  }
}
```

`guidance` maps reference filenames to ordered file paths, tried before the standard project/user locations. The highest tier that sets a filename replaces that filename's list; other filenames keep their own values. Relative paths anchor to the user config directory (user tier), the project root (project tier) or the invocation directory (`--set`); `~` is expanded. Each file falls back independently. Override one value per invocation with, for example, `--set 'guidance.VOICE.md=["docs/voice.md"]'` or `--set 'artifacts.location="adjacent"'`. `pv config` reports effective values and their provenance.

Before creating intermediate artifacts, run:

```bash
pv artifacts <essay.md> --apply
```

Pass the returned paths to agents. The resolver covers `curmudgeon`, `steelman`, `illustrations`, `draft`, `review`, `ready`, `copyedit`, `provenance`, `fact-check`, `footnoter`, `red-team` and `cold-read`. Save reports only for explicit or pre-surface work; on-edit reviews surface in chat without writing report files. Default placement is `<project>/.prosevoice/cache/<essay-relative-directory>/<essay-stem>.<purpose>.md`; this avoids collisions between same-named files in different directories. Without a Git root and without `--project`, the cache is `.prosevoice/cache/` beside the essay. With `--project`, in cache mode the essay must be inside that project. The command creates the directory and an idempotent `.prosevoice/.gitignore` entry for `/cache/`, retaining custom ignore content. Set `artifacts.location` to `adjacent` for `<essay-stem>.<purpose>.md` sidecars next to the source. No automatic move or deletion of existing sidecars occurs when switching modes; use the new resolved paths and regenerate or explicitly migrate existing artifacts. For a multi-part review, select a primary source to key its pair's paths and record all parts in order.

Intermediate artifacts are disposable review/generation history, not export dependencies. Final visual assets and editable diagram sources remain with the essay. Links in cached sidecars must be relative to the sidecar directory; links in essay Markdown are relative to the essay.

## Bounded write authority

Reviews report findings; the caller applies changes within these limits:

- Automatically apply only an exact de-jargon table replacement that is grammatical in context. Meaning-level edits and ambiguous replacements are surfaced.
- **Preserve wins:** never silently change a VOICE-protected verdict, analogy or owned hedge, even in agent-authored prose. When uncertain, surface the finding.
- **Pre-surface DRAFT exception:** before showing prose authored or rewritten by an agent this turn, clean voice/readability violations only in those authored regions. Existing user prose and uncertain authorship remain report-only. An on-edit review never auto-cleans.
- Footnotes are additive: load-bearing claims get GFM markers and definitions under `## Notes`. Propose a batch for operator prose; current-turn agent prose may receive them automatically.
- Visual assets and their sidecars may be created when requested. Inserting an image, diagram or hidden visual anchor is additive, never a sentence rewrite; insertion into operator prose is proposed for confirmation. Follow AUDIENCE figure-text guidance when present, otherwise provide descriptive alt text and a useful caption when needed.
- Grammar auto-fix is limited to an unambiguous spelling typo in body prose: Harper `kind: Spelling`, exactly one suggestion, no dictionary or protected-pattern match, and an exact `matched_text` span match. All supplemental regions and other findings are report-only.
- `curmudgeon` and `steelman-response` write only their respective review sidecars. Other reviewers report findings; the caller may save them at resolved report paths. Keep these artifacts at the configured paths; this instruction does not authorize a git commit or publishing.

## Gates

| Stage | Work | Trigger |
| :-- | :-- | :-- |
| `idea` | No gate | Silent no-op |
| `draft` | Voice + readability → sources → grammar | Identified essay edit (report-only); before presenting agent-authored prose |
| `review` | Grammar + evidence/provenance; persuasive adds argument/reader checks and the premise-gated pair | Review request or edit at this stage |
| `ready` | Source and opted-in visual checks → full editorial pass → final export | Final-readiness/export request or edit at this stage |

Visual generation is optional and separate from gate execution. No hero, section image, visual sidecar, or explicit image-decline record is required for an essay with no planned visuals.

### DRAFT gate

Run `agents/voice-stylist.md` and `agents/readability-critic.md` in parallel. Give both the resolved references; focus voice review on Do/Don't, register, generative-cadence tells and protected patterns. Readability covers sentence length, beat density, choppiness and buried payoff. Then run `agents/footnoter.md`, then an inline Harper pass so newly added citations are checked.

On-edit footnoting is research-only: use supplied sources or an adjacent `research/` directory when present; do not make web calls for every edit. Explicit/pre-surface passes may search for credible sources. Never invent a citation; leave `[needs-source]` when a load-bearing factual claim cannot be supported. Follow the agent's write rules.

Use the grammar policy in `agents/grammar-check.md`. Run `pv policy <essay.md>` to merge bundled policy (`harper/`), user `dictionary.txt` and `ignore-rules.txt` in the user prosevoice directory, project `.prosevoice/` equivalents, and optional essay-local `.harper-words`. Both dictionary entries and ignore rules are additive unions. Use the returned `data.dictionary` path and comma-separated `data.ignore_rules` for every raw Harper pass; optional repeatable `--user-dict` / `--user-ignore` paths include policy stored elsewhere.

Use `pv lint <essay.md> --dialect <dialect>` for the read-only primary pass; it merges the same policy per essay and normalizes validated tool output. Honor VOICE dialect (default `us`). A `fixable` flag is only a candidate and does not authorize a write. A `harper-unavailable` diagnostic with `data.status: skipped` means Harper is absent. `pv extract <essay.md>` adds frontmatter, figure text and fenced prose that Harper may skip. Run tools inline for on-edit draft review; on explicit/pre-surface drafts, follow the tool pass with `agents/copy-editor.md` for agreement, punctuation, sentence boundaries and consistency. The copy-editor still reads when Harper is absent. It reports proposals and never broadens spelling auto-fix authority. Respect the matched-text guard and supplemental-region restrictions. Check Markdown validity after changes.

For edits, surface findings without rewriting. Before presenting agent-authored prose, apply only the scoped pre-surface cleanup and surface the rest. Report skipped checks accurately.

### REVIEW gate

Run a report-only Harper pass using the merged policy, then `agents/fact-checker.md` and `agents/provenance.md` in parallel for both intents. Fact-checker tests accuracy and citations; provenance tests claim origins, audience suitability of internal material, and whether the reader can trace or reproduce the evidence. Neither silently changes the essay or publishes anything.

For persuasive essays, also run `agents/red-team.md` and `agents/cold-read.md` in parallel, then the premise-gated pair below. Give the cold reader only the essay and target-reader persona, not the voice/register rules. Supply all parts in order for whole-argument checks. Surface conflicting recommendations without silently choosing one. Explanatory essays add these checks only when requested or warranted by a contested account.

### Optional visual aids

Use `agents/illustrator.md` when the user asks for visuals or agrees to a concrete proposal for visuals that improve explanation or persuasion. Identify the point each visual serves; avoid mandatory decoration, heroes, or one-image-per-section quotas. Existing authorization to create visuals is sufficient; do not ask repeatedly.

Choose the technology for the content: Mermaid for ordinary structural/sequence diagrams, Pikchr for precise technical drawings, native SVG or other diagram tools when suitable, and GPT-image, Nano Banana (`naba`) or another available image model for raster illustrations. Follow relevant tool skills and resolved `ILLUSTRATIONS.md` guidance. Preserve editable sources for diagrams and record raster prompts. Use supported rendered assets in exports, inspecting legibility and accuracy. Missing one tool calls for a suitable available alternative or a clear limitation, not a global skip of visual work.

For a proposed visual, use an alphanumeric `<!-- illus:<id> -->` anchor at the intended location and a matching `## illus:<id>` block at the resolved `illustrations` artifact path. Record purpose, tool, source/prompt, asset paths and `selected: unresolved`, a chosen asset id, or `selected: no-image`. Only planned visuals get anchors; existing untracked visuals may stay as they are. After approval, insert the selected asset with a relative path (or supported native diagram source), then record its selected id. Do not generate a fixed number of alternatives. Regenerate only requested visuals, retaining prior decisions. Remove obsolete anchors or resolve them as `no-image`.

### READY gate and final export

1. Run the mechanical checks on every essay part:

   ```bash
   pv ready <essay.md> [<part.md> ...]
   ```

   Exit 1 (`status: blocked`) means blocked; the diagnostics list each `visual-unresolved` and `needs-source` location. `data.limitations` states what the mechanical check does not establish; report it with the result. Only explicitly anchored visuals need resolved sidecar selections; unillustrated essays pass the visual check. No `[needs-source]` may remain without an explicit, reported user override. Resolve missing sources or qualify/remove the claim with approval.
2. Run voice-stylist, readability-critic, fact-checker, provenance, grammar-check, copy-editor and web-enabled footnoter for both intents. Persuasive essays add red-team and cold-read; explanatory essays add those when warranted or requested. Avoid concurrent writes: collect parallel findings, apply allowed changes serially, then run grammar and copy-editing against the resulting text. Re-run mechanical checks after source/visual changes. A clean script result alone does not prove factual accuracy or visual quality; inspect visuals, links, citations and their fit with the argument.
3. For persuasive essays (or an explicitly requested explanatory pressure-test), run or reuse the premise-gated pair. Resolve or surface remaining findings under the bounded write authority. Report unavailable checks and outstanding issues.
4. Once editorial work is settled, export only to the requested format using its appropriate tools. Verify the output as described in *Working format and essay selection*. Keep the Markdown and editable visual sources. No automatic social, newsletter, SEO or promotional sidecars; distribution is outside this skill.

### Premise-gated pair

Run `pv premise <essay.md> [<part.md> ...]` for the sources under review. Compare each part's `fingerprint` with `premise_fingerprint:` in the resolved `curmudgeon` and `steelman` artifact paths. Reuse only when both sidecars exist with matching fingerprints and the same reviewed essay-part set. For a multi-part essay, record each part's fingerprint in the review context; any changed part invalidates reuse. Missing/malformed fingerprints or an explicit request to rerun also invalidate reuse.

Otherwise run `agents/curmudgeon.md`, then `agents/steelman-response.md` with the counter-essay. The pair challenges the premise and offers recommendations; it never edits the essay. Distinguish persuasive claims from explanatory accounts so an explanation is not forced into advocacy. Pass both agents the status, ordered source paths, fingerprints and designated sidecar paths.
