# Project Maturity Scorecard

This scorecard is intentionally non-flattering. It rates the current repo as a serious local system, not a production trading stack.

The final 30-day review did not justify raising any of these ratings.

## Rubric

- `0`: absent
- `1`: skeletal
- `2`: implemented but partial
- `3`: coherent and inspectable local system
- `4`: strong and policy-driving, but not yet production-scaled

Nothing in Day 29 is rated above `3`.

| Area | Rating | Strongest evidence | Limiting factor | Next milestone |
| --- | --- | --- | --- | --- |
| data integrity | 3 | typed schemas, provenance requirements, validation gates, and explicit contract violations in `libraries/schemas/data_quality.py` and `services/data_quality/service.py` | the final downstream eligibility gate is still missing | make validation and eligibility jointly block unsafe promotion |
| temporal correctness | 3 | explicit timing schemas and docs in `libraries/schemas/timing.py`, `services/timing/service.py`, and `docs/research/temporal_correctness.md` | snapshot-native selection is still incomplete across the full chain | finish snapshot-native selection across research, feature, signal, and portfolio stages |
| reproducibility | 3 | deterministic demo and daily workflows, experiment registry, explicit artifact roots, and run summaries | persistence is still local-filesystem based and some selection still relies on latest-artifact patterns | reduce implicit artifact selection and strengthen reproducible slice loading |
| evaluation | 2 | real evaluation and red-team services, reports, failure cases, and robustness checks | evaluation is inspectable but not yet a hard promotion policy | make evaluation and red-team results policy-driving for readiness |
| operator workflow | 3 | explicit review queue, review context, assignments, notes, decisions, and daily reporting | some followups and readiness decisions still depend on manual interpretation | make open followups and unresolved high-severity issues harder stop conditions |
| risk controls | 2 | risk engine, construction constraints, stress testing, reconciliation warnings, and proposal scorecards | risk remains deterministic and local, without stronger policy enforcement or richer market realism | tighten eligibility and risk policy coupling before broadening strategy scope |
| paper trading | 2 | approval-gated paper trades, paper ledger, lifecycle events, daily summaries, and outcome attribution | still paper-only bookkeeping with manual marks and no live execution feedback | use paper outcomes and followups as real readiness inputs |
| reporting | 2 | grounded summaries and scorecards for research, proposals, review queues, experiments, and daily system state | reporting is useful but not yet a decision gate and still local-root driven | connect scorecards and open issues to policy decisions explicitly |
| interface quality | 3 | unified `nta` CLI with temporary `anhf` compatibility alias, manifest/capabilities surfaces, canonical API routes, structured envelopes, and structured errors | still a local interface layer without auth, async orchestration, or external durability | expose the Week 4 eligibility surface through the cleaned interface layer |
