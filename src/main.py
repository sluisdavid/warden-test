from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.clients import NotifierClient, OrchestratorClient
from src.config import get_settings
from src.database import Database
from src.llm import LLMClient
from src.logging_config import configure_logging
from src.repositories import ApprovalRepository, EventRepository
from src.schemas import EventIn
from src.service import WardenService

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("warden.api")
database = Database(settings.database_url)
event_repository = EventRepository(database)
approval_repository = ApprovalRepository(database)
service = WardenService(
    settings=settings,
    event_repository=event_repository,
    approval_repository=approval_repository,
    llm_client=LLMClient(settings),
    orchestrator_client=OrchestratorClient(settings),
    notifier_client=NotifierClient(settings),
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize()
    yield


app = FastAPI(title="Warden", version="1.0.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    logger.error("request_validation_error", extra={"extra_fields": {"errors": exc.errors()}})
    return JSONResponse(status_code=422, content={"detail": "Invalid webhook payload", "errors": exc.errors()})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


@app.post("/webhook", status_code=202)
async def webhook(event_in: EventIn):
    event = await service.process_event(event_in)
    return {"event_id": event.id, "status": event.status, "approval_id": event.approval_id}


@app.get("/events")
async def list_events():
    return event_repository.list()


@app.get("/events/{event_id}")
async def get_event(event_id: str):
    event = event_repository.get(event_id)
    if not event:
        return JSONResponse(status_code=404, content={"detail": "Event not found"})
    return event


@app.get("/approvals")
async def list_approvals():
    return approval_repository.list_pending()


@app.post("/approvals/{approval_id}/approve")
async def approve(approval_id: str):
    return await service.approve(approval_id)


@app.post("/approvals/{approval_id}/reject")
async def reject(approval_id: str):
    return await service.reject(approval_id)
