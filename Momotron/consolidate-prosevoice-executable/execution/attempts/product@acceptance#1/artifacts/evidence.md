# Acceptance evidence (product:acceptance#1)

Independent review of the final working tree against `plan-assets/contract.md`, `plan-assets/migration.md` and `references/investigation.md`. No product files were edited by this attempt. Nothing was committed, installed into the real home, or migrated in a real project.

## Verdict: revise (one BLOCKING behavior difference)

### B1 (BLOCKING): non-Git essays route artifacts and READY differently than the prior helpers

Requirement at risk: the acceptance instruction "verify every live editorial responsibility and exact helper behavior is preserved; report any actual behavior difference as a blocker". The old `SKILL.md` stated: "Without a git root, use `.prose-voice/cache/` beside the essay." The investigation inventory also lists cache routes as something to preserve.

Old behavior (`pv_config.artifact_paths`, `prepare_artifacts`, used by `ready_preconditions.py` and `preflight.py artifacts`): when an essay has no Git root, the cache base is the essay's own directory, `<essay-dir>/.prose-voice/cache/<stem>.<kind>.md`, whatever the cwd.

New behavior (`skills/prosevoice/scripts/prosevoice_lib/config.py`: `config_for_essay` returns the cwd-selected config when `git_root` is `None`; `artifact_paths` then requires the essay to be inside that project):

- `pv ready /abs/essays/e.md` run from an unrelated non-Git cwd now returns `status: error`, exit 2 (`essay-outside-project`). The old helper evaluated the essay (blocked, exit 3, sidecar `essays/.prose-voice/cache/e.illustrations.md`). The same error affects `pv artifacts`, which every artifact-writing gate runs first.
- From a non-Git parent directory, `pv artifacts essays/e.md` routes to `<parent>/.prosevoice/cache/essays/e.*.md` instead of `<parent>/essays/.prose-voice/cache/e.*.md` (namespace rename aside). Essay-local project policy for `pv policy`/`pv lint` follows the same cwd root.

Reproduction: `repro-nongit-routing.sh <repo>` (output in `repro-nongit-routing.log`).

The new `README.md` documents this as intended ("An essay outside any Git repository uses the project selected from the current directory"). The new `SKILL.md` silently dropped the old sentence. The consolidate step's `interface_differences` does not list it. The contract's "explicit, then Git root, then cwd" rule covers project selection; it does not require changing the essay-relative cache base. The implementation already departs from the cwd rule for Git essays by using each essay's own Git root.

Consequence: outside Git, an explicit review or READY gate invoked from another directory fails operationally instead of evaluating the essay. From a parent directory, intermediate reports and illustration decisions land in a different cache than the prior rule promised.

Minimum fix (either):

1. Restore the old behavior. In `config_for_essay`, when no `--project` was given and the essay has no Git root, select the essay's directory as its project (for example `load_config(essay.parent, ...)` with a distinct `project_selection` such as `essay-dir`). Restore the SKILL.md sentence (new namespace), align the README paragraph, and add a runtime test that runs READY/artifacts on a non-Git essay from an unrelated cwd.
2. Or have the operator explicitly accept this as a contract-level behavior change. Then record it among the interface differences and restore an equivalent statement in `SKILL.md`. This reviewer cannot make that decision.

## Checks run once on the final tree

| Check | Command | Result |
| :-- | :-- | :-- |
| Acceptance regression | `uv run python -m unittest discover -s tests` | 143 tests OK, exit 0 (`check-unittest.log`) |
| Acceptance distributions | `uv run tests/check_distribution.py` | 273 assertions passed, 0 surfaces failed, 0 unverified, exit 0 (`check-distribution.log`) |

## Independent verification performed

- **Agents and SKILL**: every one of the 12 agents and `SKILL.md` was diffed against `HEAD`. The changes are limited to the namespace, the `pv` CLI calls, envelope `data.` access, exit-code text and the merged preflight setup/rule/config sections. Editorial text (stages, gates, write authority, de-jargon, protected patterns, copy-edit independence, fact/provenance, export ordering, premise reuse) is otherwise unchanged. The old preflight procedure (silent no-op on edit, setup note for missing/stale rules) is carried into `SKILL.md`.
- **Protocol, templates and Harper policy**: byte-identical apart from name/path wording. The template section headings and the `pv-template: unfilled` marker are intact.
- **Helper equivalence (executed)**: on a fixture with Unicode, quoted titles, block-scalar thesis, images and fences:
  - premise fingerprints from the old script and `pv premise` match, both with a thesis and with the first-paragraph fallback;
  - `pv extract` returns a map and snippet text identical to `extract_prose.py`;
  - the READY functions are line-for-line equal to `ready_preconditions.py` apart from the config parameter;
  - ported tests preserve all 19 original assertions, adapted to the envelope.
- **Legacy fallback**: no `.prose-voice`/`pv-*`/`PV-PROTOCOL`/`blog-voice` references in runtime modules other than `migration.py`, apart from `migrate` help text. Executed: with only legacy data present, `pv resolve` tries only `.prosevoice` and XDG paths.
- **12 artifact kinds**: `ARTIFACT_KINDS` is enforced by the `--kind` choices. Cache and adjacent routing is exercised by unit tests and the distribution check (both surfaces).
- **Migration (executed, scratch fixtures, isolated HOME/XDG)**:
  - preview and blocked runs leave the fixture tree byte-identical;
  - dependency on a legacy user guide blocks with `user-dependency-unmet`; user migration then lets project apply succeed;
  - the cache illustration decision is copied and READY stays clear;
  - a rerun is `unchanged` with no new manifest set;
  - an edited destination blocks with `destination-conflict`, exit 1;
  - a `pv-protocol` block with a non-exact marker blocks with `managed-block-malformed`, and nothing is truncated;
  - a missing installation blocks with `installation-missing`;
  - with an install, apply replaces the block and keeps unrelated AGENTS bytes before and after it. The second apply is `unchanged`, and `pv check` reports the rule `current`.
- **Docs vs parser**: `--help` for each subcommand matches the README and SKILL command tables (options, `--kind` choices, migrate flags). Config schema, provenance, anchors and rule markers match `config.py`/`rules.py`. A one-line-per-paragraph scan of README, AGENTS, both skill docs and the protocol found no wrapped prose. `CLAUDE.md` is still `@AGENTS.md`.
- **Preservation**: `.agents/`, `.claude/` and `skills-lock.json` are still untracked and present. There is no tracked diff under `Momotron/`, and the untracked older-bundle `.publish.lock` and fixtures match the baseline.
- **Momotron reference**: HEAD moved from the investigation's `4b62f96` to `6b1bf02` through the operator's own momotron plan commits, and `tests/conftest.py` has an uncommitted formatter-only reflow. No product attempt's logs reference that file. Attribution to this plan is not supported, but no pre-product momotron hash was recorded to prove it. See `momotron-reference.txt`.

## Nonblocking observations

- Contract-mandated interface changes (envelope, exit codes 0/1/2, `--cwd` → `--project`, `seed` dry-run → explicit `init`, `global` → `user` level label, Harper-unavailable reported as exit 0 with `data.status: skipped`) are documented and were not counted as blockers.
- Migration manifests under `.prosevoice/migrations/` are not git-ignored; this is documented.

## Residual limits

- Optional external editorial tools (Harper, web search, raster providers) are not certified. The distribution check does not run real `harper-cli`.
- The installer check uses the local source path at project scope for claude-code and pi only. Global targets are covered by unit tests.
