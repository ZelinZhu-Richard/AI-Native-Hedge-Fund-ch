# ANHF Research OS

Institutional-grade foundation for an AI-native hedge fund research and paper-trading platform, now extended through the first full Week 1 stack: ingestion, evidence, research, candidate features, candidate signals, exploratory backtesting, risk-aware portfolio proposals, and paper-trade candidates.

This repository is the operating system for future research workflows, not a toy demo and not a live-trading system. The current scope is deliberately narrow: establish the architecture, typed contracts, service boundaries, safety controls, local development workflow, and documentation needed to build quickly without sacrificing rigor.

Execution sequencing and phase intent are anchored in `PLAN.md`. Repository contribution behavior and architectural guardrails are anchored in `AGENTS.md`.
Rolling implementation history is tracked in `docs/plans/work_log.md`.

## Current Scope

The repository currently includes:

- a disciplined Python monorepo scaffold
- typed Pydantic contracts across ingestion, evidence, research, features, signals, backtesting, portfolio, paper-trading, memo, and audit layers
- deterministic local workflows for:
  - ingestion and normalization
  - evidence extraction
  - hypothesis and critique generation
  - candidate feature mapping
  - candidate signal generation
  - exploratory backtesting and simulation
  - risk-aware portfolio proposal construction
  - paper-trade candidate creation
- a thin FastAPI control-plane API with artifact-backed inspection endpoints
- fixture-backed local datasets for repeatable development and tests
- explicit temporal contracts, provenance, risk docs, and review plans
- local quality tooling: `ruff`, `mypy`, `pytest`, `pre-commit`, and `Makefile`

The repository still does **not** include:

- live brokerage connectivity
- autonomous execution
- production data connectors beyond local fixture-backed loaders
- validated signal-promotion gates
- snapshot-native replay across the full research-to-portfolio chain
- realistic market data, execution simulation, or portfolio optimization
- persistent infra beyond the local filesystem artifact model

## Immediate Goal

The immediate goal is Week 2 hardening, not breadth:

- replace implicit latest-artifact selection with explicit snapshot or cutoff selection
- make audit and review-state persistence operational rather than mostly structural
- introduce a first-class instrument and reference-data bridge instead of leaning on ticker strings
- tighten replay, leakage, and multi-generation artifact tests
- preserve the distinction between candidate artifacts and validated artifacts all the way downstream

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
- `artifacts/`: current local runtime materialization root
- `research_artifacts/`: future review-bundle conventions and templates
- `storage/`: future persistent storage layout and dataset metadata conventions
- `docs/`: architecture, safety, contract, and execution plans
- `tests/`: unit and integration checks

At Week 1 there are three different concepts that should not be conflated:

- `artifacts/` is the current local runtime write path used by tests and deterministic workflows
- `storage/` describes future durable dataset and storage conventions
- `research_artifacts/` describes future human-review bundle conventions

Current runtime workflows write under:

- `artifacts/ingestion/`
- `artifacts/parsing/`
- `artifacts/research/`
- `artifacts/signal_generation/`
- `artifacts/backtesting/`
- `artifacts/portfolio/`
- `artifacts/audit/`

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
│   ├── api/                  # FastAPI control plane and artifact-backed inspection endpoints
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
├── artifacts/                # Current local runtime materialization root
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
│   ├── signal_generation/
│   ├── backtesting/
│   └── portfolio/
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

## Key Architectural Choices

- `services/signal_generation/` is a distinct boundary because signal formation is operationally different from feature storage, backtesting, and portfolio construction.
- `services/backtesting/` remains exploratory and evaluation-only; it is not a route to execution.
- `services/audit/` is a separate boundary because audit concerns must remain independent from the services that emit auditable events.
- Agent descriptors are represented in code and documentation so both humans and future automation have a shared source of truth.
- Time, IDs, config, and logging live in `libraries/` to avoid hidden coupling across services.
- `artifacts/`, `research_artifacts/`, and `storage/` are kept distinct on purpose even though only `artifacts/` is operational today.

## Week 2 Review Topics

These are the highest-value structural issues still open after Week 1:

- explicit snapshot selection across the research-to-portfolio chain
- first-class instrument and security reference contracts
- persisted review-state transitions and promotion gates
- harder adversarial temporal and replay tests
- persistent audit storage and tamper-evidence strategy

## How Future Phases Build On This

Future work should extend the platform in this order:

1. parsing and evidence extraction with traceable spans over the normalized artifacts
2. first research artifact flow from evidence to hypothesis, critique, brief, and memo skeleton
3. review-gated feature computation and signal generation with temporal controls
4. backtesting and eval harnesses with strict out-of-sample discipline
5. paper portfolio construction and simulated execution under risk review
6. real provider connectors once the local artifact flow is stable

The rule for future contributions is simple: preserve the boundaries, preserve provenance, preserve temporal correctness.
