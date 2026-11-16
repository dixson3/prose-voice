# Scope: consolidate prosevoice

This scope is derived from the packet objective and `references/request.md`. It defines the work to plan; it does not approve implementation or establish findings about either repository.

## In scope

- Consolidate `pv-prosevoice` and `pv-preflight` into one skill with the entrypoint `prosevoice`, incorporating the required preflight responsibilities into the consolidated skill.
- Investigate the Python support-package structure in `~/workspace/dixson3/momotron` and use it as the model for organizing prosevoice's Python support code.
- Investigate momotron's configuration-management structure and adopt a similar structure appropriate to prosevoice.
- Provide an explicit migration helper that brings an older `pv-prosevoice` project forward to the new structure and configuration.
- Plan the necessary updates to skill instructions, supporting documentation, installation references, and validation affected by the consolidation.
- Define validation for the consolidated entrypoint, support package, configuration management, and migration helper, including representative older-project migration coverage.
- Develop and review the plan through momotron, obtain the required human approval, and execute and validate the approved plan in subsequent authorized nodes.

## Out of scope

- Retaining backward-compatible skill entrypoints, runtime interfaces, or configuration handling solely to support the former arrangement. Legacy handling belongs in the explicit migration helper.
- Unrelated editorial behavior changes or new writing features beyond those required by the consolidation.
- Modifying the momotron reference project.
- Migrating operator projects automatically as part of this scope node or treating the request for a helper as authorization to alter arbitrary older projects.
- Product edits, runner submission or advancement, and human-gate resolution in this node.

## Constraints

- Use `prosevoice` as the skill entrypoint name.
- Model the Python support and configuration organization on the referenced momotron project; inspect the relevant implementation during investigation before specifying a concrete design.
- Backward compatibility is not required, but an explicit older-project migration path is required.
- Preserve the existing skill responsibilities through consolidation unless a later approved plan explicitly identifies a behavior change.
- Keep implementation and migration details grounded in repository evidence gathered by subsequent planning nodes; this scope makes no claims about current file layouts, configuration schemas, or migration behavior.
- Scope approval is a separate human decision and does not approve the plan or authorize product execution. Product execution follows approval of the plan through the designated process.
- This attempt may write only its result, its artifact directory, and the bundle reference and review destinations permitted by the packet; protected bundle files remain read-only.

## Decisions already made

- The two existing skills will become one skill.
- The consolidated entrypoint is `prosevoice`.
- The reference for Python support-package organization and configuration management is `~/workspace/dixson3/momotron`.
- Backward compatibility is unnecessary.
- An explicit migration helper must bring older `pv-prosevoice` projects forward.
- Momotron will be used to build and execute the plan, with its human approval boundaries preserved.

## Open questions

No operator-only decision is required to establish this scope. The following investigation questions remain for plan development; they are not assumed decisions:

- Which parts of momotron's Python packaging, command entrypoints, and configuration management fit prosevoice's needs?
- Which existing preflight and prosevoice responsibilities, configuration files, installed rules, and generated artifacts are affected by consolidation?
- Which older-project layouts must the migration helper recognize, and how should it report unsupported states, existing destination conflicts, and partial migrations?
- Which validation and installation checks will demonstrate that the new skill works and the migration preserves project guidance?

Any investigation finding that requires an operator preference or changes this scope must be surfaced through the planning process rather than answered implicitly.
