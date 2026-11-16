# consolidate — evidence report

Step: `consolidate` of plan `consolidate-prosevoice-executable`. Working tree: `/Users/james/workspace/dixson3/blog-voice`. Nothing committed; legacy trees `skills/pv-prosevoice/` and `skills/pv-preflight/` are byte-unchanged (`git diff HEAD` empty) and their removal is left to the integration step.

## Checks

| Command | Result | Log |
| :-- | :-- | :-- |
| `uv run python -m unittest discover -s tests` | 110 tests OK, exit 0 | `check-unittest.log` |
| `uv run --with ruff ruff check skills/prosevoice tests` | All checks passed | `ruff.log` |
| `uv build --wheel` (scratch output dir) | exit 0; wheel ships SKILL, protocol, 12 agents, Harper policy, 3 templates under `prosevoice_lib/_skill/` | `wheel-build.log`, `wheel-contents.txt` |
| `git status --short` | only expected new/modified product files; `.agents/`, `.claude/`, `skills-lock.json` untouched | `final-status.txt` |

Test growth: the foundation step's 69 tests plus 23 runtime tests and 18 rules tests = 110. The ported legacy modules keep every test and assertion: `test_harper_lint` has 6 tests (30 assertions before, 33 now), `test_harper_policy` has 4 (10 before, 11 now) and `test_narrative_scope` has 9 (31 before, 31 now). That is 19 tests, as in the baseline.

## Files

Added under `skills/prosevoice/`: `SKILL.md`, `PROSEVOICE-PROTOCOL.md`, `agents/*.md` (12), `harper/dictionary.txt`, `harper/ignore-rules.txt`, `scripts/prosevoice_lib/essay.py`, `policy.py`, `rules.py`. Modified: `prosevoice_lib/cli.py` (7 new commands), `prosevoice_lib/config.py` (`config_for_essay`, typed leaf access), `pyproject.toml` (force-include of all resources). Tests: ported `tests/test_harper_lint.py`, `tests/test_harper_policy.py`, `tests/test_narrative_scope.py`; new `tests/test_prosevoice_runtime.py`, `tests/test_prosevoice_rules.py`.

## Responsibility mapping (prior → new)

| Prior location | Responsibility | New location |
| :-- | :-- | :-- |
| `pv-preflight/scripts/preflight.py check` | deps, guidance, rule state, `actions`, `ready` | `prosevoice_lib/rules.py:check`, `pv check` (exit 1 when not ready) |
| `preflight.py resolve` / `candidates` / `file_state` | per-file first-usable resolution, tried paths, unfilled marker | `config.py:resolve_guidance` (foundation), `pv resolve` |
| `preflight.py seed --scope project\|global` | blank VOICE/AUDIENCE seeding, never overwrite | `config.py:init`, `pv init --scope project\|user [--illustrations]` |
| `preflight.py artifacts [--apply]` + `pv_config.artifact_paths/prepare_artifacts` | 12 artifact kinds, cache/adjacent, ignore line | `config.py:artifact_paths/prepare_artifacts` + `config_for_essay`, `pv artifacts [--kind] [--apply]` |
| `preflight.py rule [--remove] [--apply]`, `rule_targets`, `target_state`, `apply_target`, `read_block`/`strip_block` | companion rule targets, OpenCode dedup, managed block | `rules.py:rule_targets/target_state/apply_target/rule`; conservative `find_block`/`replace_block` (shared with migration); `pv rule [--remove] [--apply]` |
| `pv_config.load_config/extra_guidance/project_root` | config validation, configured guidance | `config.py:load_config` (strict layered, foundation) |
| `pv-prosevoice/scripts/build_user_dict.py` | additive policy union, `--user-dict/--user-ignore/--sidecar/--out/--json` | `policy.py:read_words/read_rules/build/merge_rules/policy_sources/essay_policy/write_dictionary`; `pv policy [<essay>] [--user-dict]... [--user-ignore]... [--sidecar] [--bundled-dictionary] [--bundled-ignore] [--out]` |
| `harper_lint.py` (+ its private `project_root`/`policy_sources` import) | per-doc policy, Harper invocation, validation, span dedup, fix-candidate guard | `policy.py:normalize/validate_lints/harper_version/lint_file/render_text/lint_documents`; `pv lint <docs>... [--dialect] [--user-dict]... [--user-ignore]...` |
| `extract_prose.py` | supplemental extraction and back-map | `essay.py:extract` (code copied verbatim); `pv extract <essay> [--out-md]` |
| `premise_fingerprint.py` | title + thesis/first paragraph, normalization, 16-hex SHA-256 | `essay.py:split_frontmatter/first_body_paragraph/normalize/fingerprint` (verbatim); `pv premise <parts>...` |
| `ready_preconditions.py` (+ sibling `importlib` load of `pv_config`) | source flags in every part, active-anchor visuals, no-image, stale tolerance | `essay.py:check_image/check_source/check_ready` via `config_for_essay`; `pv ready <parts>...`; sibling import removed |
| `pv-preflight/PV-PROTOCOL.md` | always-loaded trigger rule | `skills/prosevoice/PROSEVOICE-PROTOCOL.md` (skill name updated only) |
| `pv-preflight/templates/*` | seed templates | `skills/prosevoice/templates/*` (foundation) |
| `pv-prosevoice/harper/*` | bundled dictionary/ignore rules | `skills/prosevoice/harper/*` (header comment renamed only) |
| `pv-prosevoice/agents/*.md` | 12 editorial agents | `skills/prosevoice/agents/*.md`; diff (`agents-diff.txt`) touches only helper commands, artifact/policy paths and skill names |
| `pv-prosevoice/SKILL.md` + `pv-preflight/SKILL.md` procedures | gates, preflight, setup flow, rule targets, config schema | `skills/prosevoice/SKILL.md`; diff in `skill-diff.txt` |

### SKILL.md instruction mapping

- Frontmatter/title (`pv-prosevoice` → `prosevoice`); the trigger and skip wording is unchanged apart from "run pv-preflight" → "run its preflight check".
- Sections carried over with the same wording: *Working format and essay selection*, *Review intent and requested form*, *Bounded write authority*, *Gates* table, *DRAFT gate* (except the tool-invocation sentences), *REVIEW gate*, *Optional visual aids*, *READY gate* steps 2–4, and *Premise-gated pair*, where only the first sentence's command changed. That covers essay detection, idea/draft/review-ready selection, multipart order, persuasive/explanatory distinctions, guidance and persona precedence, de-jargon, preserve-wins, copy editing, fact and provenance checks, and export ordering.
- `## SKILL_DIR` now resolves `prosevoice` and defines `pv()` (`uv run --script scripts/prosevoice.py`); it adds a command table and the envelope/exit-code contract.
- *References and preflight* runs `pv check` in place of the sibling preflight; the VOICE/AUDIENCE/ILLUSTRATIONS bullets and the optional-tool reporting paragraph are verbatim.
- The pv-preflight *Procedure* is now *Setup flow* (check → `init` → `rule` preview → `rule --apply`, missing deps). Its rule-target table is now *Companion rule targets*, with the new identity and markers and a statement that malformed blocks block the command.
- *Project configuration* now documents strict schema v1, the tiers and anchors, `--set`, `pv config` and `pv artifacts --apply`. The 12-kind list and the collision/mode-switch text are retained.
- In the DRAFT grammar paragraphs, `build_user_dict.py`/`harper_lint.py`/`extract_prose.py` became `pv policy`/`pv lint`/`pv extract` and the paragraphs were reflowed to one line each; the sentences about candidate status, copy-editor and guard are unchanged.
- READY step 1: `ready_preconditions.py --json` became `pv ready`; "Exit 3 means blocked" became "Exit 1 (`status: blocked`)".

## Interface differences (contract-mandated, not editorial)

1. Exit codes follow the envelope's 0/1/2. READY blocked was exit 3 and is now 1. Missing Harper was exit 4 and is now exit 0 with `data.status: skipped` plus a `harper-unavailable` diagnostic. Callers in `SKILL.md` and `agents/grammar-check.md` are updated.
2. All output is the JSON envelope. `policy` no longer has a bare-path mode, and results sit under `data`. `extract` keeps `orig_path` as the argument echo, as before, and adds an absolute `data.essay`.
3. Paths changed: `.prose-voice/` → `.prosevoice/`, `~/.prose-voice/` → `$XDG_CONFIG_HOME/prosevoice/` (default `~/.config/prosevoice/`), and `schema_version: 1` is required (foundation). Runtime never reads legacy locations; `test_package_has_no_legacy_imports_or_paths` guards this.
4. Project selection: `--cwd` options are replaced by `--project`. For essay operations (`artifacts`, `ready`, `lint`, `policy <essay>`) without `--project`, each essay's own nearest Git root selects its project (`config_for_essay`, reported as `essay-git`). This keeps the legacy per-essay/per-project policy isolation. An explicit `--project` applies to all essays. An essay outside any Git root uses the invocation's project, and cache mode then requires the essay to be inside it (foundation contract). Legacy used `<essay-dir>/.prose-voice/cache` instead.
5. `--global`/`--ignore` bundled overrides were renamed `--bundled-dictionary`/`--bundled-ignore`.
6. `rule --apply` no longer removes legacy `blog-voice`/`pv-protocol` artifacts; legacy rules are migration-only per contract. It now previews by default (the same as before), refuses all writes when any target block is malformed, and retains unrelated bytes including CRLF.

## Parser for migration

`rules.find_block(text, begin, end)` / `rules.replace_block(...)` take marker pairs as parameters. They reject unpaired, nested, duplicate, indented or name-prefixed marker lines, treat other tools' managed blocks as unrelated content, and preserve line endings. Tested with both the new markers and the legacy `pv-protocol` markers (`tests/test_prosevoice_rules.py`).

## Copied-tree isolation

`IsolatedLauncherTests.test_copied_skill_runs_ready_policy_lint_and_rule_without_siblings` copies only `skills/prosevoice` into an otherwise empty `skills/` dir. It then runs `ready` (blocked → ok), `policy` (bundled sources resolve inside the copy), `premise`, `check` and `version` with `python -I`.

## Residual limits

- Harper itself is mocked in tests; no real `harper-cli` run is certified here.
- Installer (`npx skills add`) and installed-wheel checks belong to the integration step (`tests/check_distribution.py`).
- Root README/AGENTS and the consolidated skill README are not yet updated (integration step).
