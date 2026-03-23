# Known Limitations

## Purpose

This doc lists the major current limitations that should stay visible during review, demos, and external explanation.

These are not bugs to hide with wording. They are real boundaries in the current release candidate.

## Data Quality And Contract Enforcement

- Data-quality gates exist, but they do not replace the missing downstream eligibility gate.
- Refusal and quarantine behavior are strongest at structural boundaries, not yet at every policy boundary.
- Some workflows still rely on local artifact-root conventions to find inputs.

## Temporal Selection And Replay Discipline

- Full selected-artifact or snapshot-native downstream selection is not complete across research -> feature -> signal -> portfolio.
- Some loaders remain cutoff-aware or latest-artifact-aware instead of being driven by an explicit selected slice.
- The repo is better on timing correctness than on replay-complete selection discipline.

## Evaluation And Readiness

- Evaluation, reconciliation, reporting, and paper-ledger followups are mostly inspectable rather than policy-driving.
- The repo still lacks a true reviewed-and-evaluated downstream eligibility artifact.
- Backtests remain exploratory and should not be treated as proof of signal validity.

## Portfolio And Risk

- Portfolio construction is deterministic and inspectable, but still heuristic.
- There is no first-class instrument/security layer yet, so company and ticker identity still carry too much tradable meaning.
- The risk layer is a serious local control surface, not institutional risk infrastructure.

## Paper Trading And Ledger

- Paper trades remain paper-only and approval-gated.
- Paper-ledger marks, closes, and daily summaries still rely on manual or local-input-driven updates.
- Placeholder PnL is bookkeeping only, not broker-verified performance reporting.

## Reporting And Interface

- Reporting artifacts are grounded and useful, but they do not replace source truth.
- The API and CLI are local inspection surfaces, not a secure multi-user control plane.
- `attention_required` is still the main visible stop-state enum, so reviewers must inspect notes and manual-intervention reasons to distinguish a healthy review gate from a harder blocked stop.

## Infrastructure And Operations

- The runtime is local-filesystem-backed.
- There is no durable job system, scheduler, or production incident tooling.
- The repo is strongest as a coherent local research OS, not as production deployment infrastructure.
