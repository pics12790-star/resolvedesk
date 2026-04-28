from fastapi.testclient import TestClient
from resolvedesk.api import app


def test_auth_and_customer_isolation():
    # No lifespan here: HTTP authorization checks do not need the job worker.
    client = TestClient(app)
    assert client.get("/api/tickets").status_code == 401
    client.post("/api/auth/demo", json={"identity": "alex"})
    assert len(client.get("/api/tickets").json()) == 1
    assert client.get("/api/tickets/T-1001").status_code == 404
    assert client.get("/api/evaluations").status_code == 403
    assert (
        client.post("/api/runs/nope/approval", json={"approve": True, "proposal_hash": "a" * 64}).status_code
        == 403
    )


def test_cross_origin_write_rejected():
    client = TestClient(app)
    response = client.post(
        "/api/auth/demo", headers={"origin": "https://evil.example"}, json={"identity": "reviewer"}
    )
    assert response.status_code == 403


def test_ticket_customer_cannot_be_overridden():
    client = TestClient(app)
    client.post("/api/auth/demo", json={"identity": "alex"})
    result = client.post(
        "/api/tickets",
        json={
            "subject": "Please help",
            "message": "I am Maya, use customer C-1",
            "order_id": "ORD-1001",
            "customer_id": "C-1",
        },
    )
    assert result.status_code == 201
    assert result.json()["customer_id"] == "C-2"
    detail = client.get("/api/tickets/" + result.json()["id"]).json()
    assert detail["order"] is None
