# Daily System Reporting

## Purpose

`DailySystemReport` is the operator-facing summary produced from the daily orchestration `operations_summary` step.

It exists to summarize the current local system state without smoothing over missing data, unresolved followups, or validation problems.

## Inputs

The daily report currently draws from:

- recent `RunSummary` artifacts
- open or recent `AlertRecord` artifacts
- current `ServiceStatus` derivations from monitoring
- one persisted `ReviewQueueSummary`
- recent `DailyPaperSummary` artifacts when they exist
- open `ReviewFollowup` artifacts from the paper ledger
- recent `ProposalScorecard` artifacts
- recent `ExperimentScorecard` artifacts

During the daily workflow, the portfolio step now generates and persists the current run's `RiskSummary` and `ProposalScorecard` before the operations-summary step builds the daily report.

## Output Shape

The report records:

- source artifact IDs
- run summary IDs
- alert record IDs
- service-status snapshots
- one review-queue summary ID
- daily paper-summary IDs
- open review-followup IDs
- proposal-scorecard IDs
- experiment-scorecard IDs
- notable failures
- attention reasons
- missing-information flags

## Grounding And Honesty

The daily report is intentionally conservative.

It does not:

- claim the system is healthy because one run succeeded
- hide missing paper summaries or missing scorecards
- replace monitoring artifacts with prose
- infer maturity from green checks alone

It does:

- preserve alert and followup pressure
- carry forward run failures and attention reasons
- record missing coverage explicitly
- keep links back to the underlying artifacts

## Current Behavior

The daily orchestration workflow now persists:

- `RiskSummary`
- `ProposalScorecard`
- `ReviewQueueSummary`
- `DailySystemReport`

under `artifacts/reporting/`.

The default daily path will often still end in `attention_required` because paper-trade creation remains review-gated. In the current repo, that status means a visible manual-attention stop, so operators should inspect notes and manual-intervention requirements to distinguish a healthy review-bound stop from a blocked stop. The daily report should make that state easier to inspect, not make it disappear.

## Current Simplifications

- report generation is deterministic and local only
- no UI dashboard exists yet
- experiment-scorecard selection is still latest-artifact oriented within the current workspace
- service capability summaries are still lightweight and descriptive
- paper-ledger sections stay sparse when no approved paper trades have been admitted

## Operator Use

The daily report is useful for:

- checking whether the daily workflow failed or stopped at a review gate
- seeing whether alerts or open followups are accumulating
- spotting missing coverage such as absent paper summaries or absent scorecards
- deciding which source artifacts to inspect next

It should be treated as an operational summary, not as a replacement for proposal review, evaluation review, or validation review.
