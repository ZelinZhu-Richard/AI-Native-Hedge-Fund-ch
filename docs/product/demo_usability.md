# Demo Usability

## Purpose

The demo should be easy to run and inspect without overstating what it proves.

Day 28 improves usability by giving the repo one obvious command-line surface and one obvious API surface for the demo and related inspection paths.

## Shortest Demo Path

After installation:

```bash
make demo
```

Equivalent direct CLI:

```bash
anhf demo run \
  --frozen-time 2026-04-01T12:00:00Z \
  --base-root artifacts/demo_runs/week3_demo
```

Equivalent API invocation:

```bash
curl -X POST http://127.0.0.1:8000/workflows/demo/run \
  -H "content-type: application/json" \
  -d '{
    "frozen_time": "2026-04-01T12:00:00Z",
    "base_root": "artifacts/demo_runs/week3_demo",
    "requested_by": "demo_api"
  }'
```

## What You Get Back

The demo API and CLI now expose a compact `DemoRunResult` instead of the full nested workflow payload.

That result tells you:

- which workflow ran
- the stable `demo_run_id`
- where the manifest lives
- which company was covered
- the final proposal identifier
- how many queue items remained
- whether paper-trade candidates were created
- the observed health status

The full stage artifacts remain the source of truth.

## Useful Follow-On Commands

```bash
anhf capabilities
anhf review queue --json
anhf monitoring recent-runs --json
```

Useful API surfaces after the demo:

- `GET /reviews/queue`
- `GET /monitoring/run-summaries/recent`
- `GET /portfolio/proposals`
- `GET /reports/proposals/{portfolio_proposal_id}/scorecard`

## What Improved In Day 28

- there is now one unified CLI surface instead of only pipeline-module entrypoints
- canonical API routes are namespaced and easier to predict
- API success and error shapes are now explicit
- capability discovery is now inspectable through normalized descriptors and a manifest

## What Still Remains Simple

- the demo is still local and filesystem-backed
- the demo remains single-company in the default path
- prices remain synthetic in the default backtest path
- workflow invocation is synchronous
- the demo still ends review-bound by default

## What The Demo Still Does Not Prove

- alpha
- realistic execution quality
- live trading readiness
- downstream policy completeness
- production operator infrastructure
