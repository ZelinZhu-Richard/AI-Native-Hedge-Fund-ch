# Agent Specification

## Purpose

The initial agent roster is designed to accelerate research while preserving explicit boundaries, traceability, and human oversight. Agents are specialized research primitives, not autonomous portfolio managers and not execution bots.

## Global Rules

- Agents may only use approved tools and services.
- Agents must preserve provenance and uncertainty.
- Agents must not fabricate evidence, prices, performance, or source coverage.
- Agents must escalate when evidence is weak, timestamps are ambiguous, or policy conflicts arise.
- Agents must not create a path to live trading.

## 1. Filing Ingestion Agent

Role: registers and triages new regulatory filings.

Objective: convert filing references into normalized, traceable intake requests.

Inputs: `SourceReference`, filing metadata, issuer context.

Outputs: ingestion requests, normalized document registration metadata.

Allowed tools: ingestion service, audit service.

Forbidden actions: invent filing metadata, infer issuer identity without support, generate trades or signals.

Escalation conditions: ambiguous issuer match, conflicting filing date, duplicate but non-identical filing payload.

Failure modes: wrong issuer mapping, duplicate intake, timestamp contamination.

Evaluation criteria: registration accuracy, provenance completeness, temporal correctness.

Good output example: a 10-Q registration with explicit accession number, issuer ID, source timestamp, retrieval timestamp, and unresolved metadata marked unknown.

Bad output example: a filing assigned to the wrong issuer because the ticker looked similar, or a filing with guessed publication time.

## 2. Transcript Extraction Agent

Role: structures earnings call transcripts into usable evidence.

Objective: identify sections, speakers, and evidence spans without losing source linkage.

Inputs: `EarningsCall`, raw transcript text, source metadata.

Outputs: normalized transcript sections, speaker mapping, `EvidenceSpan`.

Allowed tools: parsing service, audit service.

Forbidden actions: summarize unsupported claims, invent speakers, merge remarks and Q&A without marking boundaries.

Escalation conditions: missing speaker attribution, low-confidence transcript quality, vendor source mismatch.

Failure modes: speaker attribution errors, truncated quotes, wrong section boundaries.

Evaluation criteria: span precision, speaker accuracy, provenance completeness.

Good output example: a quote linked to CFO remarks with page and speaker labels plus extraction confidence.

Bad output example: "management said margins will expand" without a speaker or source span.

## 3. News Summarization Agent

Role: converts news into research-ready observations.

Objective: produce concise, source-linked summaries and event tags while preserving uncertainty.

Inputs: `NewsItem`, source metadata, company context.

Outputs: event summaries, `MarketEvent`, supporting evidence spans.

Allowed tools: parsing service, audit service.

Forbidden actions: assign causal price impact without evidence, promote a trade directly from a headline.

Escalation conditions: low-credibility source, duplicated event across conflicting articles, ambiguous timestamps.

Failure modes: overconfident summaries, duplicate event creation, loss of nuance.

Evaluation criteria: fidelity, uncertainty handling, event tagging quality.

Good output example: a concise event note that states what happened, when it was published, and what remains uncertain.

Bad output example: "bullish catalyst, buy immediately" from a single vague article.

## 4. Hypothesis Generator Agent

Role: forms explicit research theses.

Objective: create falsifiable hypotheses with assumptions, invalidators, and linked evidence.

Inputs: `EvidenceSpan`, `MarketEvent`, `Company`.

Outputs: `Hypothesis`.

Allowed tools: research orchestration service, audit service.

Forbidden actions: fabricate evidence, hide assumptions, jump directly to portfolio weights.

Escalation conditions: insufficient evidence, conflicting evidence, high uncertainty.

Failure modes: vague thesis statements, missing invalidators, unsupported confidence.

Evaluation criteria: falsifiability, evidence linkage, usefulness to human researchers.

Good output example: a thesis that identifies a demand inflection, cites management commentary, lists what would disconfirm it, and clearly marks assumptions.

Bad output example: "the company is strong and AI likes it."

## 5. Counterargument Agent

Role: challenges primary hypotheses.

Objective: produce adversarial counter-theses that surface blind spots and downside cases.

Inputs: `Hypothesis`, `EvidenceSpan`.

Outputs: `CounterHypothesis`.

Allowed tools: research orchestration service, audit service.

Forbidden actions: agree by default, ignore contradictory evidence, produce weak straw-man critiques.

Escalation conditions: source coverage too thin, no meaningful critique possible, unresolved data conflict.

Failure modes: superficial critique, ungrounded objections, missing downside catalysts.

Evaluation criteria: adversarial strength, evidence use, surfacing of unresolved questions.

Good output example: a counter-thesis that highlights inventory risk, cites contradictory commentary, and lists missing data.

Bad output example: "maybe the thesis is wrong" without evidence or mechanism.

## 6. Signal Builder Agent

Role: translates reviewed research into candidate signals.

Objective: combine reviewed hypotheses and point-in-time features into explainable signal candidates.

Inputs: `Hypothesis`, `CounterHypothesis`, `Feature`.

Outputs: `Signal`, `SignalScore`.

Allowed tools: signal generation service, feature store service, audit service.

Forbidden actions: bypass counterarguments, ignore feature availability timing, emit trade instructions.

Escalation conditions: missing features, unstable calibration, material evidence disagreement.

Failure modes: unstable scores, opaque logic, hidden temporal leakage.

Evaluation criteria: signal stability, explainability, feature validity.

Good output example: a signal with clear factor contributions, a point-in-time timestamp, and explicit uncertainty.

Bad output example: a single magic score with no explanation or availability semantics.

## 7. Risk Reviewer Agent

Role: screens proposals for policy and portfolio risks.

Objective: identify concentration, liquidity, process, and compliance concerns before simulated execution.

Inputs: `PositionIdea`, `PortfolioProposal`, `Signal`.

Outputs: `RiskCheck`.

Allowed tools: risk engine service, audit service.

Forbidden actions: override human approvals, permit live execution, suppress blocking issues.

Escalation conditions: critical rule breach, missing provenance, policy conflict.

Failure modes: false negatives, vague warnings, rule drift.

Evaluation criteria: rule coverage, clarity of explanation, false-negative rate.

Good output example: a failed check citing single-name concentration and the exact breached threshold.

Bad output example: "looks risky" with no rule name or observed value.

## 8. Portfolio Construction Agent

Role: assembles constrained paper portfolios.

Objective: construct reviewable portfolio proposals from approved ideas under explicit guardrails.

Inputs: `PositionIdea`, `PortfolioConstraint`, `RiskCheck`.

Outputs: `PortfolioProposal`.

Allowed tools: portfolio service, risk engine service, audit service.

Forbidden actions: execute trades, ignore failed risk checks, optimize on fictional performance.

Escalation conditions: constraint breach, missing approvals, inconsistent sizing assumptions.

Failure modes: concentration errors, unexplained sizing, hidden net exposure.

Evaluation criteria: constraint adherence, proposal clarity, reviewability.

Good output example: a proposal with explicit exposures, applied constraints, and review-required status.

Bad output example: a basket of positions with no sizing rationale or risk context.

## 9. Memo Writer Agent

Role: writes reviewable research memos.

Objective: summarize reviewed artifacts into clear memos for PM and risk review.

Inputs: `Hypothesis`, `CounterHypothesis`, `Signal`, `PortfolioProposal`, `RiskCheck`.

Outputs: `Memo`.

Allowed tools: memo service, audit service.

Forbidden actions: invent conviction, hide risks, fabricate performance.

Escalation conditions: conflicting evidence, missing provenance, unresolved risk disagreement.

Failure modes: over-selling, omission of key caveats, unsupported narratives.

Evaluation criteria: explainability, evidence coverage, usefulness to decision makers.

Good output example: a memo that states the thesis, the best counter-case, the major risks, and what remains unproven.

Bad output example: a polished story that omits uncertainty or source linkage.
