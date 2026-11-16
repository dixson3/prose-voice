# Revision recorder (planning-review)

The verdict was `revise`. Read the conformance and red-team passes from the dependency
outputs. Write `reviews/revision-request-<attempt>.md` listing each concern that requires a
definition change and the proposed change. Do **not** edit `plan.yaml`, `plan-assets/` or
`processes/` during this run: the definition is the candidate under review. The operator (or a
drafting session) applies the changes afterwards, which creates a new candidate digest.

Result: `status: succeeded`, `outputs.request` = the request path.
