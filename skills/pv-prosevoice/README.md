# pv-prosevoice

Write and review persuasive or explanatory narrative essays in a consistent voice. Work in one
Markdown file or an ordered set of Markdown parts, then export to the requested format only after
editorial review. Blog posts are supported, but no publishing channel, filename or directory
layout is required. See [SKILL.md](SKILL.md) for routing, write authority and export checks.

The sibling `pv-preflight` resolves required `VOICE.md` and `AUDIENCE.md`, plus optional
`ILLUSTRATIONS.md`, independently from configured paths, project `.prose-voice/`, then `~/.prose-voice/`. It also checks dependencies, seeds the two required templates and installs `PV-PROTOCOL.md`.
Optional `.pv/config.json` configures extra guidance locations and intermediate-file placement.
Reviews and visual history default to gitignored `.pv/cache/`; `artifacts.location: adjacent`
keeps them beside the essay. Preflight resolves paths for agents. Final assets stay with the essay.

## Gates

- **DRAFT:** voice and readability, then load-bearing claim sourcing and grammar. Report-only on
  edits; bounded cleanup of agent-authored regions before presenting a draft. Explicit and
  pre-surface drafts also receive a copy-editing pass that works without Harper.
- **REVIEW:** grammar, evidence and provenance for both intents. Persuasive essays also get
  argument/reader checks and the premise-gated curmudgeon/steelman pair; explanatory essays add
  those when warranted or requested. Explanations are not forced into advocacy.
- **READY:** resolve source flags and explicitly planned visual selections, run the full review,
  then perform and verify the requested final export. Plain essays need no visual sidecar,
  hero, section images or decline records.
- **IDEA:** no gate until the user asks to develop a draft.

Visual aids are optional and purposeful. The illustrator selects appropriate diagram, drawing,
chart or image technology, follows `ILLUSTRATIONS.md` when supplied, retains editable sources or
prompts, and inspects the result. Generation is requested/agreed work, never an on-edit trigger.

Use `/pv-prosevoice` for an identified essay or set of parts. Unrelated Markdown, research,
instructions, generated review sidecars and exported files do not trigger essay review. Existing
non-Markdown input is converted to Markdown before editing; Markdown remains the revision source.

## Layout

```text
SKILL.md                         workflow, gates, reference resolution, write authority
README.md                        this guide
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
scripts/
  build_user_dict.py             merge shared and essay-local dictionaries
  harper_lint.py                 validated, classified read-only Harper results
  extract_prose.py               recover Harper-skipped reader-facing prose
  premise_fingerprint.py         deterministic premise hash
  ready_preconditions.py         planned visual selections and source flags
```

## Harper grammar policy

`grammar-check` uses `harper/dictionary.txt` and `harper/ignore-rules.txt`. Optional essay-local
`.harper-words` adds proper nouns, one per line. The helper merges these at runtime; missing local
dictionaries are tolerated. Additions are proposed for operator approval. Readability advisories
and supplemental regions are surfaced, not auto-fixed; the narrowly guarded spelling exception
is documented in the skill and grammar agent.

When `harper-cli` is absent, grammar is reported skipped and other checks continue. An editor's
Harper LSP may optionally use the same dictionary for consistent feedback.
