# cwd correction for the successor plan

Scope: `plan.yaml` in this bundle only. The predecessor plan, `plan-assets/`, product source, installed tooling and the momotron reference checkout were not modified. No approvals, commits, runner dispatch or publishing.

## Cause

`executor.cwd` was `'{binding:repo}'` on all five tasks. In `.agents/skills/momotron/scripts/momotron_lib/runner.py`:

- `working_dir` (line 378) treats `executor.cwd` as `bundle`, `process`, or a literal binding name looked up in the run's bindings. `'{binding:repo}'` is not a binding name, so the run fails with `binding-missing`.
- `run_checks` (line 611) runs each check in the task's `working_dir`. A check's `cwd` is consulted only when it equals `bundle`, so the check-level `'{binding:repo}'` values had no effect.
- `{binding:...}` substitution applies only to argv (`expand_argv`).

## Change

- `executor.cwd`: `'{binding:repo}'` → `repo` on `foundation`, `consolidate`, `migration`, `integration` and `acceptance` (5 changes).
- `cwd` removed from all 9 acceptance checks. They now run in the task working directory, which is the `repo` binding.
- Formatting only, with no change to semantics: added `---`, indented block sequences, used `>-` folded scalars for long prose, and kept every line at 80 characters or fewer. `repairs: '0'` is still a string.

## Validation

Before-state snapshot: a copy of the generated plan taken before editing. Parsed comparison used `uv run --with pyyaml python -I`:

```text
executor.cwd changes: 5 check cwd removals: 9 other diffs: 0
after == before+intended changes: True
all executor.cwd in bindings ['momotron', 'repo'] ; no check cwd; argv paths relative
types: repairs '0'
```

The script built the expected document by applying only the intended changes to the parsed before-state: it set each `executor.cwd` to `repo` and removed each check `cwd`. The expected document is deep-equal to the parsed after-state.

Every `executor.cwd` value (`repo`) is a declared binding. No check has a `cwd`, so all checks run task-relative. The only path argument in any argv, `tests/check_distribution.py`, is relative and contains no `..`.

- `yamllint plan.yaml`: clean. Before the edit it reported 1 document-start, 37 indentation and 13 line-length findings.
- `momotron_lib.schema.validate_plan` on the new plan: ok. It ran in-memory without writing bytecode.
- Lines longer than 80 characters: 0. The `successor_of.digest` line is 74 characters.

## Not done

The plan was not linted through the `momotron` CLI and was not dispatched, so the binding-resolution fix has not been exercised by an actual run.
