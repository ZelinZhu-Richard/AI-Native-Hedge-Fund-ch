# Evidence Extraction Notes

## What Later Agents Can Trust

The Day 3 evidence layer is designed to be narrow but trustworthy.

Later agents can rely on these properties:

- `EvidenceSpan.text` is an exact source slice, not a summary
- `start_char` and `end_char` resolve against `ParsedDocumentText.canonical_text`
- `segment_id` points to a concrete parser-owned segment
- extracted claims, guidance changes, risk factors, and tone markers all carry explicit evidence links
- provenance records identify the extraction transformation and source reference

## What Later Agents Must Not Assume

Later agents must not assume:

- extraction completeness
- financial importance ranking
- that every useful sentence was extracted
- that every missing risk or guidance artifact means the source contained none
- that tone markers are sentiment scores

## Current Behavior

Current extraction is deterministic and lexical.

It does:

- sentence-level span extraction
- modest claim classification
- explicit guidance/outlook change detection
- explicit risk-language detection
- narrow cue-phrase tone markers

It does not:

- paraphrase
- reason across multiple sentences
- infer unsupported implications
- score conviction
- generate research theses

## Good Downstream Usage

Good downstream usage patterns:

- use `EvidenceSpan` and `DocumentSegment` as the citation layer
- use extracted claims as candidate inputs to hypothesis generation, not as finished research
- require human or agent review before promoting evidence-derived claims into features
- treat sparse extraction as a filter for reliable signals, not as a full document understanding system

## Bad Downstream Usage

Bad downstream usage patterns:

- quoting `statement` fields as if they were analyst conclusions
- turning tone markers into trading signals directly
- using missing extraction as negative evidence
- ignoring provenance or exact offsets
- rewriting extracted statements before citing them

## Known Edge Cases

- transcript headers that do not follow `Name, Role:` formatting
- headlines without punctuation
- sentences with multiple cue types
- implicit guidance without the words `guidance` or `outlook`
- risk language expressed only through context rather than explicit wording
