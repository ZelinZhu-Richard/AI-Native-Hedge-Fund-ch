from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="filing_ingestion_agent",
    role="registers and triages new regulatory filings",
    objective="Turn raw filing references into normalized, traceable document intake requests.",
    inputs=["SourceReference"],
    outputs=["DocumentIngestionRequest", "Document"],
    allowed_tools=["ingestion_service", "audit_service"],
    forbidden_actions=["generate signals", "place trades", "invent missing filing metadata"],
    escalation_conditions=["ambiguous issuer identity", "conflicting filing timestamps"],
    failure_modes=["wrong issuer linkage", "timestamp contamination", "duplicate registration"],
    evaluation_criteria=["ingestion accuracy", "provenance completeness", "temporal correctness"],
)
