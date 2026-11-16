---
type: Context
okf_spec: MOMOTRON-PROCESS
description: Planning — purpose and replacement contract.
---
# Planning

The default initial-round workflow (config `planning_process`). It is a composition of named components; replace any component by id, or select a different root with `planning_process` or `momotron plan start --workflow`. A wrapper that adds steps must use a distinct id (for example `planning-assessed`) and reference `planning` or its components; reusing the same id is a recursive reference and freezing rejects it.
