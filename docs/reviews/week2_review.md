# Week 2 Review

## Top Strengths

- The domain chain is real and inspectable: ingestion -> parsing -> research -> features -> signals -> backtesting/ablation -> portfolio proposal -> review/audit/monitoring.
- Temporal and provenance semantics are first-class across most major artifacts.
- Evaluation, monitoring, operator review, and red-team layers exist as stored artifacts rather than aspirational docs.
- The local demo is coherent and does not claim alpha, autonomous trading, or production readiness.

## Top Weaknesses

- Replay is still stronger downstream than upstream. The repo records reproducibility metadata more completely than it enforces snapshot-native replay.
- Review, validation, and eligibility semantics are still not fully separated. This pass tightened the worst gaps, but signal promotion is still incomplete.
- Portfolio construction still depends on `Company.ticker` as the tradable symbol bridge.
- The platform remains heavily local-filesystem-backed, which is fine for development but will create operational drag if left unresolved.

## Critical Technical Risks

- Snapshot-aware cutoffs exist, but upstream workflows still are not fully snapshot-native.
- Artifact duplication and layered metadata can make the source of truth harder to reason about over time.
- Dataset manifests and references are still local-development constructs, not durable dataset catalog entries.
- There is no first-class instrument or security master.

## Critical Research Risks

- Signals are still deterministic, candidate-heavy, and unvalidated by default.
- Backtests and ablations remain exploratory-only and use synthetic prices.
- There is still no basis for extrapolating performance or claiming edge.
- Evaluation is honest, but still concentrated on ablation output rather than the full research-to-proposal chain.

## Critical Workflow Risks

- Candidate and unvalidated signals can still reach portfolio proposals, even though they are explicitly warned and risk-gated.
- Proposal approval now gates paper-trade creation, but broader reviewed-and-evaluated signal eligibility is still missing.
- Operator review exists, but there is still no richer operator attention queue or multi-user workflow.
- Monitoring is useful, but still summary-oriented and local rather than durable observability infrastructure.

## Exact Fixes Made

- Restored approved-only paper-trade candidate creation. `pending_review` proposals no longer create trades.
- Tightened operator review validation so research approval now requires evidence support, and signal approval now requires complete lineage, explicit uncertainty, and validated status.
- Fixed a real reproducibility bug where persisted `DataSnapshot` artifacts could resolve to `dataset_manifest_id` instead of `data_snapshot_id`.
- Hardened backtest experiment references so dataset manifests, partitions, and references prefer concrete persisted snapshot artifact URIs and populate partition storage-location IDs.
- Updated the default end-to-end demo so it stops at a review-bound proposal rather than implying automatic trade-candidate generation.
- Updated tests and docs to match the stricter gating and narrower Week 2 claims.

## Deferred Issues

- first-class instrument and security reference layer
- full snapshot-native selection across research -> feature -> signal -> portfolio
- true reviewed-and-evaluated signal promotion gates
- broader evaluation coverage for proposal, review, and paper-trade eligibility
- richer operator attention handling and durable observability

## Week 3 Priorities

1. Add a real reviewed-and-evaluated eligibility gate between signals and downstream portfolio construction.
2. Replace cutoff-only loading with explicit snapshot or artifact selection across the research-to-portfolio chain.
3. Introduce a first-class instrument and security reference contract.
4. Extend evaluation beyond ablation into proposal, review, and paper-trade eligibility.
5. Harden monitoring and operator attention handling for stale, failed, or blocked workflows.
