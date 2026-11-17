# repair-nongit evidence

## Blocker

B1: a non-Git essay without `--project` returned `essay-outside-project` (exit 2) when invoked from an unrelated directory, and from a non-Git ancestor its cache was placed under the ancestor's `.prosevoice/cache/<rel>/` instead of beside the essay.

## Changes

The product files are untracked predecessor work, so there is no Git diff for them. The repair changed these files:

- `skills/prosevoice/scripts/prosevoice_lib/config.py`: in `config_for_essay`, when there is no explicit project and no Git root for the essay, the derived project is `essay.parent` with `project_selection: "essay-dir"`. The Git path (`essay-git`) and the non-Git path both go through the shared `read_config_file` + `build_config` merge with the original `config.cwd` and `config.overrides`, so relative `--set` guidance stays anchored to the invocation directory. Neither path goes through `select_project`, so a derived essay directory that doesn't exist yet is not validated like `--project`, and `prepare_artifacts` creates it with `mkdir(parents=True)`. Explicit `--project` returns early and is unchanged, including `project-missing` and `essay-outside-project`. The module docstring now notes the essay-command rule. The new function is in `config_for_essay.after.py`.
- `skills/prosevoice/SKILL.md`: the common-options paragraph distinguishes commands without an essay from essay commands. The artifacts paragraph restores the rule: "Without a Git root and without `--project`, the cache is `.prosevoice/cache/` beside the essay. With `--project`, in cache mode the essay must be inside that project."
- `README.md`: the guidance-resolution paragraph limits the cwd-based rule to commands without an essay. The artifacts section describes essay-directory routing for non-Git essays, `--apply` on a directory that doesn't exist yet, explicit-project containment and `--set` anchoring.
- `skills/prosevoice/README.md`: the overview sentence on cache placement names the project used for essays and for commands without an essay.
- `tests/test_prosevoice_runtime.py`: new `NonGitEssayRoutingTests` (5 tests):
  - Runs the actual launcher subprocess from an unrelated directory and from a non-Git ancestor. `artifacts` returns exactly `<essay-dir>/.prosevoice/cache/queues.<kind>.md` for all 12 kinds, including `illustrations`, and creates nothing on preview.
  - From both directories, `ready` evaluates the essay (blocked, exit 1, `no sidecar block`, sidecar at the essay-adjacent cache). After a sidecar with `selected: flowSvg` is written at that path, it returns ok with exit 0.
  - Explicit project behavior is retained: `essay-outside-project`, `explicit` routing to `<project>/.prosevoice/cache/<rel>/`, `project-missing`, and READY with `--project`.
  - The essay directory's own `.prosevoice/config.json` applies (project guidance anchored to the essay dir; `adjacent` location), and CLI `--set guidance.VOICE.md` stays anchored to the invocation directory.
  - For an essay directory that doesn't exist yet, preview creates nothing. `--apply` creates `<dir>/.prosevoice/cache` and `.gitignore` `/cache/`, and does not create the essay or an ancestor `.prosevoice`. An explicit missing `--project` still errors with `project-missing`.
- `tests/test_prosevoice_package.py`: `test_artifacts_preview_kind_and_apply` asserted the regressed behavior (a non-Git essay outside the cwd project gives `essay-outside-project`). It now asserts essay-adjacent routing without `--project`, and keeps the `essay-outside-project` assertion with an explicit `--project`.

Migration code was not changed. Its `artifact_paths(cfg, ...)` call uses the migrated project's config directly and does not go through `config_for_essay`.

## Pre-repair confirmation

With only the `config_for_essay` non-Git branch reverted to `return config`, the runtime suite failed 8 tests (`pre-repair-runtime.log`, exit 1). With the repair restored, all 29 runtime tests pass.

## Targeted reproduction (`references/repro-nongit-routing.sh`, log `repro-nongit-routing.after.log`)

| Case | Before (blocker log) | After |
| --- | --- | --- |
| Old helper `ready` from an unrelated directory | exit 3, `essays/.prose-voice/cache/e.illustrations.md` | same (reference) |
| New `pv ready` from an unrelated directory | exit 2, `essay-outside-project` | exit 1 `blocked`, sidecar `essays/.prosevoice/cache/e.illustrations.md` |
| New `pv artifacts essays/e.md` from a non-Git parent | `<W>/.prosevoice/cache/essays/` | exit 0, project `<W>/essays` (`essay-dir`), `essays/.prosevoice/cache/e.illustrations.md` |

Exit 1 is the contract's `blocked` code, which replaced the old READY exit 3.

## Checks

| Check | Command | Exit | Result |
| --- | --- | --- | --- |
| Runtime and non-Git routing regression | `uv run python -m unittest discover -s tests -p test_prosevoice_runtime.py` | 0 | 29 tests OK |
| Full regression | `uv run python -m unittest discover -s tests` | 0 | 148 tests OK (143 before, plus 5 new) |
| Distribution verification | `uv run tests/check_distribution.py` | 0 | 273 assertions passed, 0 surfaces failed, 0 unverified |

## Preserved

`.agents/`, `.claude/`, `skills-lock.json`, plan definitions, assets and other attempts are untouched. There were no commits, publication, global installs or migrations of real projects. All fixtures used temporary directories with isolated HOME and XDG.
