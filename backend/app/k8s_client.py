import logging
import os
import shlex
import subprocess

import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException


logger = logging.getLogger(__name__)


class KubernetesManager:
    """
    Kubernetes integration layer.

    Modes:
    - DEMO_MODE=true:
        Uses deterministic mock responses and never connects to Kubernetes.
    - DEMO_MODE=false or unset:
        Attempts to connect to a real Kubernetes cluster.
    - If the real cluster cannot be reached:
        Reports UNAVAILABLE and never silently returns demo data.
    """

    def __init__(self):
        self.in_cluster = False
        self.connected = False
        self.v1 = None
        self.apps_v1 = None
        self.connection_error = None

        self.force_demo = (
            os.getenv("DEMO_MODE", "false").strip().lower() == "true"
        )

        if self.force_demo:
            self.mode = "demo"
            logger.info(
                "DEMO_MODE=true. Kubernetes integration is disabled; "
                "deterministic mock data will be used."
            )
        else:
            self.mode = "unavailable"
            self._init_k8s_client()

    def _init_k8s_client(self):
        """Load Kubernetes configuration and verify API connectivity."""
        try:
            if os.getenv("KUBERNETES_SERVICE_HOST"):
                config.load_incluster_config()
                self.in_cluster = True
                logger.info("Loaded in-cluster Kubernetes configuration.")
            else:
                config.load_kube_config()
                logger.info("Loaded local Kubernetes configuration.")

            self.v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()

            # Verify that the API server is reachable and credentials work.
            self.v1.list_namespace(_request_timeout=5)

            self.connected = True
            self.mode = "live"
            self.connection_error = None

            logger.info("Connected to live Kubernetes cluster.")

        except Exception as exc:
            self.connected = False
            self.mode = "unavailable"
            self.connection_error = str(exc)

            logger.error(
                "Could not connect to Kubernetes. "
                "The application will report UNAVAILABLE instead of using mock data: %s",
                exc,
            )

    def get_cluster_status(self) -> dict:
        """Return the current demo, live, or unavailable cluster status."""
        if self.force_demo:
            return {
                "status": "DEMO",
                "mode": "demo",
                "connected": False,
                "message": "Running with deterministic mock data.",
                "node_count": 2,
                "healthy_nodes": 2,
            }

        if not self.connected:
            return {
                "status": "UNAVAILABLE",
                "mode": "unavailable",
                "connected": False,
                "message": "Live Kubernetes cluster is not reachable.",
                "error": self.connection_error,
                "node_count": 0,
                "healthy_nodes": 0,
            }

        try:
            nodes = self.v1.list_node(_request_timeout=5)

            healthy_nodes = sum(
                1
                for node in nodes.items
                if any(
                    condition.type == "Ready"
                    and condition.status == "True"
                    for condition in (node.status.conditions or [])
                )
            )

            return {
                "status": "ONLINE",
                "mode": "live",
                "connected": True,
                "message": "Connected to live Kubernetes cluster.",
                "node_count": len(nodes.items),
                "healthy_nodes": healthy_nodes,
            }

        except Exception as exc:
            logger.exception("Failed to read live Kubernetes node status.")

            return {
                "status": "ERROR",
                "mode": "unavailable",
                "connected": False,
                "message": "The Kubernetes API request failed.",
                "error": str(exc),
                "node_count": 0,
                "healthy_nodes": 0,
            }

    def get_telemetry_for_component(
        self,
        label_selector: str,
        namespace: str = "default",
    ) -> tuple[str, str]:
        """Fetch live pod logs and events for RCA analysis."""
        if self.force_demo:
            return (
                "Demo mode active - deterministic mock logs.",
                "Demo mode active - deterministic mock events.",
            )

        if not self.connected:
            return (
                "Live telemetry unavailable.",
                f"Kubernetes connection error: {self.connection_error}",
            )

        try:
            pods = self.v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app={label_selector}",
                _request_timeout=10,
            )

            if not pods.items:
                return (
                    f"No pods found with label app={label_selector}",
                    "No pod events found.",
                )

            pod_name = pods.items[0].metadata.name

            try:
                logs = self.v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    tail_lines=50,
                    previous=True,
                    _request_timeout=10,
                )
            except Exception:
                try:
                    logs = self.v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=namespace,
                        tail_lines=50,
                        _request_timeout=10,
                    )
                except Exception as log_error:
                    logs = f"Log retrieval notice: {log_error}"

            events_list = self.v1.list_namespaced_event(
                namespace=namespace,
                field_selector=f"involvedObject.name={pod_name}",
                _request_timeout=10,
            )

            events = "\n".join(
                f"[{event.type}] {event.reason}: {event.message}"
                for event in events_list.items
            )

            if not events:
                events = "No specific events logged for this pod."

            return logs, events

        except Exception as exc:
            logger.exception(
                "Failed to collect telemetry for component '%s'.",
                label_selector,
            )

            return (
                f"Telemetry error: {exc}",
                f"Event retrieval error: {exc}",
            )

    def apply_manifest(self, manifest_yaml: str) -> str:
        """
        Apply supported Kubernetes resources.

        In demo mode, no Kubernetes API call is made.
        In live mode, Deployment, Service, and Secret resources are supported.
        """
        if self.force_demo:
            return "DEMO_MODE: manifest application simulated successfully."

        if not self.connected:
            raise RuntimeError(
                "Live Kubernetes cluster is unavailable. "
                "Check AWS credentials, kubeconfig, cluster connectivity, "
                f"and permissions. Details: {self.connection_error}"
            )

        try:
            documents = list(yaml.safe_load_all(manifest_yaml))

            for manifest in documents:
                if not manifest:
                    continue

                kind = manifest.get("kind")
                metadata = manifest.get("metadata", {})
                name = metadata.get("name")
                namespace = metadata.get("namespace", "default")

                if not kind or not name:
                    raise RuntimeError(
                        "Manifest must contain both kind and metadata.name."
                    )

                if kind == "Deployment":
                    try:
                        self.apps_v1.create_namespaced_deployment(
                            namespace=namespace,
                            body=manifest,
                        )
                    except ApiException as exc:
                        if exc.status == 409:
                            self.apps_v1.replace_namespaced_deployment(
                                name=name,
                                namespace=namespace,
                                body=manifest,
                            )
                        else:
                            raise

                elif kind == "Service":
                    try:
                        self.v1.create_namespaced_service(
                            namespace=namespace,
                            body=manifest,
                        )
                    except ApiException as exc:
                        if exc.status == 409:
                            self.v1.replace_namespaced_service(
                                name=name,
                                namespace=namespace,
                                body=manifest,
                            )
                        else:
                            raise

                elif kind == "Secret":
                    try:
                        self.v1.create_namespaced_secret(
                            namespace=namespace,
                            body=manifest,
                        )
                    except ApiException as exc:
                        if exc.status == 409:
                            self.v1.replace_namespaced_secret(
                                name=name,
                                namespace=namespace,
                                body=manifest,
                            )
                        else:
                            raise

                else:
                    raise RuntimeError(
                        f"Unsupported Kubernetes resource kind: {kind}"
                    )

            return "Manifest applied successfully to the live cluster."

        except Exception as exc:
            raise RuntimeError(f"Failed to apply manifest: {exc}") from exc

    def execute_terminal_cmd(self, command: str) -> str:
        """
        Execute an already allowlisted kubectl command.

        Demo mode returns mock output.
        Live mode executes kubectl without a shell.
        """
        if self.force_demo:
            return self._get_demo_terminal_output(command)

        if not self.connected:
            raise RuntimeError(
                "Cannot execute a live kubectl command because "
                "the Kubernetes cluster is unavailable. "
                f"Details: {self.connection_error}"
            )

        try:
            command_args = shlex.split(command)

            result = subprocess.run(
                command_args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )

            output = result.stdout.strip() or result.stderr.strip()

            if not output:
                output = "Command completed without output."

            return output

        except subprocess.TimeoutExpired:
            return "Execution error: kubectl command timed out after 15 seconds."

        except Exception as exc:
            return f"Execution error: {exc}"

    @staticmethod
    def _get_demo_terminal_output(command: str) -> str:
        """Return deterministic output for the public demo."""
        normalized_command = command.strip()

        if normalized_command == "kubectl get pods":
            return (
                "[DEMO OUTPUT]\n"
                "NAME                              READY   STATUS             RESTARTS   AGE\n"
                "api-service-8646b9657c-x92kl     0/1     OOMKilled          4          2m15s\n"
                "auth-service-758dfc489d-p4l89     0/1     CrashLoopBackOff   3          1m40s\n"
                "payment-backend-5c8bd456f-m9qwx  1/1     Running            0          5m10s"
            )

        if normalized_command == "kubectl get services":
            return (
                "[DEMO OUTPUT]\n"
                "NAME              TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)   AGE\n"
                "kubernetes        ClusterIP   10.100.0.1       <none>        443/TCP   12d\n"
                "payment-service   ClusterIP   10.100.142.89    <none>        80/TCP    5m10s"
            )

        if normalized_command == "kubectl get events":
            return (
                "[DEMO OUTPUT]\n"
                "LAST SEEN   TYPE      REASON      OBJECT                        MESSAGE\n"
                "12s         Warning   OOMKilled   pod/api-service-8646b9657c    Memory limit of 64Mi exceeded.\n"
                "45s         Warning   Failed      pod/auth-service-758dfc489d   Secret missing-db-secret was not found."
            )

        if normalized_command == "kubectl get deployments":
            return (
                "[DEMO OUTPUT]\n"
                "NAME              READY   UP-TO-DATE   AVAILABLE   AGE\n"
                "api-service       0/1     1            0           2m15s\n"
                "auth-service      0/1     1            0           1m40s\n"
                "payment-backend   1/1     1            1           5m10s"
            )

        if normalized_command == "kubectl get nodes":
            return (
                "[DEMO OUTPUT]\n"
                "NAME                         STATUS   ROLES    AGE   VERSION\n"
                "demo-node-1                 Ready    <none>   12d   v1.29.0\n"
                "demo-node-2                 Ready    <none>   12d   v1.29.0"
            )

        if normalized_command == "kubectl cluster-info":
            return (
                "[DEMO OUTPUT]\n"
                "Kubernetes control plane is running in simulated demo mode.\n"
                "No AWS or Kubernetes resources were contacted."
            )

        return (
            "[DEMO OUTPUT]\n"
            f"Simulated output for command: {normalized_command}\n"
            "No live Kubernetes cluster was contacted."
        )


k8s_manager = KubernetesManager()