from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="orchestrator-mock")


@app.post("/actions")
async def execute_action(payload: dict):
    action = payload["action"]
    mapping = {
        "rollback": "rollback_executed",
        "restart": "restart_executed",
        "scale_up": "scale_up_executed",
    }
    return {"result": mapping.get(action, "noop")}
