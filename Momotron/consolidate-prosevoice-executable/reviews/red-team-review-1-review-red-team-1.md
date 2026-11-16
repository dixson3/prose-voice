---
type: Review
okf_spec: MOMOTRON-PLAN
description: Independent red-team review of the consolidate-prosevoice-executable successor plan.
---
# Red-team review

Verdict: **pass**. No BLOCKING concern was found. The open items below are NONBLOCKING or DEFERRED to named later checks.

Candidate: `consolidate-prosevoice-executable`, definition digest `7fa7754b3f688b29d9c47f1c686c75dc393dc62bd961a346dcaec16d57faa3f3`. Attempt: `review-1:review/red-team#1`.

## Inputs read

- The packet and its role, `plan.yaml`, and `plan-assets/execution.md`, `contract.md` and `migration.md`.
- `references/request.md` and `references/scope.md`, the predecessor reviews, the resolution and the execution summary.
- `reviews/cwd-correction.md` and the dependency conformance pass `reviews/conformance-20261116T221955370087Z.md`. That pass reports zero concerns, so none are left to address.
- Read-only inspection of the runner's `working_dir`, `run_checks`, `script_env`, `BASE_ENV` and `CHECK_TIMEOUT` in the momotron runner the repo has installed.
- Read-only inspection of the product repo's git status and `.gitignore`, and of the operator's installed `pv-*` skill locations.

## Findings that support the verdict

- **Binding fix holds.** `executor.cwd: repo` is now a plain binding name. `working_dir` looks the name up in the run bindings and raises `binding-missing` or `binding-stale` instead of guessing a path. Every check runs in the task's working directory, which is the repo. This resolves the predecessor's dispatch blocker. The fix has still not been exercised by an actual run (see RT-5).
- **Checks can fail.** `run_checks` passes a check only on exit 0, and a timeout or `OSError` counts as a failure. The pattern-filtered check `-p test_prosevoice_*.py` exits nonzero when it finds no tests: unittest returns 5 on Python ≥3.12, and uv's default here is 3.14. So a step cannot pass that check before its test modules exist.
- **No product changes yet.** All predecessor product nodes are `pending`. The repo shows only the expected untracked operator files (`.agents/`, `.claude/`, `skills-lock.json`) and predecessor-bundle residue. The baseline the foundation step records will therefore be a clean pre-change baseline.
- **Deleting the source trees does not break installed tooling.** `~/.agents/skills/pv-prosevoice` and `~/.agents/skills/pv-preflight` are real directories, not symlinks into `skills/pv-*`. `~/.claude/skills/pv-prosevoice` points to the `~/.agents` copy. Removing the tracked trees in the integration step leaves the operator's installed skills working, and git can restore the trees because no commit is authorized.
- **Outward-facing actions are bounded.** Publishing, pushes, product commits, real-project migration and global installs are excluded. The `npx skills add` check is confined to a scratch repo with isolated HOME and XDG directories. The check environment passes only `PATH`, `HOME`, `LANG`, `LC_ALL`, `TMPDIR` and `SYSTEMROOT`, which limits inherited harness variables. Product execution stays behind the planning-review human approval gate.
- **Failure paths are defined.** Each task has `rework.max_cycles: 2`, and an exhausted task returns to the operator. `execution.md` requires a failed requirement to fail the node. Migration blocks before writing anything, and recovery is hash-checked.

## Concerns

| ID | Class | Severity | Evidence (file, key) | Consequence | Minimum fix or disposition |
| :-- | :-- | :-- | :-- | :-- | :-- |
| RT-1 | DEFERRED | medium | `plan.yaml` `integration.checks[1]` and `acceptance.checks[1]`; `plan-assets/execution.md` § integration | The integration worker writes `tests/check_distribution.py`, the script used to check its own work. A weak script could exit 0 without exercising the wheel, the copied launcher or the scratch install. | Deferred to the independent `acceptance` reviewer (`independent: true`). That reviewer must read the script against the § integration requirements before relying on its exit code. No plan change is needed. |
| RT-2 | NONBLOCKING | low | `plan-assets/execution.md` § integration: "dependency/network failures are reported as unverified, never passes" | The text does not state an exit code for an unverified result. If a worker reads "unverified" as exit 0, a missing `npx` or no network would let the distribution checks pass. | Read the sentence as requiring a nonzero exit. The acceptance reviewer should confirm that the script exits nonzero when its dependencies are unavailable. |
| RT-3 | NONBLOCKING | low | `plan.yaml` checks use `uv run python -m unittest` in `repo`, and `foundation` adds `pyproject.toml` | After `pyproject.toml` exists, `uv run` syncs the project and creates an untracked `uv.lock` in the product repo. `.venv/` is already gitignored. The first sync may also need network access to fetch Hatchling. Either effect shows up as a visible check failure or as status noise, not as a false pass. | The acceptance status comparison should account for `uv.lock`: track it, ignore it or remove it, and report which. |
| RT-4 | DEFERRED | medium | `plan-assets/migration.md` (all sections); `plan.yaml` `migration.checks` | Migration fidelity carries the most risk in this plan: lost visual decisions, lost user policy, a truncating rule parser, or recovery overwriting edits made in between. | Same disposition as the predecessor's RT-2. Deferred to the migration tests and independent acceptance. The contract already requires preview without writes, activating rules last, and failure injection at the interruption boundaries. |
| RT-5 | DEFERRED | low | `reviews/cwd-correction.md` § Not done | The binding fix was validated against the schema and by reading the runner code, not by dispatching a node. | Deferred to the first product dispatch (`foundation`). A wrong binding stops that dispatch with `binding-missing` or `binding-stale`, so it cannot produce a false success. |

## Write boundary

This review wrote only this file and the attempt's `result.json`. It did not change the plan or the product, run the runner, resolve any gate, install anything or migrate any project. The review does not approve execution.
