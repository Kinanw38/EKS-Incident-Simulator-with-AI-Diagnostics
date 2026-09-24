import yaml
import os
import subprocess
import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)

class KubernetesManager:
    def __init__(self):
        self.in_cluster = False
        self.connected = False
        self.v1 = None
        self.apps_v1 = None

        # Check whether DEMO mode was explicitly forced via environment variable
        self.force_demo = os.getenv("DEMO_MODE", "false").lower() == "true"

        if self.force_demo:
            logger.info("DEMO_MODE=true activated. Skipping K8s connection, using Mock mode.")
        else:
            self._init_k8s_client()

    def _init_k8s_client(self):
        """Initializes connection to Kubernetes API server or falls back gracefully."""
        try:
            if os.getenv("KUBERNETES_SERVICE_HOST"):
                config.load_incluster_config()
                self.in_cluster = True
                logger.info("Loaded in-cluster Kubernetes configuration.")
            else:
                config.load_kube_config()
                logger.info("Loaded local kubeconfig.")

            self.v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self.connected = True

        except Exception as e:
            logger.warning(f"Could not connect to K8s cluster: {e}. Falling back to Mock mode.")
            self.connected = False

    def get_cluster_status(self) -> dict:
        if not self.connected or self.force_demo:
            return {
                "status": "DEMO_MODE",
                "connected": False,
                "message": "Running in simulated local mode (No live EKS cluster detected)",
                "node_count": 2,
                "healthy_nodes": 2
            }

        try:
            nodes = self.v1.list_node()

            return {
                "status": "ONLINE",
                "connected": True,
                "node_count": len(nodes.items),
                "healthy_nodes": len([
                    n for n in nodes.items
                    if any(
                        cond.type == "Ready" and cond.status == "True"
                        for cond in n.status.conditions
                    )
                ])
            }

        except Exception as e:
            return {
                "status": "ERROR",
                "connected": False,
                "error": str(e)
            }

    def get_telemetry_for_component(self, label_selector: str, namespace: str = "default") -> tuple[str, str]:
        """Fetches live Pod logs and Events from EKS for RCA analysis."""
        if not self.connected or self.force_demo:
            return "Demo mode active - no live logs.", "Demo mode active - no live events."

        try:
            pods = self.v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app={label_selector}"
            )

            if not pods.items:
                return f"No pods found with label app={label_selector}", "No pod events found."

            pod_name = pods.items[0].metadata.name

            # Fetch Container Logs
            try:
                logs = self.v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    tail_lines=50,
                    previous=True  # Fetch logs from crashed instance if available
                )
            except Exception:
                try:
                    logs = self.v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=namespace,
                        tail_lines=50
                    )
                except Exception as log_err:
                    logs = f"Log retrieval notice: {str(log_err)}"

            # Fetch Pod Events
            events_list = self.v1.list_namespaced_event(
                namespace=namespace,
                field_selector=f"involvedObject.name={pod_name}"
            )

            events = "\n".join([
                f"[{e.type}] {e.reason}: {e.message}"
                for e in events_list.items
            ]) or "No specific events logged for this pod."

            return logs, events

        except Exception as e:
            return f"Telemetry Error: {str(e)}", f"Event Retrieval Error: {str(e)}"

    def apply_manifest(self, manifest_yaml: str) -> str:
        """Applies Kubernetes resources defined in a YAML manifest (Deployment, Service, Secret)."""
        if not self.connected or self.force_demo:
            return "DEMO_MODE"

        try:
            documents = list(yaml.safe_load_all(manifest_yaml))

            for manifest in documents:
                if not manifest:
                    continue

                kind = manifest.get("kind")
                name = manifest["metadata"]["name"]
                namespace = manifest["metadata"].get("namespace", "default")

                if kind == "Deployment":
                    try:
                        self.apps_v1.create_namespaced_deployment(
                            namespace=namespace,
                            body=manifest
                        )
                    except ApiException as e:
                        if e.status == 409:
                            self.apps_v1.replace_namespaced_deployment(
                                name=name,
                                namespace=namespace,
                                body=manifest
                            )
                        else:
                            raise

                elif kind == "Service":
                    try:
                        self.v1.create_namespaced_service(
                            namespace=namespace,
                            body=manifest
                        )
                    except ApiException as e:
                        if e.status == 409:
                            self.v1.replace_namespaced_service(
                                name=name,
                                namespace=namespace,
                                body=manifest
                            )
                        else:
                            raise

                elif kind == "Secret":
                    try:
                        self.v1.create_namespaced_secret(
                            namespace=namespace,
                            body=manifest
                        )
                    except ApiException as e:
                        if e.status == 409:
                            self.v1.replace_namespaced_secret(
                                name=name,
                                namespace=namespace,
                                body=manifest
                            )
                        else:
                            raise

                else:
                    raise RuntimeError(
                        f"Unsupported Kubernetes resource kind: {kind}"
                    )

            return "Manifest applied successfully."

        except Exception as e:
            raise RuntimeError(f"Failed to apply manifest: {e}")

    def execute_terminal_cmd(self, command: str) -> str:
        """Executes a validated kubectl command."""
        if not self.connected or self.force_demo:
            if "get pods" in command:
                return (
                    "NAME                           READY   STATUS             RESTARTS   AGE\n"
                    "api-service-8646b9657c-x92kl   0/1     OOMKilled          4          2m15s\n"
                    "auth-service-758dfc489d-p4l89   0/1     CrashLoopBackOff   3          1m40s\n"
                    "payment-backend-5c8bd456f-m9qwx  1/1     Running            0          5m10s"
                )
            elif "get services" in command:
                return (
                    "NAME              TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)   AGE\n"
                    "kubernetes        ClusterIP   10.100.0.1       <none>        443/TCP   12d\n"
                    "payment-service   ClusterIP   10.100.142.89    <none>        80/TCP    5m10s"
                )
            elif "get events" in command:
                return (
                    "LAST SEEN   TYPE      REASON      OBJECT                        MESSAGE\n"
                    "12s         Warning   OOMKilled   pod/api-service-8646b9657c    Memory limit of 64Mi exceeded.\n"
                    "45s         Warning   Failed      pod/auth-service-758dfc489d   Error: Secret missing-db-secret not found."
                )
            else:
                return f"Simulated output for command: {command}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )

            return result.stdout if result.returncode == 0 else result.stderr

        except Exception as e:
            return f"Execution Error: {str(e)}"


k8s_manager = KubernetesManager()