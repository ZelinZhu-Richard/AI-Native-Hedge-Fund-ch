# Week 2 Review Plan

## Goal

Review the repo against what it now actually does, not what it hopes to do.

The review should use the end-to-end demo artifacts, the new narrative docs, and the existing architecture/risk/evaluation docs to answer whether the system is coherent, honest, and structurally disciplined.

## Review Topics

### 1. Demo Honesty

- does the end-to-end demo match the actual persisted artifacts
- does any doc overclaim what the demo proves
- are exploratory backtests and ablations clearly labeled as exploratory

### 2. Temporal And Reproducibility Discipline

- where are cutoffs explicit versus still convenience-based
- where does replay remain snapshot-aware versus only latest-artifact-safe
- do experiment and dataset references remain complete in the demo path

### 3. Lineage And Auditability

- can the demo trace evidence into hypotheses, features, signals, proposals, and paper trades
- do run summaries, audit logs, and review decisions tell a coherent story
- where do artifact summaries still hide too much detail

### 4. Review And Risk Control

- are review-bound states visible and preserved
- do proposals and paper trades remain clearly non-autonomous
- where could unsupported or weakly grounded artifacts still move downstream too easily

### 5. Monitoring And Failure Visibility

- are the major workflows now visible in run summaries
- do attention-required states surface clearly enough
- which important workflow failures would still be easy to miss

### 6. Structural Weaknesses To Recheck

- missing hard downstream eligibility gates
- incomplete snapshot-native selection
- missing instrument or security reference contract
- local-filesystem-only persistence
- deterministic research and signal heuristics that still need stronger evaluation boundaries

## Expected Review Outputs

- one honest strengths list
- one honest weaknesses list
- one concrete next-priority list for Week 3 planning
- explicit rejection of any claim the current demo cannot support
