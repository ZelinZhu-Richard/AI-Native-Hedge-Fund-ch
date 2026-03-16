# Risk and Compliance Baseline

## Purpose

This baseline defines the minimum operational safety posture for Day 1. The system is a research and paper-trading platform. It is not a live trading system.

## Paper-Trading-First Policy

- Day 1 supports simulated paper trades only.
- No component may connect to a live brokerage or route a real order.
- No agent or service may infer approval from the absence of a rejection.

## Prohibited Actions

- placing or routing live trades
- generating credentials or adapters for real broker execution
- bypassing human approval for portfolio proposals or paper trades
- fabricating performance metrics, risk metrics, or source evidence
- suppressing failed risk checks

## Human Approval Requirement

Human review is required before:

- a position idea is promoted into a portfolio proposal for action
- a portfolio proposal becomes a paper trade proposal
- a memo is treated as a decision artifact for simulated allocation review when material uncertainty exists

## Data Handling Boundaries

- Raw and normalized source artifacts must remain traceable to source references.
- Derived artifacts must carry provenance.
- Unknown or ambiguous metadata must be marked unknown rather than guessed.
- Future sensitive datasets should be permissioned by source, license, and use case.

## Audit Logging Requirements

Material actions should emit audit logs, including:

- document ingestion and parse acceptance
- agent run starts, failures, and escalations
- signal generation events
- risk check outcomes
- review decisions
- paper trade proposals, approvals, rejections, and simulated fills

## Explanation Requirements

Recommendations must be explainable in plain language. At minimum, a reviewer should be able to answer:

- what evidence supports the recommendation
- what evidence argues against it
- what assumptions remain unresolved
- what risk checks passed or failed
- what human approved the next step

## Portfolio and Position Guardrail Concepts

Day 1 defines the objects, not the final thresholds. Future enforced guardrails should cover:

- single-name concentration
- sector concentration
- gross exposure
- net exposure
- liquidity participation
- turnover
- hard blocks on unsupported or low-provenance positions

## Kill Switch Concept

The platform should support future kill switches at three levels:

- workflow kill switch: stop a research cycle
- proposal kill switch: block a portfolio proposal from further progression
- paper-execution kill switch: cancel pending paper trade simulation

Day 1 implements the conceptual boundary by making paper execution a separate service behind human approval.

## Fallback Behavior for Model Uncertainty

When model uncertainty is material:

- lower confidence in the artifact explicitly
- require human review
- prefer no action over unsupported action
- retain open questions in memos and review decisions

## Separation of Recommendation and Execution

The architecture deliberately separates:

- research generation
- signal generation
- risk review
- portfolio construction
- paper execution

This prevents an AI-generated recommendation from directly becoming even a simulated trade without passing through multiple explicit gates.

## Future Compliance Integration Points

- restricted list enforcement
- watchlist and issuer-control logic
- archival retention policies
- reviewer identity and entitlement controls
- model approval and model risk management workflow
- surveillance and exception management
