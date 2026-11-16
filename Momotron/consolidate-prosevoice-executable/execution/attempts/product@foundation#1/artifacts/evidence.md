# foundation — evidence report

## Scope performed

Package skeleton, resource lookup, strict layered config, `init`, and the JSON command envelope, per the `foundation` section of the node description and `plan-assets/contract.md` (Package and CLI, Configuration).

## Files added (working tree, uncommitted)

- `pyproject.toml`: Hatchling build. The version comes from `VERSION` via a regex. The wheel package is `skills/prosevoice/scripts/prosevoice_lib`, with templates force-included under `prosevoice_lib/_skill/templates`. The console script is `prosevoice = prosevoice_lib.cli:main`, `requires-python >=3.11`, there are no runtime dependencies, and the license is MIT with the existing `LICENSE` (2026, James Dixson). `[tool.uv] package = false`. `[tool.pyright] extraPaths` points to the source scripts directory.
- `uv.lock`: minimal lock created by `uv` for the dependency-free project.
- `skills/prosevoice/scripts/prosevoice.py`: thin PEP 723 launcher (executable) delegating to `prosevoice_lib.cli:main`.
- `skills/prosevoice/scripts/prosevoice_lib/__init__.py`: `__version__`, `skill_root()` (packaged `_skill/` first, else the source skill tree, never cwd), `resource_mode()` and `resource()`.
- `skills/prosevoice/scripts/prosevoice_lib/errors.py`: diagnostics, `ProsevoiceError`/`ConfigError`/`UsageError`, and exit codes 0/1/2.
- `skills/prosevoice/scripts/prosevoice_lib/config.py`: XDG/home user directory (a relative `XDG_CONFIG_HOME` is rejected, an empty one is treated as unset). Project selection goes explicit (must exist) > Git root > cwd. Strict JSON rejects duplicate keys and NaN/Infinity. Schema validation covers `schema_version`/`guidance`/`artifacts.location`. `--set KEY=JSON` overrides take only known dotted keys and reject duplicates. Precedence is builtin < user < project < CLI, with per-filename guidance list replacement and per-leaf provenance (tier, source, anchor). Relative paths anchor to the user dir, project root or cwd, and `~` is expanded. Guide resolution order is configured, then project `.prosevoice/<name>`, then user dir, with states absent/empty/unfilled/ok. The module also covers the 12 artifact kinds in cache/adjacent mode, `prepare_artifacts`, the idempotent cache-ignore merge that retains custom content and recognises equivalent ignore forms, and `init`, which never overwrites, puts ILLUSTRATIONS behind a flag and refuses invalid existing config.
- `skills/prosevoice/scripts/prosevoice_lib/cli.py`: the commands `version`, `config`, `init`, `resolve` and `artifacts`, with common `--project`/`--set` on each subcommand. Output is one JSON envelope (`schema_version`, `command`, `status`, `data`, `diagnostics`). Parse errors use the envelope with exit 2, and `--help` stays argparse text.
- `skills/prosevoice/templates/{VOICE,AUDIENCE,ILLUSTRATIONS}.md`: copied from `pv-preflight/templates`. The skill name and resolution paths were updated, while section headings and the inert `pv-template: unfilled` marker are kept.
- `tests/_prosevoice_path.py`: puts the source scripts dir on `sys.path` so the test imports stay at module top.
- `tests/test_prosevoice_config.py` and `tests/test_prosevoice_package.py`.

The old helpers (`skills/pv-preflight`, `skills/pv-prosevoice`) and the three existing test modules are byte-unchanged (`git diff --quiet HEAD` passes on them), as the step requires.

## Coverage against the step's required cases

| Requirement | Test(s) |
| :-- | :-- |
| Every tier and provenance, builtin explicit | `TierAndProvenanceTests.*` |
| XDG fallback and invalid (relative) XDG | `LocationTests.test_xdg_*`, `test_relative_xdg_is_rejected`, package `test_relative_xdg_is_an_error_envelope` |
| Explicit and non-Git roots, explicit must exist | `test_project_selection_explicit_git_and_cwd`, `test_explicit_project_must_exist` |
| Relative anchors and `~` | `test_relative_paths_anchor_to_their_tier_and_tilde_expands`, `test_relative_essay_is_anchored_to_cwd` |
| Duplicate and unknown keys, versions, types, malformed, no lower-tier fallthrough | `StrictValidationTests.*` (both tiers via subTest) |
| List replacement per filename without losing other guides; empty list clears | `test_list_replacement_is_per_filename_without_losing_other_guides`, `test_empty_project_list_clears_user_candidates` |
| Empty/unfilled fallback, optional illustrations | `GuidanceResolutionTests.*`, `test_illustrations_require_explicit_flag` |
| Idempotent init, never overwrite, custom cache ignores | `InitTests.*`, `ArtifactTests.test_prepare_*`, package `test_init_cli_is_idempotent` |
| `config`/`resolve`/artifact path calculation do not write | `test_resolution_and_config_never_write`, `test_artifacts_preview_kind_and_apply` |
| Legacy `.prose-voice` never discovered | `test_legacy_directories_are_never_discovered` |
| Source resource lookup, cwd-independent, packaged `_skill/` preferred | `ResourceLookupTests.*` |
| Unrelated cwd, launcher via python and `uv run --script`, copied skill tree only | `LauncherTests.*` |
| Envelope shape and exit 0/1/2 semantics | `EnvelopeAndExitTests.*` |

## Commands and results

- Baseline: `uv run python -m unittest discover -s tests` returned 19 tests OK (`baseline-tests.log`). Baseline status is in `baseline-status.txt`.
- Check "Config and source package contracts": `uv run python -m unittest discover -s tests -p 'test_prosevoice_*.py'` returned 50 tests OK, exit 0 (`check-config-package.log`).
- Check "Existing behavior remains covered": `uv run python -m unittest discover -s tests` returned 69 tests OK, exit 0 (`check-full-suite.log`). The 19 original tests run unmodified.
- `uvx ruff check skills/prosevoice/scripts tests/` passed with no findings.
- `uv build --wheel` into a scratch directory succeeded. The wheel contains `prosevoice_lib` plus `_skill/templates`, an entry point and the license (`wheel-build.log`). The wheel was built only, not installed. Installation is verified in the integration step's distribution script.
- Final status (`final-status.txt`): relative to baseline, the only additions are the files listed above. `.agents/`, `.claude/`, `skills-lock.json` and the existing Momotron untracked items are unchanged.

## Residual limits and notes for later steps

- `check`, `rule`, `policy`, `lint`, `extract`, `premise`, `ready` and `migrate` are not yet registered. They belong to the consolidate and migration steps. Invoking them now returns a usage error envelope with exit 2.
- Wheel force-include currently lists only templates, because Hatchling fails on missing paths. SKILL.md, agents, protocol and Harper policy are added as they move into `skills/prosevoice/`.
- `artifacts` does not require the essay to exist, so draft paths can be computed before the draft is written. Cache mode requires the essay to be inside the selected project (`essay-outside-project`, exit 2).
- `init --scope user` writes config and guides to the user dir with no `.gitignore`. Project scope merges `/cache/` into `.prosevoice/.gitignore`.
- The LSP probe on the final files was inconclusive (the server does not confirm clean). An earlier probe of both test modules reported 0 diagnostics, and ruff is clean.
- Nothing was committed. Product commits are out of scope for this node.
