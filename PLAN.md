# PLAN.md

## Project name

Working name: AI-Native Hedge Fund Research OS

## Mission

Build a serious AI-native research and paper-trading platform that can ingest market and company information, transform it into structured evidence, generate and critique investment hypotheses, convert validated evidence into signals, test those signals honestly, construct risk-aware portfolio proposals, and support human-reviewed paper trading with full auditability.

This project is not a toy agent demo.
This project is not a live autonomous trading system.
This project is not a performance-marketing artifact.

This project is a research operating system.

## North star

Create a system that makes research faster, cleaner, more reproducible, and more evidence-based than traditional discretionary workflows or shallow LLM wrappers.

The long-term moat is not “AI reads filings.”
The moat is:

- high-quality point-in-time data handling
- strong evidence extraction and provenance
- reproducible experimentation
- disciplined signal arbitration
- robust risk controls
- paper-trading realism
- human-reviewable decision workflows
- fast iteration across the full research loop

## Non-goals for the current phase

The following are not goals right now:

- live autonomous trading
- brokerage execution
- production-grade external integrations beyond what is needed for research foundations
- flashy multi-model complexity before baselines exist
- arbitrary Sharpe targets as engineering milestones
- novelty for its own sake
- quantum-inspired optimization experiments
- investor-persona roleplay agents as a core architecture

## Product thesis

The incumbents are slow because they are optimized for old workflows, fragmented research processes, legacy controls, and organizational inertia.

An AI-native fund platform should not just bolt AI onto existing analyst workflows.
It should redesign the research process around:

- machine-readable evidence
- structured research artifacts
- agent-assisted hypothesis generation and critique
- explicit uncertainty
- repeatable testing
- tight human oversight
- strong data and experiment lineage

## Primary system flow

The intended core flow is:

1. ingest raw data
2. normalize and timestamp it correctly
3. extract evidence and structured artifacts
4. generate research hypotheses
5. generate counterarguments and critiques
6. map valid research outputs into candidate features
7. score and arbitrate signals
8. test them through backtests and simulation
9. construct constrained portfolio proposals
10. run risk review
11. present proposals for human review
12. execute approved proposals only in paper-trading mode
13. monitor, attribute, and postmortem results

## Build philosophy

### 1. Foundations before sophistication
Strong schemas, clean ingestion, temporal discipline, and reproducible experiments come before advanced models.

### 2. Simple baselines before complex ensembles
Before building expert-routing systems or advanced agent swarms, prove strong baselines using simple and interpretable approaches.

### 3. Measurable workflows over agent theater
Use agents where they improve real workflow quality.
Do not use agents just because they sound futuristic.

### 4. Honest evaluation over vanity metrics
Prefer:
- stability
- traceability
- correctness
- robustness
- replayability
over fragile headline numbers.

### 5. Paper trading before any live path
The system should earn trust through simulation and paper operations before anyone even thinks about real execution.

## 30-day operating plan

This project should be run as a 30-day build with daily implementation prompts and weekly review prompts.

### Cadence
- Monday through Friday: daily scoped build tasks
- Saturday: review, refactor, audit, cleanup
- Sunday: roadmap update, reprioritization, next-week planning

### Weekly pattern
- Week 1: foundation and repo architecture
- Week 2: ingestion and document intelligence
- Week 3: research and signal pipeline
- Week 4: backtesting, risk, paper trading, monitoring

## Phase breakdown

---

## Phase 1: Foundation and architecture
### Recommended timeframe
Days 1 to 5

### Objective
Create the repo, architecture, data contracts, service boundaries, local tooling, and baseline documentation.

### Deliverables
- monorepo structure
- AGENTS.md
- PLAN.md
- README
- architecture docs
- core typed schemas
- basic service stubs
- basic FastAPI app
- linting, typing, tests, pre-commit
- risk and compliance baseline doc
- eval framework doc

### Success criteria
- repo boots locally
- schemas validate
- architecture is understandable
- service boundaries are explicit
- docs define future build direction clearly

### Failure signs
- repo looks like a hackathon
- no temporal logic exists
- no clear schema boundaries
- no docs explaining tradeoffs
- no testing setup

---

## Phase 2: Ingestion and normalization
### Recommended timeframe
Days 6 to 10

### Objective
Build trustworthy ingestion and normalization for the first critical data sources.

### Initial source priorities
- SEC filings
- earnings call transcripts
- market prices
- selected financial news
- company metadata
- corporate actions metadata if possible

### Deliverables
- ingestion connectors or loaders
- normalized document contracts
- canonical IDs
- timestamp handling
- source reference extraction
- fixture datasets
- sample local pipeline runs
- storage layout for raw and normalized data

### Success criteria
- can ingest and normalize a small sample set end to end
- timestamps are explicit
- source references are preserved
- raw and normalized layers are separated
- company and document entities resolve consistently

### Failure signs
- source timestamps lost
- raw and processed data mixed together
- entity resolution inconsistent
- ingestion works only for one-off demos

---

## Phase 3: Document intelligence and evidence extraction
### Recommended timeframe
Days 11 to 15

### Objective
Turn raw text into structured, reviewable evidence.

### Deliverables
- evidence span schema
- citation and provenance linking
- document parsing pipeline
- transcript segmentation
- extraction of structured events, claims, risk language, guidance changes, sentiment cues, and metadata
- quality checks for extraction output
- initial evaluation harness for extraction quality

### Success criteria
- extracted evidence points back to exact sources
- output is structured and reusable
- errors are inspectable
- extraction quality can be evaluated

### Failure signs
- summarization without evidence links
- no way to trace claims to source text
- extraction output too vague to support features later

---

## Phase 4: Hypothesis and critique engine
### Recommended timeframe
Days 16 to 19

### Objective
Use AI to generate research hypotheses and counter-hypotheses in a disciplined way.

### Deliverables
- hypothesis schema
- counter-hypothesis schema
- thesis generator agent
- thesis critic agent
- evidence grader agent
- memo-ready research artifact format
- guardrails against unsupported claims

### Success criteria
- hypotheses are evidence-backed
- critiques are meaningful
- unsupported narratives are flagged
- output can be reviewed by a human researcher

### Failure signs
- agent outputs sound smart but are not grounded
- counterarguments are weak or repetitive
- no structured confidence or uncertainty

---

## Phase 5: Feature and signal pipeline
### Recommended timeframe
Days 20 to 23

### Objective
Map validated research artifacts into measurable candidate features and signals.

### Deliverables
- feature contracts
- signal contracts
- feature registry or store skeleton
- signal generation service
- signal scoring logic
- uncertainty handling
- ablation framework for price-only, fundamentals-only, text-only, and combined approaches

### Success criteria
- every feature has lineage
- every signal has a clear source path
- simple baselines exist
- multiple input families can be compared honestly

### Failure signs
- features are created ad hoc with no registry
- agent outputs become signals without validation
- complexity is added before baselines exist

---

## Phase 6: Backtesting and simulation
### Recommended timeframe
Days 24 to 26

### Objective
Build honest testing and replay infrastructure.

### Deliverables
- backtest engine skeleton
- transaction cost assumptions
- slippage assumptions
- event-time-aware simulation rules
- walk-forward framework
- leakage tests
- benchmark strategy support
- experiment logging for runs

### Success criteria
- at least one honest baseline backtest runs end to end
- decisions only use information available at the simulated time
- results are reproducible
- assumptions are documented

### Failure signs
- future information leaks into decisions
- unrealistic fills
- no transaction costs
- one-off notebook logic with no replay path

---

## Phase 7: Portfolio construction and risk review
### Recommended timeframe
Days 27 to 28

### Objective
Convert signals into reviewable portfolio proposals under explicit constraints.

### Deliverables
- portfolio constraint schema
- position idea schema
- portfolio proposal schema
- risk checks
- exposure rules
- turnover rules
- concentration rules
- scenario stress hooks
- portfolio review artifact

### Success criteria
- proposals are constrained and inspectable
- risk checks are explicit
- signal strength is not the only decision input
- human reviewers can understand why a proposal exists

### Failure signs
- optimizer hides decisions
- no link between proposal and supporting evidence
- no explicit risk review step

---

## Phase 8: Paper trading, monitoring, and operator loop
### Recommended timeframe
Days 29 to 30

### Objective
Run the full pipeline in paper mode with a usable review loop.

### Deliverables
- paper trade schema
- review decision schema
- operator review flow
- paper ledger
- monitoring endpoints or dashboard skeleton
- daily run summary
- audit logs
- postmortem template

### Success criteria
- the system can propose paper trades
- humans can review or reject them
- every recommendation is traceable
- runs can be monitored and audited

### Failure signs
- paper trading is just a print statement
- no review path
- no audit trail
- no explanation for why a proposal exists

## Weekly review framework

At the end of each week, perform a structured review across:

- architecture quality
- repo cleanliness
- schema quality
- documentation gaps
- ingestion integrity
- temporal correctness risks
- leakage risks
- test coverage
- overengineering
- underengineering
- research usefulness
- operator usability

Each weekly review should result in:
- a list of top issues
- direct fixes where possible
- updates to AGENTS.md if repeated mistakes are appearing
- updates to PLAN.md if sequencing needs to change

## Daily execution prompt pattern

Each daily Codex prompt should contain:

1. the goal for the day
2. the exact files or modules to create or edit
3. constraints and quality bar
4. required tests or verification
5. required docs updates
6. required final output summary

## Definitions of success

This project is succeeding if, by the end of the first 30 days, we have:

- a coherent repo structure
- durable project instructions
- trustworthy core schemas
- clean data contracts
- point-in-time-aware ingestion
- evidence-linked research artifacts
- disciplined hypothesis and critique workflows
- baseline feature and signal generation
- honest backtesting infrastructure
- risk-aware portfolio proposal logic
- paper-trading review flow
- meaningful auditability
- a clear story for why this system is different from shallow AI wrappers

## Definitions of failure

This project is failing if we end up with:

- a pile of agent prompts with no architecture
- untraceable claims
- made-up metrics
- backtests with leakage
- dashboards without research truth
- portfolio proposals with no evidence trail
- hype words substituting for infrastructure
- complexity without baselines
- no clear human review layer

## Open strategic rules

### Rule 1
Do not chase sophistication before trust.

### Rule 2
Do not judge modules by how exciting they sound.
Judge them by whether they increase truth, speed, or decision quality.

### Rule 3
Do not lock into one model or one vendor too early.
Keep interfaces modular.

### Rule 4
Do not optimize the narrative at the expense of the system.
The narrative will get stronger when the infrastructure gets stronger.

### Rule 5
Do not confuse a research artifact with a trading edge.
Many useful research outputs will not immediately produce alpha.
That is normal.

## Immediate next moves

The build order should begin with:
1. repo scaffold
2. architecture docs
3. typed schemas
4. service stubs
5. local dev environment
6. risk baseline
7. ingestion foundation
8. document intelligence
9. research workflow
10. signal and backtest infrastructure

## Summary

This project should be built like a hybrid of:
- a strong research lab
- a serious quant platform team
- a disciplined hedge fund risk culture
- a fast-moving startup with excellent technical taste

The standard is not “looks impressive.”
The standard is “can survive scrutiny.”