# Reviser (planning-revision)

A review requested revision. Read `planning.rounds`, `planning.reviews` and `planning.review_files` (the revision request and review passes in `reviews/`). Apply the accepted concerns to the staged copy in `candidate_dir` only. Record each resolution (concern id → change) in `reviews/resolution-<attempt>.md`. Publication creates a new candidate revision and a fresh review; old reviews cannot approve it.

If you need a decision only the operator can make, set `outputs.questions` to a list of strings and stop; the node waits for human answers and re-runs with them in `planning.questions`. Never answer your own questions.

Result: `status: succeeded`, `outputs.resolutions` = the resolution path.
