# Day 2 Plan

## Goal

Day 2 should make the first artifact flow real: from a source document to evidence-bearing research objects that can be inspected end to end.

## Priority 1: Document Ingestion Connectors

- implement a local file ingestion adapter for filings, transcripts, and news fixtures
- implement a connector interface for future SEC, transcript vendor, and news provider adapters
- persist `SourceReference` and `Document` artifacts to local file-backed storage under `artifacts/`
- record ingestion audit events automatically

## Priority 2: Sample Fixture Data

- add representative fixtures for one filing, one earnings call transcript, and one news item
- include realistic timestamps and metadata edge cases
- add expected normalized outputs for regression testing

## Priority 3: Filing Parsing Pipeline

- build the first normalization pipeline for filing HTML or text
- extract sections and evidence spans with stable offsets
- create parser tests against golden fixtures
- surface parsing confidence and provenance in outputs

## Priority 4: Transcript Normalization

- split prepared remarks and Q&A
- extract speakers and section boundaries
- create `EvidenceSpan` outputs with speaker labels and timestamps where available
- add evaluation fixtures for speaker attribution failures

## Priority 5: Source Reference Extraction

- populate `SourceReference` consistently from all supported fixture types
- normalize publisher, external IDs, published timestamps, and retrieval timestamps
- add duplicate detection logic based on source metadata and content hash

## Priority 6: First Research Artifact Flow

- wire the orchestrator to run ingestion -> parsing -> hypothesis generation on fixture data
- create one source-linked `Hypothesis`
- create one source-linked `CounterHypothesis`
- generate a stub `Memo` that cites the hypothesis and counter-hypothesis
- emit audit events for each stage

## Execution Notes

- keep persistence simple and local on Day 2
- do not add a database unless fixture volume makes file-backed storage unacceptable
- keep live trading disabled
- do not introduce backtesting claims before temporal fixtures and snapshot logic exist
