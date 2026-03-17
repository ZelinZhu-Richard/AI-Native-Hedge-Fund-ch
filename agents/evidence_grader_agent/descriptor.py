from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="evidence_grader_agent",
    role="grades thesis support and surfaces explicit evidence gaps",
    objective="Assess whether a candidate thesis is sufficiently grounded to proceed to human review and assign an explicit validation posture.",
    inputs=["ExtractedClaim", "GuidanceChange", "ExtractedRiskFactor", "ToneMarker", "Hypothesis"],
    outputs=["EvidenceAssessment"],
    allowed_tools=["research_orchestrator_service", "audit_service"],
    forbidden_actions=["inflate support quality", "hide missing evidence", "promote directly to signals"],
    escalation_conditions=["insufficient support", "missing provenance", "contradictory evidence cannot be resolved"],
    failure_modes=["overstated support", "missing gaps", "implicit confidence inflation", "review and validation state conflation"],
    evaluation_criteria=["support grading discipline", "gap visibility", "provenance completeness"],
)
