import pytest

from app import rca_engine


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Never contact a real Ollama during tests."""

    def boom(*args, **kwargs):
        raise ConnectionError("disabled in tests")

    monkeypatch.setattr(rca_engine.requests, "post", boom)


def test_root(client):
    body = client.get("/").json()
    assert body["status"] == "running"
    assert body["mode"] == "demo"


def test_health_reports_demo_mode(client):
    body = client.get("/api/health").json()
    assert body["status"] == "healthy"
    assert body["mode"] == "demo"
    assert body["cluster"]["status"] == "DEMO"


def test_list_and_get_scenarios(client):
    scenarios = client.get("/api/scenarios").json()
    assert {s["id"] for s in scenarios} == {
        "oomkilled",
        "crashloop",
        "broken_routing",
    }
    assert client.get("/api/scenarios/oomkilled").status_code == 200


@pytest.mark.parametrize("incident_id", ["oomkilled", "crashloop", "broken_routing"])
def test_trigger_rca_and_remediate(client, incident_id):
    trigger = client.post(f"/api/scenarios/{incident_id}/trigger")
    assert trigger.status_code == 200
    assert trigger.json()["status"] == "ACTIVE"

    rca = client.get(f"/api/scenarios/{incident_id}/rca").json()
    assert rca["source"] == "DETERMINISTIC_EXPERT_ENGINE"
    assert rca["incident_id"] == incident_id

    fix = client.post("/api/remediate", json={"incident_id": incident_id})
    assert fix.status_code == 200
    body = fix.json()
    assert body["status"] == "RESOLVED"
    # Demo mode must not pretend it verified a real cluster.
    assert body["reconciliation_loop"][-1]["status"] == "SIMULATED"


def test_unknown_scenario_returns_404(client):
    assert client.get("/api/scenarios/nope").status_code == 404
    assert client.post("/api/scenarios/nope/trigger").status_code == 404
    assert client.get("/api/scenarios/nope/rca").status_code == 404
    response = client.post("/api/remediate", json={"incident_id": "nope"})
    assert response.status_code == 404


def test_health_analysis(client):
    body = client.get("/api/health-analysis").json()
    assert body["status"] == "healthy"


def test_terminal_allows_read_only_commands(client):
    response = client.post(
        "/api/terminal/execute", json={"command": "kubectl get pods"}
    )
    assert response.status_code == 200
    assert "NAME" in response.json()["output"]


@pytest.mark.parametrize(
    "command",
    ["kubectl delete pod x", "kubectl get pods; id", "rm -rf /"],
)
def test_terminal_rejects_dangerous_commands(client, command):
    response = client.post("/api/terminal/execute", json={"command": command})
    assert response.status_code == 403
