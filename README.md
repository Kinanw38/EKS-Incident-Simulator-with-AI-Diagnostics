# EKS Incident Simulator with AI Diagnostics

![CI](https://github.com/Kinanw38/EKS-Incident-Simulator-with-AI-Diagnostics/actions/workflows/ci-cd.yml/badge.svg)
![AWS](https://img.shields.io/badge/AWS-232F3E?style=flat&logo=amazon-aws&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=flat&logo=kubernetes&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=flat&logo=terraform&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)

A cloud engineering and SRE platform that provisions an Amazon EKS cluster with Terraform, injects controlled failures into Kubernetes workloads, watches the cluster's metrics, collects telemetry, and produces a structured Root Cause Analysis with a one-click remediation.

It runs in two modes that share the same dashboard and API:

- **Demo Mode**: safe and free. Deterministic, clearly labelled simulated data. This is what the public demo uses.
- **Live AWS Mode**: a real EKS cluster with real nodes, pods, logs, events and metrics.

**[Open the public demo](https://eks-incident-simulator-ai-diagnosti.vercel.app/)**

<p align="center">
  <img src="assets/screenshots/dashboard-overview.png" alt="Dashboard overview in Live Mode" width="100%" />
</p>

---

## Highlights

- **Five incident scenarios** that you can see in the metrics: memory leak, CPU saturation, OOMKilled, missing Secret, and a Service selector mismatch. Each one has a faulty manifest, an RCA, and a corrected manifest to apply.
- **Cluster metrics dashboard**: node and pod health, restarts, capacity, and CPU/memory gauges. In Live Mode the usage numbers come from metrics-server; in Demo Mode they are simulated, follow the active incident, and are labelled `SIMULATED`.
- **AI diagnostics with a safe fallback**: a local Ollama model can write the analysis; if it is unavailable, a deterministic expert engine answers instead, so the workflow never breaks.
- **Zero-trust terminal**: only allow-listed, read-only `kubectl` commands are executed, and the allowlist is enforced on the server.
- **Safe infrastructure lifecycle**: `setup.sh` confirms the AWS account and cost before creating anything; `destroy.sh` deletes only what belongs to the simulator and then verifies that nothing is left behind.
- **Light and dark themes**, and a layout that works on phones.

---

## What's new in v2

| Area | Change |
| :--- | :--- |
| Dashboard | New metrics panel, light/dark theme, mobile layout with bottom navigation, notifications that always disappear |
| Incidents | Two new resource incidents (memory leak, CPU saturation), bounded by resource limits |
| Live mode | Real CPU/memory usage through metrics-server, "reserved" numbers as a fallback, readiness checks that wait for the real rollout |
| `setup.sh` | Account and cost confirmation, localhost-only services, automatic detection of the allowed IP range, clear errors that name the failing phase |
| `destroy.sh` | Explicit kubeconfig, label-scoped cleanup, load balancer handling, retries, and a PASS/FAIL verification of what is left in AWS |
| Terraform | Pinned Kubernetes version, Amazon Linux 2023 nodes, managed log group, validated inputs, no default that opens the API to the internet |
| Quality | Pytest suite, shell script tests and ShellCheck, CodeQL, Dependabot, non-root container with a health check |

The full list is in [CHANGELOG.md](CHANGELOG.md).

---

## Tech Stack

| Category | Technologies |
| :--- | :--- |
| Cloud | AWS, Amazon EKS |
| Infrastructure as Code | Terraform |
| Containers | Kubernetes, Docker |
| Backend and AI | Python, FastAPI, Ollama (optional) |
| Frontend | React, Vite, Tailwind CSS |
| Automation and CI | Bash, GitHub Actions, CodeQL, Dependabot |

---

## System Architecture

<p align="center">
  <img src="assets/architecture.svg" alt="EKS Incident Simulator system architecture" width="100%" />
</p>

A FastAPI control plane serves the React dashboard and talks to one of two runtimes:

- **Demo Mode** returns realistic deterministic responses.
- **Live Mode** talks to a real Kubernetes cluster on Amazon EKS and reads usage from metrics-server.

Both modes use the same workflow and API contract. Only the source of the Kubernetes data differs.

---

## Incident Scenarios

| Scenario | What goes wrong | What you see |
| :--- | :--- | :--- |
| **Memory leak** | A cache keeps allocating more than its limit allows | Cluster memory climbs, pods are OOMKilled and restart |
| **CPU saturation** | Workers spin at their CPU limit | Cluster CPU climbs, pods are throttled |
| **OOMKilled** | One container exceeds a small memory limit | Restarts and an unhealthy pod |
| **Missing Secret** (`crashloop`) | A Secret that the pod needs does not exist | The pod stays in `CreateContainerConfigError`; there are no logs, only events |
| **Service selector mismatch** (`broken_routing`) | The Service selector matches no pod | Pods are healthy but the Service has no endpoints |

The two resource incidents are bounded on purpose: at most two replicas, each with a memory limit (and a CPU limit for the CPU incident), so they cannot exhaust a small cluster.

The id `crashloop` is kept for API compatibility even though the pod state is `CreateContainerConfigError`.

---

## Diagnostic Workflow

1. **Select** a scenario in the Testing Lab.
2. **Trigger** it. Demo Mode simulates this; Live Mode applies the faulty manifest to the cluster.
3. **Observe** pod status, restarts, events, missing endpoints, and the cluster metrics.
4. **Investigate**: the backend collects logs, previous container logs, events, and service endpoints.
5. **Review the RCA**: root cause, impact, and the recommended fix. When Ollama is unavailable or returns an invalid answer, the deterministic engine provides the analysis.
6. **Remediate**: compare the faulty and the corrected manifest and apply the fix. In Live Mode the backend then waits for the real rollout to finish and reports `APPLIED_NOT_READY` instead of claiming success if the workload is not ready.

### Zero-trust terminal

The terminal accepts only allow-listed, read-only commands (`kubectl get pods`, `get services`, `get events`, `get deployments`, `get nodes`, `cluster-info`, and a few more). The server validates every command. The interface always shows the current environment: `LIVE`, `DEMO`, or `OFFLINE`; when offline it returns a clear connection error instead of fake output.

---

## Screenshots

### Incident Simulation Lab
<p align="center">
  <img src="assets/screenshots/incident-lab.png" alt="Incident Lab" width="100%" />
</p>

### AI Root Cause Analysis
<p align="center">
  <img src="assets/screenshots/ai-rca-result.png" alt="AI RCA Result" width="100%" />
</p>

### Zero-Trust Interactive Terminal
<p align="center">
  <img src="assets/screenshots/zero-trust-terminal.png" alt="Zero Trust Terminal" width="100%" />
</p>

---

## Quick Start

**Demo Mode (no AWS needed)**, in two terminals.

Backend:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
DEMO_MODE=true .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000`. Vite picks another port if 3000 is busy and prints the address.

**Live AWS Mode**:

```bash
./scripts/setup.sh
```

When you are done, always run:

```bash
./scripts/destroy.sh
```

---

## Public Demo

The hosted demo runs in Demo Mode: the frontend is on Vercel and the backend is on Render.

- It uses simulated Kubernetes data and needs no AWS credentials.
- It never creates AWS resources and never touches a real cluster.
- Render's free tier may need a few seconds to wake up after inactivity.

---

## Live AWS Mode in detail

### Requirements

- AWS CLI, authenticated (`aws sts get-caller-identity` must work)
- Terraform 1.9 or newer
- kubectl, Python 3.11 or newer, Node.js 20.19 or newer (or 22.12+), npm, curl
- Linux, macOS or WSL

### Cost

While the cluster runs, expect roughly **0.23 to 0.25 USD per hour (about 5 to 6 USD per day)**: the EKS control plane (about 0.10), the NAT gateway (about 0.045 plus data transfer), and two `t3.medium` nodes (about 0.08), plus small items. This is an estimate, not a bill. **Leaving the cluster running burns money fast.**

`setup.sh` shows your AWS account, the region, and this estimate, and asks for confirmation before it creates anything (`--yes` skips the question).

### What `setup.sh` does

1. Checks your tools (including the Terraform version).
2. Confirms the AWS account and cost.
3. Builds the infrastructure with Terraform (about 10 to 15 minutes). If a CloudWatch log group from an older run is still there, it is imported into Terraform instead of failing with "already exists".
4. Connects `kubectl` to the new cluster and waits until the API answers.
5. Waits for all nodes to be Ready.
6. Installs metrics-server (one small pod, no extra AWS cost) for real CPU and memory usage.
7. Prepares and starts the backend and the frontend, each in its own process group and **bound to `127.0.0.1` only** (the live backend has no authentication and can run kubectl against your cluster).

If something fails, the message names the phase and the command that failed. If it failed after Terraform started, it tells you to run `./scripts/destroy.sh`.

### Who may reach the Kubernetes API

The EKS API endpoint is public but restricted. `setup.sh` asks a few "what is my IP" services a couple of times each and allows the smallest range that contains every address it saw. This matters because many home and mobile connections leave the internet from more than one address, and a single address would lock you out of your own cluster.

| `EKS_ALLOWED_CIDR` | Meaning |
| :--- | :--- |
| not set | Detect automatically (a range no broader than `/16` is accepted) |
| `203.0.113.0/24` | Use exactly this range |
| `open` | `0.0.0.0/0`, reachable from anywhere. AWS credentials are still required, but this is not recommended |

```bash
EKS_ALLOWED_CIDR=203.0.113.0/24 ./scripts/setup.sh
```

After the cluster is created, `setup.sh` checks that `kubectl` can really reach the API. If it cannot, it says why and offers to widen the range to your `/16` network. Terraform itself has **no default** for `public_access_cidrs`, so a plain `terraform apply` can never open the endpoint by accident.

### What `destroy.sh` does

- Reads the cluster name and region from Terraform and builds its own temporary kubeconfig, so it never acts on whatever `kubectl` context happens to be active. If the cluster is unreachable, it skips the Kubernetes cleanup and touches nothing else.
- Stops the local frontend and backend (whole process groups) and checks that the ports are free.
- Deletes only the simulator's Kubernetes resources, selected by the label `app.kubernetes.io/part-of=incident-simulator`, plus any `LoadBalancer` Service, which owns an AWS load balancer that would block VPC deletion.
- Runs `terraform destroy` with up to three attempts, because VPC dependency errors are often temporary.
- **Verifies** the result and prints a PASS/FAIL list: no resources tagged `Project=AI-Incident-Simulator`, the EKS cluster is gone, NAT gateways are deleted, the Elastic IP is released, and the CloudWatch log group is gone. The tag index can lag behind reality, so it retries, ignores NAT gateways whose state is `deleted`, and prints the ARN of anything still listed.
- Removes this cluster's entries from `~/.kube/config`.

`./scripts/destroy.sh --yes` skips the confirmation question. The script never deletes `backend/.venv` or `frontend/node_modules`.

---

## Project structure

```text
backend/    FastAPI control plane, RCA engine, incident scenarios, tests
frontend/   React + Vite + Tailwind dashboard
k8s/        The same manifests as the scenarios (problem.yaml, fix.yaml), plus metrics-server
terraform/  VPC, EKS cluster, node group, log group
scripts/    setup.sh, destroy.sh, and their helpers and tests
assets/     Architecture diagram and screenshots
```

---

## Tests and CI

Backend tests run in Demo Mode, with no AWS account and no cluster:

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

Shell script helpers have their own tests, and ShellCheck runs on every script:

```bash
bash scripts/tests/cidr_test.sh
```

GitHub Actions runs on every push and pull request:

- Terraform `fmt` and `validate`.
- Python lint and the pytest suite.
- ShellCheck and the shell script tests.
- Frontend production build.
- Docker image build, and a check that the container does not run as root.
- CodeQL security analysis (Python and JavaScript), also weekly.
- Dependabot keeps pip, npm, Docker, Terraform and GitHub Actions dependencies up to date, with grouped minor updates and a limit of three open pull requests per ecosystem. Major upgrades arrive as separate pull requests so they can be reviewed and migrated deliberately.

---

## Design Decisions

- **Terraform state is local on purpose.** This is a single-user, short-lived simulator. A remote backend needs a bucket that exists before Terraform runs, an extra AWS resource that would outlive `terraform destroy`. Keep `terraform/terraform.tfstate` until the destroy finishes; deleting it orphans the AWS resources. For a team, [`terraform/backend.s3.example`](terraform/backend.s3.example) shows how to move to S3 with state locking.
- **The EKS API endpoint is public but restricted.** A private endpoint would need a VPN or a bastion host to run `kubectl` from a laptop. The restriction is detected and applied by `setup.sh`, and there is no open default in Terraform.
- **Nodes stay in private subnets behind a NAT gateway.** Removing the NAT gateway or moving nodes to public subnets would save money but expose the nodes, so the cost is accepted. Cost is documented above.
- **The Kubernetes version is pinned** (`kubernetes_version`, default 1.35) to a version in standard support. Versions in extended support cost 0.60 USD/h instead of 0.10 USD/h for the control plane. Check `aws eks describe-cluster-versions` when updating.
- **Worker nodes use Amazon Linux 2023** (`AL2023_x86_64_STANDARD`).
- **The CloudWatch log group is managed by Terraform** (7-day retention), so `terraform destroy` removes it.
- **metrics-server is vendored** in `k8s/metrics-server/` at a pinned version with one local change, a memory limit, so setup does not depend on a download from the internet.
- **Honest numbers.** Demo values are labelled as simulated. In Live Mode, if metrics-server has not reported yet, the dashboard shows what pods have reserved through their resource requests compared with the allocatable capacity of the nodes, instead of inventing usage.
- **Not included on purpose:** KMS envelope encryption for Kubernetes Secrets (it leaves a key pending deletion after destroy) and a remote Terraform backend. Both are standard in production and would be the next hardening steps.

---

## Security Notes

This project is intended for controlled testing and learning.

- Never commit AWS access keys or private credentials.
- Do not expose a live EKS-connected backend publicly without authentication. The scripts bind it to `127.0.0.1`.
- Use a dedicated AWS account or sandbox.
- Review remediation manifests before applying them.
- Keep the terminal allowlist restrictive.
- Do not run the simulator against production workloads.
- Destroy unused AWS infrastructure after testing.

The public hosted backend must stay in Demo Mode and must never receive credentials that can reach a real AWS account or cluster.

---

## License

MIT. See [LICENSE](LICENSE).
