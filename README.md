# prose-voice

[![skills.sh](https://skills.sh/b/dixson3/prose-voice)](https://skills.sh/dixson3/prose-voice)

Version: **[1.1.0](VERSION)**. The repository uses semantic versioning (`MAJOR.MINOR.PATCH`); `VERSION` is the version source of truth, and release tags use the form `v1.1.0`.

Write and review persuasive or explanatory essays with an AI agent while preserving the author's voice and addressing a defined reader. prose-voice coordinates checks for clarity, evidence, grammar, argument and reader experience. Optional visuals support the explanation, and final exports can be Markdown, HTML, PDF, a document or a slide deck.

You define the editorial direction in three guidance files: **`VOICE.md` describes how the author writes, `AUDIENCE.md` describes who they are writing for, and optional `ILLUSTRATIONS.md` describes how visuals should look.** The skills read these guides before reviewing an essay; they do not assume a universal house style.

Drafts and revisions stay in Markdown, using one file or an explicitly ordered set of parts. Other formats are final exports. Blog posts are supported, but no publishing channel, filename or directory layout is required.

## What is included

Install both skills together:

| Skill           | Role                                                                                                                                                    |
| :-------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `pv-prosevoice` | Drafting and editorial review: voice, readability, sources, grammar, provenance, argument, reader experience and optional visuals.                      |
| `pv-preflight`  | Setup and checks: finds guidance, checks tool availability, seeds templates, resolves review-file locations and installs the small activation reminder. |

These are instructions and helper scripts for an AI coding agent, not a standalone writing application. They are packaged for installation through [`skills`](https://github.com/vercel-labs/skills), which supports Claude Code, pi, Codex, OpenCode and other agents.

## Install and set up

### 1. Install the skills

The installer requires Node.js 22.20 or newer. The helpers require `uv` and `git`. Install all prose-voice skills at user scope so they are available across projects:

```bash
# Recommended: current version from the repository's default branch
npx skills@latest add dixson3/prose-voice --skill '*' -g -y

# Alternatively: install the tagged v1.1.0 release
npx skills@latest add dixson3/prose-voice@v1.1.0 --skill '*' -g -y
```

`skills@latest` selects the latest installer. The first command installs from the repository's default branch, not the newest GitHub Release; the second selects the specific Git tag. Do not use `dixson3/prose-voice@latest`: that suffix is interpreted as a skill name, not a latest-release selector.

The quoted `--skill '*'` selects every skill in this repository, currently `pv-prosevoice` and `pv-preflight`. Keep the quotes so your shell passes the wildcard to the installer. `-g` selects user scope and `-y` skips confirmation prompts. The installer selects agents based on context: ordinarily detected agents, or the current agent plus shared universal agents when run inside a recognized AI agent. Use `-a <agent>` to select an agent explicitly, or omit `-y` to allow interactive selection in an ordinary terminal.

For project scope, omit `-g` and run the command from your writing repository.

The installer uses `.agents/skills/` as a shared location and creates harness-specific links where needed. Use `--copy` if you prefer copies to symlinks.

### 2. Set up guidance

Ask your agent to run `pv-preflight`, or invoke `/pv-preflight` where the harness supports slash commands. Choose project or user scope for the guidance files. Skill installation scope and guidance scope are independent: a user-installed skill can use project-specific guidance.

For direct setup, run these commands from your writing repository:

```bash
# Use this path for the recommended user-scope installation:
PF="$HOME/.agents/skills/pv-preflight/scripts/preflight.py"

# For project-installed skills, use this instead:
# PF=".agents/skills/pv-preflight/scripts/preflight.py"

uv run "$PF" seed --scope project --apply
uv run "$PF" rule --apply
```

Use `--scope global` with `seed` to create guidance in `~/.prose-voice/`. Without `--apply`, `seed` and `rule` preview their changes. Seeding never overwrites an existing guide and creates only the required `VOICE.md` and `AUDIENCE.md` templates.

Fill in both files and remove their `pv-template: unfilled` comment. You can adapt the [filled examples](examples/) instead of starting from blank templates. Illustration guidance is optional; copy the [ILLUSTRATIONS template](skills/pv-preflight/templates/ILLUSTRATIONS.md) into the same guidance directory when you want it, without overwriting an existing guide.

### 3. Check and start writing

```bash
uv run "$PF" check
```

The check reports required tools, resolved guides and companion-rule status. Empty files and files still marked `pv-template: unfilled` are not usable guidance. If a required guide is missing, an explicit skill request reports the setup needed; automatic edit checks quietly skip editorial work. Missing illustration guidance does not block review or visual work.

## Start an essay or request a review

Use `pv-prosevoice` explicitly, or ask for essay writing or review in ordinary language. For example:

> Use pv-prosevoice to draft an explanatory essay in `essays/shared-queues.md` about why shared work queues sometimes reduce delays. Use our guidance files, distinguish evidence from assumptions, and leave unsupported factual claims visible.

> Review `essays/shared-queues.md` for clarity and evidence. Treat it as an explanation rather than a persuasive argument. Report proposed changes before rewriting my prose.

> Review `opening.md`, `mechanism.md` and `conclusion.md` as one essay, in that order. Check for repetition and gaps between the parts.

> Prepare this essay for a final PDF. Complete the readiness checks, report unresolved issues, then export when they are resolved or explicitly accepted.

When useful, add a request such as “Propose a diagram of the process using our illustration guidance.” Visuals are created only when requested or agreed, not as an automatic consequence of editing an essay.

The skill description and a small companion rule remind the agent to invoke review after edits to an identified essay and before presenting prose it authored or rewrote. These are agent instructions, not a filesystem watcher or an enforced save hook. Explicit invocation is useful when you want to ensure the agent loads the workflow. Unrelated notes, code, review reports and exports are outside automatic essay review.

## The guidance files

### `VOICE.md`: how the author writes

This required guide defines the author's voice and editorial preferences. It is used during drafting and by the voice and readability reviewers. Record concrete rules and examples rather than adjectives alone: “state the condition alongside the claim” gives a reviewer more direction than “be thoughtful.”

| Section                                      | How it is used                                                                                              |
| :------------------------------------------- | :---------------------------------------------------------------------------------------------------------- |
| How the author argues / patterns to preserve | Identifies distinctive moves, verdicts, analogies and qualifications that must not be silently edited away. |
| Register / mechanics                         | Sets tone, person, tense, punctuation and other prose conventions.                                          |
| Readability                                  | Guides checks for sentence length, clause density, paragraph focus and placement of the main point.         |
| Do / Don't                                   | Supplies concrete preferences for drafting and review.                                                      |
| Generative-cadence tells                     | Identifies repetitive or formulaic constructions the author wants flagged.                                  |
| Forms, optional                              | Adapts the voice to requested forms, such as slide titles and speaker notes.                                |

Protected voice patterns take precedence over routine cleanup. A reviewer may raise a concern about one, but must not silently replace it. Keep visual style in `ILLUSTRATIONS.md`, rather than mixing it into prose guidance.

[Blank VOICE template](skills/pv-preflight/templates/VOICE.md) · [Filled VOICE example](examples/VOICE.md)

### `AUDIENCE.md`: who the essay is for

This required guide describes the actual reader: what they already understand, what needs explanation, why they are reading and what they should be able to understand or decide afterwards. It shapes terminology, context, examples and the amount of detail the essay needs.

| Section               | How it is used                                                                                                                                   |
| :-------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------- |
| The reader            | Supplies the target persona. The cold-read reviewer encounters the essay as this reader, without the author's voice instructions.                |
| Register              | Describes the tone and assumed background appropriate for that reader.                                                                           |
| Loosen for the reader | Guides how much to unpack, when to define terms and when to add examples.                                                                        |
| De-jargon table       | Provides specific replacements. Automatic replacement is allowed only for an exact match that remains grammatical and preserves protected voice. |
| Figure text           | Defines accessible alt text, captions and title conventions.                                                                                     |

For example, a voice guide might favor direct, compact prose while an audience guide asks for an unfamiliar process to be explained step by step. The result should retain that voice while supplying the missing context. The two guides address different questions and are used together.

An essay's optional frontmatter `audience:` can override the reader persona for that essay. It does not replace the rest of `AUDIENCE.md` or remove the requirement for the guide.

[Blank AUDIENCE template](skills/pv-preflight/templates/AUDIENCE.md) · [Filled AUDIENCE example](examples/AUDIENCE.md)

### `ILLUSTRATIONS.md`: how optional visuals should look

This optional guide supplies a visual brief: medium, palette, typography, composition, accessibility, aspect ratios and any tool preferences. Its **Style block** should stand alone as a usable brief; **Aspect** gives sizing preferences for visuals that are actually requested.

The illustrator combines that guidance with the point the visual needs to explain. A process may suit a diagram, a comparison may suit a chart, and a conceptual idea may suit a raster illustration. Tool choice follows the content and available capabilities; no image vendor is required.

The guide does not impose a cover image, a visual for every section or any image quota. Without it, the agent can still propose useful visuals using the user's instructions. `AUDIENCE.md` supplies reader-facing figure-text conventions; `ILLUSTRATIONS.md` supplies visual treatment. Final assets and editable sources stay with the essay.

[Blank ILLUSTRATIONS template](skills/pv-preflight/templates/ILLUSTRATIONS.md) · [Filled ILLUSTRATIONS example](examples/ILLUSTRATIONS.md)

The filled examples are generic, vendor-neutral starting points without company or personal names. Adapt them to your own author and audience. They are not installed as active guidance automatically.

### Where guides are found

Each guide resolves independently, taking the first usable file:

1. Additional paths configured for that filename in the project's `.prose-voice/config.json`.
2. `<git-root>/.prose-voice/<filename>`.
3. `~/.prose-voice/<filename>`.

For example, you can keep a personal `VOICE.md` at user scope and a project-specific `AUDIENCE.md` in the writing repository. A project guide replaces the user guide for that file; their contents are not merged. The resolved contents are passed to reviewers so they use the same references.

Use `uv run "$PF" resolve` to inspect which files are selected. The project directory is the Git root, not necessarily the directory containing the essay. Configuration paths are described below.

## How editorial review works

The workflow separates developing prose, examining its claims and preparing a final deliverable. A stage selects the applicable checks; it is not a guarantee that the essay is correct or ready to publish.

| Stage    | Main work                                                                                                                                                      |
| :------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `idea`   | No automatic editorial pass until you ask to develop the idea.                                                                                                 |
| `draft`  | Voice and readability, source gaps and grammar. Explicit drafting and review before presenting agent-authored prose also include a copy-editor pass.           |
| `review` | Evidence, source accuracy, provenance and grammar. Persuasive essays also receive argument and reader-experience checks plus a premise challenge and response. |
| `ready`  | Source-gap and planned-visual checks, the full applicable editorial review, then the requested final export after issues are resolved or accepted.             |

You can select a stage in your request or use optional frontmatter. Missing `status:` defaults to `draft`; an explicit review or readiness request selects the corresponding stage.

```yaml
---
status: draft
intent: explanatory
thesis: Clear ownership matters more than the choice of queue.
audience: Team members evaluating how to handle incoming requests.
---
```

**Intent determines the depth of argument review.** Persuasive essays aim to change a belief or support a decision. Explanatory essays aim to make an account or process understandable; `informational` is also accepted as an intent value. Your explicit intent takes precedence over frontmatter. If neither the request nor frontmatter specifies intent, the agent infers it from the narrative and reports the choice. A `thesis:` field alone does not make an essay persuasive.

Argument review includes a red-team pass for weaknesses, a cold read from the target reader's perspective, and a curmudgeon/steelman pair that challenges the premise and develops a response. Explanatory essays add these checks when requested or when a contested explanation warrants them. The premise pair may reuse prior reports when the relevant fingerprints and reviewed parts still match.

Fact-checking asks whether claims and citations are accurate. Provenance review asks where claims came from, whether the reader can trace the evidence, and whether actual internal material is suitable for the intended audience. The agent reports unavailable checks and unresolved findings rather than treating them as passes. Unsupported claims remain marked `[needs-source]`; readiness requires resolving them or an explicit, reported user override. A script passing does not establish factual accuracy.

### What the agent may change

Review findings generally remain proposals. Routine exceptions are narrowly defined: exact, grammatical de-jargon substitutions and guarded, unambiguous spelling corrections in body prose. Meaning-level changes, protected voice patterns and uncertain cases are surfaced for a decision.

Before presenting prose it authored or rewrote during the current turn, the agent may clean voice and readability violations within those authored regions and add supporting footnotes. Existing user prose and uncertain authorship do not receive that cleanup automatically. On-edit review reports findings without automatically cleaning the essay. Citation and visual insertions into user prose are proposed for confirmation.

The workflow does not authorize committing, publishing or distributing an essay. It does not automatically generate social posts, newsletters or promotional material.

### Markdown and final exports

Use any Markdown filenames, or provide an explicit reading order for multiple files. Existing non-Markdown inputs are converted to Markdown before editorial work, preserving the original and reporting extraction limitations. For a presentation, settle the narrative and slide sequence in Markdown first.

After readiness review, export only to the requested format using an appropriate available tool. Check the result for completeness, reading order, citations, links, visuals and layout. Retain Markdown and editable visual sources; later revisions start there and regenerate the export. If Markdown is the deliverable, no conversion is needed.

## Configuration and review files

A typical project uses one helper directory:

```text
.prose-voice/
  VOICE.md
  AUDIENCE.md
  ILLUSTRATIONS.md       optional
  config.json           optional project settings
  dictionary.txt        optional Harper vocabulary
  ignore-rules.txt      optional Harper rule exclusions
  .gitignore            ignores /cache/
  cache/                intermediate reviews and visual history
```

Optional project configuration can add guide locations and choose where intermediate files go:

```json
{
  "guidance": {
    "AUDIENCE.md": ["guides/readers.md"],
    "ILLUSTRATIONS.md": ["guides/visuals.md"]
  },
  "artifacts": { "location": "cache" }
}
```

Configured paths are tried in order before the standard locations. Relative paths resolve from the Git root; absolute paths and `~` are supported. Invalid configuration is reported as an error. The configuration file itself is project-scoped; user-scoped guidance and Harper policy do not require one.

Review reports and visual iteration history default to `.prose-voice/cache/<essay-relative-directory>/`. Preflight creates the cache ignore rule without replacing existing rules. Guidance and policy files remain versionable. Outside a Git repository, the cache is placed in `.prose-voice/cache/` beside the essay.

```bash
uv run "$PF" artifacts path/to/essay.md          # preview paths
uv run "$PF" artifacts path/to/essay.md --apply  # prepare directories and cache ignore rule
```

Set `artifacts.location` to `adjacent` to put intermediate files beside the essay instead. Changing this setting does not move existing files. On-edit findings are surfaced in chat; explicit and pre-surface reviews may save reports. Final visual assets and editable sources are kept with the essay, so exports do not depend on the disposable cache.

## Optional tools and grammar policy

| Capability                  | Availability and fallback                                                                                                                                                                                                   |
| :-------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Harper spelling and grammar | Uses `harper-cli` (for example, `brew install harper` on macOS). If absent, the Harper pass is reported as skipped; the copy-editor still runs where applicable.                                                            |
| Web search and retrieval    | Used for source discovery and verification when the agent has these tools. Without them, use supplied evidence and report unverified claims or `[needs-source]` gaps. Routine edit checks do not launch fresh web searches. |
| Visual tools                | Selected only when visuals are requested. Diagrams, charts and raster illustrations can use different tools; no provider is mandatory.                                                                                      |
| Export tools                | Depend on the requested format. Missing tools or rendering limitations are reported rather than claiming an unverified export.                                                                                              |

Harper combines bundled policy with user files at `~/.prose-voice/dictionary.txt` and `~/.prose-voice/ignore-rules.txt`, the corresponding project files, and optional essay-local `.harper-words`. Unlike guidance-file resolution, **Harper policy is merged additively**: project entries do not remove user vocabulary or re-enable suppressed rules.

Dictionary files contain one word per line, preserving case. Ignore files contain one Harper rule name per line. Both support blank lines and full-line `#` comments; rule files also support trailing comments. Policy additions require approval, and merging does not rewrite the inputs. Advanced callers can supply additional policy paths through the helpers' repeatable `--user-dict` and `--user-ignore` options.

## Activation reminder, updates and removal

`pv-preflight rule --apply` installs the short `PV-PROTOCOL.md` reminder. It tells the agent when to load the skill; the full workflow remains in `SKILL.md`.

| Installation detected                          | Rule destination                                                                                                                                       |
| :--------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Project or user `.claude/skills/pv-prosevoice` | Corresponding `.claude/rules/PV-PROTOCOL.md`                                                                                                           |
| Project `.agents/skills/pv-prosevoice`         | Managed block in the project's `AGENTS.md`                                                                                                             |
| User `.agents/skills/pv-prosevoice`            | Managed blocks in existing pi, Codex and OpenCode harness configuration: `~/.pi/agent/AGENTS.md`, `~/.codex/AGENTS.md`, `~/.config/opencode/AGENTS.md` |
| User `.config/opencode/skills/pv-prosevoice`   | Managed block in `~/.config/opencode/AGENTS.md`                                                                                                        |

Missing or stale reminders produce a setup note but do not block an explicit editorial pass.

```bash
# Update skills, then refresh the reminder:
npx skills update
uv run "$PF" rule --apply

# To uninstall, remove the reminder before removing the skills:
uv run "$PF" rule --remove --apply
npx skills remove pv-prosevoice pv-preflight  # add -g for user scope
```

Rule commands operate on all detected installations in the current project and at user scope. If you remove only one installation scope, the removal command also clears reminders for any detected installation you retain. After removing the unwanted skills, point `PF` at the retained preflight helper and run `uv run "$PF" rule --apply` from the writing repository to restore its reminders.

## Repository reference

This README is the public guide. The [pipeline reference](skills/pv-prosevoice/README.md), [editorial skill instructions](skills/pv-prosevoice/SKILL.md) and [preflight instructions](skills/pv-preflight/SKILL.md) provide implementation details and exact operating rules.

```text
skills/pv-prosevoice/     editorial instructions, reviewer prompts and helpers
skills/pv-preflight/      setup helper, companion rule and blank templates
examples/                filled, generic guidance examples
tests/                   helper regression tests
```

Repository Markdown uses one source line per prose paragraph, with editor soft wrapping. Structural formatting and intentional hard breaks are preserved.

## License

MIT — see [LICENSE](LICENSE).
