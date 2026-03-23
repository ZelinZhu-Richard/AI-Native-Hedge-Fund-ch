# Day 29 Plan

## Goal

Package the current repo for external scrutiny without adding fluff, unsupported product claims, or fake maturity.

## Deliverables

- audience-specific narrative docs for founder, technical, quant/research, and operator/risk readers
- a proof artifact inventory grounded in real code, docs, tests, and interface surfaces
- an honest project maturity scorecard
- a concise external demo script with safe and unsafe claims
- a lightweight drift check that keeps the new proof package tied to the live repo

## Chosen Defaults

- documentation-first pass, not a new service or schema build
- all claims anchored to current CLI, API, docs, and tests
- no area rated above `3` on the maturity rubric
- no alpha claims, no live-trading claims, no production-readiness claims

## Main Review Questions

1. Can an external reader understand what is real today without being misled?
2. Do the new narratives match the actual code and interface surface?
3. Does the proof inventory cite real repo surfaces instead of vague capability language?
4. Does the demo script focus on review-bound workflow truth instead of hype?

## Verification

- add one unit test that checks doc existence, file references, capability anchors, command references, and maturity rubric coverage
- run targeted CLI and API smoke coverage because the new proof package cites those surfaces directly
- keep `ruff`, `mypy`, and `pytest -q` green
