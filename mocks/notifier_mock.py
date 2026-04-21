from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="notifier-mock")
notifications: list[dict] = []


@app.post("/notify")
async def notify(payload: dict):
    notifications.append(payload)
    return {"status": "sent", "count": len(notifications)}


@app.get("/notifications")
async def list_notifications():
    return notifications
