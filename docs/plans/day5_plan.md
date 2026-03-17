# Day 5 Plan

## Goal

Turn the Day 4 research artifacts into a real promotion boundary for later feature work without jumping into signals prematurely.

## Priority 1: Human Review And Promotion Gate

- attach `ReviewDecision` records to `Hypothesis`, `EvidenceAssessment`, `CounterHypothesis`, and `ResearchBrief`
- define the exact conditions for `approved_for_feature_work`
- persist review decisions and audit events for research artifacts

## Priority 2: Reviewed-Research Input Contract For Features

- define how approved research artifacts map into candidate feature definitions
- require exact evidence linkage and explicit availability timestamps for any derived feature candidate
- keep feature-candidate generation separate from final signal scoring

## Priority 3: Better Research Eval Coverage

- add golden expected outputs for the Apex fixture workflow
- add negative fixtures with thin or contradictory support
- add checks for unsupported claims leaking into briefs or memo skeletons

## Priority 4: Broader Research Context

- support multiple hypotheses per company when evidence genuinely supports them
- improve document weighting so product-launch context does not dominate core operating evidence
- add better contradiction handling between support and critique artifacts

## Exact Day 5 Target

Build the human review and promotion gate for research artifacts, then define the first reviewed-research-to-feature contract.
