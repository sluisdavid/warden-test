from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    test_data_dir = Path(__file__).resolve().parent / ".testdata"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    db_path = test_data_dir / f"warden-test-{uuid4()}.db"
    monkeypatch.setenv("WARDEN_DATABASE_URL", str(db_path))
    monkeypatch.setenv("WARDEN_LLM_PROVIDER", "heuristic")
    monkeypatch.setenv("WARDEN_HISTORY_LIMIT", "3")
    monkeypatch.setenv("WARDEN_ORCHESTRATOR_BASE_URL", "http://testserver")
    monkeypatch.setenv("WARDEN_NOTIFIER_BASE_URL", "http://testserver")

    from src import main
    from src.clients import NotifierClient, OrchestratorClient

    class FakeOrchestratorClient(OrchestratorClient):
        async def execute(self, action, event):
            return f"{action.value}_executed"

    class FakeNotifierClient(NotifierClient):
        def __init__(self, settings):
            super().__init__(settings)
            self.messages: list[dict] = []

        async def notify(self, message: dict) -> None:
            self.messages.append(message)

    main.settings = main.get_settings.cache_clear() or main.get_settings()
    main.database = main.Database(main.settings.database_url)
    main.event_repository = main.EventRepository(main.database)
    main.approval_repository = main.ApprovalRepository(main.database)
    notifier = FakeNotifierClient(main.settings)
    main.service = main.WardenService(
        settings=main.settings,
        event_repository=main.event_repository,
        approval_repository=main.approval_repository,
        llm_client=main.LLMClient(main.settings),
        orchestrator_client=FakeOrchestratorClient(main.settings),
        notifier_client=notifier,
    )
    main.database.initialize()
    test_client = TestClient(main.app)
    test_client.notifier = notifier
    return test_client
