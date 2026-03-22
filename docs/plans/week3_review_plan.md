# Week 3 Review Plan

## Review Goal

Review the repo as a serious local research operating system, not as a production trading platform.

The purpose of the review is to confirm:

- which workflows are genuinely coherent today
- where the interfaces are now cleaner and more truthful
- which structural gaps still block stronger downstream trust

## Suggested Review Order

1. Top-level narrative and commands
   - `README.md`
   - `docs/product/week3_demo_status.md`
2. End-to-end local walkthrough
   - `docs/product/end_to_end_demo.md`
   - `pipelines/demo/end_to_end_demo.py`
3. Daily operator path
   - `docs/architecture/daily_orchestration.md`
   - `docs/product/operator_runbook.md`
   - `pipelines/daily_operations/daily_workflow.py`
4. Core artifact chain
   - ingestion
   - parsing
   - research
   - feature and signal generation
   - signal arbitration
   - portfolio construction
   - portfolio analysis
   - operator review
5. Monitoring and audit trail

## Safe Claims To Make

- the repo supports a real local artifact-backed path from fixtures to review-bound portfolio proposals
- paper-trade candidates are approval-gated
- timing, provenance, monitoring, audit, and review semantics are first-class concerns
- the repo now has real signal arbitration, research retrieval, portfolio attribution, stress testing, and daily orchestration layers
- quality checks and tests cover meaningful parts of the strongest workflow seams

## Claims To Avoid

- validated alpha
- production readiness
- autonomous trading capability
- realistic execution or institutional-grade risk modeling
- complete downstream promotion gating
- full snapshot-native replay

## Questions To Press Hard During Review

1. Where do candidate artifacts still flow downstream without a true eligibility gate?
2. Which workflows still rely on latest-artifact scans instead of explicit selected snapshots?
3. Where does company identity still stand in for instrument identity?
4. Which local filesystem conventions are still doing too much implicit coordination work?
5. Which docs would become misleading again if the implementation moved one step further without updates?

## Specific Gaps To Evaluate

- reviewed-and-evaluated signal eligibility gate
- snapshot-native selection across research -> feature -> signal -> portfolio
- first-class instrument and reference data layer
- stronger operator attention handling for stale or blocked workflows
- broader evaluation coverage beyond exploratory backtesting and ablation

## Desired Output Of The Review

- one honest statement of what Week 3 achieved
- one prioritized list of structural gaps
- one decision on whether the repo is ready to move into explicit eligibility-gate work
