# Day 4 Plan

## Goal

Make the evidence layer broader and more reusable without weakening its current exact-span guarantees.

## Priority 1: Better Segmentation

- improve filing section detection beyond a single `body` section
- add explicit prepared-remarks versus Q&A transcript boundaries
- support multi-paragraph news and transcript blocks more robustly

## Priority 2: Stronger Extraction Objects

- add structured numeric metric capture for explicit financial result claims
- add richer guidance topic normalization
- support explicit event and catalyst extraction where source language is concrete

## Priority 3: Better Eval Coverage

- add golden expected outputs for current fixtures
- measure extraction coverage by document kind
- add negative tests for malformed transcript headers and ambiguous guidance language

## Priority 4: Storage And Traceability

- add a manifest for parsing runs and document evidence bundles
- emit audit events for extraction runs
- record parser version and workflow run metadata more explicitly

## Priority 5: Prepare For Research Agents

- define the minimum evidence contract hypothesis agents may consume
- add bundle-loading helpers for orchestrator and agent services
- keep evidence and research-thesis layers separate
