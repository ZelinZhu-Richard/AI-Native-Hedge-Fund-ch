# ANHF Research OS

Deterministic local research operating system for AI-assisted equity research, review-bound portfolio proposals, and approval-gated paper-trade candidates.

This repository is not a live trading system, not a brokerage integration, and not a performance-marketing demo. It is a serious local stack for building and reviewing research workflows with explicit provenance, timing, risk controls, and human oversight.

Treat the current repo as a release candidate for a 30-day local build, not as a production trading platform. It proves that the current workflow layers connect coherently and can be inspected honestly. It does not prove validated edge, live-market readiness, or complete downstream policy enforcement.

Execution sequencing and phase intent are anchored in `PLAN.md`. Repository guardrails are anchored in `AGENTS.md`. Rolling implementation history lives in `docs/plans/work_log.md`.

## What Is Real Today

- fixture-backed ingestion and normalization
- evidence extraction with source linkage
- research artifact generation:
  - evidence assessments
  - hypotheses
  - counter-hypotheses
  - research briefs
  - memo skeletons
- metadata-first research memory and retrieval
- point-in-time timing and availability contracts
- candidate feature mapping and candidate signal generation
- deterministic signal arbitration with explicit conflicts and uncertainty context
- exploratory backtesting and baseline ablation
- portfolio proposal construction with attribution and simple stress scenarios
- operator review queue, notes, and review decisions
- approval-gated paper-trade candidate generation
- monitoring, audit logging, experiment artifacts, and local daily orchestration

## What Is Still Skeletal Or Deliberately Limited

- no live trading or brokerage connectivity
- no production market-data connectors beyond local fixtures
- no full reviewed-and-evaluated signal eligibility gate yet
- no snapshot-native selection across the full research-to-portfolio chain
- no first-class instrument or security master
- no realistic execution simulator, liquidity model, or optimizer
- no persistent infra beyond local filesystem artifacts
- no semantic retrieval or vector indexing

## Current Operating Paths

### End-to-end demo

Runs a deterministic single-company local walkthrough over the APEX fixtures and synthetic prices.

```bash
make demo
```

Primary direct CLI:

```bash
anhf demo run \
  --frozen-time 2026-04-01T12:00:00Z \
  --base-root artifacts/demo_runs/release_candidate
```

Legacy module entrypoint still works:

```bash
python -m pipelines.demo.end_to_end_demo \
  --frozen-time 2026-04-01T12:00:00Z \
  --base-root artifacts/demo_runs/release_candidate
```

This proves that the current layers connect coherently. It does not prove alpha, production readiness, or autonomous execution.

See:

- `docs/product/end_to_end_demo.md`
- `docs/product/demo_usability.md`
- `docs/product/release_candidate_status.md`
- `docs/product/known_limitations.md`

### Final 30-day proof

Runs the same review-bound stack as the demo, then adds an explicit approval-only appendix that proves paper-trade and paper-ledger continuity without implying automatic downstream promotion.

```bash
make final-proof
```

Direct module entrypoint:

```bash
python -m pipelines.demo.final_30_day_proof \
  --frozen-time 2026-04-01T12:00:00Z \
  --base-root artifacts/demo_runs/final_30_day_proof
```

The resulting manifest is the strongest single proof artifact for the first 30-day build. It still does not prove validated edge, live trading, or complete policy enforcement.

See:

- `docs/reviews/final_30_day_review.md`
- `docs/plans/phase2_roadmap.md`
- `docs/product/end_to_end_demo.md`

### Daily local workflow

Runs the repeatable local operating path:

```bash
make daily-run
```

Primary direct CLI:

```bash
anhf daily run \
  --artifact-root artifacts/daily_runs/latest \
  --requested-by manual_local_run
```

Legacy module entrypoint still works:

```bash
python -m pipelines.daily_operations.daily_workflow \
  --artifact-root artifacts/daily_runs/latest \
  --requested-by manual_local_run
```

The default healthy outcome is usually `attention_required`, because paper-trade candidate creation remains review-gated.

See:

- `docs/architecture/daily_orchestration.md`
- `docs/product/operator_runbook.md`

## Quickstart

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

### 3. Configure the local environment

```bash
cp .env.example .env
```

### 4. Run verification checks first

```bash
make lint
make typecheck
make test
```

Optional maintenance:

```bash
make format
```

### 5. Run the demo, final proof, or daily workflow

```bash
make demo
make final-proof
make daily-run
```

### 6. Start the API

```bash
make api
```

Open `http://127.0.0.1:8000/docs` for the FastAPI inspection endpoints.

See:

- `docs/product/api_and_interface_contracts.md`

### 7. Inspect the interface surface

```bash
anhf capabilities
anhf manifest
anhf review queue --json
```

## External Proof Materials

Use these docs when you need to explain the repo to skeptical external readers without inflating what it can do:

- [Founder Narrative](docs/product/founder_narrative.md)
- [Technical Narrative](docs/product/technical_narrative.md)
- [Quant And Research Narrative](docs/product/quant_research_narrative.md)
- [Operator And Risk Narrative](docs/product/operator_and_risk_narrative.md)
- [Proof Artifact Inventory](docs/product/proof_artifact_inventory.md)
- [Project Maturity Scorecard](docs/product/project_maturity_scorecard.md)
- [Release Candidate Status](docs/product/release_candidate_status.md)
- [Known Limitations](docs/product/known_limitations.md)
- [Demo Script](docs/product/demo_script.md)
- [Final 30-Day Review](docs/reviews/final_30_day_review.md)
- [Phase 2 Roadmap](docs/plans/phase2_roadmap.md)

## Practical Repo Map

```text
apps/
  api/                       FastAPI inspection and coordination surface
  cli/                       unified local CLI for demo, daily, and inspection paths
services/
  ingestion/                fixture-backed intake and normalization
  parsing/                  parsing and evidence extraction
  research_orchestrator/    evidence -> hypothesis/critique/brief/memo flow
  research_memory/          metadata-first artifact retrieval
  feature_store/            derived feature creation and lookup
  signal_generation/        candidate signal construction
  signal_arbitration/       deterministic calibration, conflict handling, arbitration
  backtesting/              exploratory simulation and ablation support
  portfolio/                proposal construction
  portfolio_analysis/       attribution and structured stress testing
  risk_engine/              proposal-facing risk checks
  operator_review/          queue, notes, assignments, review actions
  paper_execution/          approval-gated paper-trade candidate creation
  monitoring/               run summaries, health checks, failure views
  audit/                    structured audit artifacts
  daily_orchestration/      repeatable local daily workflow
libraries/
  schemas/                  typed domain contracts
  core/                     service framework, provenance, local artifact helpers
  time/                     explicit clock and timezone handling
pipelines/
  document_processing/      ingestion and evidence-extraction entrypoints
  daily_research/           research workflow entrypoint
  signal_generation/        feature + signal + arbitration entrypoint
  portfolio/                portfolio review pipeline
  daily_operations/         daily operator workflow entrypoint
  demo/                     isolated end-to-end demo
docs/
  architecture/             workflow and boundary documentation
  contracts/                contract narratives
  product/                  operator-facing and demo-facing docs
  research/                 research system notes
  risk/                     risk and portfolio analysis docs
  plans/                    daily and weekly plans
tests/
  unit/                     logic and schema checks
  integration/              cross-service and pipeline checks
artifacts/
  local runtime materialization root
```

## Reality Checks

- Candidate signals are not validated edge claims.
- Backtests are exploratory and use synthetic prices in the default demo path.
- Portfolio proposals are review objects, not execution instructions.
- Paper trades are paper-only and require an explicitly approved parent proposal.
- The repo is strongest on structure, traceability, and workflow discipline, not on live-market realism.
- The API is a local inspection and coordination surface, not a production control plane.

## Developer Notes

- All important timestamps should remain timezone-aware UTC at rest.
- Services should use explicit clocks rather than hidden `now()` calls.
- Provenance is mandatory for important derived artifacts.
- Prefer explicit service boundaries over convenience coupling.
- When in doubt, preserve auditability and point-in-time discipline over speed.

## Release Candidate Focus

The most important release-candidate questions now are:

1. Where candidate artifacts still flow downstream without a true eligibility gate.
2. Where selected-artifact or snapshot-native selection is still incomplete.
3. Where issuer identity still stands in for instrument identity.
4. Where evaluation, reconciliation, and paper-ledger followups are still inspectable rather than policy-driving.
5. Where local-filesystem ergonomics are acceptable for development but not durable enough long term.

See:

- `docs/reviews/week4_review.md`
- `docs/plans/final_30_day_push.md`
- `docs/product/release_candidate_status.md`
- `docs/product/known_limitations.md`
