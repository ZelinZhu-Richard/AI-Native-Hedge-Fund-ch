# ANHF Research OS

Institutional-grade foundation for an AI-native hedge fund research and paper-trading platform, now extended with the first local ingestion and normalization slice.

This repository is the operating system for future research workflows, not a toy demo and not a live-trading system. The current scope is deliberately narrow: establish the architecture, typed contracts, service boundaries, safety controls, local development workflow, and documentation needed to build quickly without sacrificing rigor.

Execution sequencing and phase intent are anchored in `PLAN.md`. Repository contribution behavior and architectural guardrails are anchored in `AGENTS.md`.
Rolling implementation history is tracked in `docs/plans/work_log.md`.

## Current Scope

The repository currently includes:

- a disciplined Python monorepo scaffold
- typed Pydantic contracts for core research, portfolio, risk, memo, and audit entities
- service interfaces and stub implementations for each major platform boundary
- a minimal FastAPI control-plane API
- an initial agent framework and agent registry
- a local fixture-backed ingestion and normalization pipeline for filings, transcripts, news, company metadata, and price-series metadata
- a deterministic evidence-first research workflow that produces hypotheses, critiques, support grades, research briefs, and draft memo skeletons
- documentation for architecture, temporal contracts, risk controls, eval philosophy, and Day 2 execution
- local quality tooling: `ruff`, `mypy`, `pytest`, `pre-commit`, and `Makefile`

The repository still does **not** include:

- live brokerage connectivity
- autonomous execution
- real alpha claims
- backtest performance claims
- production data connectors beyond local fixture-backed loaders
- real feature computation or signal ranking logic
- persistent storage or deployment infrastructure

## Immediate Goal

The immediate goal is to harden the research workflow boundary before feature work begins:

- preserve exact evidence linkage from research artifacts back to source spans
- keep hypotheses, critiques, support grades, and memo-ready briefs reviewable and modular
- preserve point-in-time and provenance discipline
- keep signals and portfolio logic downstream of explicit human review

## Design Intent

The platform is structured so future work can separate and audit:

- data ingestion
- parsing and extraction
- evidence linkage
- hypothesis generation
- adversarial critique
- feature construction
- signal scoring
- risk review
- portfolio construction
- memo generation
- paper execution
- audit logging

That separation matters because not every AI output is trustworthy, not every hypothesis becomes a signal, and not every signal is safe to express as a position.

## Architecture Summary

The repo is organized as a Python monorepo with explicit top-level boundaries:

- `apps/`: thin entrypoints such as the API and future research console
- `services/`: application services with clear responsibilities
- `agents/`: machine-readable agent descriptors and future agent implementations
- `configs/`: versionable non-secret configuration assets and local examples
- `libraries/`: shared contracts, utilities, config, logging, and time primitives
- `pipelines/`: orchestration entrypoints for scheduled or event-driven workflows
- `data_contracts/`: future machine-readable data contract artifacts
- `research_artifacts/`: reviewable research outputs and templates that are not raw source data
- `storage/`: storage layout and dataset metadata conventions
- `docs/`: architecture, safety, contract, and execution plans
- `tests/`: unit and integration checks

At the repository level, the intended artifact split is:

- `storage/raw/` for raw source payloads
- `storage/normalized/` for normalized documents and parser-friendly text
- `storage/derived/` for derived machine-readable artifacts
- `storage/audit/` for durable audit/event storage
- `research_artifacts/` for human-reviewable outputs such as evidence packs, memos, and proposal bundles

The current ingestion slice writes exact raw fixture copies and canonical normalized artifacts so the system has a real local substrate even while provider integrations remain intentionally deferred.

## Project Structure

```text
/
├── README.md
├── AGENTS.md
├── PLAN.md
├── pyproject.toml
├── Makefile
├── .env.example
├── .pre-commit-config.yaml
├── apps/
│   ├── api/                  # FastAPI control plane and placeholder endpoints
│   └── research_console/     # Reserved for future analyst-facing application
├── services/
│   ├── ingestion/            # Raw artifact intake and registration
│   ├── parsing/              # Text normalization and structured extraction
│   ├── feature_store/        # Point-in-time feature registration and retrieval
│   ├── signal_generation/    # Signal construction from hypotheses and features
│   ├── research_orchestrator/# Research workflow coordination
│   ├── backtesting/          # Temporal-safe evaluation interfaces
│   ├── risk_engine/          # Pre-portfolio and pre-trade guardrails
│   ├── portfolio/            # Paper portfolio proposal construction
│   ├── paper_execution/      # Human-approved simulated trading only
│   ├── memo/                 # Research memo generation
│   └── audit/                # Structured immutable event logging
├── agents/
│   ├── filing_ingestion_agent/
│   ├── transcript_agent/
│   ├── news_agent/
│   ├── hypothesis_agent/
│   ├── counterargument_agent/
│   ├── signal_builder_agent/
│   ├── risk_reviewer_agent/
│   ├── portfolio_agent/
│   └── memo_writer_agent/
├── configs/                  # Versionable local config examples and future profiles
├── libraries/
│   ├── core/                 # Agent/service abstractions and registries
│   ├── schemas/              # Core typed domain models
│   ├── config/               # Environment and runtime settings
│   ├── time/                 # Explicit UTC handling
│   ├── logging/              # Structured logging hooks
│   └── utils/                # Shared helpers such as ID generation
├── pipelines/
│   ├── daily_research/
│   ├── document_processing/
│   └── signal_generation/
├── data_contracts/           # Reserved for versioned machine-readable contracts
├── infra/                    # Reserved for future deployment/IaC assets
├── notebooks/                # Ad-hoc research with stricter rules documented
├── research_artifacts/       # Reviewable research deliverables and templates
│   ├── evidence/
│   ├── hypotheses/
│   ├── features/
│   ├── signals/
│   ├── portfolio_proposals/
│   ├── paper_trades/
│   ├── memos/
│   └── audit_logs/
├── storage/                  # Storage layout and dataset metadata conventions
│   ├── raw/
│   ├── normalized/
│   ├── derived/
│   └── audit/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── docs/
    ├── architecture/
    ├── agents/
    ├── contracts/
    ├── research/
    ├── risk/
    └── plans/
```

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

### 3. Configure local environment

```bash
cp .env.example .env
```

### 4. Run checks

```bash
make format
make lint
make typecheck
make test
```

### 5. Start the API

```bash
make api
```

Open `http://127.0.0.1:8000/docs` for the generated FastAPI docs.

## Local Development Notes

- All timestamps should be timezone-aware UTC at rest.
- Services receive an explicit clock so future replay and testing can avoid hidden time dependencies.
- Provenance is mandatory for derived artifacts and strongly preferred for raw artifacts.
- Service stubs are intentionally thin; replace them with real adapters without changing the typed interfaces casually.
- Empty directories such as `infra/` and `data_contracts/` exist to reserve clean ownership boundaries early.
- Storage and research-artifact directories are intentionally pre-shaped so future persistence work does not blur raw, normalized, derived, and reviewable outputs.
- The API is a coordination surface, not the core business logic layer.

## Key Day 1 Choices

- `services/signal_generation/` was added beyond the initial sample layout because signal formation is operationally distinct from feature storage and portfolio construction.
- `services/audit/` exists as a separate boundary because audit concerns must remain independent from business services that emit audit events.
- Agent descriptors are represented in code and documentation so both humans and future automation have a shared source of truth.
- Time, IDs, config, and logging live in `libraries/` to avoid hidden coupling across services.
- `configs/`, `research_artifacts/`, and `storage/` exist because the operating docs require explicit homes for versioned config, reviewable research outputs, and dataset/storage metadata.

## Review-Later Topics

These are deliberate Day 1 deferrals that deserve review before Day 3:

- storage engine choice for raw artifacts, normalized text, and derived research objects
- event bus vs workflow engine for orchestration
- schema publication strategy for machine-readable contracts in `data_contracts/`
- point-in-time feature store implementation
- vector storage and retrieval policy for evidence search
- model routing policy and prompt registry versioning
- authentication, RBAC, and approval workflow persistence
- persistent audit log storage and tamper-evidence strategy

## How Future Phases Build On This

Future work should extend the platform in this order:

1. parsing and evidence extraction with traceable spans over the normalized artifacts
2. first research artifact flow from evidence to hypothesis, critique, brief, and memo skeleton
3. review-gated feature computation and signal generation with temporal controls
4. backtesting and eval harnesses with strict out-of-sample discipline
5. paper portfolio construction and simulated execution under risk review
6. real provider connectors once the local artifact flow is stable

The rule for future contributions is simple: preserve the boundaries, preserve provenance, preserve temporal correctness.
