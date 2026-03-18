# Week 1 Review

## Top Strengths

- The domain layering is real: ingestion -> parsing -> research -> features -> signals -> backtesting -> portfolio proposals -> paper trades.
- Typed schemas are broad and disciplined enough to make hidden coupling harder.
- The local workflows are deterministic and fixture-backed, which makes the repo testable instead of performative.
- Temporal discipline is explicit in the backtesting boundary and now partially enforced upstream through `as_of_time` cutoffs.
- There is still no live broker path or autonomous execution path.

## Top Weaknesses

- Upstream workflows are still only cutoff-aware, not snapshot-native.
- The repo still duplicates child artifacts inside parent artifacts while also storing them separately.
- Instrument identity is still weaker than it should be; too much downstream logic still leans on ticker strings.
- Review-state persistence exists structurally but is still shallow relative to what a real multi-user workflow will need.
- The runtime storage story was easy to misread until Week 1 hardening clarified `artifacts/`, `storage/`, and `research_artifacts/`.

## Critical Risks

- Omitting `as_of_time` still leaves the repo on latest-artifact semantics, which is useful for local development but unsafe for replay.
- Candidate signals can still flow downstream into exploratory backtests and proposals; they remain visibly provisional, but the promotion gate is not real yet.
- Audit logs are now persisted locally, but there is still no tamper-evident ledger or durable review-state model.
- The system still lacks a first-class instrument and security reference contract.

## Exact Fixes Made

- added explicit `as_of_time` support to feature mapping, signal generation, and portfolio workflows
- added upstream loader filtering by artifact `created_at`, signal `effective_at`, and feature `available_at`
- added notes that make latest-artifact loading explicit as a local-development convenience, not replay-safe behavior
- made `AuditLoggingService` persist local `AuditLog` artifacts under `artifacts/audit/`
- emitted audit events from research, feature mapping, signal generation, backtesting, and portfolio review workflows
- replaced placeholder API list endpoints with artifact-backed reads
- clarified runtime storage semantics in the repo docs and added `artifacts/README.md`
- refreshed stale Week 1 docs and metadata

## Issues Deferred

- first-class instrument or security master
- removal of parent/child artifact duplication
- trade-level approval workflow service
- snapshot-native replay across the full research-to-portfolio chain
- durable multi-user review workflow persistence

## Week 2 Priorities In Order

1. Replace cutoff-only selection with explicit artifact and snapshot selection across research, signals, backtests, and proposals.
2. Build real review-state persistence and promotion gates between candidate and validated artifacts.
3. Introduce a first-class instrument and security reference contract so downstream workflows stop leaning on ticker strings.
4. Expand adversarial temporal and replay tests for multi-generation artifact sets.
5. Harden auditability beyond local files toward durable, review-aware event persistence.
