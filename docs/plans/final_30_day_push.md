# Final 30-Day Push

## Summary

The remaining push should stop trying to look broader and should instead finish the trust-critical boundary work that Week 4 exposed but did not complete.

The main rule for the final push is simple:

- prefer structural enforcement over more summary surfaces
- prefer selected inputs over latest-artifact convenience
- prefer visible stop states over review-by-convention

## Strict Priority Order

1. True reviewed-and-evaluated downstream eligibility enforcement
2. Explicit selected-artifact or snapshot-native downstream selection
3. Operator attention handling and policy-visible blocked states
4. Readiness consumption of evaluation, reconciliation, and paper-ledger followups
5. First-class instrument/security layer as the first post-30-day structural build if it does not fit honestly into the remaining window

## Day 29

Focus: eligibility enforcement plus interface and monitoring visibility of blocked state.

Required outcomes:

- add one explicit downstream eligibility artifact or projection between candidate signals and portfolio-consumable inputs
- make portfolio construction reject ineligible signals structurally rather than only recording warnings or review-bound notes
- thread the blocked-state artifact through:
  - portfolio workflow responses
  - operator review context
  - monitoring run summaries
  - API and CLI inspection surfaces where relevant
- keep candidate signals queryable and reviewable, but non-promotable by default

Failure signs:

- portfolio construction can still build from candidate signals without an explicit eligibility artifact
- blocked state is still mostly note text instead of typed contract output
- interface surfaces cannot show why a proposal path was blocked

## Day 30

Focus: selected-artifact enforcement plus operator/demo hardening around the stricter gate.

Required outcomes:

- replace the strongest remaining latest-artifact and cutoff-only downstream paths with explicit selected-artifact references
- thread selected artifact identifiers across the research -> feature -> signal -> portfolio path where the eligibility gate depends on them
- harden the operator and demo docs around the stricter blocked-state behavior so the demo remains honest after the gate lands
- keep the interface and reporting surfaces aligned with the new stop states

Failure signs:

- selected-artifact enforcement remains optional or easy to bypass
- the stricter gate lands but the operator/demo path still explains it poorly
- the repo advertises trust improvements that the selection layer does not actually enforce

## What Not To Do In The Final Push

- do not widen into live trading or broker work
- do not start the instrument/security layer unless the remaining time is clearly enough to do it honestly
- do not add new dashboards or narrative packaging to compensate for missing enforcement
- do not turn evaluation or reconciliation into fake composite scores

## Expected State At The End

If the final push goes well, the repo should end the 30-day build as:

- a coherent and inspectable local research OS
- stricter about which signals are promotable downstream
- clearer about which exact artifact slice a workflow used
- better at surfacing blocked and review-required states operationally

It should still not be presented as:

- a live trading platform
- a production operator system
- a source of validated market edge
