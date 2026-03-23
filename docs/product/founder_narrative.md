# Founder Narrative

## What The System Is Today

ANHF Research OS is a local, deterministic research operating system for turning raw fixtures into typed research artifacts, review-bound portfolio proposals, and approval-gated paper-trade candidates.

It is not a live trading system. It is not a brokerage integration. It does not claim alpha. The current product value is workflow discipline: the system forces research, risk, review, and paper execution into explicit artifacts instead of loose notes and hidden spreadsheets.

## What Is Genuinely Strong

- The artifact chain is real and inspectable: ingestion, parsing, research, features, signals, portfolio construction, risk review, paper-trade candidates, paper ledger, and reporting all persist typed objects.
- Review boundaries are explicit. Signals do not become paper trades without a human decision path.
- Provenance and timing are first-class. The repo is structurally stronger than a thin AI wrapper because it treats timestamps, source linkage, and review state as core product surfaces.
- The interface layer is now coherent enough to demo honestly through `anhf`, `make demo`, `make daily-run`, and the local API.

## What Is Still Limited

- The repo is still local-first and filesystem-backed.
- There is still no downstream reviewed-and-evaluated eligibility gate.
- Snapshot-native selection is still incomplete across the full chain.
- Paper trading is still paper-only bookkeeping, not execution realism.
- This is not yet a production control plane or a source of market-edge claims.

## Why The Architecture Matters

The commercial argument is not “AI reads filings.” That can be copied quickly and usually collapses into an untrustworthy demo. The stronger wedge is a system that turns research into reviewable and auditable operating objects:

- typed research artifacts instead of chat logs
- explicit review queue state instead of informal handoff
- explicit proposal and risk artifacts instead of one opaque score
- paper-first execution and outcomes instead of premature live-trading claims

That architecture matters because it supports a more credible product surface for internal teams, allocators, and future compliance-minded buyers.

## Why This Is Not A Shallow AI Wrapper

The repo separates evidence from hypotheses, hypotheses from features, features from signals, signals from proposals, and proposals from approved paper trades. That separation is expensive to build and hard to fake.

The system is strongest where shallow wrappers are weakest:

- explicit schemas instead of UI-only state
- persisted provenance instead of implied lineage
- review gating instead of silent automation
- deterministic reporting and scorecards instead of narrative-only summaries
- paper-ledger and outcome loops instead of one-shot demo objects

## Near-Term Milestones

1. Make eligibility, evaluation, reconciliation, and paper-ledger followups policy-driving instead of merely inspectable.
2. Complete snapshot-native artifact selection across the research-to-portfolio chain.
3. Add a first-class instrument and security reference layer so tradable identity is not overloaded onto company identity.
4. Keep the external interface honest while preserving the internal typed-artifact discipline.

## Supporting Proof Surfaces

- [Proof Artifact Inventory](./proof_artifact_inventory.md)
- [Project Maturity Scorecard](./project_maturity_scorecard.md)
- [End-To-End Demo](./end_to_end_demo.md)
- [API And Interface Contracts](./api_and_interface_contracts.md)
- [Portfolio Construction V2](../risk/portfolio_construction_v2.md)
- [`pipelines/demo/end_to_end_demo.py`](../../pipelines/demo/end_to_end_demo.py)
