# prosevoice

Write and review persuasive or explanatory narrative essays in a consistent voice. Work in one Markdown file or an ordered set of Markdown parts, then export to the requested format only after editorial review. Blog posts are supported, but no publishing channel, filename or directory layout is required. See [SKILL.md](SKILL.md) for routing, write authority and export checks, and the [repository README](../../README.md) for installation, configuration and migration.

The skill's helper command, `pv` (`scripts/prosevoice.py`), resolves required `VOICE.md` and `AUDIENCE.md`, plus optional `ILLUSTRATIONS.md`, independently from configured paths, project `.prosevoice/`, then the user prosevoice directory (`$XDG_CONFIG_HOME/prosevoice/`, else `~/.config/prosevoice/`). It also checks dependencies, seeds blank templates and installs `PROSEVOICE-PROTOCOL.md`. Optional strict `config.json` files at user and project scope configure extra guidance locations and intermediate-file placement. Reviews and visual history default to gitignored `.prosevoice/cache/` in the essay's project: `--project`, else the essay's nearest Git root, else the essay's own directory (commands without an essay use `--project`, else the invocation directory's Git root, else the invocation directory); `artifacts.location: adjacent` keeps them beside the essay. The helper resolves paths for agents. Final assets stay with the essay.

## Gates

- **DRAFT:** voice and readability, then load-bearing claim sourcing and grammar. Report-only on edits; bounded cleanup of agent-authored regions before presenting a draft. Explicit and pre-surface drafts also receive a copy-editing pass that works without Harper.
- **REVIEW:** grammar, evidence and provenance for both intents. Persuasive essays also get argument/reader checks and the premise-gated curmudgeon/steelman pair; explanatory essays add those when warranted or requested. Explanations are not forced into advocacy.
- **READY:** resolve source flags and explicitly planned visual selections, run the full review, then perform and verify the requested final export. Plain essays need no visual sidecar, hero, section images or decline records.
- **IDEA:** no gate until the user asks to develop a draft.

Visual aids are optional and purposeful. The illustrator selects appropriate diagram, drawing, chart or image technology, follows `ILLUSTRATIONS.md` when supplied, retains editable sources or prompts, and inspects the result. Generation is requested/agreed work, never an on-edit trigger.

Use `/prosevoice` for an identified essay or set of parts. Unrelated Markdown, research, instructions, generated review sidecars and exported files do not trigger essay review. Existing non-Markdown input is converted to Markdown before editing; Markdown remains the revision source.

## Layout

```text
SKILL.md                         workflow, gates, reference resolution, write authority
README.md                        this guide
PROSEVOICE-PROTOCOL.md           always-loaded companion rule installed by `pv rule`
agents/
  voice-stylist.md               voice and register
  fact-checker.md                claims and references
  readability-critic.md          mechanical readability
  red-team.md                    argument and explanatory structure
  cold-read.md                   target-reader experience
  grammar-check.md               Harper spelling and grammar
  copy-editor.md                 agreement, punctuation and consistency
  provenance.md                  claim origins and traceability
  footnoter.md                   load-bearing claim sourcing
  illustrator.md                 optional visuals using appropriate tools
  curmudgeon.md                  premise critique sidecar
  steelman-response.md           adjudication and recommendations sidecar
harper/
  dictionary.txt                 shared custom words
  ignore-rules.txt               house-style rule suppressions
templates/
  VOICE.md, AUDIENCE.md          blank required guides seeded by `pv init`
  ILLUSTRATIONS.md               blank optional guide (`pv init --illustrations`)
scripts/
  prosevoice.py                  PEP 723 launcher; `pv` in SKILL.md
  prosevoice_lib/
    cli.py                       argument parsing and the JSON envelope
    config.py                    strict layered config, project selection, guidance, artifact paths, init
    rules.py                     `check`, companion-rule targets and the managed-block parser
    policy.py                    Harper policy union (`policy`) and read-only lint (`lint`)
    essay.py                     `extract`, `premise` and `ready`
    migration.py                 `migrate`; the only module that reads legacy prose-voice data
    errors.py                    error and diagnostic types
```

The former helper scripts map to commands as follows: `preflight.py check|resolve|seed|rule|artifacts` → `pv check`, `pv resolve`, `pv init`, `pv rule`, `pv artifacts`; `build_user_dict.py` → `pv policy`; `harper_lint.py` → `pv lint`; `extract_prose.py` → `pv extract`; `premise_fingerprint.py` → `pv premise`; `ready_preconditions.py` → `pv ready`. There are no aliases for the old names. Every command prints one JSON envelope and exits 0 (ok), 1 (blocked) or 2 (error); READY blocked was previously exit 3, and a missing `harper-cli` previously exited 4 and is now `data.status: skipped` with exit 0. `--cwd` is replaced by `--project`, and the policy options `--global`/`--ignore` are now `--bundled-dictionary`/`--bundled-ignore`.

Resources are found through `prosevoice_lib.skill_root()`: the packaged `_skill/` directory in an installed wheel, otherwise this source tree. The current directory is never used.

## Harper grammar policy

`grammar-check` uses `harper/dictionary.txt` and `harper/ignore-rules.txt`, plus `dictionary.txt` and `ignore-rules.txt` from the user prosevoice directory and the project `.prosevoice/`. Optional essay-local `.harper-words` adds proper nouns, one per line. `pv policy` and `pv lint` merge these additively at runtime, per essay; missing optional files are tolerated. Additions are proposed for operator approval. Readability advisories and supplemental regions are surfaced, not auto-fixed; the narrowly guarded spelling exception is documented in the skill and grammar agent.

When `harper-cli` is absent, grammar is reported skipped and other checks continue. An editor's Harper LSP may optionally use the same dictionary for consistent feedback.
