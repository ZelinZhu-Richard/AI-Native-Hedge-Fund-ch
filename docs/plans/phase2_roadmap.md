# Phase 2 Roadmap

## Summary

Phase 2 should not widen into live trading or polished product theatrics.

Its purpose is to finish the trust-critical research boundary work that the first 30-day build exposed, then deepen data, evaluation, paper operations, and operator usefulness on top of that stronger base.

## 1. Downstream Eligibility Enforcement And Selected-Artifact Discipline

- Why it matters: the current repo is still weakest where candidate artifacts can move too far downstream by convention.
- Weakness addressed: missing reviewed-and-evaluated eligibility gate and incomplete selected-artifact enforcement.
- Done means: portfolio construction can only consume explicitly eligible signal artifacts, blocked state is typed and visible, and downstream workflows carry selected artifact IDs instead of relying on latest-artifact convenience.
- Still should not be claimed: this alone does not prove edge, live readiness, or institutional robustness.

## 2. Stronger Data Providers And Broader Normalization Coverage

- Why it matters: fixture discipline is a good start, but the next phase needs broader and more realistic source coverage.
- Weakness addressed: current ingestion and normalization are structurally sound but still narrow and fixture-heavy.
- Done means: at least one stronger non-fixture provider path lands with the same schema, provenance, timing, and validation standards as the current local fixtures.
- Still should not be claimed: broader coverage does not automatically mean better research quality or better signals.

## 3. Better Extraction Quality And Calibration

- Why it matters: richer sources only help if the extraction layer becomes more reliable and easier to challenge.
- Weakness addressed: extraction coverage is real but still narrow and only lightly calibrated.
- Done means: extraction quality reports, failure cases, and narrower calibration checks become part of normal inspection for evidence bundles and research outputs.
- Still should not be claimed: better extraction does not imply causal or predictive correctness.

## 4. Richer Evaluation, Red-Team, And Readiness Policy

- Why it matters: Week 4 made evaluation more inspectable, but it still does not drive enough downstream behavior.
- Weakness addressed: evaluation, red-team, reconciliation, and paper-ledger followups are mostly advisory.
- Done means: high-severity evaluation, validation, reconciliation, or open followup issues can visibly block readiness in downstream workflows and interface surfaces.
- Still should not be claimed: policy-driving evaluation is still not the same thing as validated market edge.

## 5. Improved Backtest Realism And Live-Vs-Paper Gap Analysis

- Why it matters: backtests and paper trading are now honest but still simplified, and their gaps need better explicit treatment.
- Weakness addressed: synthetic pricing, limited cost realism, advisory reconciliation, and weak live-vs-paper comparison.
- Done means: richer realism assumptions, better cost and timing modeling, and clearer paper-vs-backtest divergence reporting are available without pretending to have a full execution simulator.
- Still should not be claimed: improved realism remains research support, not broker-grade execution truth.

## 6. First-Class Instrument/Security Model

- Why it matters: company identity cannot keep carrying tradable identity without creating future distortion.
- Weakness addressed: ticker and company metadata still stand in for a real instrument/security layer.
- Done means: proposals, paper trades, ledger states, attribution, and reconciliation link to explicit tradable instruments rather than overloading company identity.
- Still should not be claimed: an instrument layer does not by itself make the platform live-trading ready.

## 7. Longer-Duration Paper Operation And Outcome Learning

- Why it matters: the current paper ledger proves continuity, but not sustained operating discipline.
- Weakness addressed: marks, closes, outcomes, and summaries remain local-input-driven and short-horizon.
- Done means: longer-running paper positions, recurring summaries, open followups, and outcome learning become normal operating artifacts rather than isolated proof steps.
- Still should not be claimed: longer paper operations still do not equal broker-verified performance.

## 8. Deeper Operator Console And Stronger Reporting

- Why it matters: the repo has a serious summary layer, but operators still have to assemble too much context manually.
- Weakness addressed: reporting is grounded but still local and relatively thin for operational triage.
- Done means: operators can inspect blocked states, followups, scorecards, queue pressure, and recent proof artifacts more directly without losing source-truth linkage.
- Still should not be claimed: a better operator surface is not a substitute for stronger policy enforcement underneath.
