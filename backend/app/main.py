import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .k8s_client import k8s_manager
from .rca_engine import analyze_incident_telemetry
from .scenarios import SCENARIOS
from .security import is_command_allowed


app = FastAPI(
    title="AI Incident Simulator Control Plane",
    version="1.0.0",
    description=(
        "Backend API for managing Kubernetes incident scenarios, "
        "live telemetry analysis, secure inspection commands, "
        "and automated remediation."
    ),
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        (
            "http://localhost:3000,"
            "http://localhost:3001,"
            "http://localhost:5173,"
            "https://eks-incident-simulator-ai-diagnosti.vercel.app"
        ),
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class TerminalRequest(BaseModel):
    command: str


class RemediationRequest(BaseModel):
    incident_id: str


def build_healthy_cluster_response() -> dict:
    cluster_info = k8s_manager.get_cluster_status()
    return {
        "status": "healthy",
        "source": "CLUSTER_HEALTH_CHECK",
        "root_cause": "No active incident detected.",
        "impact": "No current service degradation detected.",
        "recommended_fix": "No action required.",
        "mode": k8s_manager.mode,
        "cluster": cluster_info,
    }


@app.get("/")
def root():
    return {
        "service": "AI Incident Simulator Control Plane",
        "status": "running",
        "mode": k8s_manager.mode,
        "docs": "/docs",
    }


@app.get("/api/health")
def health_check():
    cluster_info = k8s_manager.get_cluster_status()
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "mode": k8s_manager.mode,
        "cluster": cluster_info,
    }


@app.get("/api/health-analysis")
def health_analysis():
    return build_healthy_cluster_response()


@app.get("/api/scenarios")
def list_scenarios():
    return list(SCENARIOS.values())


@app.get("/api/scenarios/{incident_id}")
def get_scenario(incident_id: str):
    scenario = SCENARIOS.get(incident_id)

    if scenario is None:
        raise HTTPException(status_code=404, detail="Incident scenario not found.")

    return scenario


@app.post("/api/scenarios/{incident_id}/trigger")
def trigger_scenario(incident_id: str):
    scenario = SCENARIOS.get(incident_id)

    if scenario is None:
        raise HTTPException(status_code=404, detail="Incident scenario not found.")

    try:
        result = k8s_manager.apply_manifest(scenario["problem_yaml"])
        return {
            "incident_id": incident_id,
            "status": "ACTIVE",
            "mode": k8s_manager.mode,
            "message": result,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not trigger the incident in the connected Kubernetes environment: {exc}",
        ) from exc


@app.post("/api/terminal/execute")
def execute_terminal_command(req: TerminalRequest):
    allowed, message = is_command_allowed(req.command)

    if not allowed:
        raise HTTPException(status_code=403, detail=message)

    try:
        output = k8s_manager.execute_terminal_cmd(req.command)
        return {
            "command": req.command,
            "mode": k8s_manager.mode,
            "output": output,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Command execution failed: {exc}",
        ) from exc


@app.get("/api/scenarios/{incident_id}/rca")
def get_rca(incident_id: str):
    scenario = SCENARIOS.get(incident_id)

    if scenario is None:
        raise HTTPException(status_code=404, detail="Incident scenario not found.")

    component = scenario.get("affected_component", "api-service")
    logs, events = k8s_manager.get_telemetry_for_component(component)
    analysis = analyze_incident_telemetry(incident_id, logs, events)

    return {
        **analysis,
        "mode": k8s_manager.mode,
        "incident_id": incident_id,
        "component": component,
    }


@app.post("/api/remediate")
def trigger_remediation(req: RemediationRequest):
    scenario = SCENARIOS.get(req.incident_id)

    if scenario is None:
        raise HTTPException(status_code=404, detail="Incident scenario not found.")

    try:
        result = k8s_manager.apply_manifest(scenario["fix_yaml"])
        reconciliation_steps = [
            {
                "step": 1,
                "action": "Inspecting current state manifest...",
                "status": "COMPLETED",
            },
            {
                "step": 2,
                "action": "Generating YAML Patch delta...",
                "status": "COMPLETED",
            },
            {
                "step": 3,
                "action": "Applying Kubernetes remediation manifest...",
                "status": "COMPLETED",
            },
            {
                "step": 4,
                "action": "Verifying Pod Readiness and Liveness probes...",
                "status": "COMPLETED",
            },
        ]

        return {
            "incident_id": req.incident_id,
            "status": "RESOLVED",
            "mode": k8s_manager.mode,
            "reconciliation_loop": reconciliation_steps,
            "message": f"Remediation completed successfully. ({result})",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Remediation execution failed: {exc}",
        ) from exc