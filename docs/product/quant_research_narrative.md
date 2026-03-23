# Quant And Research Narrative

## What The System Is Today

The repo is a structured research and paper-trading system with explicit evidence lineage, timing contracts, signal construction, exploratory backtesting, portfolio proposal construction, and paper-first review boundaries.

It does not claim live-trading readiness or market edge. It is a disciplined research operating system, not a performance-marketing shell.

## 30-Day Build Summary

- What is real today: the repo can trace fixture-backed research into signals, proposals, reconciliation artifacts, and an explicit approval-only paper-ledger appendix.
- What this audience can safely conclude: the system is serious about lineage, timing, review state, and research-process integrity.
- What this audience must not conclude: the repo does not prove validated alpha, realistic execution, or a completed downstream promotion gate.
- Next-phase focus: harden eligibility, selected-artifact discipline, evaluation, and backtest-to-paper realism before broadening strategy complexity.

## What Is Genuinely Strong

- Evidence, hypotheses, counter-hypotheses, features, signals, and proposals are separate artifacts with explicit lineage.
- Timing and availability are treated as real constraints rather than afterthoughts.
- Signal arbitration surfaces conflicts and withheld-action states instead of smoothing them away.
- Backtesting now records execution timing, fill assumptions, cost models, and realism warnings explicitly.
- Paper-trade and outcome artifacts now link back into the research chain so learning does not stop at candidate creation.

## What Is Still Limited

- The missing reviewed-and-evaluated downstream eligibility gate is still the main structural weakness.
- Snapshot-native artifact selection is still incomplete across the full chain.
- Default demo prices remain synthetic, so backtests are exploratory only.
- Portfolio construction is inspectable and deterministic, but still heuristic rather than optimized.
- Evaluation exists, but it is not yet strong enough to function as a real promotion policy.

## Why The Architecture Matters

Quant credibility comes from resisting silent leakage and hand-wavy lineage. The architecture matters because:

- timing logic is explicit
- provenance is required on important artifacts
- backtest and paper assumptions are compared explicitly
- proposal and paper-trade layers stay downstream of research and review rather than bypassing them

That makes the repo more suitable for skeptical internal research iteration than a notebook stack with loose conventions.

## Why This Is Not A Shallow AI Wrapper

The system does not ask a model to “pick stocks” and then wrap the output in confidence language. It builds a chain of intermediate artifacts that can be inspected and challenged:

- evidence support is graded
- counter-theses are explicit
- signals are arbitration-aware
- portfolio inclusion and exclusion decisions are recorded
- paper outcomes and followups feed back into attribution

The repo is still limited, but it is limited in visible ways.

## Near-Term Milestones

1. Implement the reviewed-and-evaluated eligibility gate that blocks downstream use of structurally or policy-incomplete candidates.
2. Finish snapshot-native selection to reduce cutoff-based ambiguity.
3. Add a first-class instrument/security layer before broadening portfolio construction or paper-trading complexity.
4. Strengthen evaluation and red-team outputs so they materially affect readiness, not just post hoc inspection.

## Supporting Proof Surfaces

- [Temporal Correctness](../research/temporal_correctness.md)
- [Backtest Realism V2](../research/backtest_realism_v2.md)
- [Backtest Paper Reconciliation](../research/backtest_paper_reconciliation.md)
- [Feature And Signal Pipeline](../research/feature_and_signal_pipeline.md)
- [`services/signal_arbitration/service.py`](../../services/signal_arbitration/service.py)
- [`tests/integration/test_point_in_time_availability.py`](../../tests/integration/test_point_in_time_availability.py)
