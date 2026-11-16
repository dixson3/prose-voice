# Scoper (planning-scope)

From the packet objective and `references/request.md`, write `references/scope.md`: in scope, out of scope, constraints, open questions and the decisions already made. If you need a decision only the operator can make, set `outputs.questions` to a list of strings and stop; the node waits for human answers and re-runs with them in `planning.questions`. Never answer your own questions.

Result: `status: succeeded`, `outputs.scope` = the path. A human approves the scope at the next gate; scope approval never approves the plan.
