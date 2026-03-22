# Week 3 Review

## Top Strengths

- The core artifact chain is real, typed, and inspectable: ingestion -> parsing -> research -> features -> signals -> arbitration -> backtesting -> portfolio -> review -> paper-trade candidates.
- Provenance, timing, audit, and monitoring are not decorative. They are persisted artifacts across the strongest workflow paths.
- Signal arbitration is unusually honest for this stage: conflicts, exclusions, and uncertainty are explicit instead of being hidden behind one score.
- Portfolio proposals are materially more useful than a toy optimizer output because attribution, stress results, and risk checks are structured and reviewable.
- Daily orchestration and operator review are coherent enough that a reviewer can actually walk the system without guessing what happened.

## Top Weaknesses

1. There is still no real reviewed-and-evaluated downstream eligibility gate between candidate signals and promotable portfolio inputs.
2. Snapshot-native selection is still incomplete. The repo is better at recording provenance than enforcing explicit artifact slices everywhere upstream.
3. Company identity still doubles as tradable identity in the portfolio and paper-trade path.
4. The system is still too dependent on local filesystem conventions and sibling-root assumptions.
5. Evaluation and red-team infrastructure exist, but they are not yet strong policy inputs on the main downstream path.
6. Some research, feature, signal, and stress heuristics are useful but still easy to oversell if the docs drift.
7. Retrieval is honest and useful, but still metadata-first only.
8. Backtesting is timing-aware, but still synthetic-price-backed and exploratory.
9. Operator attention handling exists, but it is still summary-oriented rather than policy-driving.
10. The repo is strong on structure and inspection, but still lacks a first-class instrument or security reference layer.

## Critical Technical Risks

- Candidate artifacts can still flow into downstream construction without a true promotion gate.
- Latest-artifact convenience paths still exist when `as_of_time` is omitted.
- First-class instrument identity is missing, so `Company.ticker` still leaks into tradable symbol handling.
- Local filesystem roots still carry too much coordination responsibility.
- Evaluation and red-team findings are still mostly diagnostic rather than gating.

## Critical Research Risks

- Candidate signals remain heuristic and unvalidated by default.
- Evidence grading, calibration, arbitration, and stress outputs are deterministic baselines, not model-backed truth.
- Metadata-first retrieval helps reuse, but it is not semantic research memory.
- Backtests remain exploratory and should not be treated as evidence of edge.

## Critical Operator Risks

- An operator can review the system, but policy-hard downstream stopping is still weaker than it should be.
- Raw-signal fallback remains available when arbitration context is missing.
- Reviewers still need to understand current local workspace conventions to reason about some artifact paths.
- Monitoring is useful for inspection, but not yet strong enough to drive workflow policy automatically.

## Exact Fixes Made

- Standardized shared artifact-workspace usage in the remaining high-value seams:
  - backtesting service and pipelines now derive default sibling roots from the feature workspace rather than ad hoc parent inference
  - operator review now infers sibling roots from one shared workspace and rejects mismatched explicit root combinations
  - red-team now infers sibling roots from one shared workspace and rejects mismatched explicit root combinations
  - feature-store write and query paths now use the shared workspace helper rather than hard-coded artifact-root joins
- Added a nested stage-path workspace resolver to make stage-root resolution explicit instead of relying on brittle path math.
- Tightened interface honesty:
  - fixed the stale FastAPI description that still described the repo as a Week 1 scaffold
  - removed a stale `placeholder` test name from the API integration suite
  - made red-team behavior explicit when `evaluation_root` is supplied but not yet consumed by current scenarios
- Hardened stop-state notes:
  - non-approved proposals now emit a stable note that zero paper-trade candidates were created
  - portfolio review pipeline now records that paper-trade creation stopped at the review gate because the proposal is not approved
- Added regression coverage for:
  - nested stage-path workspace resolution
  - custom-workspace backtest defaults
  - operator-review workspace inference and mismatch rejection
  - red-team workspace inference and mismatch rejection
  - explicit zero-trade stop-state notes

## Deferred Issues

- real reviewed-and-evaluated signal eligibility gate
- snapshot-native selection across research -> feature -> signal -> portfolio
- first-class instrument and security reference layer
- policy-driving evaluation and red-team enforcement
- stronger operator attention handling beyond summary artifacts
- durable storage and scheduling beyond local filesystem conventions

## Week 4 Priorities

1. Implement the reviewed-and-evaluated downstream eligibility gate so candidate signals stop flowing into portfolio construction by wording alone.
2. Replace latest-artifact and cutoff-only selection with explicit snapshot or selected-artifact references across research -> feature -> signal -> portfolio.
3. Add a first-class instrument and security reference layer so tradable identity stops leaking through `Company.ticker`.
4. Promote evaluation and red-team outputs from diagnostics into explicit readiness inputs for proposal and paper-trade eligibility.
5. Strengthen operator attention handling so blocked, stale, or review-bound states become clearer operational workflow boundaries rather than just notes and summaries.

## Bottom Line

Week 3 produced a serious local research operating system, not a production trading system.

The repo is strongest on typed artifacts, provenance, timing, arbitration inspectability, review surfaces, and workflow coherence. The weakest remaining gap is still the missing downstream eligibility boundary. That is the decision point for Week 4.
