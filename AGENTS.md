# Repository Agent Guide

## Mission

This repository is the Day 1 foundation for an AI-native hedge fund research OS. Contributions must improve rigor, reproducibility, explainability, modularity, and paper-trading safety.

## Core Expectations

- Prefer explicit contracts over implicit conventions.
- Keep service boundaries narrow and named by business responsibility.
- Treat every timestamp as meaningful. If semantics are unclear, document them before coding.
- Preserve a clear chain from raw source to derived recommendation.
- Default to human review when uncertainty is material.

## Coding Standards

- Use Python 3.11+ features conservatively and keep code readable.
- Use Pydantic models for boundary contracts.
- Keep functions and classes small enough that intent is obvious.
- Prefer enums, typed models, and named fields over loosely typed payloads.
- Use comments sparingly and only to explain non-obvious reasoning.
- Use structured logging hooks, never `print`.

## Architecture Rules

- Business logic belongs in `services/`, not in FastAPI routes.
- Shared contracts belong in `libraries/schemas/`.
- Shared primitives for time, config, IDs, and logging belong in `libraries/`.
- Agents may propose artifacts but must not bypass service boundaries.
- Audit logging must remain a first-class concern, not an afterthought.

## Naming Conventions

- IDs should be explicit and prefixed by entity type, for example `doc_...`, `hyp_...`, `trade_...`.
- Modules should be named for domain concepts, not framework patterns.
- Avoid generic names like `manager`, `handler`, or `processor` unless the responsibility is genuinely broad.

## Documentation Expectations

- Document assumptions, non-goals, and tradeoffs in the nearest relevant doc.
- Keep architecture docs aligned with code boundaries.
- If an interface is a stub, say what it will own later and what it intentionally does not do yet.

## Testing Requirements

- Add or update unit tests for new schema rules and utility helpers.
- Add integration tests for API contract changes.
- Do not merge hidden behavior changes without a test or an explicit documented reason.

## Temporal Correctness Rules

- Distinguish source event time, ingestion time, processing time, and effective time.
- No backtest or feature logic may access information unavailable at decision time.
- Derived artifacts must reference the snapshot or upstream artifacts they depend on.
- If temporal semantics are unknown, mark them unknown explicitly rather than guessing.

## Anti-Hallucination Rules

- Do not fabricate performance metrics, source coverage, or model accuracy.
- Do not invent evidence. Link every claim to a source reference or mark it as an unverified assumption.
- If a field is unknown, use a typed optional field and document the uncertainty.

## Financial Safety Rules

- No live trading integrations.
- No autonomous execution path.
- Every paper trade proposal must remain reviewable and blockable by a human.
- Risk checks are required before portfolio proposals and before paper trade simulation.

## Behavior Under Uncertainty

- Surface uncertainty directly in schemas, logs, and memos.
- Escalate to human review if evidence conflicts, provenance is incomplete, or risk signals disagree materially.
- Prefer partial but correct output over polished but unverifiable output.

## Tradeoff Documentation

- Record why a boundary exists if it is not obvious.
- Record what was deferred and why.
- Prefer visible assumptions over hidden convenience.
