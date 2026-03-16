# AGENTS.md

## Purpose

This repository is the foundation of an AI-native hedge fund research and paper-trading platform.

The goal is not to build a toy demo, a fake autonomous trader, or a hype-driven “agent swarm.”
The goal is to build a serious research operating system with strong data discipline, reproducibility, explainability, risk controls, and human oversight.

All work in this repository must support one or more of these long-term outcomes:

- trustworthy financial data ingestion
- point-in-time correct research workflows
- evidence-backed hypothesis generation
- structured feature and signal creation
- rigorous backtesting and simulation
- risk-aware portfolio construction
- paper-trading-first execution workflows
- full auditability and traceability
- fast but disciplined experimentation

## Core principles

### 1. Research first
This repository exists to support research, validation, and paper trading first.
Do not build live autonomous trading functionality.
Do not connect to real brokerages unless explicitly requested in a future controlled phase.

### 2. Human in the loop
No AI output should directly become an executed action without a human review step.
The architecture should clearly separate:
- raw information
- evidence
- hypotheses
- features
- signals
- position ideas
- portfolio proposals
- approved paper trades

### 3. No fake performance
Never invent alpha, Sharpe, CAGR, hit rates, or any other performance claims.
Never fabricate results to make a module appear useful.
If performance is unknown, say it is unknown.

### 4. Temporal correctness matters
Financial systems break when they accidentally use future information.
Always design with point-in-time correctness in mind.
Track:
- event time
- publication time
- ingestion time
- processing time
- snapshot time
- backtest decision time

Assume leakage is a default risk until proven otherwise.

### 5. Provenance is mandatory
All important outputs should be traceable back to:
- source data
- timestamps
- transformations
- model or agent runs
- configuration versions
- experiment metadata

### 6. Clarity over cleverness
Prefer explicit designs over fancy abstractions.
Prefer readable interfaces over framework gymnastics.
Prefer modular systems over hidden coupling.

### 7. Build for iteration
The system should be easy to extend, test, inspect, and refactor.
Future researchers should be able to understand what happened and why.

### 8. Simple before sophisticated
Do not introduce complex model routing, mixture-of-experts logic, or advanced portfolio methods until strong baselines, clean data contracts, and honest validation already exist.

## Operating philosophy for Codex

When working in this repository:

- act like a strong principal engineer and quant platform builder
- prefer disciplined defaults over asking unnecessary clarifying questions
- make assumptions explicit in docs and comments
- surface tradeoffs clearly
- keep architecture serious and future-proof
- avoid overengineering
- avoid hackathon shortcuts unless explicitly requested
- when uncertain, choose the option that improves rigor, testability, and future research speed

## Repository expectations

Every meaningful addition should fit into a clean architecture with clear boundaries.

Expected major areas include:
- apps
- services
- agents
- pipelines or orchestration
- libraries
- data contracts
- configs
- docs
- tests
- research artifacts
- storage or dataset metadata

Do not collapse unrelated concerns into one folder or one massive module.

## Engineering standards

### Language and style
- Use Python as the primary language unless there is a strong reason otherwise.
- Use type hints.
- Prefer pydantic for schemas and typed contracts where appropriate.
- Use docstrings on important public classes, functions, and interfaces.
- Keep functions and classes focused.

### Naming
- Use strong, precise names.
- Avoid vague names like `manager`, `helper`, `thing`, `stuff`, `misc`.
- Name modules after their real domain role.
- Use explicit names like `risk_engine`, `signal_registry`, `document_ingestion_service`.

### Architecture
- Keep service boundaries explicit.
- Separate domain logic from transport logic.
- Separate schemas from service implementations.
- Separate research artifacts from production-facing interfaces.
- Separate raw data from normalized data from derived data.

### Logging
- Prefer structured logging hooks over print statements.
- Log useful events, not noise.
- Important workflows should be inspectable.

### Configuration
- Configuration must be explicit and versionable.
- Do not scatter magic constants through the codebase.
- Put environment-specific settings in config files or environment variables.

### Time handling
- Centralize time handling.
- Be explicit about timezone assumptions.
- Avoid hidden `now()` usage in logic that affects replayability or backtests.

## Testing standards

Every non-trivial change should move the repository toward stronger verification.

At minimum:
- add or update unit tests for schema and logic changes
- add integration tests for service boundaries when relevant
- preserve or improve linting and typing health
- avoid introducing code that cannot be validated at all

Prefer tests that check:
- schema validity
- timestamp logic
- data contract integrity
- service wiring
- API boot or endpoint behavior
- no obvious temporal leakage in simulation or backtest paths

## Documentation standards

When creating or modifying systems, also update relevant docs.

Important docs should explain:
- what the system does
- what it does not do
- inputs and outputs
- assumptions
- limitations
- major tradeoffs
- future extension points

Do not write bloated or decorative docs.
Write docs that future engineers and researchers can actually use.

## Financial safety rules

Do not build or imply:
- live autonomous trading
- hidden execution paths
- unreviewed position placement
- fabricated PnL claims
- unsupported claims of market edge

All trading-related flows must clearly distinguish:
- recommendation
- review
- approval
- paper execution
- monitoring

## Agent design rules

Agents in this repository are workflow components, not celebrity roleplay bots.

Good agent types:
- document analyst
- thesis generator
- counter-thesis generator
- evidence grader
- factor mapper
- risk reviewer
- portfolio reviewer
- memo writer

Avoid gimmicky agents modeled after famous investors unless explicitly requested for experimentation.

For every agent, define:
- purpose
- inputs
- outputs
- allowed tools
- forbidden behaviors
- failure modes
- escalation conditions
- evaluation criteria

## Data contract rules

Every important object should have:
- a clear ID
- clear timestamps
- provenance where relevant
- status where relevant
- confidence or uncertainty where relevant
- versioning where relevant

Examples of important entities:
- Document
- Filing
- EarningsCall
- NewsItem
- Company
- EvidenceSpan
- Hypothesis
- Feature
- Signal
- PositionIdea
- PortfolioProposal
- RiskCheck
- BacktestRun
- Experiment
- Memo
- AgentRun
- AuditLog
- ReviewDecision
- PaperTrade
- DataSnapshot

## Backtesting and simulation rules

Backtests must be designed with extreme skepticism.

Always think about:
- look-ahead bias
- leakage
- survivorship bias
- stale prices
- timestamp mismatch
- unrealistic fills
- unrealistic turnover
- data snooping
- overfitting
- unstable signal behavior

Do not treat a backtest as truth.
Treat it as a controlled test that can still be wrong.

## Output expectations for tasks

Unless explicitly told otherwise, when completing a task:
1. briefly state the plan
2. implement the requested changes
3. run or describe verification steps
4. summarize what changed
5. list open risks or weak points
6. suggest the next highest-leverage step

## What to do when uncertain

If requirements are slightly ambiguous:
- choose the most rigorous reasonable interpretation
- make assumptions explicit
- document tradeoffs
- do not block on unnecessary questions

If requirements are highly ambiguous and multiple architectures are plausible:
- choose the best default
- explain the alternative briefly
- keep the chosen design modular enough to evolve later

## Anti-patterns to avoid

Do not:
- dump all logic into one file
- hide important behavior behind vague abstractions
- add shiny complexity before baselines exist
- mix raw data and engineered features carelessly
- conflate agent opinion with validated signal
- build dashboards before core truth and simulation are sound
- sacrifice auditability for convenience
- create fake confidence with polished language

## Definition of good work in this repo

Good work makes the system:
- more trustworthy
- more testable
- more explainable
- more modular
- more point-in-time correct
- more auditable
- more useful to researchers and reviewers

That is the bar.