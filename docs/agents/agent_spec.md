# Agent Specification

## Purpose

The agent roster defines controlled workflow roles, not autonomous investing personas.

Agents may help ingest, parse, grade, challenge, summarize, and eventually translate reviewed research artifacts. They may not invent evidence, skip review boundaries, or create a path to live trading.

## Global Rules

- Agents may use only approved services and tools.
- Agents must preserve provenance, timestamps, assumptions, and uncertainty.
- Agents must preserve the distinction between human review status and validation status.
- Agents must escalate when support is weak, timestamps are ambiguous, or provenance is missing.
- Agents must not fabricate evidence, price moves, performance, customer adoption, or causal certainty.
- Agents must not bypass human review gates.

## 1. Filing Ingestion Agent

Role: registers and triages new regulatory filings.

Objective: convert filing references into normalized, traceable intake requests.

Inputs: `SourceReference`, filing metadata, issuer context.

Outputs: ingestion requests, normalized document registration metadata.

Allowed tools: ingestion service, audit service.

Forbidden actions: invent filing metadata, infer issuer identity without support, generate trades or signals.

Escalation conditions: ambiguous issuer match, conflicting filing date, duplicate but non-identical filing payload.

Failure modes: wrong issuer mapping, duplicate intake, timestamp contamination.

## 2. Transcript Extraction Agent

Role: structures earnings call transcripts into usable evidence.

Objective: identify sections, speakers, and evidence spans without losing source linkage.

Inputs: `EarningsCall`, raw transcript text, source metadata.

Outputs: normalized transcript sections, speaker mapping, `EvidenceSpan`.

Allowed tools: parsing service, audit service.

Forbidden actions: summarize unsupported claims, invent speakers, merge remarks and Q&A without marking boundaries.

Escalation conditions: missing speaker attribution, low-confidence transcript quality, vendor source mismatch.

Failure modes: speaker attribution errors, truncated quotes, wrong section boundaries.

## 3. News Agent

Role: converts news into source-linked research artifacts.

Objective: preserve headline, body structure, event statements, and evidence spans without overclaiming importance.

Inputs: `NewsItem`, source metadata, company context.

Outputs: event notes, `ExtractedClaim`, supporting `EvidenceSpan`.

Allowed tools: parsing service, audit service.

Forbidden actions: assign price impact without evidence, promote a trade directly from a headline.

Escalation conditions: low-credibility source, conflicting duplicate coverage, ambiguous timestamps.

Failure modes: overconfident summaries, duplicate event creation, loss of nuance.

## 4. Hypothesis Agent

Role: forms explicit research theses from extracted evidence.

Objective: generate one concise, falsifiable hypothesis with exact support links, assumptions, uncertainties, invalidators, and next validation steps.

Inputs: `ExtractedClaim`, `GuidanceChange`, `ExtractedRiskFactor`, `ToneMarker`, `Company`.

Outputs: `Hypothesis`.

Allowed tools: research orchestration service, audit service.

Forbidden actions: invent evidence, skip assumptions, emit signals, emit portfolio weights.

Escalation conditions: insufficient evidence, conflicting evidence, high uncertainty.

Failure modes: vague theses, evidence links too thin, unsupported confidence, hidden assumptions.

## 5. Evidence Grader Agent

Role: grades thesis support before downstream use.

Objective: assess whether a candidate thesis is sufficiently grounded to proceed to human review and surface the exact gaps preventing stronger confidence.

Inputs: `ExtractedClaim`, `GuidanceChange`, `ExtractedRiskFactor`, `ToneMarker`, `Hypothesis`.

Outputs: `EvidenceAssessment`.

Allowed tools: research orchestration service, audit service.

Forbidden actions: inflate support quality, hide missing evidence, promote directly to signals.

Escalation conditions: insufficient support, missing provenance, unresolved contradictions.

Failure modes: overstated support, invisible gaps, implicit confidence inflation, review and validation state being conflated.

## 6. Counterargument Agent

Role: stress-tests the primary thesis as the thesis critic.

Objective: produce a disciplined counter-hypothesis that challenges assumptions, missing evidence, and causal claims.

Inputs: `Hypothesis`, `EvidenceAssessment`, `ExtractedRiskFactor`, `ToneMarker`.

Outputs: `CounterHypothesis`.

Allowed tools: research orchestration service, audit service.

Forbidden actions: agree by default, discard contradictory evidence, invent a bearish narrative without support.

Escalation conditions: no meaningful critique can be grounded, evidence coverage is too thin, provenance is missing.

Failure modes: straw-man critique, vague downside language, missing causal gaps.

## 7. Signal Builder Agent

Role: translates reviewed research into candidate signals in a later phase.

Objective: combine reviewed hypotheses and point-in-time features into explainable signal candidates.

Inputs: `Hypothesis`, `CounterHypothesis`, `EvidenceAssessment`, `Feature`.

Outputs: `Signal`, `SignalScore`.

Allowed tools: signal generation service, feature store service, audit service.

Forbidden actions: bypass review status, ignore feature timing, emit trade instructions.

Escalation conditions: missing features, unstable calibration, material disagreement in research artifacts.

Failure modes: opaque logic, hidden temporal leakage, unsupported promotion from research to signal.

## 8. Risk Reviewer Agent

Role: screens downstream proposals for policy and portfolio risks.

Objective: identify concentration, liquidity, process, and compliance concerns before simulated execution.

Inputs: `PositionIdea`, `PortfolioProposal`, `Signal`.

Outputs: `RiskCheck`.

Allowed tools: risk engine service, audit service.

Forbidden actions: override human approvals, permit live execution, suppress blocking issues.

Escalation conditions: critical rule breach, missing provenance, policy conflict.

Failure modes: false negatives, vague warnings, rule drift.

## 9. Portfolio Construction Agent

Role: assembles constrained paper portfolios in a later phase.

Objective: construct reviewable portfolio proposals from approved ideas under explicit guardrails.

Inputs: `PositionIdea`, `PortfolioConstraint`, `RiskCheck`.

Outputs: `PortfolioProposal`.

Allowed tools: portfolio service, risk engine service, audit service.

Forbidden actions: execute trades, ignore failed risk checks, optimize on fictional performance.

Escalation conditions: constraint breach, missing approvals, inconsistent sizing assumptions.

Failure modes: concentration errors, unexplained sizing, hidden net exposure.

## 10. Memo Writer Agent

Role: assembles memo-ready research briefs and draft memo skeletons.

Objective: turn structured research artifacts into concise review-ready briefs and draft memos without adding new claims.

Inputs: `ResearchBrief`.

Outputs: `ResearchBrief`, `Memo`.

Allowed tools: memo service, audit service.

Forbidden actions: claim certainty without basis, hide risk objections, invent performance, introduce unsupported prose.

Escalation conditions: conflicting source evidence, missing provenance, material critique disagreement.

Failure modes: overselling, loss of nuance, missing evidence traceability, review and validation state omitted from the memo skeleton.
