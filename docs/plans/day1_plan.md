# Day 1 Plan

## Goal

Build the Day 1 foundation of the AI-native hedge fund research OS.

Day 1 is about operating-system quality, not alpha claims, not flashy demos, and not autonomous execution.

The outcome should be a serious local monorepo that can support disciplined future work across ingestion, evidence extraction, research workflows, feature generation, backtesting, risk review, and paper trading.

## Core Principles

- no live trading
- human-in-the-loop by default
- no fake results or fabricated performance
- full provenance for important outputs
- strict temporal discipline
- modular architecture and swappable components
- explainability over mystique
- research-first and paper-trading-first design

## Priority 1: Repo Scaffold And Architecture

- create a disciplined monorepo layout for apps, services, agents, libraries, pipelines, docs, tests, storage, and research artifacts
- reserve explicit homes for raw data, normalized data, derived artifacts, and reviewable outputs
- make boundaries obvious between ingestion, parsing, evidence, hypotheses, features, signals, risk, portfolio, memo, paper execution, and audit
- keep the structure future-proof without overbuilding infrastructure on Day 1

## Priority 2: Root Control Docs

- create a serious `README.md` that explains what the repo is, what Day 1 includes, what does not exist yet, and how future phases build on the foundation
- create `AGENTS.md` with coding standards, architecture rules, testing expectations, temporal correctness rules, anti-hallucination rules, and financial safety rules
- create architecture docs that explain service boundaries, agent boundaries, data flow, control flow, provenance, evals, risk controls, and human approval placement

## Priority 3: Core Typed Schemas

- define realistic Pydantic contracts for core Day 1 entities including:
  - `Document`
  - `Filing`
  - `EarningsCall`
  - `NewsItem`
  - `MarketEvent`
  - `Company`
  - `SourceReference`
  - `EvidenceSpan`
  - `Hypothesis`
  - `CounterHypothesis`
  - `Feature`
  - `Signal`
  - `SignalScore`
  - `PositionIdea`
  - `PortfolioConstraint`
  - `PortfolioProposal`
  - `RiskCheck`
  - `BacktestRun`
  - `Experiment`
  - `Memo`
  - `AgentRun`
  - `AuditLog`
  - `ReviewDecision`
  - `PaperTrade`
  - `DataSnapshot`
- require explicit IDs, explicit timestamps, provenance where relevant, status enums where relevant, and confidence or uncertainty where relevant

## Priority 4: Service Boundaries And Stubs

- create coherent service interfaces or stubs for:
  - ingestion
  - parsing and extraction
  - research orchestration
  - feature store
  - signal generation
  - backtesting
  - risk engine
  - portfolio construction
  - paper execution
  - memo generation
  - audit logging
- keep responsibilities explicit and minimal
- avoid fake business logic while still making interfaces concrete and typed

## Priority 5: API And Local Dev Setup

- add a minimal FastAPI app with health and version endpoints plus placeholder research-facing endpoints
- configure local development with:
  - `pyproject.toml`
  - `ruff`
  - `mypy`
  - `pytest`
  - `pre-commit`
  - `.env.example`
  - `Makefile`
- ensure the repo runs locally with a simple setup flow

## Priority 6: Data Contracts, Risk Baseline, And Eval Philosophy

- define canonical ID semantics
- define event time vs publication time vs ingestion time vs processing time
- define raw vs normalized vs derived data semantics
- define provenance and evidence-linking expectations
- document leakage and look-ahead guardrails for future backtests
- document the paper-trading-first compliance posture and prohibited actions
- document what Day 1 evals should focus on before any future alpha claims are entertained

## Priority 7: Tests And Quality Baseline

- add schema validation tests
- add import and service smoke tests
- add API boot tests if an API app exists
- add at least one helper utility test
- keep linting, typing, and tests green from Day 1 onward

## Success Criteria

- the repo boots locally
- schemas validate cleanly
- architecture is understandable and documented
- service boundaries are explicit
- risk and temporal rules are written down early
- the codebase looks like the first day of a real research platform, not a hackathon demo

## Non-Goals

- no live brokerage integration
- no autonomous trading path
- no made-up backtest or performance claims
- no fake “AI reads filings and makes money” logic
- no investor-persona roleplay agents
- no overengineered infrastructure before the research substrate exists

## Carry-Forward To Day 2

Once Day 1 is complete, the next focus should be:

- real local ingestion and normalization
- fixture datasets
- canonical source references and document IDs
- explicit raw and normalized artifact persistence
- first trustworthy input layer for parsing and evidence extraction
