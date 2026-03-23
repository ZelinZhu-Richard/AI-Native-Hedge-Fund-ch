# Day 30 Plan

## Summary

Day 30 is a release-candidate hardening pass, not a feature-expansion pass.

The point of the day is to make the repo easier to install, verify, run, inspect, and explain without hiding the biggest remaining structural gaps.

## Priorities

1. Tighten release-facing workflow boundaries and stop-state wording.
2. Remove stale demo and quickstart drift.
3. Improve artifact linkage and auditability in the demo and daily surfaces.
4. Add high-signal checks around demo, daily workflow, CLI/API surfaces, and release-candidate docs.

## Required Truths

- the repo is coherent and serious locally
- the repo is still missing a true downstream eligibility gate
- selected-artifact enforcement is still incomplete
- paper trading and backtesting remain honest but simplified
- the release candidate should not be oversold as production, live trading, or validated alpha
