# Day 28 Plan

## Goal

Clean up the API and interface layer so the system is easier to consume, demonstrate, and inspect without adding fake polish.

## Implemented Direction

- add shared interface schemas for envelopes, errors, capability descriptors, manifests, and compact workflow invocation results
- split the FastAPI app into route groups instead of keeping all transport logic in one file
- standardize canonical namespaced routes while preserving older aliases during the cleanup pass
- expose only honest runnable workflow entrypoints: demo and daily workflow
- add one unified local CLI for capabilities, manifest inspection, demo runs, daily runs, review queue inspection, and recent monitoring summaries
- update docs so the interface layer matches current repo reality

## Why This Matters

The repo already has serious typed artifacts and workflow layers, but the interface surface had become inconsistent:

- route names were uneven
- API response contracts were ad hoc
- errors were not structured
- capability discovery was too thin
- runnable commands were spread across Make targets and pipeline-module entrypoints

Day 28 addresses those seams without inventing a dashboard or a product shell.

## Chosen Constraints

- keep the API local and unversioned for now
- do not expose arbitrary service execution
- do not claim production control-plane behavior
- do not replace source artifacts with interface summaries

## Best Follow-On

Use this cleaned interface layer to surface the Week 4 eligibility gate, proposal scorecards, validation gates, reconciliation warnings, and paper-ledger followups through one honest inspection surface.
