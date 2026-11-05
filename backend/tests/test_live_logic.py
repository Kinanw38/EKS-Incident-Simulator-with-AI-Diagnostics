"""Tests for the live-mode code paths, using fake Kubernetes clients."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app import rca_engine
from app.k8s_client import KubernetesManager
from app.scenarios import SCENARIOS


def make_live_manager():
    manager = KubernetesManager()  # demo mode, no cluster needed
    manager.force_demo = False
    manager.connected = True
    manager.mode = "live"
    manager.v1 = MagicMock()
    manager.apps_v1 = MagicMock()
    manager.discovery_v1 = MagicMock()
    return manager


def test_rca_endpoint_uses_pod_label_not_component_name(client, monkeypatch):
    """Regression: payment pods are labeled payment-processor."""
    from app import main

    captured = {}

    def fake_telemetry(label, namespace="default", service_name=None):
        captured["label"] = label
        captured["service_name"] = service_name
        return "logs", "events"

    monkeypatch.setattr(
        main.k8s_manager, "get_telemetry_for_component", fake_telemetry
    )
    monkeypatch.setattr(
        rca_engine.requests,
        "post",
        lambda *a, **k: (_ for _ in ()).throw(ConnectionError("off")),
    )

    response = client.get("/api/scenarios/broken_routing/rca")

    assert response.status_code == 200
    assert captured["label"] == SCENARIOS["broken_routing"]["pod_label"]
    assert captured["label"] == "payment-processor"
    assert captured["service_name"] == "payment-service"


def test_telemetry_selects_pods_by_label_and_reports_endpoints():
    manager = make_live_manager()
    pod = SimpleNamespace(metadata=SimpleNamespace(name="p-1"))
    manager.v1.list_namespaced_pod.return_value = SimpleNamespace(items=[pod])
    manager.v1.read_namespaced_pod_log.return_value = "some logs"
    manager.v1.list_namespaced_event.return_value = SimpleNamespace(items=[])
    manager.discovery_v1.list_namespaced_endpoint_slice.return_value = (
        SimpleNamespace(items=[])
    )

    logs, events = manager.get_telemetry_for_component(
        "payment-processor", service_name="payment-service"
    )

    kwargs = manager.v1.list_namespaced_pod.call_args.kwargs
    assert kwargs["label_selector"] == "app=payment-processor"
    assert logs == "some logs"
    assert "0 ready endpoint" in events


def test_wait_for_deployments_ready_reports_real_status():
    manager = make_live_manager()
    manager.apps_v1.read_namespaced_deployment_status.return_value = (
        SimpleNamespace(
            spec=SimpleNamespace(replicas=1),
            status=SimpleNamespace(
                ready_replicas=1, updated_replicas=1, replicas=1
            ),
        )
    )

    result = manager.wait_for_deployments_ready(
        SCENARIOS["oomkilled"]["fix_yaml"], timeout_seconds=5, poll_seconds=0
    )

    assert result["verified"] is True
    assert result["simulated"] is False
    assert "api-service: 1/1 ready" in result["details"]


def test_wait_for_deployments_ready_times_out():
    manager = make_live_manager()
    manager.apps_v1.read_namespaced_deployment_status.return_value = (
        SimpleNamespace(
            spec=SimpleNamespace(replicas=1),
            status=SimpleNamespace(
                ready_replicas=None, updated_replicas=None, replicas=None
            ),
        )
    )

    result = manager.wait_for_deployments_ready(
        SCENARIOS["oomkilled"]["fix_yaml"], timeout_seconds=0, poll_seconds=0
    )

    assert result["verified"] is False
    assert result["simulated"] is False


def test_wait_for_deployments_not_ready_while_old_pods_still_run():
    """During a rollout the old pod is Ready, but the new one is not yet."""
    manager = make_live_manager()
    manager.apps_v1.read_namespaced_deployment_status.return_value = (
        SimpleNamespace(
            spec=SimpleNamespace(replicas=1),
            status=SimpleNamespace(
                ready_replicas=1, updated_replicas=0, replicas=2
            ),
        )
    )

    result = manager.wait_for_deployments_ready(
        SCENARIOS["oomkilled"]["fix_yaml"], timeout_seconds=0, poll_seconds=0
    )

    assert result["verified"] is False


def _pod(phase, restarts, cpu="100m", memory="128Mi"):
    return SimpleNamespace(
        spec=SimpleNamespace(
            containers=[
                SimpleNamespace(
                    resources=SimpleNamespace(
                        requests={"cpu": cpu, "memory": memory}
                    )
                )
            ]
        ),
        status=SimpleNamespace(
            phase=phase,
            container_statuses=[SimpleNamespace(restart_count=restarts)],
        ),
    )


def test_live_metrics_use_real_counts_and_no_fake_usage():
    manager = make_live_manager()
    node = SimpleNamespace(
        status=SimpleNamespace(
            conditions=[SimpleNamespace(type="Ready", status="True")],
            allocatable={"cpu": "1930m", "memory": "3Gi"},
        )
    )
    manager.v1.list_node.return_value = SimpleNamespace(items=[node, node])
    manager.v1.list_pod_for_all_namespaces.return_value = SimpleNamespace(
        items=[_pod("Running", 0), _pod("Running", 2), _pod("Pending", 1)]
    )

    result = manager.get_metrics_summary()

    assert result["mode"] == "live"
    assert result["simulated"] is False
    assert result["nodes"] == {"total": 2, "ready": 2}
    assert result["pods"]["running"] == 2
    assert result["pods"]["pending"] == 1
    assert result["pods"]["restarts"] == 3
    assert result["capacity"] == {"cpu_cores": 3.86, "memory_gib": 6.0}
    # Usage needs metrics-server: never invent it in live mode.
    assert result["usage"] == {"cpu_percent": None, "memory_percent": None}
    # 3 pods x (100m, 128Mi) requested vs 3.86 vCPU / 6 GiB allocatable.
    assert result["reserved"]["cpu_percent"] == round(0.3 / 3.86 * 100, 1)
    assert result["reserved"]["memory_percent"] == round(0.375 / 6 * 100, 1)


def test_quantity_parsers():
    from app.k8s_client import _parse_cpu_cores, _parse_memory_gib

    assert _parse_cpu_cores("250m") == 0.25
    assert _parse_cpu_cores("2") == 2.0
    assert _parse_memory_gib("1Gi") == 1.0
    assert _parse_memory_gib("512Mi") == 0.5
    assert round(_parse_memory_gib("1G"), 3) == 0.931
    assert _parse_memory_gib(None) == 0.0


def test_metrics_unavailable_when_not_connected():
    manager = make_live_manager()
    manager.connected = False

    result = manager.get_metrics_summary()

    assert result["available"] is False
    assert result["mode"] == "unavailable"
