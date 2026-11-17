# Acceptance evidence: B1 repair and consolidation

Verdict: pass. No BLOCKING concerns.

## Checks (final tree)

| Check | Command | Result |
| --- | --- | --- |
| Acceptance regression | `uv run python -m unittest discover -s tests` | 148 tests OK, exit 0 (`check-unittest.log`) |
| Acceptance distributions | `uv run tests/check_distribution.py` | 273 assertions passed, 0 surfaces failed, 0 unverified, exit 0 (`check-distribution.log`) |
| Independent B1 reproduction | `repro-acceptance.sh <repo>` with isolated HOME/XDG and `GIT_CEILING_DIRECTORIES` | script exit 0; per-command exits listed below (`repro-acceptance.log`) |

## Independent reproduction (repro-acceptance.log)

The fixture is a non-Git `parent/essays/e.md` with an `illus:fig1` anchor, invoked through the real launcher.

- `ready <abs essay>` from an unrelated cwd: exit 1 blocked, `visual-unresolved`; sidecar `parent/essays/.prosevoice/cache/e.illustrations.md`. Before the repair this was exit 2 `essay-outside-project`.
- `artifacts --kind illustrations` from the unrelated cwd and from the non-Git ancestor `parent/`: exit 0, `project_selection: essay-dir`, path `parent/essays/.prosevoice/cache/e.illustrations.md`. Before the repair the ancestor case routed to `parent/.prosevoice/cache/essays/`.
- `ready essays/e.md` from the ancestor: exit 1 blocked, with the same sidecar path.
- After writing `selected: fig1Svg` at that sidecar, `ready` returns exit 0 ok from both directories.
- Explicit `--project`: an unrelated project gives exit 2 `essay-outside-project`; `--project parent` gives exit 0 with `explicit` and `parent/.prosevoice/cache/essays/e.draft.md`; a missing project gives exit 2 `project-missing`. Unchanged.
- Git-backed essay `gitproj/a/b/g.md` from the unrelated cwd: `essay-git`, `gitproj/.prosevoice/cache/a/b/g.draft.md`. Unchanged.
- `--set guidance.VOICE.md=["v.md"]` through `load_config` and then `config_for_essay` gives the derived project `essays/` (`essay-dir`), with `cwd` and the VOICE candidate still anchored at the unrelated invocation directory. The CLI's `resolve` and `check` take no essay, so essay-scoped guidance anchoring is only reachable through the library; `test_essay_directory_project_config_applies_and_cli_guidance_stays_cwd_anchored` covers it too.
- `artifacts parent/new/x/d.md --apply` for a directory that does not exist yet: exit 0, 12 paths under `new/x/.prosevoice/cache/`, `.gitignore` = `/cache/`, the essay is not created, and no `.prosevoice` directory appears in `parent/`.

## Diff review

- `config_for_essay` (config.py:368-393): when no Git root is found, it uses `essay.parent` with `how="essay-dir"`. It goes through the existing `read_config_file` + `build_config` path with the original `config.cwd`, so CLI anchors are preserved. The explicit branch returns early, so `select_project` validation is untouched. Git routing is unchanged apart from the label variable. No parallel resolver was added.
- `artifact_paths` / `prepare_artifacts` are unchanged; `prepare_artifacts` already does `mkdir(parents=True)`, so not-yet-created directories work.
- migration.py does not call `config_for_essay` and was not changed.
- SKILL.md:54 and :140 restore the rule "Without a Git root and without `--project`, the cache is `.prosevoice/cache/` beside the essay", and distinguish essay commands from commands without an essay. The root README (:145, :255) and the skill README (:5) match the implementation.
- New tests: `NonGitEssayRoutingTests` (5 tests) in tests/test_prosevoice_runtime.py run the real launcher from an unrelated cwd and from a non-Git ancestor. They assert exact paths, READY blocked→ok with a selected sidecar, explicit project, essay-dir config plus cwd-anchored `--set`, and a not-yet-created directory with apply. The test_prosevoice_package.py assertion of the regressed behaviour now expects the beside-essay cache, and the explicit `--project` outside-project assertion is kept.
- The tests that cover Git-root routing and all 12 artifact kinds still pass in the full suite.

## Preservation

- `.agents/`, `.claude/`, `skills-lock.json` and the CLAUDE.md `@AGENTS.md` wrapper are present and untouched. There is no tracked diff under `Momotron/`.
- The momotron reference HEAD is `6b1bf023bf30147ab6855a3f8e8d000a76a95a2b`, the same as the predecessor's record. Its `tests/conftest.py` formatter-only diff was already noted by the predecessor.
- Single skill: `skills/` contains only `prosevoice`. The legacy trees are deleted. Legacy names appear only in migration, the migrate help text and the docs saying they are never read.

## Nonblocking

- N1: when the invocation cwd is itself the non-Git essay directory, `config_for_essay` returns the invocation config, so `project_selection` reports `cwd` rather than `essay-dir`. The paths are identical; only the label differs.
- N2: the old helper returned READY blocked as exit 3; it is now exit 1, which is a documented contract change.

## Residual limits

- Optional external tools (Harper, web, raster) are not certified, and the distribution check does not exercise a real harper-cli.
- The installer check covers only the local source path, project scope, claude-code and pi.
