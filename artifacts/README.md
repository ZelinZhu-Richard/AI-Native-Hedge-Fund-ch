# Artifacts

`artifacts/` is the current local runtime materialization root.

This directory is where the repo's deterministic local workflows write their actual outputs during development and testing. It is not the long-term storage contract and it is not the review-bundle convention layer.

Current workflow roots live under:

- `artifacts/ingestion/`
- `artifacts/parsing/`
- `artifacts/research/`
- `artifacts/signal_generation/`
- `artifacts/backtesting/`
- `artifacts/portfolio/`
- `artifacts/audit/`

The distinction from the other top-level directories matters:

- `storage/` documents future persistent dataset-layout and storage conventions.
- `research_artifacts/` documents future human-review bundle conventions.
- `artifacts/` is the current local filesystem source of truth for generated runtime outputs.

Week 1 hardening note:

- upstream loaders may still use latest-artifact selection when `as_of_time` is omitted
- that behavior is a local-development convenience and is not replay-safe
- replay-safe workflows should pass explicit cutoffs or later snapshot identifiers
