from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from src.clients import NotifierClient, OrchestratorClient
from src.config import Settings
from src.repositories import ApprovalRepository, EventRepository
from src.schemas import ApprovalRecord, ApprovalResolution, EventIn, EventRecord
from src.llm import LLMClient
from src.policy import apply_safety_policy

logger = logging.getLogger("warden.service")


class WardenService:
    def __init__(
        self,
        settings: Settings,
        event_repository: EventRepository,
        approval_repository: ApprovalRepository,
        llm_client: LLMClient,
        orchestrator_client: OrchestratorClient,
        notifier_client: NotifierClient,
    ) -> None:
        self.settings = settings
        self.event_repository = event_repository
        self.approval_repository = approval_repository
        self.llm_client = llm_client
        self.orchestrator_client = orchestrator_client
        self.notifier_client = notifier_client

    async def process_event(self, event_in: EventIn) -> EventRecord:
        now = datetime.now(timezone.utc)
        event = EventRecord(
            id=str(uuid4()),
            project_id=event_in.project_id,
            environment_id=event_in.environment_id,
            severity=event_in.severity,
            signal=event_in.signal,
            context=event_in.context,
            timestamp=event_in.timestamp,
            status="received",
            created_at=now,
            updated_at=now,
        )
        self.event_repository.create(event)
        logger.info("event_received", extra={"extra_fields": {"event_id": event.id, "project_id": event.project_id}})

        history = self.event_repository.history(event.project_id, event.environment_id, self.settings.history_limit + 1)
        history = [item for item in history if item.event_id != event.id][: self.settings.history_limit]
        decision = await self.llm_client.reason(event_in, history)
        logger.info(
            "llm_decision_produced",
            extra={"extra_fields": {"event_id": event.id, "decision": decision.model_dump(mode="json")}},
        )

        constrained_decision, restrictions = apply_safety_policy(
            event_in,
            decision,
            self.settings.productive_environment_names,
        )
        if restrictions:
            logger.info(
                "safety_policy_applied",
                extra={"extra_fields": {"event_id": event.id, "restrictions": restrictions}},
            )

        event.llm_decision = constrained_decision

        if constrained_decision.safe_to_auto:
            event.status = "auto_executing"
            result = await self._execute_action(event, constrained_decision.action.value)
            event.status = "completed"
            event.action_result = result
        else:
            approval = ApprovalRecord(
                id=str(uuid4()),
                event_id=event.id,
                action=constrained_decision.action,
                status="pending",
                requested_reason=constrained_decision.reasoning,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.approval_repository.create(approval)
            event.approval_id = approval.id
            event.status = "pending_approval"
            await self.notifier_client.notify(
                {
                    "type": "approval_required",
                    "approval_id": approval.id,
                    "event_id": event.id,
                    "project_id": event.project_id,
                    "environment_id": event.environment_id,
                    "proposed_action": constrained_decision.action.value,
                }
            )

        event.updated_at = datetime.now(timezone.utc)
        self.event_repository.update(event)
        return event

    async def _execute_action(self, event: EventRecord, action: str) -> str:
        result = await self.orchestrator_client.execute(event.llm_decision.action, event)
        logger.info("action_execution_result", extra={"extra_fields": {"event_id": event.id, "result": result}})
        if event.llm_decision.action.value == "notify_human":
            await self.notifier_client.notify(
                {
                    "type": "notification_only",
                    "event_id": event.id,
                    "project_id": event.project_id,
                    "environment_id": event.environment_id,
                }
            )
        return result

    async def approve(self, approval_id: str) -> ApprovalResolution:
        approval = self.approval_repository.get(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval request not found")
        if approval.status != "pending":
            raise HTTPException(status_code=409, detail="Approval request is not pending")
        event = self.event_repository.get(approval.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        result = await self.orchestrator_client.execute(approval.action, event)
        self.approval_repository.update_status(approval_id, "approved")
        event.status = "completed"
        event.action_result = result
        event.updated_at = datetime.now(timezone.utc)
        self.event_repository.update(event)
        return ApprovalResolution(
            approval_id=approval_id,
            event_id=event.id,
            status="approved",
            action_result=result,
        )

    async def reject(self, approval_id: str) -> ApprovalResolution:
        approval = self.approval_repository.get(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval request not found")
        if approval.status != "pending":
            raise HTTPException(status_code=409, detail="Approval request is not pending")
        event = self.event_repository.get(approval.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        self.approval_repository.update_status(approval_id, "rejected")
        event.status = "rejected"
        event.action_result = "action_rejected_by_human"
        event.updated_at = datetime.now(timezone.utc)
        self.event_repository.update(event)
        return ApprovalResolution(
            approval_id=approval_id,
            event_id=event.id,
            status="rejected",
            action_result=event.action_result,
        )
