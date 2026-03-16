# Storage

This directory defines storage layout intent and dataset metadata conventions for future phases.

Day 1 keeps storage abstract on purpose, but the architecture expects future separation between:

- raw source payload storage
- normalized document storage
- derived artifact storage
- dataset manifests and partitions
- audit/event storage

The canonical machine-readable metadata for that future layer starts in the storage-related schemas under `libraries/schemas/`.
