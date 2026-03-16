# Storage

This directory defines storage layout intent and dataset metadata conventions for future phases.

Day 1 keeps storage abstract on purpose, but the architecture expects future separation between:

- raw source payload storage
- normalized document storage
- derived artifact storage
- dataset manifests and partitions
- audit/event storage

The canonical machine-readable metadata for that future layer starts in the storage-related schemas under `libraries/schemas/`.

Repository-level layout conventions:

- `storage/raw/` stores source payloads exactly as received
- `storage/normalized/` stores cleaned, parser-friendly representations
- `storage/derived/` stores machine-readable derived artifacts tied to provenance
- `storage/audit/` stores durable event and decision logs
