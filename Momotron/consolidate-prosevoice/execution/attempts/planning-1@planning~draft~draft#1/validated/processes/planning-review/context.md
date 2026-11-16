---
type: Context
okf_spec: MOMOTRON-PROCESS
description: Why the default planning review looks the way it does and how to replace it.
---
# Planning review

Each run reviews one **candidate digest**. Conformance is mechanical and writes a pass to
`reviews/`; the red-team reviewer is an agent that must work from the packet alone. A `pass`
verdict leads to portability validation and the human approval gate; `revise` records the
requested changes and ends the run without approval. Editing the definition then produces a
new candidate, and a fresh run is required.

Replace it by placing a process with id `planning-review` in `.momotron/processes/` or user
config, or set `review_process` to another id. Any replacement must contain a human gate;
`freeze` rejects one that does not.
