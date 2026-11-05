import json
import logging
import os

import requests

logger = logging.getLogger(__name__)


def analyze_incident_telemetry(incident_id: str, logs: str, events: str) -> dict:
    """
    Queries local or remote LLM (Ollama) to perform Root Cause Analysis.
    Falls back to deterministic expert analysis if the LLM is unreachable
    OR if it responds but doesn't return the structured fields we need.
    """
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    # (connect timeout, read timeout) in seconds. A local LLM can take a while
    # to answer, but an unreachable Ollama should fail fast.
    ollama_timeout = (2, float(os.getenv("OLLAMA_TIMEOUT", "30")))

    prompt = f"""
    You are an expert Kubernetes Reliability Engineer (SRE).
    Analyze the following incident telemetry:

    Incident ID: {incident_id}
    Cluster Logs: {logs}
    Cluster Events: {events}

    Respond with ONLY a JSON object with strictly these keys, no extra text:
    1. "root_cause": Clear explanation of what went wrong.
    2. "impact": Business / infrastructure operational impact.
    3. "recommended_fix": Exact technical steps or YAML changes required.
    """

    try:
        response = requests.post(
            ollama_url,
            json={"model": "llama3", "prompt": prompt, "stream": False, "format": "json"},
            timeout=ollama_timeout
        )
        if response.status_code == 200:
            raw_text = response.json().get("response", "")
            # The model is asked for JSON, but LLM output is never fully
            # guaranteed - so we validate the shape before trusting it,
            # rather than returning a payload the frontend can't render.
            parsed = json.loads(raw_text)

            if all(key in parsed for key in ("root_cause", "impact", "recommended_fix")):
                return {
                    "source": "AI_LLM_MODEL",
                    "root_cause": parsed["root_cause"],
                    "impact": parsed["impact"],
                    "recommended_fix": parsed["recommended_fix"]
                }
            logger.warning(
                "Ollama response is missing required keys; using the fallback."
            )
        else:
            logger.warning(
                "Ollama returned HTTP %s; using the fallback.",
                response.status_code,
            )
    except Exception as exc:
        logger.info("Ollama is not usable (%s); using the fallback.", exc)

    # Deterministic Expert Fallback (Guarantees 100% Reliability)
    fallback_database = {
        "oomkilled": {
            "root_cause": "Memory boundary violation (Exit Code 137). The application process requested ~150Mi memory while Cgroup limit was hard set to 64Mi.",
            "impact": "Pod enters crash loop state; API requests fail with 502/504 Gateway Timeouts.",
            "recommended_fix": "Increase Deployment container memory limit to 256Mi and requests to 128Mi."
        },
        "crashloop": {
            "root_cause": "Failed environment variable population due to missing Kubernetes Secret 'missing-db-secret'.",
            "impact": "The pod stays in CreateContainerConfigError: the container is never created, so the auth service never starts.",
            "recommended_fix": "Create Opaque Secret 'missing-db-secret' containing key 'password'."
        },
        "broken_routing": {
            "root_cause": "Service label selector mismatch ('app: wrong-label-selector' vs Pod label 'app: payment-processor').",
            "impact": "ClusterIP Service has 0 active endpoints; incoming traffic is dropped.",
            "recommended_fix": "Update Service spec.selector.app to match Deployment pod template label 'payment-processor'."
        },
        "memory_leak": {
            "root_cause": "The cache-service container keeps allocating memory (~700Mi) while its limit is 512Mi, so the kernel OOM killer terminates it each time it reaches the limit (exit code 137).",
            "impact": "Both replicas restart in a loop, cluster memory usage climbs and drops, and cache requests fail while the pods restart.",
            "recommended_fix": "Fix the leak so the working set stays well below the limit (here: ~200Mi), and keep a memory limit as a safety net."
        },
        "cpu_saturation": {
            "root_cause": "The report-worker pods run a CPU busy loop (no useful work), so each replica consumes its entire CPU limit (800m).",
            "impact": "Cluster CPU usage climbs, the pods are CPU-throttled, and other workloads on the same nodes compete for CPU.",
            "recommended_fix": "Right-size the workload: reduce replicas to 1 and lower the CPU limit to 200m (requests stay at 100m)."
        }
    }

    expert_data = fallback_database.get(incident_id, {
        "root_cause": "Unidentified telemetry pattern in active workload.",
        "impact": "Service degradation or partial availability loss.",
        "recommended_fix": "Review deployment specifications and active pod logs."
    })

    return {
        "source": "DETERMINISTIC_EXPERT_ENGINE",
        "root_cause": expert_data["root_cause"],
        "impact": expert_data["impact"],
        "recommended_fix": expert_data["recommended_fix"]
    }