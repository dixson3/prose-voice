# Prose Voice Protocol

Always-loaded trigger contract for `pv-prosevoice`: persuasive or explanatory narrative essays,
including but not limited to blog posts. Procedures and write authority live in its `SKILL.md`;
reference resolution, setup and rule installation live in `pv-preflight`.

**Required references:** `VOICE.md` and `AUDIENCE.md`, each resolved independently from
`<git-root>/.prose-voice/` then `~/.prose-voice/` (non-empty, no `pv-template: unfilled` marker).
Unresolved references make automatic triggers silent no-ops; an explicit request reports setup
needs. Optional `ILLUSTRATIONS.md` follows the same paths and guides visual work; absence does
not block the skill. Optional `.pv/config.json` adds ordered guidance file paths before the
standard project/global locations. Intermediate reviews and visual history default to gitignored
`.pv/cache/`; `artifacts.location: adjacent` places them beside the essay. Resolve paths with
`pv-preflight artifacts <essay.md> --apply` before writing. Keep final visual assets with the essay.

## Markdown source, final export

Always draft, review and revise in one Markdown file or an explicitly ordered set of Markdown
parts. Convert existing non-Markdown input to Markdown before editorial work, preserving the
original and reporting extraction losses. HTML, DOCX, PowerPoint, PDF and other outputs are
final exports after editorial review. Retain Markdown and editable visual sources; later changes
start there and regenerate the export. Inspect final output for content and rendering fidelity.

## Essay identification and gates

Use the user-selected essay paths; `ESSAY.md` / `ESSAY-<number>.md` are optional conventions.
Automatic edit triggers apply only to identified essay sources
or those conventional filenames, never arbitrary Markdown, review/visual sidecars, research,
instructions or exports. Intermediate paths come from preflight, never from a naming guess.

Use frontmatter `status:` or the explicitly requested gate. Missing status defaults to `draft`.
Optional `thesis:` records the main claim or explanation for premise checking.

- **`draft`**: voice, readability, sources and grammar; report-only on edits.
- **`review`**: argument, reader and evidence review, then premise-gated curmudgeon/steelman pair.
- **`ready`**: source flags and explicitly planned visual selections, full editorial pass, then
  the requested export. No automatic marketing or distribution artifacts.
- **`idea`**: silent no-op until the user asks to develop a draft.

## Pre-surface rule

Before presenting essay prose authored or rewritten this turn, run the DRAFT gate with fresh-eyes
review and clean agent-authored violations within the skill's bounded write authority. Preserve
VOICE-protected patterns; operator prose and uncertain authorship remain surface-only. Review all
parts of a multi-file essay in their intended order.

## Optional visuals

Generate visual aids only when requested or agreed, never as an on-edit side effect. Choose
appropriate diagram/drawing tools (such as Mermaid or Pikchr) or raster models (such as GPT-image
or Nano Banana), following resolved `ILLUSTRATIONS.md` and current user guidance. Preserve editable
sources/prompts and verify results. No hero, per-section image, or decline bookkeeping is required
for an unillustrated essay. Only explicitly anchored planned visuals require resolved selections.
