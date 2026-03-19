# System Narrative

## What The System Actually Is

The repository is now a serious local research operating system scaffold.

It already has real typed contracts, persisted artifacts, review workflows, monitoring, evaluation, reproducibility metadata, and a coherent paper-only downstream path.

It is **not** a finished hedge fund platform. It is also not a shallow AI wrapper that glues a model call onto a dashboard and calls that “research.”

## Founder / Investor Lens

What is real now:

- the repo has a genuine end-to-end path from raw fixture data to reviewable paper-trade candidates
- every major layer has typed artifacts rather than loose text blobs
- the system already has explicit audit, review, risk, evaluation, monitoring, and red-team surfaces
- the architecture is intentionally designed to keep human review visible and avoid accidental autonomous trading

Why this is different from shallow wrappers:

- temporal correctness, lineage, and artifact structure are first-class
- candidate signals are separate from reviewed or validated states
- portfolio proposals and paper trades are explicit review objects, not hidden side effects
- baseline comparisons and evaluation artifacts exist to keep the system honest

What is still not there:

- no production connectors
- no validated alpha claims
- no hard promotion gates across the full chain
- no production operator UI

## Engineer / Research-Platform Lens

Current strengths:

- domain separation is real: ingestion -> parsing -> research -> features -> signals -> backtesting -> portfolio -> review
- schemas are broad and serious enough to support auditability and extension
- experiment, evaluation, monitoring, and red-team layers now give the repo operational depth instead of only pipeline depth
- the end-to-end demo path is reproducible and isolated under its own artifact root

Current weaknesses:

- snapshot-native selection still is not end to end
- some service and pipeline boundaries still mix orchestration with persistence
- instrument identity still leans too much on company or ticker shortcuts
- local filesystem persistence is useful but not durable infrastructure
- downstream gating is still convention-heavy in places

## Quant / Risk Lens

What is credible:

- point-in-time concerns are explicit in the contracts
- backtests are exploratory and documented as such
- baseline ablations are mechanical comparisons, not winner declarations
- risk checks and review decisions are explicit artifacts
- paper trades are clearly paper-only

What is not yet trustworthy enough:

- signal quality is still deterministic and skeletal
- price fixtures are synthetic
- there is no realistic transaction model, liquidity model, or portfolio optimizer
- reviewed state exists but is not yet a full hard eligibility gate
- there is no basis yet for performance extrapolation

## Strongest Architectural Decisions

- typed artifacts over loose text
- explicit provenance and timestamps
- separation of candidate, review, and validation semantics
- paper-trading-only downstream posture
- monitoring, audit, evaluation, and red-team work added before any live execution idea

## Weakest Open Gaps

- incomplete downstream enforcement
- incomplete snapshot-native replay
- no first-class security master or instrument reference layer
- local-only persistence and operator workflow
- deterministic heuristics still dominate the research and signal stack

## Next Milestones After Week 2

1. hard eligibility gates for reviewed and evaluated artifacts
2. snapshot-native selection across the full research-to-portfolio chain
3. first-class instrument identity and reference data
4. stronger operator attention queues for failed, stale, or blocked workflows
5. broader adversarial and replay testing around downstream enforcement
