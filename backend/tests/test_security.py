import pytest

from app.security import is_command_allowed


@pytest.mark.parametrize(
    "command",
    [
        "kubectl get pods",
        "kubectl get services",
        "kubectl get events",
        "kubectl get deployments",
        "kubectl get nodes",
        "kubectl get pods -n kube-system",
        "kubectl describe pod my-pod-1",
        "kubectl logs my-pod-1 --tail=50",
        "kubectl cluster-info",
        "kubectl version",
        "kubectl version --client",
    ],
)
def test_allowed_commands(command):
    allowed, _ = is_command_allowed(command)
    assert allowed, command


@pytest.mark.parametrize(
    "command",
    [
        "",
        "   ",
        "ls",
        "kubectl delete pod my-pod",
        "kubectl exec -it my-pod -- sh",
        "kubectl get secrets",
        "kubectl apply -f x.yaml",
        "kubectl get pods; id",
        "kubectl get pods && id",
        "kubectl get pods || id",
        "kubectl get pods | cat",
        "kubectl get pods `id`",
        "kubectl get pods $(id)",
        "kubectl get pods > /tmp/out",
        "kubectl get pods < /etc/passwd",
        "kubectl get pods\nid",
        "kubectl get pods\\ id",
        "kubectl version --short",
        "kubectl get pods " + "a" * 300,
    ],
)
def test_rejected_commands(command):
    allowed, _ = is_command_allowed(command)
    assert not allowed, command


def test_non_string_is_rejected():
    allowed, _ = is_command_allowed(None)
    assert not allowed
