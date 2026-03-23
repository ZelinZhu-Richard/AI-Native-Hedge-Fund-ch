# Technical Narrative

## What The System Is Today

The repository is a coherent local platform with explicit service boundaries, typed schemas, orchestration entrypoints, review workflows, monitoring artifacts, reporting artifacts, and a cleaned interface layer.

It is strongest as an inspectable local system. It is not yet a production-scaled distributed platform.

## 30-Day Build Summary

- What is real today: the repo has a passing local proof path that spans research, proposal, review, reporting, audit, and an explicit approval-only paper-ledger appendix.
- What this audience can safely conclude: the architecture is serious enough for skeptical code and workflow review, with real typed boundaries and persisted artifacts.
- What this audience must not conclude: the repo is not production infrastructure, not selection-complete, and not policy-hard at the final eligibility boundary.
- Next-phase focus: make eligibility and selected-artifact enforcement structural before widening data or infra ambition.

## What Is Genuinely Strong

- Core domain objects are strongly typed across research, validation, backtesting, portfolio construction, paper-trading, ledger, and reporting layers.
- Services are separated by domain role instead of collapsing into one workflow module.
- Validation, refusal, and quarantine semantics now exist as explicit artifacts rather than only as exceptions or logs.
- Backtest-to-paper reconciliation, proposal scorecards, and paper-ledger outcome tracking make downstream inspection materially better than a typical demo stack.
- The CLI and API are now consistent enough to expose the platform honestly without inventing unsupported product surfaces.

## What Is Still Limited

- Persistence is still local-filesystem oriented rather than snapshot-native or database-backed.
- Service coordination still relies on artifact roots and local loading patterns in several paths.
- The repo has strong structural contracts, but the final policy-driving eligibility gate is still missing.
- There is still no first-class instrument master or realistic execution model.

## Why The Architecture Matters

This architecture matters because it preserves clarity under growth:

- schemas live separately from service implementations
- orchestration is separated from domain logic
- review and reporting artifacts do not replace source truth
- demo and API surfaces sit on top of the same underlying workflows

That keeps the repo extensible. Future researchers can add richer models or broader datasets without unpicking a monolith first.

## Why This Is Not A Shallow AI Wrapper

Most shallow wrappers hide important behavior in prompts and UI state. This repo does the opposite:

- agent outputs become typed artifacts
- important transitions create audit and monitoring records
- failure states are visible through validation gates, review state, and scorecards
- risk and portfolio construction are inspectable service layers, not buried post-processing

The value is not “we called a model.” The value is that the system preserves what happened, when, and why.

## Near-Term Milestones

1. Turn validation, reconciliation, evaluation, and paper-ledger followups into policy-driving readiness inputs.
2. Finish snapshot-native selection across research, feature, signal, and portfolio stages.
3. Reduce sibling-root inference and local implicit coordination further.
4. Add a first-class instrument/security layer before the proposal engine becomes more sophisticated.

## Supporting Proof Surfaces

- [System Narrative](./system_narrative.md)
- [Data Quality And Validation Gates](../contracts/data_quality_and_validation_gates.md)
- [Reporting And Scorecards](./reporting_and_scorecards.md)
- [API And Interface Contracts](./api_and_interface_contracts.md)
- [`services/data_quality/service.py`](../../services/data_quality/service.py)
- [`tests/integration/test_api.py`](../../tests/integration/test_api.py)
