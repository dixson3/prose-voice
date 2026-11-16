# Consolidate and modernize prosevoice

Bundle `consolidate-prosevoice-executable` (okf_spec `MOMOTRON-PLAN`). Members listed only when present.

| Member | Description |
| :-- | :-- |
| [`plan.yaml`](plan.yaml) | Authoritative plan definition (MOMOTRON-PLAN). |
| [`context.md`](context.md) | Environment snapshot captured at authoring time. |
| [`references/`](references/) | Captured inputs: request, upstream bodies, prior evidence. |
| [`reviews/`](reviews/) | Review passes and imported HTML feedback. |
| [`plan-assets/`](plan-assets/) | Long descriptions and attachments referenced by plan.yaml. |
| [`processes/`](processes/) | Frozen process closure pinned by processes/closure.yaml. |
| [`execution/`](execution/) | Execution ledger (state.json), packets, results and receipts. |
| [`plan.html`](plan.html) | Rendered plan view with embedded review comments. |
| [`log.md`](log.md) | Newest-first bundle history (projection of the ledger). |
