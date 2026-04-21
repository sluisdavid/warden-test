from __future__ import annotations

import json
import logging

import httpx

from src.config import Settings
from src.schemas import Action, EventIn, HistoryItem, LLMDecision

logger = logging.getLogger("warden.llm")


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def reason(self, event: EventIn, history: list[HistoryItem]) -> LLMDecision:
        if self.settings.llm_provider == "heuristic" or not self.settings.llm_api_key:
            return self._heuristic_decision(event, history)
        return await self._remote_reason(event, history)

    async def _remote_reason(self, event: EventIn, history: list[HistoryItem]) -> LLMDecision:
        prompt = self._build_prompt(event, history)
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.settings.llm_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Warden, a cloud remediation assistant. "
                        "Return a JSON object with keys: action, confidence, reasoning, safe_to_auto."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(self.settings.llm_api_url, headers=headers, json=body)
            response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        logger.info("llm_remote_response", extra={"extra_fields": {"provider": self.settings.llm_provider}})
        return LLMDecision.model_validate(json.loads(content))

    def _heuristic_decision(self, event: EventIn, history: list[HistoryItem]) -> LLMDecision:
        signal = event.signal.lower()
        action = Action.notify_human
        confidence = 0.72
        reasoning = "Defaulting to human notification because the signal does not match a high-confidence heuristic."
        safe_to_auto = False

        if "deploy" in signal or "rollback" in signal:
            action = Action.rollback
            confidence = 0.85
            reasoning = "The issue appears correlated with a recent deployment, so rollback is the most likely remediation."
            safe_to_auto = True
        elif "latency" in signal or "cpu" in signal:
            action = Action.scale_up
            confidence = 0.76
            reasoning = "The signal suggests resource saturation, so scaling up is the likely remediation."
            safe_to_auto = True
        elif "restart" in signal or "crash" in signal or "oom" in signal:
            action = Action.restart
            confidence = 0.81
            reasoning = "The signal points to process instability, so a restart is a reasonable first action."
            safe_to_auto = True
        elif "false positive" in signal:
            action = Action.no_action
            confidence = 0.9
            reasoning = "The signal indicates a false positive, so no action is recommended."
            safe_to_auto = True

        rejected_matches = [
            item for item in history if item.llm_action == action.value and item.feedback == "rejected"
        ]
        if rejected_matches:
            confidence = min(confidence, 0.55)
            reasoning += " Similar recommendations were previously rejected by a human, lowering confidence."
            safe_to_auto = False

        return LLMDecision(
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            safe_to_auto=safe_to_auto,
        )

    @staticmethod
    def _build_prompt(event: EventIn, history: list[HistoryItem]) -> str:
        history_payload = [item.model_dump(mode="json") for item in history]
        return json.dumps(
            {
                "event": event.model_dump(mode="json"),
                "history": history_payload,
                "instructions": {
                    "valid_actions": [action.value for action in Action],
                    "return_fields": ["action", "confidence", "reasoning", "safe_to_auto"],
                },
            }
        )
