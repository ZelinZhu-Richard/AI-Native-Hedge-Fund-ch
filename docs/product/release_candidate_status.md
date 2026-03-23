# Release Candidate Status

## Purpose

This doc describes what the first 30-day build can honestly be treated as today.

The short version:

- it is a coherent and inspectable local research operating system
- it is not a production trading platform
- it is not a validated alpha engine
- it is not a finished downstream trust boundary

## Current Status

| Area | Status | What Is Real Today | Main Caveat |
| --- | --- | --- | --- |
| Ingestion and normalization | `real` | Fixture-backed ingestion, normalized documents, explicit timestamps, provenance, and data-quality gates. | Source coverage is still local-fixture heavy. |
| Evidence extraction | `real` | Structured evidence spans, bundle evaluation, and source linkage are implemented and tested. | Coverage is still narrow compared with a broader document universe. |
| Research workflow | `partial` | Evidence assessments, hypotheses, counter-hypotheses, briefs, and memo skeletons exist as typed artifacts. | Research-side reporting and downstream eligibility enforcement are still incomplete. |
| Feature and signal pipeline | `partial` | Candidate features, candidate signals, arbitration, and timing-aware lineage checks are real. | Candidate artifacts can still travel too far downstream without a true eligibility gate. |
| Backtesting and reconciliation | `partial` | Exploratory backtests, ablations, realism assumptions, and backtest-to-paper reconciliation are implemented. | Default prices are synthetic and reconciliation remains advisory. |
| Portfolio construction and risk | `partial` | Construction decisions, constraints, conflicts, attribution, stress tests, risk checks, and proposal scorecards are inspectable. | Construction is still heuristic and there is no first-class instrument/security layer. |
| Review workflow | `real` | Review queue, notes, assignments, review decisions, and approval-gated proposal/trade flow are implemented. | The operating model is still local and manual. |
| Paper-trade and ledger flow | `partial` | Approval-gated trade candidates, paper ledger admission, lifecycle events, outcomes, and followups are present. | No broker integration, no realistic execution engine, and marks/closes remain manual or local-input driven. |
| Monitoring, reporting, and interface | `partial` | Run summaries, health checks, daily reports, API/CLI manifest surfaces, and proposal/experiment scorecards are real. | Reporting is inspectable, but not yet policy-driving, and interfaces are local only. |
| Runtime and storage | `skeletal` | Local artifact roots are coherent enough to support deterministic runs and inspection. | Coordination still relies heavily on filesystem conventions rather than stronger selected-artifact infrastructure. |

## What The Release Candidate Actually Proves

- the repo can run deterministically from ingestion to a review-bound portfolio proposal
- the repo now has one stronger final proof path that extends the same workspace into an explicit approval-only paper-trade and paper-ledger appendix
- important artifacts are typed, persisted, and traceable
- validation, review, reporting, monitoring, and paper-ledger layers are real subsystems rather than slideware
- the local demo and daily workflow are honest enough for skeptical technical review

## What It Does Not Prove

- no true reviewed-and-evaluated downstream eligibility gate yet
- no full selected-artifact or snapshot-native enforcement yet
- no first-class instrument/security layer
- no live trading or broker execution
- no validated alpha and no validated market edge or performance claim
- no production operator or infrastructure maturity
