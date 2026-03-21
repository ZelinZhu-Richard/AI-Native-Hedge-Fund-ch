# Entity Resolution Contracts

## Purpose

Day 16 adds a dedicated entity-resolution layer around the existing canonical `company_id`.

The goal is not a knowledge graph. The goal is to make cross-source company identity:

- explicit
- inspectable
- conservative under ambiguity
- traceable through provenance and stored decisions

## Canonical Identity Strategy

The current canonical company key remains `Company.company_id`.

Current construction rule:

- use `CIK` when present
- otherwise use deterministic stable identity parts such as ticker, legal name, and country of risk

Day 16 does not replace `Company`. It adds `EntityReference` as a wrapper that makes alias state, cross-source links, and latest resolution decisions explicit.

## Primary Artifacts

### `EntityReference`

Canonical wrapper around one `company_id`.

Carries:

- canonical legal name
- primary ticker and exchange when known
- identifier set such as `cik`, `isin`, `lei`, `figi`
- active flag
- linked alias IDs
- linked cross-source IDs
- latest resolution decision ID

### `CompanyAlias`

Preserves observed company-name variants without rewriting canonical identity.

Current alias kinds:

- `legal_name`
- `former_name`
- `source_name`
- `trade_name`

### `TickerAlias`

Preserves ticker and vendor-symbol variants without treating them as canonical identity.

### `CrossSourceLink`

Attaches exact source-facing identifiers back to one canonical company.

Current identifier kinds:

- `cik`
- `isin`
- `lei`
- `figi`
- `ticker`
- `legal_name`
- `vendor_symbol`

### `DocumentEntityLink`

Links one normalized document, headline/body mention, or inherited evidence bundle back to a canonical company.

Current scopes:

- `document_metadata`
- `headline_mention`
- `body_mention`
- `evidence_inherited`

### `ResolutionDecision`

First-class deterministic decision artifact.

Current statuses:

- `resolved`
- `ambiguous`
- `unresolved`

### `ResolutionConflict`

First-class explicit conflict artifact.

Current conflict kinds:

- `multiple_candidates`
- `metadata_mismatch`
- `alias_collision`
- `missing_metadata`

## Confidence And Ambiguity

Current confidence labels:

- `high`
- `medium`
- `low`
- `ambiguous`
- `unresolved`

Important rule:

- ambiguity is not a note
- unresolved is not a silent fallback
- both must be persisted as structured outputs

## Deterministic Matching Precedence

Current source-metadata matching precedence:

1. exact `cik`
2. exact `figi`
3. exact `isin`
4. exact `lei`
5. exact `ticker + exchange`
6. exact normalized legal name
7. exact preserved company-name alias

Current document-text matching precedence:

1. canonical `document.company_id`
2. source-carried company metadata
3. exact unique alias match in title or headline
4. exact unique alias match in parser-owned body text

Current rules are deliberately conservative:

- no fuzzy string similarity
- no embedding retrieval
- no probabilistic tie-breaking
- no forced winner when more than one candidate remains

## Ambiguity Handling

The resolver preserves ambiguity explicitly for:

- multiple ticker aliases across exchanges
- company name changes
- alias collisions
- partial metadata
- missing metadata
- parser-carried company IDs that contradict document resolution

Ambiguous or unresolved documents may still be stored and parsed, but they must not be silently treated as company-resolved inputs.

## Downstream Contract

Downstream systems still use `company_id`.

Day 16 clarifies what that means:

- it is a canonical entity-resolution-backed company key
- it is not a raw ticker string
- it is not a vendor symbol
- downstream services should not perform their own entity matching

Current downstream dependencies include:

- research artifacts
- features
- signals
- position ideas
- portfolio proposals
- experiments
- monitoring summaries

## Known Limits

- no instrument or security master yet
- no corporate hierarchy modeling
- no broad entity extraction or NER
- no manual resolution console yet
- upstream canonical company records can still reflect last-write-wins source updates; Day 16 preserves aliases and conflicts but does not yet introduce a full canonical mastering workflow
