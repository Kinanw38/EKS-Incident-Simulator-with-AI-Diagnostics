# EKS Incident Simulator with AI Diagnostics
 
![AWS](https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)

A cloud engineering and SRE platform that provisions an Amazon EKS cluster with Terraform, injects controlled failure scenarios into Kubernetes workloads, collects cluster telemetry, and generates structured Root Cause Analysis with recommended remediation.

The project supports two environments:

- **Demo Mode** — a public, safe experience using deterministic mock data.
- **Live AWS Mode** — a real EKS integration using live Kubernetes nodes, pods, logs, and events.

[Open the Public Demo](https://eks-incident-simulator-ai-diagnosti.vercel.app/)

---

## 🛠 Tech Stack
 
| Category | Technologies |
| :--- | :--- |
| **Cloud Infrastructure** | ![AWS](https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white) ![EKS](https://img.shields.io/badge/AWS_EKS-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white) |
| **Infrastructure as Code** | ![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white) |
| **Container Orchestration** | ![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white) |
| **Backend & AI Engine** | ![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white) ![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white) |
| **Frontend Management UI** | ![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB) ![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white) ![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white) |
| **Automation** | ![Bash](https://img.shields.io/badge/GNU_Bash-4EAA25?style=for-the-badge&logo=gnu-bash&logoColor=white) |
 
---

## 🏗 System Architecture

<p align="center">
  <img
    src="assets/architecture.svg"
    alt="EKS Incident Simulator system architecture"
    width="100%"
  />
</p>

The platform is built around a FastAPI control plane that communicates with the React dashboard and connects to one of two runtime environments:

- In **Demo Mode**, it returns realistic deterministic mock responses.
- In **Live Mode**, it connects to a real Kubernetes cluster backed by Amazon EKS.

Both environments use the same frontend workflow and API contract. The difference is the source of the Kubernetes data.

---

## 🎯 What the Platform Does

The application demonstrates an end-to-end Kubernetes incident-response workflow:

1. Select a controlled failure scenario.
2. Inject the faulty workload configuration.
3. Observe the resulting Kubernetes symptoms.
4. Collect logs and Kubernetes events.
5. Generate a structured Root Cause Analysis.
6. Review the recommended remediation.
7. Apply the corrected manifest.
8. Inspect the cluster through a restricted terminal.

This makes the project useful as both an interactive cloud engineering demo and a practical SRE incident simulation tool.

---

## 🚨 Incident Scenarios

### OOMKilled

A workload exceeds its configured memory limit.

The simulator demonstrates how Kubernetes terminates the container when the process exceeds its cgroup memory boundary.

### CrashLoopBackOff

A workload depends on a Kubernetes Secret that does not exist.

The container fails during startup and repeatedly restarts until the missing configuration is restored.

### Broken Service Routing

A Service selector does not match the labels of the target workload.

The pods may be running, but the Service has no valid endpoints and traffic cannot reach the application.

---

## 🧠 Simulation and Diagnostic Workflow

### 1. Select a Scenario

Choose one of the available Kubernetes failure scenarios from the Testing Lab.

### 2. Trigger the Incident

The backend receives the selected scenario and applies its faulty manifest.

- In **Demo Mode**, the action is simulated.
- In **Live Mode**, the manifest is applied to the connected EKS cluster.

### 3. Observe the Failure

The dashboard presents the resulting workload state, including:

- Pod status.
- Restart counts.
- Kubernetes events.
- Missing service endpoints.
- Node health.
- Workload availability.

### 4. Run the Investigation

The backend collects telemetry from the affected component:

- Recent pod logs.
- Previous container logs when available.
- Kubernetes events.
- Live cluster information.

### 5. Review the RCA

The RCA engine returns:

- Root cause.
- Operational impact.
- Recommended technical fix.
- Analysis source.

When Ollama is available, it can generate the analysis. If Ollama is unavailable or returns an invalid response, the deterministic expert engine provides a reliable fallback.

### 6. Apply the Remediation

The interface displays the faulty manifest next to the recommended fix.

- In **Demo Mode**, remediation is simulated.
- In **Live Mode**, the corrected manifest is applied to Kubernetes.

---

## 🖥 Zero-Trust Interactive Terminal

The dashboard includes a restricted terminal for safe Kubernetes inspection.

The interface provides ready-to-use commands such as:

```text
kubectl get pods
kubectl get services
kubectl get events
kubectl get deployments
kubectl get nodes
kubectl cluster-info
```

Commands are validated on the backend through a strict allowlist. Only approved read-only inspection commands can be executed.

The terminal behaves differently according to the environment:

- **Demo Mode** returns deterministic simulated output.
- **Live Mode** executes approved commands against the connected Kubernetes cluster.
- **Offline** returns a clear connection error instead of pretending to provide live data.

The interface clearly reports the current environment as:

```text
LIVE
DEMO
OFFLINE
```

---

## 📸 Screenshots

<p align="center">
  <img
    src="assets/screenshots/dashboard-overview.png"
    alt="EKS Incident Simulator dashboard overview"
    width="49%"
  />
  <img
    src="assets/screenshots/incident-lab.png"
    alt="Kubernetes incident simulation lab"
    width="49%"
  />
</p>

<p align="center">
  <img
    src="assets/screenshots/ai-rca-result.png"
    alt="AI root cause analysis result"
    width="49%"
  />
  <img
    src="assets/screenshots/zero-trust-terminal.png"
    alt="Zero-Trust interactive terminal"
    width="49%"
  />
</p>

---

## Public Demo Mode

The public demo is available through the hosted frontend:

[Open the EKS Incident Simulator Demo](https://eks-incident-simulator-ai-diagnosti.vercel.app/)

The frontend communicates with the hosted backend API:

[Open the Demo Backend](https://eks-incident-simulator-with-ai.onrender.com/)

The hosted version runs in Demo Mode:

- It uses deterministic mock Kubernetes data.
- It does not require AWS credentials.
- It does not create AWS resources.
- It does not modify a real EKS cluster.
- It uses the same interface as the Live AWS deployment.

Because the backend uses Render's free hosting tier, it may take a few seconds to wake up after inactivity. The frontend communicates with the backend when it loads, so the first request may take longer than usual.

---

## Option A: Local Demo Mode

To run the mock version locally without AWS, start the backend with `DEMO_MODE=true`:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DEMO_MODE=true uvicorn app.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend usually opens at:

```text
http://localhost:3000
```

If port `3000` is already in use, Vite automatically selects another available port and prints the exact URL in the terminal.

Local Demo Mode does not require AWS credentials or a Kubernetes cluster.

---

## Option B: Full AWS / EKS Deployment

Live Mode connects the backend to a real Kubernetes cluster.

### Requirements

- AWS CLI.
- Terraform 1.5 or newer.
- kubectl.
- Python 3.11 or newer.
- Node.js 18 or newer.
- npm.
- curl.
- Linux, macOS, WSL, or another Bash-compatible environment.
- AWS credentials with permission to create the required infrastructure.

Before starting, verify that the AWS CLI is authenticated:

```bash
aws sts get-caller-identity
```

Review the Terraform configuration under:

```text
terraform/
```

Then run the setup script from the repository root:

```bash
chmod +x scripts/setup.sh scripts/destroy.sh
./scripts/setup.sh
```

The setup script automatically:

- Checks the required tools.
- Runs Terraform.
- Creates or updates the EKS infrastructure.
- Updates the local kubeconfig.
- Waits for Kubernetes to become available.
- Creates `backend/.venv` if it does not exist.
- Installs backend dependencies when needed.
- Installs frontend dependencies when needed.
- Starts the FastAPI backend.
- Starts the Vite frontend.
- Prints the actual localhost URLs.

Typical output:

```text
Frontend: http://localhost:3000
Backend:  http://localhost:8000
API docs: http://localhost:8000/docs
```

If port `3000` is already in use, the script displays the alternative URL selected by Vite.

---

## Dependency Installation

The setup script avoids unnecessary installations.

For the backend:

- `backend/.venv` is created only if it does not already exist.
- Python dependencies are installed only when `requirements.txt` has changed.

For the frontend:

- `npm ci` runs only when `frontend/node_modules` is missing.
- Existing frontend dependencies are reused on later runs.

The normal workflow is simply:

```bash
./scripts/setup.sh
```

---

## Stop and Destroy

When the AWS environment is no longer needed, run:

```bash
./scripts/destroy.sh
```

The destroy script automatically:

- Stops the Vite frontend.
- Stops the Uvicorn backend.
- Removes Kubernetes workloads where possible.
- Waits for related AWS resources to detach.
- Runs `terraform destroy`.

The script does not delete:

```text
backend/.venv
frontend/node_modules
```

Those are local development dependencies and are preserved for the next setup.

Always destroy unused AWS infrastructure to avoid unnecessary cloud charges.

---

## Security Notes

This project is intended for controlled testing and educational use.

- Never commit AWS access keys or private credentials.
- Do not expose a live EKS-connected backend publicly without authentication.
- Use a dedicated AWS account or sandbox environment.
- Review remediation manifests before applying them.
- Keep the terminal allowlist restrictive.
- Do not run the simulator against production workloads.
- Destroy unused AWS infrastructure after testing.

The public hosted backend should remain in Demo Mode and should not receive credentials that can access a real AWS account or production Kubernetes cluster.

---

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.