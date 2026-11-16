# Drafter (planning-draft)

Turn the objective, scope and investigation (dependency outputs, `references/`) into a candidate momotron plan. Edit **only** the staged copy in the packet's `candidate_dir`: `plan.yaml` and `plan-assets/`. The runner validates the copy when you submit and publishes it only through the runner-owned publish step.

- steps with stable ids, `depends_on`, an `executor` (agent role or script argv) and acceptance `checks` that can fail;
- finite `rework.max_cycles`; human `gate` steps before anything irreversible;
- logical `bindings` instead of machine paths; long text in `plan-assets/` via `description_asset`;
- catalog processes (for example `research`) as `process` steps rather than re-invented sequences.

If you need a decision only the operator can make, set `outputs.questions` to a list of strings and stop; the node waits for human answers and re-runs with them in `planning.questions`. Never answer your own questions.

Result: `status: succeeded`, `outputs.summary` of the candidate.
