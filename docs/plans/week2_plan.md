# Week 2 Plan

## Goal

Turn the current Week 1 scaffold into a replay-safer, review-safer system without widening into new product areas.

## Priorities

### 1. Explicit Artifact And Snapshot Selection

- replace cutoff-only loading with explicit research, feature, signal, and portfolio snapshot selection
- make the selected snapshot identity visible in downstream artifacts
- stop relying on implicit latest-artifact behavior outside local dev convenience paths

### 2. Review-State Persistence And Promotion Gates

- persist review-state transitions for hypotheses, signals, proposals, and paper trades
- define the first promotion gate between:
  - candidate research artifacts
  - candidate signals
  - reviewed validation work
- make downstream services reject artifacts that have not crossed the required gate

### 3. Instrument And Reference Contract

- introduce a first-class instrument or security reference model
- stop using ticker strings as the only bridge between signals, backtests, proposals, and paper trades
- make benchmark and execution references attach to the same identity layer

### 4. Harder Temporal And Replay Tests

- add multi-generation replay fixtures
- add stale-artifact exclusion tests
- add adversarial joins that try to pull future evidence, future features, or future signals into current workflows

### 5. Audit And Review Trace Hardening

- keep local audit writes, but connect them more tightly to review transitions
- prepare for durable review history rather than isolated event files

## Non-Goals

- live trading
- portfolio optimization
- real market data integration
- performance marketing metrics

## Exact Target

At the end of Week 2, the repo should be able to say exactly which artifact slice was used, why it was eligible, who reviewed it, and why a downstream workflow was allowed or blocked.
