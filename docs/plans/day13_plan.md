# Day 13 Plan

## Goal

Use the new evaluation, review, and monitoring layers to enforce stricter downstream eligibility instead of only recording state.

## Priority Work

### 1. Downstream Eligibility Gates

- require reviewed and evaluation-eligible signals before portfolio proposal generation
- require approved proposals before paper-trade candidate generation
- make blocked eligibility explicit in persisted outputs and monitoring summaries

### 2. Attention Queues

- surface stale, failed, or attention-required runs through reviewable attention artifacts
- distinguish operational failures from research-quality warnings

### 3. Snapshot-Native Selection

- push explicit selected snapshot IDs further upstream
- reduce remaining cutoff-only loading paths

### 4. Review And Monitoring Join

- make operator review context show recent `RunSummary`, open alerts, and evaluation status together
- keep audit and monitoring separate, but make them easier to inspect side by side

## Non-Goals

- live trading
- external observability platforms
- portfolio optimization
- performance claims

## Exact Target

At the end of Day 13, downstream workflows should be able to say not only what was reviewed and evaluated, but also why an artifact was eligible or blocked for the next stage.
