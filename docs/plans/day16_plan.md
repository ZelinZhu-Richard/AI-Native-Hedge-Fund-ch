# Day 16 Follow-On

## What Day 16 Added

Day 16 made entity identity explicit across ingestion and parsing by adding:

- `EntityReference`
- preserved company and ticker aliases
- cross-source identifier links
- deterministic `ResolutionDecision`
- explicit `ResolutionConflict`
- document and evidence-to-company linking

The system now preserves ambiguity instead of collapsing it silently.

## What Day 16 Did Not Add

- a security or instrument master
- fuzzy entity matching
- a manual resolution console
- full snapshot-native replay upstream
- downstream eligibility gating based on unresolved entity state

## Best Next Target

The exact next target should be a first-class instrument and security reference contract layered on top of these entity-resolution artifacts.

That work should:

1. separate issuer identity from tradable symbol identity
2. stop relying on raw ticker strings as the downstream bridge
3. support portfolio and paper-trade workflows with canonical instrument references
4. prepare the real reviewed-and-evaluated eligibility gate for downstream construction
