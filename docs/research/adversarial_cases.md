# Adversarial Cases

## Purpose

Day 13 adds the first explicit adversarial case library for the research OS.

These cases are designed to answer:

- what weak behavior can be triggered intentionally
- which structural gaps are already detectable
- which bad states still need stronger downstream enforcement

They are not meant to simulate all real-world errors.

## Current Case Families

### Missing provenance

Clone a downstream artifact and strip usable provenance fields such as:

- `processing_time`
- `transformation_name`
- source or upstream linkage

Expected guardrail:

- `required_provenance_present`

### Contradictory evidence ignored

Keep a reviewable research artifact, inject stronger certainty language, and pair it with contradictory or weak support.

Expected guardrail:

- `claim_strength_matches_support`

### Timestamp corruption

Corrupt an otherwise valid signal or time window so expiry or cutoff ordering becomes invalid.

Expected guardrail:

- `timestamp_ordering_valid`

### Review bypass

Promote a proposal or trade into a stronger status while removing the review state that should justify it.

Expected guardrails:

- `review_bypass_detected`
- `paper_trade_approval_state_complete`

### Unsupported causal or recommendation claims

Inject narrow overstrong language such as “guaranteed”, “must buy”, or “proves” into low-support or low-confidence summaries.

Expected guardrail:

- `claim_strength_matches_support`

### Weak lineage

Remove exact feature, evidence, or research-artifact lineage from a signal clone.

Expected guardrail:

- `required_evidence_present`

### Empty extraction flowing downstream

Force parsing output to empty while a downstream signal still exists.

Expected guardrail:

- `non_empty_extraction_required_for_downstream`

### Missing experiment references

Remove config and dataset references from a recorded experiment.

Expected guardrail:

- `evaluation_references_complete`

## Failure Handling

When a case exposes a weakness, the system records:

- a `GuardrailViolation`
- one `SafetyFinding`
- one `RedTeamCase`
- a monitoring `RunSummary`
- alerts when the suite status is failed or attention-required

Failures are stored as artifacts, not buried in notes.

## Current Limitations

- case selection is deterministic and local; it is not yet operator-configurable
- coverage is structural, not statistical
- phrase-based unsupported-language checks are intentionally conservative
- the suite does not yet red-team every workflow boundary or every snapshot-selection path

## Honest Interpretation Rule

A passing adversarial case only means the current deterministic check did not detect the injected weakness.

It does not mean:

- the workflow is correct in production
- the model is safe
- the research output is trustworthy
- the downstream artifact is promotion-ready
