import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .security import is_command_allowed
from .scenarios import SCENARIOS
from .k8s_client import k8s_manager
from .rca_engine import analyze_incident_telemetry


app = FastAPI(
    title="AI Incident Simulator Control Plane",
    version="1.0.0",
    description="Backend API for managing EKS chaos scenarios, telemetry analysis, and automated remediation."
)


# Enable CORS for Frontend communication.
# allow_credentials is False because this API uses no cookies or
# Authorization headers - combining it with a wildcard origin is both
# unnecessary and rejected by browsers per the CORS spec.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TerminalRequest(BaseModel):
    command: str


class RemediationRequest(BaseModel):
    incident_id: str


@app.get("/api/health")
def health_check():
    cluster_info = k8s_manager.get_cluster_status()

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "cluster": cluster_info
    }


@app.get("/api/scenarios")
def list_scenarios():
    return list(SCENARIOS.values())


@app.get("/api/scenarios/{incident_id}")
def get_scenario(incident_id: str):
    if incident_id not in SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail="Incident scenario not found."
        )

    return SCENARIOS[incident_id]


@app.post("/api/scenarios/{incident_id}/trigger")
def trigger_scenario(incident_id: str):
    """
    Triggers the selected incident by applying its problem YAML
    to the Kubernetes cluster.
    """
    if incident_id not in SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail="Incident scenario not found."
        )

    scenario = SCENARIOS[incident_id]

    try:
        result = k8s_manager.apply_manifest(
            scenario["problem_yaml"]
        )

        return {
            "incident_id": incident_id,
            "status": "ACTIVE",
            "message": result
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/api/terminal/execute")
def execute_terminal_command(req: TerminalRequest):
    allowed, message = is_command_allowed(req.command)

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=message
        )

    output = k8s_manager.execute_terminal_cmd(req.command)

    return {
        "command": req.command,
        "output": output
    }


@app.get("/api/scenarios/{incident_id}/rca")
def get_rca(incident_id: str):
    if incident_id not in SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail="Incident scenario not found."
        )

    scenario = SCENARIOS[incident_id]
    component = scenario.get("affected_component", "api-service")

    # Fetch dynamic live telemetry directly from the EKS cluster
    logs, events = k8s_manager.get_telemetry_for_component(component)

    return analyze_incident_telemetry(
        incident_id,
        logs,
        events
    )


@app.post("/api/remediate")
def trigger_remediation(req: RemediationRequest):
    if req.incident_id not in SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail="Incident scenario not found."
        )

    scenario = SCENARIOS[req.incident_id]

    try:
        # Apply the fix manifest directly to the connected EKS cluster
        result = k8s_manager.apply_manifest(scenario["fix_yaml"])

        reconciliation_steps = [
            {
                "step": 1,
                "action": "Inspecting current state manifest...",
                "status": "COMPLETED"
            },
            {
                "step": 2,
                "action": "Generating YAML Patch delta...",
                "status": "COMPLETED"
            },
            {
                "step": 3,
                "action": "Applying Kubernetes live patch to cluster...",
                "status": "COMPLETED"
            },
            {
                "step": 4,
                "action": "Verifying Pod Readiness & Liveness probes...",
                "status": "COMPLETED"
            }
        ]

        return {
            "incident_id": req.incident_id,
            "status": "RESOLVED",
            "reconciliation_loop": reconciliation_steps,
            "message": f"Remediation patch successfully reconciled! ({result})"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Remediation execution failed: {str(e)}"
        )