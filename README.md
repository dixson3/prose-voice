# prose-voice

[![skills.sh](https://skills.sh/b/dixson3/prose-voice)](https://skills.sh/dixson3/prose-voice)

Version: **[1.1.0](VERSION)**. The repository uses semantic versioning (`MAJOR.MINOR.PATCH`); `VERSION` is the version source of truth, and release tags use the form `v1.1.0`.

Write and review persuasive or explanatory essays with an AI agent while preserving the author's voice and addressing a defined reader. prose-voice coordinates checks for clarity, evidence, grammar, argument and reader experience. Optional visuals support the explanation, and final exports can be Markdown, HTML, PDF, a document or a slide deck.

You define the editorial direction in three guidance files: **`VOICE.md` describes how the author writes, `AUDIENCE.md` describes who they are writing for, and optional `ILLUSTRATIONS.md` describes how visuals should look.** The skill reads these guides before reviewing an essay; it does not assume a universal house style.

Drafts and revisions stay in Markdown, using one file or an explicitly ordered set of parts. Other formats are final exports. Blog posts are supported, but no publishing channel, filename or directory layout is required.

## What is included

| Component                    | Role                                                                                                                                                                                              |
| :--------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `prosevoice` skill           | Drafting and editorial review (voice, readability, sources, grammar, provenance, argument, reader experience and optional visuals), plus setup checks, guidance resolution and the companion rule. |
| `prosevoice` support package | The `pv` helper command the skill runs: configuration, guidance resolution, artifact paths, Harper policy, READY checks, the companion rule and legacy migration. It is stdlib-only Python.       |

These are instructions and a helper command for an AI coding agent, not a standalone writing application. The skill is packaged for installation through [`skills`](https://github.com/vercel-labs/skills), which supports Claude Code, pi, Codex, OpenCode and other agents. The installed skill carries its own helper; installing the Python package separately is optional.

Releases up to v1.1.0 shipped two skills, `pv-prosevoice` and `pv-preflight`, with guidance in `.prose-voice/` and `~/.prose-voice/`. The single `prosevoice` skill and the `.prosevoice/` layout replace them; the new skill does not read the old locations. See [Migrating from pv-prosevoice and pv-preflight](#migrating-from-pv-prosevoice-and-pv-preflight).

## Install and set up

### 1. Install the skill

The installer requires Node.js 22.20 or newer. The helper requires `uv` and `git`; `uv` provides the Python 3.11 or newer runtime. Install the skill at user scope so it is available across projects:

```bash
npx skills@latest add dixson3/prose-voice --skill prosevoice -g -y
```

`skills@latest` selects the latest installer, and the command installs from the repository's default branch, not the newest GitHub Release. To pin a release, use `dixson3/prose-voice@<tag>` with a tag that contains `skills/prosevoice`; v1.1.0 and earlier tags contain only the retired skills. Do not use `dixson3/prose-voice@latest`: that suffix is interpreted as a skill name, not a latest-release selector.

`-g` selects user scope and `-y` skips confirmation prompts. The installer selects agents based on context: ordinarily detected agents, or the current agent plus shared universal agents when run inside a recognized AI agent. Use `-a <agent>` to select an agent explicitly, or omit `-y` to allow interactive selection in an ordinary terminal. For project scope, omit `-g` and run the command from your writing repository.

The installer uses `.agents/skills/` as a shared location and creates harness-specific links where needed. Use `--copy` if you prefer copies to symlinks.

### 2. Set up guidance

Ask your agent to set up prosevoice, or invoke `/prosevoice` where the harness supports slash commands. Choose project or user scope for the guidance files. Skill installation scope and guidance scope are independent: a user-installed skill can use project-specific guidance.

For direct setup, define the helper command and run it from your writing repository:

```bash
# Recommended user-scope installation:
pv() { uv run --script "$HOME/.agents/skills/prosevoice/scripts/prosevoice.py" "$@"; }

# For a project-installed skill, use this instead:
# pv() { uv run --script "$(git rev-parse --show-toplevel)/.agents/skills/prosevoice/scripts/prosevoice.py" "$@"; }

pv init            # seed <project>/.prosevoice/ (never overwrites)
pv rule            # preview the companion rule
pv rule --apply    # install it
```

`pv init` creates missing `config.json`, `VOICE.md` and `AUDIENCE.md` files and never overwrites an existing file. Add `--illustrations` to also seed the optional `ILLUSTRATIONS.md`, and `--scope user` to seed the user prosevoice directory instead of the project (see [Configuration](#configuration)). In project scope it also adds the `/cache/` line to `.prosevoice/.gitignore`, retaining any other content. `rule` only previews its changes unless `--apply` is given.

Fill in both required files and remove their `pv-template: unfilled` comment. You can adapt the [filled examples](examples/) instead of starting from blank templates.

### 3. Check and start writing

```bash
pv check
```

The check reports required tools, resolved guides, companion-rule status and the setup actions still needed; it never writes. Empty files and files still marked `pv-template: unfilled` are not usable guidance. If a required guide is missing, an explicit skill request reports the setup needed; automatic edit checks quietly skip editorial work. Missing illustration guidance does not block review or visual work.

## Start an essay or request a review

Use `prosevoice` explicitly, or ask for essay writing or review in ordinary language. For example:

> Use prosevoice to draft an explanatory essay in `essays/shared-queues.md` about why shared work queues sometimes reduce delays. Use our guidance files, distinguish evidence from assumptions, and leave unsupported factual claims visible.

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

[Blank VOICE template](skills/prosevoice/templates/VOICE.md) · [Filled VOICE example](examples/VOICE.md)

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

[Blank AUDIENCE template](skills/prosevoice/templates/AUDIENCE.md) · [Filled AUDIENCE example](examples/AUDIENCE.md)

### `ILLUSTRATIONS.md`: how optional visuals should look

This optional guide supplies a visual brief: medium, palette, typography, composition, accessibility, aspect ratios and any tool preferences. Its **Style block** should stand alone as a usable brief; **Aspect** gives sizing preferences for visuals that are actually requested.

The illustrator combines that guidance with the point the visual needs to explain. A process may suit a diagram, a comparison may suit a chart, and a conceptual idea may suit a raster illustration. Tool choice follows the content and available capabilities; no image vendor is required.

The guide does not impose a cover image, a visual for every section or any image quota. Without it, the agent can still propose useful visuals using the user's instructions. `AUDIENCE.md` supplies reader-facing figure-text conventions; `ILLUSTRATIONS.md` supplies visual treatment. Final assets and editable sources stay with the essay.

[Blank ILLUSTRATIONS template](skills/prosevoice/templates/ILLUSTRATIONS.md) · [Filled ILLUSTRATIONS example](examples/ILLUSTRATIONS.md)

The filled examples are generic, vendor-neutral starting points without company or personal names. Adapt them to your own author and audience. They are not installed as active guidance automatically.

### Where guides are found

Each guide resolves independently, taking the first usable file:

1. Paths configured for that filename under `guidance` in the effective configuration, in order.
2. `<project>/.prosevoice/<filename>`.
3. `<user prosevoice directory>/<filename>`: `$XDG_CONFIG_HOME/prosevoice/` when `XDG_CONFIG_HOME` is set, otherwise `~/.config/prosevoice/`.

For example, you can keep a personal `VOICE.md` at user scope and a project-specific `AUDIENCE.md` in the writing repository. A project guide replaces the user guide for that file; their contents are not merged. The resolved contents are passed to reviewers so they use the same references.

Use `pv resolve` to inspect which files are selected and which paths were tried. For commands without an essay argument, such as `resolve`, `config`, `check` and `init`, the project is the directory given by `--project`, otherwise the nearest Git root of the current directory, otherwise the current directory. Essay commands select a project per essay, as described in *How editorial review works*.

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

## Configuration

A typical project uses one helper directory:

```text
.prosevoice/
  VOICE.md
  AUDIENCE.md
  ILLUSTRATIONS.md       optional
  config.json           optional project settings
  dictionary.txt        optional Harper vocabulary
  ignore-rules.txt      optional Harper rule exclusions
  .gitignore            ignores /cache/
  cache/                intermediate reviews and visual history
  migrations/           present only after `pv migrate --apply`
```

The user prosevoice directory, `$XDG_CONFIG_HOME/prosevoice/` or `~/.config/prosevoice/` when `XDG_CONFIG_HOME` is unset, can hold the same guides, `config.json`, `dictionary.txt` and `ignore-rules.txt`. `XDG_CONFIG_HOME` must be an absolute path when set; a relative value is an error.

### Configuration files

Configuration is strict JSON in two optional files, `<user prosevoice directory>/config.json` and `<project>/.prosevoice/config.json`:

```json
{
  "schema_version": 1,
  "guidance": {
    "VOICE.md": ["guides/voice.md"],
    "AUDIENCE.md": ["guides/readers.md", "~/shared/readers.md"],
    "ILLUSTRATIONS.md": []
  },
  "artifacts": { "location": "cache" }
}
```

| Key                  | Type                                         | Meaning                                                                                                          |
| :------------------- | :------------------------------------------- | :--------------------------------------------------------------------------------------------------------------- |
| `schema_version`     | integer, must be `1`                         | Format version.                                                                                                  |
| `guidance`           | object with keys `VOICE.md`, `AUDIENCE.md`, `ILLUSTRATIONS.md` only | Each value is an ordered list of non-empty path strings tried before the standard locations; `[]` clears configured candidates. |
| `artifacts.location` | `"cache"` (default) or `"adjacent"`          | Where intermediate review and visual-history files go.                                                           |

Unknown keys, unknown versions, duplicate keys, wrong types and malformed JSON are errors (exit 2). An invalid file is never skipped in favor of a lower tier.

Precedence is builtin < user < project < `--set`. Guidance merges by filename: the highest tier that sets a filename replaces that filename's whole list, and other filenames keep their own values. `artifacts.location` is taken from the highest tier that sets it. Override one value for a single invocation with repeatable `--set KEY=JSON`, where the key is `guidance.VOICE.md`, `guidance.AUDIENCE.md`, `guidance.ILLUSTRATIONS.md` or `artifacts.location`:

```bash
pv resolve --set 'guidance.VOICE.md=["docs/voice.md"]'
pv artifacts essays/queues.md --set 'artifacts.location="adjacent"'
```

Relative configured paths anchor to the directory of the tier that set them: the user prosevoice directory for the user file, the project root for the project file and the current directory for `--set`. A leading `~` is expanded. Absolute paths, including paths outside the project, are used as given.

`pv config` reports the effective values, the tier and source file of each value (`builtin`, `user`, `project` or `cli`), which configuration files were found, the selected project root and how it was chosen, and the resolved paths.

### Review files and the cache

Before an agent saves intermediate reports it resolves their paths:

```bash
pv artifacts path/to/essay.md                  # preview all 12 paths
pv artifacts path/to/essay.md --kind review    # one kind
pv artifacts path/to/essay.md --apply          # also create the directory and cache ignore rule
```

The kinds are `curmudgeon`, `steelman`, `illustrations`, `draft`, `review`, `ready`, `copyedit`, `provenance`, `fact-check`, `footnoter`, `red-team` and `cold-read`. In cache mode each path is `<project>/.prosevoice/cache/<essay-relative-directory>/<essay-stem>.<kind>.md`, so same-named essays in different directories do not collide, and the essay must be inside the selected project. In adjacent mode each path is `<essay-stem>.<kind>.md` beside the essay. `--apply` merges `/cache/` into `.prosevoice/.gitignore` without replacing existing rules. Guidance and policy files remain versionable.

Unless `--project` is given, essay commands (`artifacts`, `ready`, `policy` and `lint`) use each essay's own nearest Git root as its project, so essays in different repositories keep separate configuration and policy. An essay outside any Git repository uses its own directory as the project, so its cache is `.prosevoice/cache/<essay-stem>.<kind>.md` beside the essay wherever the command runs from; `--apply` creates that directory even if the essay's directory does not exist yet. With `--project`, every essay uses that project and must be inside it in cache mode. Relative `--set` guidance paths still anchor to the current directory.

Changing `artifacts.location` does not move existing files. On-edit findings are surfaced in chat; explicit and pre-surface reviews may save reports. Final visual assets and editable sources are kept with the essay, so exports do not depend on the disposable cache.

## Optional tools and grammar policy

| Capability                  | Availability and fallback                                                                                                                                                                                                   |
| :-------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Harper spelling and grammar | Uses `harper-cli` (for example, `brew install harper` on macOS). If absent, the Harper pass is reported as skipped; the copy-editor still runs where applicable.                                                            |
| Web search and retrieval    | Used for source discovery and verification when the agent has these tools. Without them, use supplied evidence and report unverified claims or `[needs-source]` gaps. Routine edit checks do not launch fresh web searches. |
| Visual tools                | Selected only when visuals are requested. Diagrams, charts and raster illustrations can use different tools; no provider is mandatory.                                                                                      |
| Export tools                | Depend on the requested format. Missing tools or rendering limitations are reported rather than claiming an unverified export.                                                                                              |

Harper combines the bundled policy in the skill's `harper/` directory with `dictionary.txt` and `ignore-rules.txt` from the user prosevoice directory, the corresponding project `.prosevoice/` files, and optional essay-local `.harper-words`. Unlike guidance-file resolution, **Harper policy is merged additively**: project entries do not remove user vocabulary or re-enable suppressed rules, and configuration precedence never removes a layer. Each essay gets its own merged policy, so essays in different projects do not share project vocabulary.

Dictionary files contain one word per line, preserving case. Ignore files contain one Harper rule name per line. Both support blank lines and full-line `#` comments; rule files also support trailing comments. Missing optional files are skipped; a present but unreadable file is an error. Policy additions require approval, and merging does not rewrite the inputs. Advanced callers can supply additional policy paths with the repeatable `--user-dict` and `--user-ignore` options of `pv policy` and `pv lint`.

## Activation reminder, updates and removal

`pv rule --apply` installs the short `PROSEVOICE-PROTOCOL.md` reminder next to each `prosevoice` installation it finds in the selected project and at user scope. It tells the agent when to load the skill; the full workflow remains in `SKILL.md`.

| Installation detected                       | Rule destination                                                                                                                                       |
| :------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Project or user `.claude/skills/prosevoice` | Corresponding `.claude/rules/PROSEVOICE-PROTOCOL.md`                                                                                                   |
| Project `.agents/skills/prosevoice`         | Managed block in the project's `AGENTS.md`                                                                                                             |
| User `.agents/skills/prosevoice`            | Managed blocks in existing pi, Codex and OpenCode harness configuration: `~/.pi/agent/AGENTS.md`, `~/.codex/AGENTS.md`, `~/.config/opencode/AGENTS.md` |
| User `.config/opencode/skills/prosevoice`   | Managed block in `~/.config/opencode/AGENTS.md`                                                                                                        |

Targets are deduplicated by path. The managed block runs from `<!-- BEGIN prosevoice (managed by prosevoice rule; edits are overwritten) -->` to `<!-- END prosevoice -->`; every byte outside it is preserved. If a target contains a malformed, nested or duplicate block, `rule` reports `blocked` and writes nothing. Missing or stale reminders produce a setup note but do not block an explicit editorial pass.

```bash
# Update the skill, then refresh the reminder:
npx skills update
pv rule --apply

# To uninstall, remove the reminder before removing the skill:
pv rule --remove --apply
npx skills remove prosevoice  # add -g for user scope
```

Rule commands operate on all detected installations in the current project and at user scope. If you remove only one installation scope, the removal command also clears reminders for any installation you retain. After removing the unwanted installation, run `pv rule --apply` from the writing repository with the retained skill's helper to restore its reminders.

## Migrating from pv-prosevoice and pv-preflight

The `prosevoice` skill does not read `.prose-voice/`, `~/.prose-voice/`, `PV-PROTOCOL.md` or `pv-protocol` blocks. `pv migrate` converts them on request; nothing migrates automatically. Install the new skill first, because migration replaces old reminders only where a `prosevoice` installation exists.

```bash
pv migrate --scope user              # preview: ~/.prose-voice -> user prosevoice directory, global reminders
pv migrate --scope user --apply
pv migrate                           # preview: <project>/.prose-voice -> <project>/.prosevoice, project reminders
pv migrate --apply
```

| Option                     | Meaning                                                                                                 |
| :------------------------- | :------------------------------------------------------------------------------------------------------ |
| `--scope project` (default) | Migrate the selected project (`--project PATH`, else the nearest Git root, else the current directory). Never writes the user directory or global reminders. |
| `--scope user`             | Migrate the legacy user directory and reminders under `$HOME`. Never writes project files.               |
| `--apply`                  | Perform the planned changes. Without it, migration validates everything and writes nothing, not even a manifest or directory. |
| `--legacy-user-dir PATH`   | Legacy user directory to read (default `~/.prose-voice`).                                               |
| `--user-dir PATH`          | `--scope user` only: destination directory (default the user prosevoice directory).                      |

Run user migration before project migration when a project relies on guides or Harper policy in `~/.prose-voice`. Project migration reads those legacy user files only for comparison; if the project still depends on them, it reports `blocked` with a `user-dependency-unmet` blocker and lists each missing file and its new location under `data.dependencies`.

What migration does:

- Validates the old `config.json` strictly and translates it to `schema_version: 1`, preserving guide candidate order and the artifact mode. Paths inside the old directory map to their new counterparts; guide paths outside it are kept as external references and reported, never copied or changed. Unknown configuration keys block.
- Copies filled guides, `dictionary.txt`, `ignore-rules.txt` and custom `.gitignore` content byte for byte, and keeps blank templates inert.
- Copies saved illustration decisions for essays with active visual anchors to their new cache paths and rebases their relative links. Other cached reports stay in the old cache for regeneration and are listed under `skipped`. Ambiguous or unsupported cases block with the exact paths.
- Leaves adjacent sidecars, essays, final assets and `.harper-words` unchanged.
- Recognizes only the released `PV-PROTOCOL.md` and `BLOG_VOICE.md` files and exact `pv-protocol` / `blog-voice` managed blocks at the supported reminder locations, and replaces them with the new reminder. Modified rule files and malformed, nested or duplicate markers block before anything is written. Unrelated `AGENTS.md` content is preserved byte for byte.
- Checks that the new configuration selects the same guide content, the same merged Harper policy, the same artifact mode and the same READY results before it activates the new reminders, which happens last.

`data.operation` is `would-change`, `applied`, `unchanged` or `blocked`. Blocked runs exit 1, invalid invocations exit 2, and a destination that already holds different content blocks with its path and expected and actual hashes. Rerunning a completed migration does nothing and creates no new backups.

`--apply` records its plan in `.prosevoice/migrations/<id>/manifest.json` (or `migrations/<id>/` in the user directory), with input, before and after hashes for every write, and keeps backups of replaced reminder files and `AGENTS.md` files in that directory's `backups/`. Migration does not add `migrations/` to `.gitignore`; keep it until you have checked the result, then commit or delete it as you prefer.

The original `.prose-voice/` data stays in place, unchanged and inactive. Remove it, and the old skills (`npx skills remove pv-prosevoice pv-preflight`, adding `-g` for user scope), yourself once you are satisfied; migration never edits installer locks or symlinks.

### Recovering from an interrupted or unwanted migration

- **Interrupted `--apply`:** rerun the same command. It resumes from the unfinished manifest, accepting files whose bytes already equal the recorded after hash and continuing files that still equal their recorded before state. If any file was edited in between, it reports `blocked` naming that file and the manifest; reconcile the file by hand, then rerun.
- **Undo a written file:** check that its current SHA-256 still equals the action's `after` hash in the manifest. If so, delete it when the action's `before` is `null`, or restore it from the backup listed for that action. A differing hash means the file changed after migration; reconcile it by hand.
- **Old data:** nothing needs restoring, because migration never modifies `.prose-voice/` or `~/.prose-voice/`.

Each report also includes these instructions under `data.recovery`, with the actual manifest path.

## Command reference

Every command prints one JSON object, `{schema_version: 1, command, status, data, diagnostics}`, where `status` is `ok`, `blocked` or `error` and each diagnostic has `code`, `message` and `paths`. Exit 0 means `ok`, 1 means evaluated blockers (unresolved guidance, READY failures, migration conflicts), and 2 means an invalid invocation, invalid configuration or an operational error. `--help` prints conventional text. Every command accepts `--project PATH` and repeatable `--set KEY=JSON`.

| Command                                                                                                   | Writes                                              | Purpose                                                                  |
| :-------------------------------------------------------------------------------------------------------- | :-------------------------------------------------- | :----------------------------------------------------------------------- |
| `pv version`                                                                                              | nothing                                             | Package version, Python version and resource location                   |
| `pv config`                                                                                               | nothing                                             | Effective configuration with per-value provenance                        |
| `pv check`                                                                                                | nothing                                             | Dependencies, resolved guidance, reminder state, setup actions           |
| `pv resolve`                                                                                              | nothing                                             | Resolved guides and every path tried                                     |
| `pv init [--scope project\|user] [--illustrations]`                                                       | missing config and blank guides, cache ignore rule  | Seed setup; never overwrites                                             |
| `pv artifacts <essay.md> [--kind KIND] [--apply]`                                                         | with `--apply`: artifact directory, cache ignore    | Intermediate artifact paths                                              |
| `pv rule [--remove] [--apply]`                                                                            | with `--apply`: reminder files and managed blocks   | Install or remove `PROSEVOICE-PROTOCOL.md`                               |
| `pv policy [<essay.md>] [--sidecar P] [--user-dict P]... [--user-ignore P]... [--bundled-dictionary P] [--bundled-ignore P] [--out P]` | merged dictionary (temporary unless `--out`) | Merged Harper dictionary and ignore rules for one essay                  |
| `pv lint <part.md>... [--dialect us\|uk\|au\|ca\|in] [--user-dict P]... [--user-ignore P]...`             | nothing                                             | Read-only Harper pass; parts in the order given                         |
| `pv extract <essay.md> [--out-md P]`                                                                      | snippet file (temporary unless `--out-md`)          | Reader-facing prose that Harper skips, with a map back to the source     |
| `pv premise <part.md>...`                                                                                 | nothing                                             | 16-character premise fingerprint per part                                |
| `pv ready <part.md>...`                                                                                   | nothing                                             | READY source-flag and active-anchor visual checks; parts in reading order |
| `pv migrate [--scope project\|user] [--apply] [--legacy-user-dir P] [--user-dir P]`                       | with `--apply`: new data, manifest, reminders       | Convert legacy prose-voice data on request                               |

A `harper-cli` that is not installed makes `lint` report `data.status: skipped` with a `harper-unavailable` diagnostic and exit 0. `ready` checks mechanically for unresolved `[needs-source]` markers in every part and for a selection or `selected: no-image` behind every active `<!-- illus:ID -->` anchor; `data.source` and `data.image` report each check, `data.ready` combines them, and `data.limitations` lists what the check does not establish. A clear result does not show that sources were reviewed or that the essay is correct.

### Python package

The skill runs its own copy of the helper through `uv`. To use the `prosevoice` console command instead, build and install the package from a checkout:

```bash
uv tool install /path/to/prose-voice    # provides `prosevoice`
prosevoice version
```

The wheel contains `prosevoice_lib` and the skill resources (`SKILL.md`, agents, companion rule, Harper policy and templates). It has no runtime dependencies.

## Repository reference

This README is the public guide. The [skill reference](skills/prosevoice/README.md) and [skill instructions](skills/prosevoice/SKILL.md) provide implementation details and exact operating rules.

```text
skills/prosevoice/        skill instructions, reviewer prompts, companion rule, templates and helper
  scripts/prosevoice.py   PEP 723 launcher for the helper
  scripts/prosevoice_lib/ helper package
examples/                 filled, generic guidance examples
tests/                    regression tests and the distribution check
pyproject.toml            Hatchling package definition
```

Run `uv run python -m unittest discover -s tests` for the regression suite and `uv run tests/check_distribution.py` to build and install the wheel and the skill in isolation.

Repository Markdown uses one source line per prose paragraph, with editor soft wrapping. Structural formatting and intentional hard breaks are preserved.

## License

MIT — see [LICENSE](LICENSE).
