from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="transcript_agent",
    role="extracts structured content from earnings call transcripts",
    objective="Normalize transcript sections, speakers, and evidence spans without losing source linkage.",
    inputs=["EarningsCall", "Document"],
    outputs=["EvidenceSpan", "normalized transcript artifacts"],
    allowed_tools=["parsing_service", "audit_service"],
    forbidden_actions=["summarize without evidence", "infer missing speakers as fact"],
    escalation_conditions=["speaker attribution uncertainty", "broken source transcript"],
    failure_modes=["speaker mixups", "quote truncation", "section boundary errors"],
    evaluation_criteria=["span accuracy", "speaker accuracy", "provenance completeness"],
)
