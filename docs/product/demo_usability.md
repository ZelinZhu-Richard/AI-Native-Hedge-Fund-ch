# Demo Usability

## Purpose

The demo should be easy to run and inspect without overstating what it proves.

The repo now exposes one obvious command-line surface for normal local use, plus one explicit final-proof wrapper for deeper release review.

## Shortest Demo Path

After installation:

```bash
make demo
```

Equivalent direct CLI:

```bash
nta demo run \
  --frozen-time 2026-04-01T12:00:00Z \
  --base-root artifacts/demo_runs/release_candidate
```

Equivalent API invocation:

```bash
make api
# run the HTTP call from a separate terminal while the API is serving locally
curl -X POST http://127.0.0.1:8000/workflows/demo/run \
  -H "content-type: application/json" \
  -d '{
    "frozen_time": "2026-04-01T12:00:00Z",
    "base_root": "artifacts/demo_runs/release_candidate",
    "requested_by": "demo_api"
}'
```

## Full Proof Path

When you want one stronger build-cycle proof artifact instead of only the lighter review-bound demo:

```bash
make final-proof
```

Equivalent direct module entrypoint:

```bash
python -m pipelines.demo.final_30_day_proof \
  --frozen-time 2026-04-01T12:00:00Z \
  --base-root artifacts/demo_runs/final_30_day_proof
```

This path still uses the default demo as its base. It then adds one explicit approval-only appendix that proves paper-trade and paper-ledger continuity without implying automatic downstream promotion.

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

For the final proof path, the strongest convenience artifact is the final proof manifest under `demo/manifests/`.

## Useful Follow-On Commands

```bash
nta capabilities
nta review queue --json
nta monitoring recent-runs --json
```

Useful API surfaces after the demo:

- `GET /reviews/queue`
- `GET /monitoring/run-summaries/recent`
- `GET /portfolio/proposals`
- `GET /reports/proposals/{portfolio_proposal_id}/scorecard`

When you want to inspect those HTTP endpoints, keep `make api` running in a separate terminal. The demo run itself does not start the API server.

## What Is Better About The Current Interface

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
- the final proof appendix uses explicit local approvals and manual lifecycle events

## What The Demo Still Does Not Prove

- alpha
- realistic execution quality
- live trading readiness
- downstream policy completeness
- production operator infrastructure
