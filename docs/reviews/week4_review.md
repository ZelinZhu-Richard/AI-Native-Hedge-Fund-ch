# Week 4 Review

## Bottom Line

Week 4 made the repo materially stricter in a few important places:

- structural data-quality failure is now explicit and persisted through `ValidationGate` artifacts in [services/data_quality/service.py](../../services/data_quality/service.py)
- portfolio construction is now inspectable instead of silently dropping losing candidates in [services/portfolio/construction.py](../../services/portfolio/construction.py)
- approved paper trades can now become tracked paper positions with explicit lifecycle state in [services/paper_ledger/service.py](../../services/paper_ledger/service.py)
- the API and CLI are cleaner and more honest local interfaces in [apps/api/main.py](../../apps/api/main.py) and [apps/cli/main.py](../../apps/cli/main.py)

Week 4 also made several layers much more inspectable without yet making them policy-driving:

- backtest-to-paper reconciliation
- proposal and experiment scorecards
- paper-trade outcome attribution
- external proof packaging

That distinction matters. The repo is now a stronger local research OS, but it still stops short of a true downstream trust boundary.

## Top Strengths

- The typed artifact chain is now deep and coherent across research, validation, reconciliation, construction, paper ledger, reporting, and interface layers.
- Structural quality failure is no longer hidden in logs. Refusal and quarantine behavior is explicit in [docs/contracts/data_quality_and_validation_gates.md](../contracts/data_quality_and_validation_gates.md) and enforced in [services/data_quality/service.py](../../services/data_quality/service.py).
- Portfolio construction is materially better than a toy signal-to-position mapping. Inclusion, exclusion, conflicts, sizing, and constraint pressure are inspectable in [services/portfolio/construction.py](../../services/portfolio/construction.py).
- Operator review, paper-trade approval, and paper-ledger admission are now a coherent chain instead of disconnected objects across [services/operator_review/service.py](../../services/operator_review/service.py) and [services/paper_ledger/service.py](../../services/paper_ledger/service.py).
- The interface and proof package are honest enough to survive external scrutiny better than before, especially after the manifest and daily-reporting fixes in this pass.

## Top Weaknesses

1. There is still no true reviewed-and-evaluated downstream eligibility gate. Portfolio construction still loads candidate or approved signals directly and treats raw-signal fallback as a warning-bearing path rather than a hard promotion boundary. See [services/portfolio/loaders.py](../../services/portfolio/loaders.py), [services/portfolio/construction.py](../../services/portfolio/construction.py), and [services/risk_engine/rules.py](../../services/risk_engine/rules.py).
2. Snapshot-native selection is still incomplete. Important flows remain cutoff-aware or latest-artifact-aware instead of selected-artifact-driven. See [services/feature_store/service.py](../../services/feature_store/service.py), [services/signal_generation/service.py](../../services/signal_generation/service.py), and [services/portfolio/loaders.py](../../services/portfolio/loaders.py).
3. Company identity still carries too much of the tradable identity burden. The current proposal and paper-trade path still leans on ticker and company metadata instead of a first-class instrument/security layer. See [libraries/schemas/portfolio.py](../../libraries/schemas/portfolio.py) and [services/portfolio/construction.py](../../services/portfolio/construction.py).
4. Evaluation, reconciliation, reporting, and paper-ledger followups are still mostly inspectable rather than policy-driving. They improve reviewer visibility but do not yet block unsafe downstream promotion. See [services/evaluation/service.py](../../services/evaluation/service.py), [services/backtest_reconciliation/service.py](../../services/backtest_reconciliation/service.py), [services/reporting/service.py](../../services/reporting/service.py), and [services/paper_ledger/service.py](../../services/paper_ledger/service.py).
5. Local filesystem roots still do too much coordination work. The repo is cleaner than before, but many workflows still depend on artifact-root conventions instead of explicit selected slices.
6. The research workflow still does not auto-generate `ResearchSummary`, so the reporting layer is strongest downstream and weaker on the research side. See [services/reporting/service.py](../../services/reporting/service.py) and [docs/product/reporting_and_scorecards.md](../product/reporting_and_scorecards.md).
7. Paper-ledger realism is honest but still sparse. Daily summaries, closes, and marks remain manual or local-input-driven, which is acceptable today but still operationally thin. See [services/paper_ledger/service.py](../../services/paper_ledger/service.py).
8. The backtest and paper paths are now compared honestly, but reconciliation remains advisory. High-severity mismatches still do not stop readiness automatically. See [docs/research/backtest_paper_reconciliation.md](../research/backtest_paper_reconciliation.md).
9. The daily workflow still ends largely by convention at `attention_required` instead of reaching stricter policy-visible blocked states from a true eligibility contract. See [services/daily_orchestration/executors.py](../../services/daily_orchestration/executors.py).
10. The external proof package is now much better aligned, but its honesty still depends on not overstating the current maturity of evaluation, readiness, and tradable identity.

## Critical Technical Risks

- Candidate signals still reach proposal construction without a reviewed-and-evaluated promotion artifact.
- Latest-artifact and cutoff-based selection still remain in core upstream loaders.
- Instrument identity is still implicit, so tradable handling can drift as scope widens.
- Policy-sensitive layers are still mostly additive and inspectable rather than gate-enforcing.
- Artifact-root conventions are still carrying coordination responsibilities that should eventually move into stronger selection and storage contracts.

## Critical Research Risks

- Candidate signals remain exploratory artifacts by default, but the repo still lacks the explicit hard promotion layer that would make that boundary structural.
- Deterministic scoring, arbitration, and construction remain heuristics and must stay framed that way.
- Backtests are timing-aware and more realistic than before, but still synthetic-price-backed in the default path and not live-execution credible.
- Outcome attribution is useful bookkeeping, not causal inference or performance evidence.

## Critical Operator Or Demo Risks

- A strong reviewer can inspect the system, but still cannot rely on a fully policy-hard downstream readiness boundary.
- The daily workflow is coherent, but its main stop state is still review-bound convention rather than explicit eligibility refusal.
- Demo and manifest surfaces were drifting toward stale or incomplete route advertising before this pass; that has been corrected, but the deeper operational gaps remain.
- The proof package is honest enough now to support a serious demo, but only if the presenter avoids implying policy completeness, live execution realism, or alpha evidence.

## Exact Fixes Made

- Canonicalized service capability route advertising so the manifest and capability surface now prefer the namespaced routes that the API actually documents and exposes:
  - [services/monitoring/service.py](../../services/monitoring/service.py)
  - [services/portfolio/service.py](../../services/portfolio/service.py)
  - [services/paper_execution/service.py](../../services/paper_execution/service.py)
  - [services/reporting/service.py](../../services/reporting/service.py)
  - [services/research_orchestrator/service.py](../../services/research_orchestrator/service.py)
- Fixed daily workflow reporting drift by making the daily portfolio step generate and persist same-run `RiskSummary` and `ProposalScorecard`, re-persist the proposal with `proposal_scorecard_id`, and feed the current-run scorecard into the daily report path:
  - [services/daily_orchestration/executors.py](../../services/daily_orchestration/executors.py)
  - [services/daily_orchestration/service.py](../../services/daily_orchestration/service.py)
- Corrected operator and demo docs so the CLI/API surfaces are described more honestly and `make api` is clearly a separate-terminal step for HTTP inspection:
  - [docs/product/operator_runbook.md](../product/operator_runbook.md)
  - [docs/product/demo_usability.md](../product/demo_usability.md)
  - [docs/product/end_to_end_demo.md](../product/end_to_end_demo.md)
  - [docs/product/api_and_interface_contracts.md](../product/api_and_interface_contracts.md)
  - [docs/product/demo_script.md](../product/demo_script.md)
  - [docs/product/daily_system_reporting.md](../product/daily_system_reporting.md)
- Added regression coverage for the corrected manifest/capability surface and the daily same-run scorecard path:
  - [tests/integration/test_api.py](../../tests/integration/test_api.py)
  - [tests/integration/test_daily_workflow.py](../../tests/integration/test_daily_workflow.py)
  - [tests/integration/test_operator_review_pipeline.py](../../tests/integration/test_operator_review_pipeline.py)

## Deferred Issues

- true reviewed-and-evaluated downstream eligibility enforcement
- explicit selected-artifact or snapshot-native selection across research -> feature -> signal -> portfolio
- first-class instrument and security reference layer
- policy-driving evaluation, reconciliation, and paper-ledger followup enforcement
- stronger operator attention handling that uses harder stop semantics instead of mostly review-facing notes
- durable storage and coordination beyond local artifact-root conventions

## Final 30-Day Push Priorities

1. True reviewed-and-evaluated downstream eligibility enforcement
2. Explicit selected-artifact or snapshot-native downstream selection
3. Operator attention handling and policy-visible blocked states
4. Readiness consumption of evaluation, reconciliation, and paper-ledger followups
5. First-class instrument/security layer as the first post-30-day structural build if it does not fit honestly into the remaining window
