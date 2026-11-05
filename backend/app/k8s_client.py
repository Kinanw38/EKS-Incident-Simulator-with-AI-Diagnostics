import logging
import os
import shlex
import subprocess
import time

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
        self.discovery_v1 = None
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
            self.discovery_v1 = client.DiscoveryV1Api()

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

    def get_service_endpoints_summary(
        self,
        service_name: str,
        namespace: str = "default",
    ) -> str:
        """Describe how many ready endpoints a Service has (live mode only).

        Uses EndpointSlice, because the older Endpoints API is deprecated.
        """
        try:
            slices = self.discovery_v1.list_namespaced_endpoint_slice(
                namespace=namespace,
                label_selector=f"kubernetes.io/service-name={service_name}",
                _request_timeout=10,
            )
            ready = 0
            for endpoint_slice in slices.items:
                for endpoint in endpoint_slice.endpoints or []:
                    conditions = endpoint.conditions
                    if conditions is None or conditions.ready is not False:
                        ready += 1
            return (
                f"Service '{service_name}' has {ready} ready endpoint(s)."
                + (" Traffic cannot reach any pod." if ready == 0 else "")
            )
        except Exception as exc:
            return f"Could not read endpoints for Service '{service_name}': {exc}"

    def get_telemetry_for_component(
        self,
        label_selector: str,
        namespace: str = "default",
        service_name: str | None = None,
    ) -> tuple[str, str]:
        """Fetch live pod logs and events for RCA analysis.

        label_selector is the value of the pod label "app". If service_name
        is given, the Service's endpoint status is appended to the events,
        because routing problems are not visible in pod logs.
        """
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

            if service_name:
                events += "\n" + self.get_service_endpoints_summary(
                    service_name, namespace
                )

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

    def wait_for_deployments_ready(
        self,
        manifest_yaml: str,
        timeout_seconds: int = 60,
        poll_seconds: int = 3,
    ) -> dict:
        """Check whether the Deployments in a manifest become available.

        Demo mode simulates the check. In live mode it polls the real
        Deployment status instead of claiming success.
        """
        if self.force_demo:
            return {"verified": False, "simulated": True, "details": []}

        names = []
        for document in yaml.safe_load_all(manifest_yaml):
            if document and document.get("kind") == "Deployment":
                metadata = document.get("metadata", {})
                names.append(
                    (metadata["name"], metadata.get("namespace", "default"))
                )

        if not names:
            return {"verified": True, "simulated": False, "details": []}

        deadline = time.monotonic() + timeout_seconds
        details = []

        while True:
            details = []
            all_ready = True

            for name, namespace in names:
                deployment = self.apps_v1.read_namespaced_deployment_status(
                    name=name, namespace=namespace
                )
                desired = deployment.spec.replicas or 0
                ready = deployment.status.ready_replicas or 0
                details.append(f"{name}: {ready}/{desired} ready")
                if ready < desired:
                    all_ready = False

            if all_ready:
                return {"verified": True, "simulated": False, "details": details}

            if time.monotonic() >= deadline:
                return {"verified": False, "simulated": False, "details": details}

            time.sleep(poll_seconds)

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
        """Return deterministic output for the public demo.

        Note: this returns only the raw command output, with no
        "[DEMO OUTPUT]" prefix — the frontend already prepends
        "[{mode} OUTPUT]" uniformly for DEMO/LIVE/OFFLINE, so adding
        it here too caused a duplicated label in the terminal.
        """
        normalized_command = command.strip()

        if normalized_command == "kubectl get pods":
            return (
                "NAME                              READY   STATUS                       RESTARTS   AGE\n"
                "api-service-8646b9657c-x92kl     0/1     OOMKilled                    4          2m15s\n"
                "auth-service-758dfc489d-p4l89     0/1     CreateContainerConfigError   0          1m40s\n"
                "payment-backend-5c8bd456f-m9qwx  1/1     Running                      0          5m10s"
            )

        if normalized_command == "kubectl get services":
            return (
                "NAME              TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)   AGE\n"
                "kubernetes        ClusterIP   10.100.0.1       <none>        443/TCP   12d\n"
                "payment-service   ClusterIP   10.100.142.89    <none>        80/TCP    5m10s"
            )

        if normalized_command == "kubectl get events":
            return (
                "LAST SEEN   TYPE      REASON      OBJECT                        MESSAGE\n"
                "12s         Warning   OOMKilled   pod/api-service-8646b9657c    Memory limit of 64Mi exceeded.\n"
                "45s         Warning   Failed      pod/auth-service-758dfc489d   Error: secret \"missing-db-secret\" not found"
            )

        if normalized_command == "kubectl get deployments":
            return (
                "NAME              READY   UP-TO-DATE   AVAILABLE   AGE\n"
                "api-service       0/1     1            0           2m15s\n"
                "auth-service      0/1     1            0           1m40s\n"
                "payment-backend   1/1     1            1           5m10s"
            )

        if normalized_command == "kubectl get nodes":
            return (
                "NAME                         STATUS   ROLES    AGE   VERSION\n"
                "demo-node-1                 Ready    <none>   12d   v1.29.0\n"
                "demo-node-2                 Ready    <none>   12d   v1.29.0"
            )

        if normalized_command == "kubectl cluster-info":
            return (
                "Kubernetes control plane is running in simulated demo mode.\n"
                "No AWS or Kubernetes resources were contacted."
            )

        return (
            f"Simulated output for command: {normalized_command}\n"
            "No live Kubernetes cluster was contacted."
        )


k8s_manager = KubernetesManager()