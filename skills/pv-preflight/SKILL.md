---
name: pv-preflight
description: >-
  Preflight for the pv-prosevoice skill: verifies tool dependencies (uv, git, harper-cli, naba),
  resolves required VOICE.md / AUDIENCE.md and optional ILLUSTRATIONS.md (<git-root>/.prose-voice/ → ~/.prose-voice/), seeds blank voice templates, and installs the always-loaded PV-PROTOCOL.md rule
  wherever pv-prosevoice is installed. TRIGGER when: pv-prosevoice calls it at the start of a
  gate; /pv-preflight; setting up prose-voice in a project or globally. SKIP for: reviewing an
  essay (pv-prosevoice).
---

# pv-preflight

Checks and setup that `pv-prosevoice` depends on. `pv-prosevoice` runs `check` before every gate; the operator runs `seed` and `rule` once per project (or once globally).

## SKILL_DIR

Use the directory this `SKILL.md` was read from. When the harness does not state it, resolve:

```bash
PF_DIR="${PF_DIR:-}"
if [ -z "$PF_DIR" ]; then
  GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo .)
  for _root in \
    "$GIT_ROOT/.claude/skills" "$GIT_ROOT/.agents/skills" \
    "$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.config/opencode/skills"
  do
    if [ -d "$_root/pv-preflight" ]; then PF_DIR="$_root/pv-preflight"; break; fi
  done
  unset _root
fi
[ -z "$PF_DIR" ] && { echo "ERROR: pv-preflight skill directory not found" >&2; exit 1; }
PF="uv run $PF_DIR/scripts/preflight.py"
```

## Commands

Every subcommand prints JSON. Run from inside the writing repo (or pass `--cwd DIR`).

| Command | Writes | Purpose |
| :-- | :-- | :-- |
| `$PF check` | nothing | deps, resolved voice files, rule state, `actions` list, `ready` flag |
| `$PF resolve` | nothing | required voice and optional visual reference paths |
| `$PF seed --scope project\|global [--apply]` | `.prose-voice/` | copy blank templates; never overwrites |
| `$PF artifacts <essay.md> [--apply]` | with `--apply`: artifact directory and cache ignore rule | resolve visual history, agent and gate report paths |
| `$PF rule [--remove] [--apply]` | rule files, `AGENTS.md` blocks | install or remove `PV-PROTOCOL.md` |

`seed` and `rule` are dry runs without `--apply`.

## Voice-file resolution

Per file, first usable match wins. Optional configured paths are checked first. Usable = exists, non-empty, and free of the `pv-template: unfilled` marker the templates ship with.

`<git-root>/.prose-voice/<file>` → `~/.prose-voice/<file>`, for required `VOICE.md` and `AUDIENCE.md`, and optional `ILLUSTRATIONS.md` visual guidance.

A project can override each file independently. Missing optional guidance does not affect `ready`. `seed` creates only VOICE and AUDIENCE templates. For optional visual guidance, offer [`templates/ILLUSTRATIONS.md`](templates/ILLUSTRATIONS.md): copy it to the selected scope's `.prose-voice/ILLUSTRATIONS.md` only when requested, without overwriting an existing guide. Fill its `Style block` and `Aspect` sections and remove the unfilled marker. The template sets preferences, not a requirement to create visuals.

## Project configuration and intermediate files

Optional `<git-root>/.prose-voice/config.json`:

```json
{
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

All keys are optional. `guidance` values are ordered lists of **file paths**, tried before the standard `.prose-voice/` project/global candidates. Relative paths resolve from the git root; absolute paths and `~` are accepted. Missing/empty/unfilled candidates fall through; optional ILLUSTRATIONS never blocks readiness. Unknown keys, malformed JSON and invalid value types fail with an error. External workflows may seed this file; no integration-specific paths are built in.

`artifacts.location` is `cache` (default) or `adjacent`. The `artifacts` command returns explicit paths for visual history, the adversarial pair, gate reports (`draft`, `review`, `ready`) and review reports (`copyedit`, `provenance`, `fact-check`, `footnoter`, `red-team`, `cold-read`). Cache placement is `<git-root>/.prose-voice/cache/<essay-relative-directory>/<essay-stem>.<purpose>.md`; outside git it uses `<essay-dir>/.prose-voice/cache/`. `--apply` creates the chosen directory and adds `/cache/` to `.prose-voice/.gitignore` without overwriting existing rules. Adjacent mode uses the essay's directory. Neither mode moves or deletes existing files; after changing modes regenerate or explicitly migrate old intermediates. Final assets and editable diagram sources stay with the essay.

Run `artifacts <essay.md> --apply` before dispatching writers; pass returned paths rather than letting agents infer placement. Config and the ignore rule can be versioned; cache content is ignored. `artifacts` without `--apply` is a read-only preview.

## Rule targets

`rule` installs `PV-PROTOCOL.md` next to each `pv-prosevoice` install it finds (project = git root, global = `$HOME`):

| Skill found at | Rule written to |
| :-- | :-- |
| `.claude/skills/pv-prosevoice` | `.claude/rules/PV-PROTOCOL.md` |
| `<root>/.agents/skills/pv-prosevoice` | managed block in `<root>/AGENTS.md` |
| `~/.agents/skills/pv-prosevoice` | managed block in `~/.pi/agent/AGENTS.md`, `~/.codex/AGENTS.md` and `~/.config/opencode/AGENTS.md` (each only if that harness dir exists) |
| `~/.config/opencode/skills/pv-prosevoice` | managed block in `~/.config/opencode/AGENTS.md` |

The managed block is delimited by `<!-- BEGIN pv-protocol … -->` / `<!-- END pv-protocol -->`; everything outside it is preserved. `rule --apply` also removes legacy `blog-voice` rule files and blocks.

## Procedure

### Called by pv-prosevoice (gate start)

1. Run `$PF check`. Do not write anything.
2. `ready: false` because voice files are unresolved:
   - on an **edit trigger** → silent no-op (end the gate, say nothing);
   - on an **explicit `/pv-prosevoice`** → report the `actions` and offer the setup flow below.
3. `ready: true` → hand all resolved reference paths (including optional ILLUSTRATIONS) and the `deps` map to `pv-prosevoice`. A rule target in state `missing`/`stale`, or a legacy hit, is reported once as a one-line note with the `rule --apply` command; it does not block the gate.

### Setup (explicit `/pv-preflight`, or offered from `/pv-prosevoice`)

1. Run `$PF check` and show the report.
2. Voice files: ask project or global scope, show `seed --scope <s>` (dry run), apply on confirm. Then tell the operator to fill in each file and delete its `pv-template: unfilled` line. On request, draft the sections from the repo's existing essays for operator approval.
3. Rule: show `rule` (dry run), apply on confirm.
4. Missing `uv` or `git` → report; the skill cannot run. Missing `harper-cli` skips grammar. `naba` is one optional raster tool; absence does not disable diagrams or other image tools. Select and check visual capabilities only when visual work is requested.

To uninstall the rule before `npx skills remove`, run `$PF rule --remove --apply`.
