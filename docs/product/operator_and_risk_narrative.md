# Operator And Risk Narrative

## What The System Is Today

The repo provides a local operator-facing workflow for review queue management, proposal risk checks, construction inspection, paper-trade approval, paper-ledger tracking, and deterministic reporting.

It is not an automated execution stack. Operator judgment still matters, and the current design keeps that visible.

## What Is Genuinely Strong

- Reviewable objects are explicit: research briefs, signals, portfolio proposals, and paper trades each have review context and decisions.
- Portfolio construction now records inclusion, exclusion, constraint pressure, and sizing rationale instead of silently mapping signals into positions.
- Risk review is inspectable and can see validation, construction, reconciliation, and proposal context.
- Approved paper trades can now become tracked paper positions with lifecycle events, followups, and outcome attribution.
- Daily reporting and queue summaries give operators a digestible surface without replacing source artifacts.

## What Is Still Limited

- Some policy boundaries remain soft because readiness artifacts are inspectable but not yet universally gate-enforcing.
- Paper-ledger marks, closes, and outcomes still require manual or local inputs.
- There is no real execution venue, holdings engine, or broker feedback.
- The system still depends on local artifact roots and explicit operator context more than a mature multi-user platform would.

## Why The Architecture Matters

Risk and operator workflows are credible only when they preserve context:

- risk checks must retain upstream artifact linkage
- review decisions must remain auditable
- proposal summaries must preserve what was rejected and why
- paper outcomes must link back to research and prior warnings

That architecture matters because it makes accountability possible. Operators can inspect the chain rather than relying on one opaque recommendation object.

## Why This Is Not A Shallow AI Wrapper

The operator surface is not a narrative veneer over raw model outputs. It is built from typed review, risk, construction, reconciliation, ledger, and reporting artifacts.

The repo now exposes:

- explicit review queues and context loading
- proposal scorecards and risk summaries
- construction decisions and binding constraints
- paper-ledger states, outcomes, and followups

That is a more serious operator model than “AI says buy, human clicks approve.”

## Near-Term Milestones

1. Make high-severity validation, reconciliation, evaluation, and paper-ledger followups policy-driving for downstream readiness.
2. Complete snapshot-native selection so proposal and review context are less dependent on local latest-artifact loading.
3. Strengthen operator attention handling for unresolved conflicts, followups, and outcome gaps.
4. Improve tradable-identity handling before broadening paper-ledger or portfolio complexity.

## Supporting Proof Surfaces

- [Operator Review Workflow](./operator_review_workflow.md)
- [Portfolio Construction V2](../risk/portfolio_construction_v2.md)
- [Constraint Engine](../risk/constraint_engine.md)
- [Paper Ledger And Outcomes](../risk/paper_ledger_and_outcomes.md)
- [`services/operator_review/service.py`](../../services/operator_review/service.py)
- [`tests/integration/test_paper_ledger_workflow.py`](../../tests/integration/test_paper_ledger_workflow.py)
