# Day 6 Plan

## Goal

Build the first honest signal evaluation and ablation harness on top of the new Day 5 candidate feature and signal pipeline.

## Priority 1: Temporal Evaluation Boundary

- define the exact `as_of_time`, `available_at`, and decision-cutoff rules for candidate features and signals
- add checks that reject signals whose features were not available by the requested cutoff
- define the minimal replay interface for one company and one fixture time slice

## Priority 2: Ablation Harness

- compare `text_only` against future `price_only`, `fundamentals_only`, and `combined` slices using the same signal contract
- record which feature families participated in each candidate signal
- add empty-but-explicit baseline handling so missing families do not silently disappear

## Priority 3: Candidate Signal Eval Artifacts

- define lightweight evaluation outputs for:
  - lineage completeness
  - score stability under small input changes
  - support-gap visibility
  - ablation coverage
- persist those eval artifacts alongside candidate signals

## Priority 4: Promotion Guardrails

- define the first explicit gate between candidate signals and any future backtest or portfolio logic
- require review and validation state to remain visible
- keep unvalidated signals out of any future proposal workflow by default

## Exact Day 6 Target

Implement a temporally honest candidate-signal evaluation and ablation workflow before any portfolio construction or paper-trading work begins.
