from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Action(str, Enum):
    rollback = "rollback"
    restart = "restart"
    scale_up = "scale_up"
    notify_human = "notify_human"
    no_action = "no_action"


class EventIn(BaseModel):
    project_id: str = Field(min_length=1)
    environment_id: str = Field(min_length=1)
    severity: Severity
    signal: str = Field(min_length=1)
    context: dict[str, Any]
    timestamp: datetime

    model_config = ConfigDict(extra="forbid")


class LLMDecision(BaseModel):
    action: Action
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1)
    safe_to_auto: bool


class HistoryItem(BaseModel):
    event_id: str
    signal: str
    llm_action: str | None = None
    llm_confidence: float | None = None
    llm_safe_to_auto: bool | None = None
    execution_state: str
    result: str | None = None
    feedback: str | None = None
    created_at: datetime


class EventRecord(BaseModel):
    id: str
    project_id: str
    environment_id: str
    severity: Severity
    signal: str
    context: dict[str, Any]
    timestamp: datetime
    status: str
    llm_decision: LLMDecision | None = None
    approval_id: str | None = None
    action_result: str | None = None
    created_at: datetime
    updated_at: datetime


class ApprovalRecord(BaseModel):
    id: str
    event_id: str
    action: Action
    status: str
    requested_reason: str
    created_at: datetime
    updated_at: datetime


class ApprovalResolution(BaseModel):
    approval_id: str
    event_id: str
    status: str
    action_result: str | None = None

