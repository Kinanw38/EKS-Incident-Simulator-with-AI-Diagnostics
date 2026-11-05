# Changelog

All notable changes to this project are listed here.

## [2.0.0]

A large update across the dashboard, the incident library, the infrastructure code and the setup and teardown scripts.

### Added

- **Cluster metrics dashboard** (`GET /api/metrics`): nodes, pods, restarts, capacity, and CPU/memory gauges. Demo Mode returns simulated values labelled `SIMULATED` that follow the active incident; Live Mode returns real counts from the Kubernetes API and real usage from metrics-server, with a "reserved" fallback (pod requests versus allocatable capacity) when usage is not available yet. An "unhealthy pods" count includes pods that are `Running` but not Ready, which is how OOMKilled and crash-looping pods appear.
- **Two incident scenarios that move the metrics**: `memory_leak` and `cpu_saturation`. Both are bounded by resource limits and at most two replicas.
- **Light and dark themes** with a toggle (remembered in the browser), a warmer palette, and a responsive layout with bottom navigation on small screens.
- **metrics-server** installed by `setup.sh`, from a vendored and pinned manifest in `k8s/metrics-server/` (one local change: a memory limit).
- **Automatic detection of the allowed IP range** for the EKS API endpoint, based on several lookups, with a connectivity check after the cluster is created and an offer to widen the range. `EKS_ALLOWED_CIDR` accepts a CIDR or `open`.
- **Post-destroy verification** in `destroy.sh` with a PASS/FAIL list.
- ShellCheck and shell script tests in CI, `backend.s3.example` for team setups, a non-root container with a health check, CodeQL, and a pytest suite.
- Terraform: a `kubernetes_version` variable, a `cluster_version` output, and validation of node group sizes.

### Changed

- **`setup.sh`**: confirms the AWS account and an approximate cost before creating anything; starts services in their own process groups and binds them to `127.0.0.1`; waits for nodes with `kubectl wait`; imports an existing CloudWatch log group instead of failing; reports the failing phase and command.
- **`destroy.sh`**: uses its own temporary kubeconfig instead of the current context; deletes only resources labelled `app.kubernetes.io/part-of=incident-simulator` and any `LoadBalancer` Service; waits only when needed; retries `terraform destroy`; removes this cluster from `~/.kube/config`.
- **Terraform**: pinned Kubernetes version (1.35), Amazon Linux 2023 nodes, a CloudWatch log group managed by Terraform with 7-day retention, a committed provider lock file, and Terraform 1.9 as the minimum version. `public_access_cidrs` no longer has a default that opens the endpoint to the internet.
- **Frontend**: Vite 8, `@vitejs/plugin-react` 6 and Tailwind CSS 4, each upgraded in its own commit.
- **Remediation** in Live Mode waits for the real rollout (updated replicas, no old pods left) and reports `APPLIED_NOT_READY` instead of claiming success.
- Dependabot: grouped minor and patch updates and at most three open pull requests per ecosystem.
- The demo numbers now match what a fresh two-node EKS cluster shows.

### Fixed

- Notifications that never disappeared (their timer was reset on every render).
- `setup.sh` failing at the tool check on some machines: a `head` in a pipeline received SIGPIPE under `set -o pipefail`. The same pattern with `grep -q` was fixed in three more places.
- A single-address allowlist locking users out when their internet connection leaves from more than one address.
- `destroy.sh` reporting a failure for a NAT gateway that was already deleted (the tag index lags behind reality).
- `kubectl version --short` (removed from kubectl) in the allowlist.
- Live telemetry for `broken_routing` looked for the wrong pod label; the Service's endpoints are now reported too.
- The `crashloop` scenario is documented as `CreateContainerConfigError`, which is what Kubernetes really reports for a missing Secret.
- The RCA engine no longer hides errors, and its timeout is configurable (`OLLAMA_TIMEOUT`).

### Compatibility

All existing API routes and response shapes are unchanged. `/api/metrics` is an addition; the dashboard simply hides the metrics panel if a backend does not provide it.
