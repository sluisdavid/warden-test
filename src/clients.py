from __future__ import annotations

import logging

import httpx

from src.config import Settings
from src.schemas import Action, EventRecord

logger = logging.getLogger("warden.clients")


class OrchestratorClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def execute(self, action: Action, event: EventRecord) -> str:
        if action == Action.no_action:
            return "no_action_recorded"
        if action == Action.notify_human:
            return "human_notification_only"

        payload = {
            "project_id": event.project_id,
            "environment_id": event.environment_id,
            "event_id": event.id,
            "action": action.value,
        }
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(f"{self.settings.orchestrator_base_url}/actions", json=payload)
            response.raise_for_status()
        result = response.json()["result"]
        logger.info("action_executed_via_orchestrator", extra={"extra_fields": payload | {"result": result}})
        return result


class NotifierClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def notify(self, message: dict) -> None:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(f"{self.settings.notifier_base_url}/notify", json=message)
            response.raise_for_status()
        logger.info("notification_sent", extra={"extra_fields": message})
