# Signal Generation Pipeline

Day 5 now provides a deterministic local pipeline that:

1. loads persisted Day 4 research artifacts
2. materializes candidate feature definitions, values, and features
3. generates candidate signals and score components
4. persists outputs under `artifacts/signal_generation/`

Current scope:

- only `text_only` is populated
- outputs are candidate-only and unvalidated
- no portfolio or execution logic lives here
