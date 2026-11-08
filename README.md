# prose-voice

Agent skills for writing and reviewing persuasive or explanatory narrative essays: voice and
readability checks, claim sourcing, grammar, argument and reader-experience review, and optional
visual aids. Draft and revise in Markdown, then export to HTML, DOCX, PowerPoint, PDF or another
requested format as the final step. Blog posts are supported without assuming a publishing channel.
Installed with [`skills`](https://github.com/vercel-labs/skills) into Claude Code, pi,
Codex, opencode and any other agent that CLI supports.

The voice is not in this repo. The skills read `VOICE.md` and `AUDIENCE.md` from
`.prose-voice/` in the writing repo, falling back per file to `~/.prose-voice/`.

## Skills

| Skill | Purpose |
| :-- | :-- |
| `pv-prosevoice` | The editorial pipeline: DRAFT / REVIEW / READY stage gates, agents, helper scripts. |
| `pv-preflight` | Called by `pv-prosevoice` before every gate. Checks dependencies, resolves the voice files, seeds blank templates, and installs the always-loaded `PV-PROTOCOL.md` rule. |

## Layout

```text
skills/pv-prosevoice/      the pipeline
  SKILL.md                 router, stage gates, write authority
  agents/                  one prompt per editorial step
  harper/                  Harper dictionary + suppressed rules
  scripts/                 uv-run helpers (stdlib only)
skills/pv-preflight/       setup and checks
  SKILL.md
  PV-PROTOCOL.md           always-loaded companion rule (triggers + pre-surface rule)
  scripts/preflight.py     check | resolve | seed | artifacts | rule
  scripts/pv_config.py     shared guidance and intermediate-path configuration
  templates/               blank VOICE.md, AUDIENCE.md
```

## Install

Requires Node.js 22.20+ for `npx skills`. Install both skills together.

```bash
# Project scope (run from the writing repo)
npx skills add dixson3/prose-voice -s pv-prosevoice -s pv-preflight -a claude-code -a pi -a codex -a opencode

# User scope
npx skills add dixson3/prose-voice -s pv-prosevoice -s pv-preflight -g -a claude-code -a pi -a codex -a opencode
```

`skills` writes one canonical copy under `.agents/skills/` and symlinks it into the other agents'
skill directories. Use `--copy` if symlinks are not wanted. Update with `npx skills update`.

Then set up, from the writing repo, either by invoking `/pv-preflight` in an agent or directly:

```bash
PF="uv run .agents/skills/pv-preflight/scripts/preflight.py"   # ~/.agents/... at user scope
$PF check                                  # report deps, voice files, rule state
$PF seed --scope project --apply           # .prose-voice/{VOICE,AUDIENCE}.md (or --scope global)
$PF rule --apply                           # install PV-PROTOCOL.md where pv-prosevoice is installed
```

`seed` and `rule` are dry runs without `--apply`. Fill in both voice files and delete each
file's `pv-template: unfilled` line; until then the skill is a silent no-op.

### Where the rule goes

| `pv-prosevoice` found at | `PV-PROTOCOL.md` installed to |
| :-- | :-- |
| `.claude/skills/` (project or `~`) | `.claude/rules/PV-PROTOCOL.md` |
| `<root>/.agents/skills/` | managed block in `<root>/AGENTS.md` |
| `~/.agents/skills/` | managed block in `~/.pi/agent/AGENTS.md` and `~/.codex/AGENTS.md` (each only if that harness is present) |
| `~/.config/opencode/skills/` | managed block in `~/.config/opencode/AGENTS.md` |

`rule --apply` also removes rule files and `AGENTS.md` blocks left by the old `blog-voice`
`install.sh`.

### Uninstall

```bash
$PF rule --remove --apply
npx skills remove pv-prosevoice pv-preflight      # add -g for user scope
```

## Voice files

Resolved per file, first usable match wins: `<git-root>/.prose-voice/<file>` →
`~/.prose-voice/<file>`. A project can override one file and inherit the other. The image
alt/title convention is the `## Figure text` section in `AUDIENCE.md`.

Optional `ILLUSTRATIONS.md` resolves through the same project/global paths. Supply it when you
want consistent visual style, tool preferences, palette, typography or aspect ratios. It is not
required or seeded by setup; missing guidance never blocks prose review or useful visual work.
Visuals are chosen for the explanation: Mermaid diagrams, Pikchr drawings, evidence-based charts,
or raster illustrations from GPT-image, Nano Banana or another available tool. Preserve editable
sources/prompts and inspect results. Unillustrated essays need no visual-selection bookkeeping.

## Project configuration

Optional `.pv/config.json` adds guidance locations and selects where intermediate files go:

```json
{
  "guidance": {
    "AUDIENCE.md": ["guides/readers.md"],
    "ILLUSTRATIONS.md": ["guides/visuals.md"]
  },
  "artifacts": {"location": "cache"}
}
```

Configured paths are tried in order before the usual project/global `.prose-voice/` locations.
Relative paths are relative to the git root; absolute and `~` paths also work. Each reference
falls back independently. External tools can seed this configuration without coupling the skill
to their directory layout. See [preflight configuration](skills/pv-preflight/SKILL.md#project-configuration-and-intermediate-files).

Intermediate `*.curmudgeon.md`, `*.steelman.md` and `*.illustrations.md` default to
`.pv/cache/<essay-relative-directory>/`. Preflight prepares this location and adds `/cache/` to
`.pv/.gitignore`. Set `artifacts.location` to `adjacent` to place them beside the essay instead.
Switching modes does not move existing files. Final visual assets and editable diagram sources
stay with the essay so exports do not depend on disposable cache contents.

```bash
$PF artifacts path/to/essay.md          # preview paths
$PF artifacts path/to/essay.md --apply  # prepare directory and cache ignore rule
```

## Harper dictionaries and ignored rules

Project `.pv/dictionary.txt` and `.pv/ignore-rules.txt` are merged with user-scoped
`~/.pv/dictionary.txt` and `~/.pv/ignore-rules.txt`, bundled policy, and optional essay-local
`.harper-words`. All layers are additive unions; project files do not replace user policy.
Only `.pv/cache/` is ignored, so project policy files can be versioned.

Dictionary files contain one word per line (case preserved). Rule files contain one Harper rule
name per line. Both ignore blank lines and full-line `#` comments; rule files also allow trailing
comments. Missing optional files are fine. No existing policy file is rewritten by the merge.

The grammar agent uses `build_user_dict.py --cwd <essay-dir> --json` to obtain both the merged
dictionary and ignored rules. Repeatable `--user-dict <path>` / `--user-ignore <path>` options
include user policy stored elsewhere. Additions require approval at the appropriate scope.

## Requirements

- `uv` and `git` — required.
- `harper-cli` (`brew install harper`) — grammar step; absent, it is skipped.
- Visual and export tools — selected for the requested content and final format; no mandatory image provider.
- Web search/fetch tools — footnoter gap-filling; absent, claims are flagged `[needs-source]`.

## Essay workflow

Use one Markdown source or an explicitly ordered set of Markdown parts, with any filenames.
`ESSAY.md` / `ESSAY-<n>.md` remain supported conventions; no particular directory layout is required.
Existing non-Markdown inputs are converted to Markdown before editorial work. The frontmatter
`status:` can be `idea`, `draft`, `review` or `ready`; missing status defaults to draft, and an
explicit review/export request selects the appropriate gate. Optional `thesis:` states the
main claim or explanation.

DRAFT checks voice, readability, sourcing and grammar, with a copy-editing pass for explicit and
pre-surface drafts. REVIEW checks evidence and provenance for both intents; persuasive essays
also receive argument/reader checks and the adversarial pair. Explanatory essays add those when
warranted or requested. READY runs the full applicable pass and checks source gaps and planned visuals.
Then export the settled Markdown to the requested format and verify the result. Keep Markdown
and visual sources for later revisions. No automatic social, newsletter or SEO artifacts are
part of this workflow. See [the pipeline guide](skills/pv-prosevoice/README.md) and
[skill instructions](skills/pv-prosevoice/SKILL.md).

## License

MIT — see [LICENSE](LICENSE).
