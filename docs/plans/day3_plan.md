# Day 3 Plan

## Goal

Turn normalized source artifacts into the first reviewable evidence objects.

Day 2 established local fixture intake, deterministic IDs, UTC-normalized canonical objects, and raw-versus-normalized storage separation. Day 3 should use that substrate to produce reusable evidence instead of summaries.

## Priority 1: Filing And Transcript Segmentation

- split normalized filings into coarse sections
- split transcripts into prepared remarks and Q&A
- preserve stable offsets or section boundaries
- attach speaker labels where available

## Priority 2: Evidence Extraction

- emit `EvidenceSpan` from normalized documents
- retain `document_id`, `source_reference_id`, and offsets
- keep extraction outputs machine-readable and reviewable
- reject extraction outputs that cannot point back to source text

## Priority 3: Parsing Artifact Layout

- define where parser outputs live relative to normalized documents
- keep parser outputs separate from raw and normalized layers
- add local file-backed persistence for parsed sections and evidence spans

## Priority 4: Quality Checks

- add fixture-based parser regression tests
- test offset validity and speaker attribution
- add failure cases for ambiguous speakers and incomplete sections

## Priority 5: Traceability And Audit

- emit structured audit events for ingestion and parsing stages
- attach workflow run IDs to parsing outputs
- start recording dataset and artifact lineage beyond fixture-path notes

## Success Criteria

- one filing fixture produces traceable sections and evidence spans
- one transcript fixture produces traceable speaker-linked evidence spans
- parser outputs remain point-in-time safe and source-linked
- tests catch timestamp drift, offset bugs, and provenance loss

## Non-Goals

- no feature engineering
- no hypothesis generation yet
- no backtesting
- no live integrations beyond the existing local fixture path
