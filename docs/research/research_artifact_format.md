# Research Artifact Format

## Purpose

This document defines the Day 4 research artifact contract built on top of exact-span evidence.

The format is designed for:

- reviewability
- provenance
- uncertainty visibility
- clean downstream consumption

It is not designed to be polished memo prose or a signal payload.

## Core Artifacts

### `SupportingEvidenceLink`

This is the atomic research citation unit.

Required properties:

- exact `evidence_span_id`
- `document_id`
- `source_reference_id`
- optional upstream extracted artifact ID
- role: `support`, `contradict`, or `context`
- exact `quote`
- provenance

Rule:

- if a research artifact cites support or contradiction, it should do so through `SupportingEvidenceLink`

### `Hypothesis`

This is the primary thesis artifact.

Required content:

- concise thesis text
- research stance
- support links
- assumptions
- uncertainties
- invalidation conditions
- next validation steps
- review status
- provenance

Rules:

- support links must be non-empty
- hidden assumptions are not allowed
- support does not imply approval for feature work

### `EvidenceAssessment`

This is the honesty layer for support quality.

Required content:

- support grade
- support summary
- linked support IDs
- key gaps
- contradiction notes
- review status
- provenance

Rules:

- support grade must be explicit
- missing evidence must stay visible even when support looks promising

### `CounterHypothesis`

This is the structured critique artifact.

Required content:

- concise counter-thesis
- critique kinds
- contradictory or contextual evidence links when available
- challenged assumptions
- missing evidence
- causal gaps
- unresolved questions
- review status
- provenance

Rules:

- critique must contain a concrete basis
- vague skepticism is not enough

### `ResearchBrief`

This is the memo-ready structured review package.

Required content:

- company context summary
- core hypothesis
- counter-hypothesis summary
- support links
- counterarguments
- uncertainty summary
- next validation steps
- review status
- provenance

Rules:

- this is the main Day 4 review artifact
- it is upstream of `Memo`
- later feature work should consume structured research artifacts, not brief prose alone

### `Memo`

This remains a render target.

Day 4 usage:

- generated only as a draft skeleton
- derived from `ResearchBrief`
- not used as a decision engine input

## Provenance Rules

- every artifact must carry provenance
- every evidence-backed claim in a research artifact should resolve to exact source spans
- every downstream artifact should preserve upstream artifact IDs

## Review Rules

- all research artifacts default to human review
- approval for feature work is a separate state, not an implied consequence of a strong thesis
- unsupported narrative language should be rejected or rewritten into assumptions, gaps, or questions
