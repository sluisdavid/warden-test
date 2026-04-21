from __future__ import annotations


def _create_pending_approval(client):
    response = client.post(
        "/webhook",
        json={
            "project_id": "payments-api",
            "environment_id": "prod",
            "severity": "high",
            "signal": "P99 latency spiked to 4s after the 14:30 deploy",
            "context": {"last_deploy": "v2.3.1"},
            "timestamp": "2024-04-03T14:45:00Z",
        },
    )
    approval_id = response.json()["approval_id"]
    event_id = response.json()["event_id"]
    return approval_id, event_id


def test_approve_executes_action(client):
    approval_id, event_id = _create_pending_approval(client)
    response = client.post(f"/approvals/{approval_id}/approve")
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    event = client.get(f"/events/{event_id}")
    assert event.status_code == 200
    assert event.json()["action_result"] == "rollback_executed"


def test_reject_marks_event_and_preserves_feedback(client):
    approval_id, event_id = _create_pending_approval(client)
    response = client.post(f"/approvals/{approval_id}/reject")
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    event = client.get(f"/events/{event_id}")
    assert event.status_code == 200
    assert event.json()["status"] == "rejected"
    assert event.json()["action_result"] == "action_rejected_by_human"
