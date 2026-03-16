# Day 1 Evals Framework

## Purpose

Day 1 does not claim model performance. It defines how future work will be evaluated so the platform does not drift into unverifiable output quality or fabricated alpha narratives.

## Evaluation Philosophy

- Evaluate each stage independently before trusting end-to-end output.
- Prefer source-linked correctness over stylistic fluency.
- Treat temporal hygiene as a first-class eval dimension.
- Red-team failure modes early, especially where AI can overstate certainty.
- Any future alpha claim must survive strict out-of-sample testing and adversarial review.

## Evaluation Dimensions

### Extraction Accuracy

- document normalization correctness
- speaker attribution quality
- evidence span precision and recall
- source metadata preservation

### Provenance Completeness

- presence of source references
- presence of upstream artifact IDs
- explicit transformation versioning
- completeness of timestamp fields

### Agent Response Quality

- faithfulness to inputs
- explicit uncertainty handling
- action constraint compliance
- absence of fabricated evidence

### Hypothesis Usefulness

- falsifiability
- clarity of catalyst and invalidators
- strength of evidence linkage
- usefulness to a PM or analyst

### Counterargument Quality

- adversarial strength
- non-trivial disagreement with the base thesis
- evidence coverage of downside case
- surfacing of unresolved questions

### Feature Reliability

- stable definitions
- point-in-time availability correctness
- robustness to missing or delayed data
- schema and unit consistency

### Signal Stability

- sensitivity to small input changes
- calibration drift
- dependence on brittle features
- explainability of score movement

### Backtest Hygiene

- point-in-time data enforcement
- correct train/test splits
- no leakage across timestamps
- reproducibility from snapshot IDs and code versions

### Explainability

- recommendation traceability to evidence
- clarity of main drivers
- clarity of uncertainty
- clarity of risk objections

### Risk-Screen Coverage

- portfolio constraint coverage
- single-name concentration coverage
- liquidity and turnover coverage
- policy violation detection rate

### Latency

- ingestion-to-document registration time
- parsing time by artifact class
- hypothesis generation latency
- memo generation latency

### Failure Detection

- duplicate source detection
- conflicting timestamp detection
- provenance gaps
- model refusal or malformed output detection

### Red-Team Scenarios

- fabricated quote insertion
- look-ahead leakage through revised filings
- source mismatch across companies
- agent output that recommends live trading
- model output that hides uncertainty or contradicts evidence

## Day 1 Deliverables in Support of Evals

- explicit typed schemas for artifacts and timestamps
- service and agent boundaries that localize eval responsibility
- documentation for temporal semantics and prohibited actions
- audit and review entities that can later support evaluator attribution

## Future Implementation Guidance

- start with fixture-based golden datasets for parsing and evidence extraction
- add rubric-based review for hypotheses and memos
- add regression tests around temporal leakage scenarios
- require out-of-sample evaluation before any research artifact is promoted to signal research
- forbid production-facing performance claims without reproducible experiment metadata
