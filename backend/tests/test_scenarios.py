import yaml

from app.scenarios import SCENARIOS

REQUIRED_KEYS = {
    "id",
    "title",
    "category",
    "severity",
    "affected_component",
    "pod_label",
    "description",
    "problem_yaml",
    "fix_yaml",
}


def test_expected_scenarios_exist():
    assert set(SCENARIOS) == {
        "oomkilled",
        "crashloop",
        "broken_routing",
        "memory_leak",
        "cpu_saturation",
    }


def test_resource_incidents_are_bounded_by_limits():
    """A demo incident must not be able to exhaust a small cluster."""
    for key in ("memory_leak", "cpu_saturation"):
        for field in ("problem_yaml", "fix_yaml"):
            deployment = next(
                doc
                for doc in yaml.safe_load_all(SCENARIOS[key][field])
                if doc and doc.get("kind") == "Deployment"
            )
            assert deployment["spec"]["replicas"] <= 2, (key, field)
            for container in deployment["spec"]["template"]["spec"]["containers"]:
                limits = container["resources"]["limits"]
                assert "memory" in limits, (key, field)
                if key == "cpu_saturation":
                    assert "cpu" in limits, (key, field)


def test_k8s_folder_matches_the_scenarios():
    """k8s/*/ is a copy of each scenario's YAML, so they must not drift."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "k8s"
    folders = {
        "memory_leak": "04-memory-leak",
        "cpu_saturation": "05-cpu-saturation",
    }
    for key, folder in folders.items():
        for kind in ("problem", "fix"):
            on_disk = (root / folder / f"{kind}.yaml").read_text()
            assert on_disk == SCENARIOS[key][f"{kind}_yaml"], (key, kind)


def test_scenarios_have_required_keys_and_matching_ids():
    for key, scenario in SCENARIOS.items():
        assert REQUIRED_KEYS <= set(scenario), key
        assert scenario["id"] == key


def test_manifests_are_valid_yaml_with_kind_and_name():
    for key, scenario in SCENARIOS.items():
        for field in ("problem_yaml", "fix_yaml"):
            documents = [
                doc for doc in yaml.safe_load_all(scenario[field]) if doc
            ]
            assert documents, f"{key}.{field} is empty"
            for doc in documents:
                assert doc.get("kind"), f"{key}.{field} has no kind"
                assert doc.get("metadata", {}).get("name"), (
                    f"{key}.{field} has no metadata.name"
                )


def test_fix_differs_from_problem():
    for key, scenario in SCENARIOS.items():
        assert scenario["problem_yaml"] != scenario["fix_yaml"], key


def test_pod_label_matches_the_deployment_labels():
    """Telemetry finds pods by app=<pod_label>, so it must exist in the YAML."""
    for key, scenario in SCENARIOS.items():
        deployments = [
            doc
            for doc in yaml.safe_load_all(scenario["problem_yaml"])
            if doc and doc.get("kind") == "Deployment"
        ]
        labels = {
            doc["spec"]["template"]["metadata"]["labels"]["app"]
            for doc in deployments
        }
        assert scenario["pod_label"] in labels, key
