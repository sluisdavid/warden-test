from __future__ import annotations

from src.schemas import Action, EventIn, LLMDecision


def apply_safety_policy(event: EventIn, decision: LLMDecision, productive_environment_names: set[str]) -> tuple[LLMDecision, list[str]]:
    restricted_reasons: list[str] = []
    safe_to_auto = decision.safe_to_auto

    if event.severity.value == "critical":
        safe_to_auto = False
        restricted_reasons.append("critical_severity_requires_human")

    if decision.confidence < 0.7:
        safe_to_auto = False
        restricted_reasons.append("confidence_below_threshold")

    if event.environment_id.lower() in productive_environment_names and decision.action in {
        Action.rollback,
        Action.scale_up,
    }:
        safe_to_auto = False
        restricted_reasons.append("productive_env_sensitive_action_requires_human")

    return decision.model_copy(update={"safe_to_auto": safe_to_auto}), restricted_reasons
