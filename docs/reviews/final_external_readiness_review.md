# Final External Readiness Review

## What Is Impressive

- The repo is clearly beyond a shallow AI wrapper. The core operating objects are typed, persisted, and linked across ingestion, evidence extraction, research, features, signals, arbitration, portfolio construction, review, paper-ledger tracking, reporting, monitoring, and audit.
- Provenance and timing discipline are real implementation concerns, not just doc language. The strongest evidence is in `libraries/schemas/`, `services/data_quality/service.py`, `services/timing/service.py`, `services/portfolio/construction.py`, and `docs/research/temporal_correctness.md`.
- Human review boundaries are genuine. The default demo stops at a review-bound proposal, the daily workflow exposes manual stops, and the stronger final proof path requires explicit portfolio and paper-trade approvals before the paper-ledger appendix exists.
- Portfolio construction is inspectable enough to survive scrutiny. Candidate inclusion, exclusion, conflict resolution, constraint pressure, and sizing rationale are explicit artifacts instead of hidden scoring.
- The repo now has honest proof surfaces for external scrutiny: `make demo`, `make final-proof`, `anhf manifest`, `anhf capabilities`, the local API, persisted scorecards, and the final proof manifest.

## What Is Honest But Incomplete

- Data-quality gates and refusal behavior are meaningful, but they are not yet the full downstream readiness policy.
- Temporal handling is materially stronger than a typical demo stack, but full selected-artifact or snapshot-native enforcement is still incomplete across research -> feature -> signal -> portfolio.
- Evaluation, reconciliation, reporting, and paper-ledger outcomes are useful and inspectable, but they still inform operators more than they constrain the system.
- Paper-trading support is coherent, but it is still manual-input-heavy bookkeeping rather than realistic execution simulation.
- The interface layer is clean for local inspection and demo use, but it is not a production control plane.
- There is still no first-class instrument/security layer, so company and ticker identity still carry too much tradable meaning.

## What Should Never Be Oversold

- This repo does not prove alpha, validated alpha, Sharpe, hit rate, or real trading performance.
- It does not prove extraction quality at scale across a broad issuer and document universe.
- It does not prove live operational reliability, broker realism, or realistic execution quality.
- It does not prove live trading or any safe path from research output to autonomous execution.
- It does not prove advanced market-risk realism or long-horizon paper-trading performance.
- It does not prove production-grade integrations, durability, or multi-user operations.

## What Phase 2 Must Prove

- A true reviewed-and-evaluated downstream eligibility boundary that blocks unsafe promotion instead of merely describing it.
- Explicit selected-artifact or snapshot-native downstream selection so replay and provenance do not depend on latest-artifact convenience paths.
- Better extraction quality, calibration, and broader normalization coverage against stronger data-provider inputs.
- Richer readiness policy that actually consumes evaluation, reconciliation, and paper-ledger followups.
- Better market realism, longer paper operation, and a first-class instrument/security model.

## What A Technical Reviewer Is Most Likely To Challenge

- Whether candidate signals can still travel too far downstream without a hard promotion boundary.
- Whether replay is actually complete if some loaders remain cutoff-aware or latest-artifact-aware.
- Whether company and ticker identity are still carrying too much tradable meaning.
- Whether the paper-ledger layer proves only continuity, not execution realism.
- Whether the reporting layer is descriptive rather than policy-driving.

## Top Architectural Strengths

1. Schema-first boundaries between raw sources, evidence, research, features, signals, proposals, reviews, trades, and ledger states.
2. Strong provenance and timing posture for an early local research stack.
3. Real review, monitoring, reporting, and audit subsystems rather than presentation-only layers.
4. Honest proof paths that reuse the same underlying workflows instead of maintaining separate demo logic.
5. Clear separation between review-bound defaults and explicit approval-only appendix behavior.

## Top Technical Debts

1. Missing reviewed-and-evaluated downstream eligibility gate.
2. Incomplete selected-artifact and snapshot-native loading discipline.
3. Missing first-class instrument/security model.
4. Policy-soft evaluation, reconciliation, reporting, and paper-ledger followups.
5. Heavy dependence on local filesystem artifact-root conventions.

## Top Research Risks

- Exploratory backtests remain synthetic-price-backed and should not be treated as proof of signal quality.
- Deterministic heuristics in scoring, arbitration, and construction remain heuristics.
- Extraction quality is still narrow-scope compared with the variability of real-world filings, calls, and news.
- Outcome attribution is traceability, not causal inference.

## Top Operator And Workflow Risks

- `attention_required` still covers both healthy review-bound stops and harder blocked states, so operators must read notes and linked artifacts rather than relying on the status alone.
- Paper-ledger marks, closes, and daily summaries still rely on explicit local inputs.
- Review is coherent, but some of the most important trust boundaries remain manual rather than policy-hard.
- The local API and CLI are good inspection tools, but they are not durable operating infrastructure.

## Exact Fixes Made In This Pass

- Added explicit `paper_trade_stop_kind=review_bound` and `paper_trade_stop_kind=blocked` notes in paper-trade proposal responses so zero-trade outcomes are easier to inspect programmatically and by humans.
- Propagated explicit stop-kind notes into the daily workflow paper-trade step so `attention_required` is less ambiguous in workflow artifacts.
- Added explicit review-bound stop notes to the final proof manifest’s baseline branch so the proof package shows the default stop condition directly.
- Added this external-readiness review and a consistency test so the closeout docs, proof docs, and README stay aligned on the major unresolved gaps.

## Strongest Remaining Evidence Paths To Inspect First

- `pipelines/demo/final_30_day_proof.py`
- `pipelines/demo/end_to_end_demo.py`
- `services/data_quality/service.py`
- `services/portfolio/construction.py`
- `services/operator_review/service.py`
- `services/paper_execution/service.py`
- `services/paper_ledger/service.py`
- `services/reporting/service.py`
- `tests/integration/test_final_30_day_proof.py`
- `tests/integration/test_daily_workflow.py`
- `docs/reviews/final_30_day_review.md`
- `docs/product/known_limitations.md`
