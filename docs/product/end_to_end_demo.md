# End-To-End Demo

## Purpose

This demo is the clearest local walkthrough of the current research OS.

It is meant to show that the implemented layers connect coherently:

- ingestion and normalization
- evidence extraction
- research artifacts
- feature mapping and candidate signal generation
- signal arbitration
- exploratory backtesting and baseline ablation
- portfolio proposal construction
- portfolio attribution and stress testing
- operator review artifacts
- monitoring and audit artifacts

It does **not** prove alpha, production readiness, or autonomous execution.

## Default Command

```bash
make demo
```

Direct CLI entrypoint:

```bash
anhf demo run \
  --frozen-time 2026-04-01T12:00:00Z \
  --base-root artifacts/demo_runs/week3_demo
```

Legacy module entrypoint:

```bash
python -m pipelines.demo.end_to_end_demo \
  --frozen-time 2026-04-01T12:00:00Z \
  --base-root artifacts/demo_runs/week3_demo
```

If you want to inspect the demo over HTTP, start `make api` in a separate terminal. The demo run and the API server are separate local processes.

## Inputs Used

The default demo uses:

- `tests/fixtures/ingestion/`
- `tests/fixtures/backtesting/apex_synthetic_daily_prices.json`

The run is local, deterministic, single-company, and synthetic-price-backed.

## What The Demo Runs

In order, the demo executes:

1. fixture ingestion and normalization
2. evidence extraction
3. research workflow
4. feature mapping, signal generation, and signal arbitration
5. one exploratory text-signal backtest
6. one four-family baseline ablation
7. portfolio review pipeline
8. review queue sync
9. one conservative operator note
10. one conservative proposal review action: `needs_revision`
11. health checks and recent run-summary collection

## Artifact Layout

The demo writes beneath one isolated base root, for example:

```text
artifacts/demo_runs/week3_demo/
  ingestion/
  parsing/
  research/
  signal_generation/
  signal_arbitration/
  backtesting/
  ablation/
  experiments/
  evaluation/
  portfolio/
  portfolio_analysis/
  review/
  audit/
  monitoring/
  timing/
  entity_resolution/
  demo/manifests/
```

The manifest under `demo/manifests/` is a convenience summary. The normal stage-specific artifact directories remain the source of truth.

## What To Inspect After A Run

Useful artifact categories:

- `research/research_briefs/`
- `signal_generation/signals/`
- `signal_arbitration/signal_bundles/`
- `backtesting/runs/`
- `ablation/ablation_results/`
- `portfolio/portfolio_proposals/`
- `portfolio_analysis/portfolio_attributions/`
- `portfolio_analysis/stress_test_results/`
- `review/queue_items/`
- `review/review_notes/`
- `review/review_decisions/`
- `audit/audit_logs/`
- `monitoring/run_summaries/`

`portfolio/paper_trades/` is only populated on an explicit approved-proposal path. The default demo does not create trade candidates.

Useful API inspection endpoints:

- `/system/manifest`
- `/monitoring/run-summaries/recent`
- `/monitoring/failures/recent`
- `/reviews/queue`
- `/reviews/context/{target_type}/{target_id}`
- `/portfolio/proposals`
- `/portfolio/paper-trades`

## What The Demo Proves

- the current typed workflow layers connect end to end
- temporal, audit, and review artifacts are persisted rather than implied
- signal arbitration, proposal attribution, and simple stress testing are real implemented layers
- downstream work remains review-bound and paper-only

## What The Demo Does Not Prove

- no alpha claim
- no validated signal-promotion gate
- no production data integration
- no realistic execution simulation
- no portfolio optimizer
- no snapshot-native replay across the full chain
- no multi-user production operator system

## Current Sharp Edges

- the demo is still single-company and local-filesystem-backed
- pricing is synthetic
- research, features, signals, and stress logic remain deterministic baselines
- reviewed and evaluated eligibility is still not enforced as a true downstream promotion gate
- the demo uses real artifact flows, but not production operations infrastructure
