---
type: Review
okf_spec: MOMOTRON-PLAN
description: Independent red-team review of the B1 non-Git routing repair plan (review-1).
---
# Red-team review: consolidate-prosevoice-repair-1

Verdict: **pass**. No BLOCKING concerns remain. The conformance pass (`reviews/conformance-20261117T002315091950Z.md`) had no concerns.

The plan targets one reproduced blocker (`references/acceptance-blocker.json`, B1). Its fix is narrow and fully specified (`plan-assets/repair.md`, section `repair-nongit`). It keeps the explicit `--project`, Git-routing and CLI-anchor invariants. An independent reviewer accepts the work and has to reproduce both failure cases itself. Product edits stay behind the `approval` human gate of `planning-review`. The plan authorizes no publication, product commits or real-project migration.

I checked the premise against the repo's HEAD. In `skills/pv-preflight/scripts/pv_config.py`, `artifact_paths` uses `base = root or essay.parent` and `load_config(None)` returns `{}`. In the current `config_for_essay` (`skills/prosevoice/scripts/prosevoice_lib/config.py`), a missing Git root returns the invocation config. So the blocker is real, and the fix the plan prescribes is the right one.

| id | class | severity | evidence | consequence | minimum fix |
| :-- | :-- | :-- | :-- | :-- | :-- |
| R1 | NONBLOCKING | medium | `plan.yaml` steps `repair-nongit.checks` and `acceptance.checks` only run the existing unittest suites and `check_distribution.py`. `references/repro-nongit-routing.sh` always exits 0 and is not a check. | Every mechanical check passes on the unrepaired tree, because the predecessor already passed 143 tests and 273 assertions. The checks alone cannot show that B1 is fixed. That proof depends on the worker adding the regression test and on the independent acceptance reviewer, who `repair.md` § acceptance directs to reproduce both cases. | Optional: add a check that runs only the new non-Git test by name, or an asserting repro script. Then a missing test makes the check fail rather than pass vacuously. |
| R2 | NONBLOCKING | medium | `plan-assets/contract.md` line 15 says "Project selection is explicit `--project`, then nearest Git root, then cwd". `acceptance` is told to verify against the "unchanged contract". `repair.md` adds an essay-directory tier for essay commands. | A literal acceptance reviewer could call the repaired behavior a contract deviation and loop through rework. In practice `repair.md` (the acceptance step's own description asset) and criterion `b1-resolved` say plainly that essay commands differ. | Optional: one sentence in `repair.md` stating that it refines contract line 15 for essay commands without `--project` outside Git. |
| R3 | NONBLOCKING | low | Criterion `b1-resolved` makes `<essay-dir>/.prosevoice/` the project tier for non-Git essays. The old helper had no project tier outside Git, only user guidance. | A non-Git working directory's own `.prosevoice/config.json` or guides no longer apply to essays in its subdirectories. This is a new-namespace design choice, not a regression from the old behavior, and the plan's scope sets it on purpose. The docs need to state it. | The `repair-nongit` doc alignment already covers this. The acceptance reviewer should confirm that the README states it. |
| R4 | DEFERRED | low | `plan-assets/execution.md` § acceptance asks for "Compare baseline to final status". This plan captures no fresh baseline. The predecessor notes that no pre-product hash was recorded. | The preservation check has to use the predecessor's final status and diffstat as its baseline, so it is weaker than a true baseline diff. | Deferred to the `acceptance` step: use the predecessor's recorded final status (`references/predecessor/`) and git tracked-diff checks on `.agents/`, `.claude/`, `skills-lock.json` and the bundles. |
| R5 | DEFERRED | low | `check_distribution.py` runs `npx skills add` and uv builds that need the network. `repair.md` says "an unverified distribution is a nonzero failure". | A network outage fails the node instead of passing it silently. That is the correct, fail-closed behavior. It may need an operator retry. | None. The runner's rework/operator path handles it. |

Other checks with no concern found:
- The human gate exists (`processes/planning-review/process.yaml`, `approval`).
- Rework is bounded at `max_cycles: 2`.
- Fixtures use temporary HOME/XDG.
- `cwd: repo` is a binding, not a machine path.
- Both steps have honest failure instructions.
