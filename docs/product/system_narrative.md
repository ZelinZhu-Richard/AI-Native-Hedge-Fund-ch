# System Narrative

## What The System Actually Is

The repository is now a serious local research operating system scaffold with real typed workflows, persisted artifacts, and explicit review boundaries.

It is not a finished hedge fund platform. It is not a live trading system. It is not a shallow model wrapper around a dashboard.

## What Is Credible Today

- the repo has a genuine end-to-end path from raw fixtures to review-bound portfolio proposals
- paper-trade candidate creation is explicit and approval-gated
- major layers persist typed artifacts instead of loose text blobs
- timing, provenance, monitoring, audit, and review semantics are first-class
- research memory, signal arbitration, portfolio attribution, stress testing, and daily orchestration are implemented as real local layers

## Why This Is Structurally Better Than A Thin Demo

- candidate artifacts remain distinct from reviewed or validated ones
- evidence, hypotheses, features, signals, proposals, and trade candidates are separate objects
- portfolio proposals and paper trades are explicit review objects, not hidden side effects
- monitoring, audit, evaluation, and run summaries make workflows inspectable after the fact

## Current Strengths

- the domain chain is coherent:
  ingestion -> parsing -> research -> features -> signals -> arbitration -> backtesting -> portfolio -> review -> paper-trade candidates
- service boundaries are explicit enough to extend without collapsing everything into one module
- point-in-time timing and provenance semantics are now stronger across multiple layers
- the repo has a repeatable local demo path and a repeatable local daily workflow

## Current Weaknesses

- snapshot-native selection is still incomplete across the full chain
- company identity still carries too much of the tradable-instrument burden
- many workflows are rigorous locally but still depend on filesystem-scanning rather than explicit selected slices
- portfolio construction can still consume candidate artifacts before a true reviewed-and-evaluated gate exists
- local persistence is useful for development but not durable infrastructure

## Quant And Risk Reality

What is credible:

- backtests are explicitly exploratory
- ablations are mechanical comparisons, not winner declarations
- signal conflicts and proposal fragility are surfaced rather than hidden
- portfolio proposals remain review objects
- paper trades are clearly paper-only and human-gated

What is not yet trustworthy enough:

- there is still no basis for claiming market edge
- price fixtures are synthetic in the default demo
- there is no realistic transaction-cost, liquidity, or execution model
- calibration and arbitration are deterministic heuristics, not statistical truth
- stress testing is structured but simple

## What Week 3 Actually Achieved

- tightened point-in-time timing and availability semantics
- added metadata-first research retrieval
- added inspectable signal arbitration and uncertainty handling
- added explainable portfolio attribution and structured stress testing
- added repeatable local daily orchestration and runbook support
- improved repo consistency around artifact roots, local JSON persistence, validation errors, and review-facing notes

## What Would Be Misleading To Claim

- that the repo has a real promotion gate for downstream-eligible signals
- that the system is production-ready
- that the demo proves alpha or realistic paper-trading performance
- that retrieval is semantic or model-ranked
- that the current stress layer is institutional risk modeling

## Main Review Themes For Week 3

1. Where candidate artifacts still flow too far downstream by convention.
2. Where cutoff-based loading still stands in for explicit snapshot selection.
3. Where instrument identity is still too weak.
4. Where local development ergonomics are good enough, but operational durability is not.
