from __future__ import annotations


def test_webhook_rejects_malformed_payload(client):
    response = client.post(
        "/webhook",
        json={
            "project_id": "payments-api",
            "environment_id": "prod",
            "severity": "bad-value",
            "signal": "P99 latency spiked",
            "context": {},
            "timestamp": "2024-04-03T14:45:00Z",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid webhook payload"


def test_critical_event_requires_approval(client):
    response = client.post(
        "/webhook",
        json={
            "project_id": "payments-api",
            "environment_id": "prod",
            "severity": "critical",
            "signal": "P99 latency spiked to 4s after the 14:30 deploy",
            "context": {"last_deploy": "v2.3.1"},
            "timestamp": "2024-04-03T14:45:00Z",
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending_approval"
    approvals = client.get("/approvals")
    assert approvals.status_code == 200
    assert len(approvals.json()) == 1


def test_non_prod_restart_auto_executes(client):
    response = client.post(
        "/webhook",
        json={
            "project_id": "checkout-api",
            "environment_id": "qa",
            "severity": "medium",
            "signal": "Pod crashloop requires restart",
            "context": {"pod": "checkout-api-784d"},
            "timestamp": "2024-04-03T14:45:00Z",
        },
    )
    assert response.status_code == 202
    event_id = response.json()["event_id"]
    event = client.get(f"/events/{event_id}")
    assert event.status_code == 200
    payload = event.json()
    assert payload["status"] == "completed"
    assert payload["action_result"] == "restart_executed"


def test_prod_scale_up_requires_approval_due_to_policy(client):
    response = client.post(
        "/webhook",
        json={
            "project_id": "inventory-api",
            "environment_id": "prod",
            "severity": "high",
            "signal": "CPU saturation and latency spike",
            "context": {"cpu_usage": "91%"},
            "timestamp": "2024-04-03T14:45:00Z",
        },
    )
    assert response.status_code == 202
    event_id = response.json()["event_id"]
    event = client.get(f"/events/{event_id}").json()
    assert event["status"] == "pending_approval"
    assert event["llm_decision"]["action"] == "scale_up"
    assert event["llm_decision"]["safe_to_auto"] is False
