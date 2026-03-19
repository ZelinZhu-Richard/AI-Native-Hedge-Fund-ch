# End-To-End Demo

## Purpose

This demo is the first honest end-to-end walkthrough of the current research OS.

It is meant to prove that the existing layers connect coherently:

- ingestion and normalization
- evidence extraction
- research artifact generation
- feature and signal creation
- exploratory backtesting
- baseline ablation
- portfolio proposal and risk checks
- operator review and approval-gated paper trading
- monitoring, audit, and operator review artifacts

It does **not** prove alpha, statistical significance, production readiness, or autonomous execution.

## Default Command

```bash
make demo
```

Direct module entrypoint:

```bash
python -m pipelines.demo.end_to_end_demo \
  --frozen-time 2026-04-01T12:00:00Z \
  --base-root artifacts/demo_runs/week2_demo
```

## Inputs Used

The default demo uses:

- `tests/fixtures/ingestion/`
- `tests/fixtures/backtesting/apex_synthetic_daily_prices.json`

The run is local, deterministic, single-company, and synthetic-price-backed.

## What The Demo Runs

In order, the demo executes:

1. fixture ingestion
2. evidence extraction
3. research workflow
4. feature mapping
5. signal generation
6. one exploratory text-signal backtest
7. one four-family baseline ablation:
   - naive baseline
   - price-only baseline
   - text-only candidate baseline
   - combined baseline
8. portfolio review pipeline
9. review queue sync
10. one conservative review note
11. one conservative proposal review action: `needs_revision`
12. health checks and recent run-summary collection

## Artifact Layout

The demo writes beneath one isolated base root, for example:

```text
artifacts/demo_runs/week2_demo/
  ingestion/
  parsing/
  research/
  signal_generation/
  backtesting/
  ablation/
  experiments/
  evaluation/
  portfolio/
  review/
  audit/
  monitoring/
  demo/manifests/
```

The persisted manifest under `demo/manifests/` is a convenience summary. The source of truth remains the normal stage-specific artifact directories.

## What To Inspect After A Run

Useful artifact categories:

- `research/research_briefs/`
- `signal_generation/signals/`
- `backtesting/runs/`
- `ablation/ablation_results/`
- `evaluation/reports/`
- `portfolio/portfolio_proposals/`
- `review/queue_items/`
- `review/review_notes/`
- `review/review_decisions/`
- `audit/audit_logs/`
- `monitoring/run_summaries/`

`portfolio/paper_trades/` is only populated on an explicit approved-proposal path. The default demo does not write trade candidates.

Useful API inspection endpoints:

- `/monitoring/run-summaries/recent`
- `/monitoring/failures/recent`
- `/reviews/queue`
- `/reviews/context/{target_type}/{target_id}`
- `/portfolio-proposals`
- `/paper-trades/proposals`

## What The Demo Proves

- the current typed workflow layers connect end to end
- upstream lineage survives into signals and proposals, with a separate approved-only path to paper trades
- monitoring, audit, and review artifacts are not just placeholders
- the system can compare simple baseline variants on the same slice
- downstream work remains review-bound and paper-only

## What The Demo Does Not Prove

- no alpha claim
- no validated signal promotion
- no production data integration
- no realistic execution simulation
- no portfolio optimization
- no multi-user operator console
- no snapshot-native replay across the full chain

## Current Sharp Edges

- the demo is single-company and local-filesystem-backed
- pricing is synthetic
- research, scoring, and ablation logic are still deterministic mechanical baselines
- some workflow monitoring is still newer than the underlying artifact layers
- review exists, and proposal approval now gates trade-candidate creation, but broader signal eligibility enforcement is still incomplete
