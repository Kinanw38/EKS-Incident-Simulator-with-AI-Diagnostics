import json

import requests

from app import rca_engine


def test_fallback_when_ollama_is_unreachable(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("no ollama")

    monkeypatch.setattr(rca_engine.requests, "post", boom)

    result = rca_engine.analyze_incident_telemetry("oomkilled", "logs", "events")

    assert result["source"] == "DETERMINISTIC_EXPERT_ENGINE"
    for key in ("root_cause", "impact", "recommended_fix"):
        assert result[key]


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_fallback_when_llm_returns_invalid_json(monkeypatch):
    monkeypatch.setattr(
        rca_engine.requests,
        "post",
        lambda *a, **k: FakeResponse(200, {"response": "not json"}),
    )

    result = rca_engine.analyze_incident_telemetry("crashloop", "", "")

    assert result["source"] == "DETERMINISTIC_EXPERT_ENGINE"


def test_fallback_when_llm_misses_required_keys(monkeypatch):
    monkeypatch.setattr(
        rca_engine.requests,
        "post",
        lambda *a, **k: FakeResponse(
            200, {"response": json.dumps({"root_cause": "x"})}
        ),
    )

    result = rca_engine.analyze_incident_telemetry("broken_routing", "", "")

    assert result["source"] == "DETERMINISTIC_EXPERT_ENGINE"


def test_valid_llm_answer_is_used(monkeypatch):
    answer = {"root_cause": "a", "impact": "b", "recommended_fix": "c"}
    monkeypatch.setattr(
        rca_engine.requests,
        "post",
        lambda *a, **k: FakeResponse(200, {"response": json.dumps(answer)}),
    )

    result = rca_engine.analyze_incident_telemetry("oomkilled", "", "")

    assert result["source"] == "AI_LLM_MODEL"
    assert result["root_cause"] == "a"


def test_crashloop_text_describes_the_real_pod_state(monkeypatch):
    """A missing Secret leaves the pod in CreateContainerConfigError."""

    def boom(*args, **kwargs):
        raise requests.ConnectionError("no ollama")

    monkeypatch.setattr(rca_engine.requests, "post", boom)

    result = rca_engine.analyze_incident_telemetry("crashloop", "", "")

    assert "CreateContainerConfigError" in result["impact"]
    assert "CrashLoopBackOff" not in result["impact"]
