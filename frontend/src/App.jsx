import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertOctagon,
  ArrowRight,
  BrainCircuit,
  Check,
  FlaskConical,
  LayoutDashboard,
  RefreshCw,
  ShieldCheck,
  Terminal as TerminalIcon,
  Zap
} from "lucide-react";
import ToastContainer from "./components/Notifications";

const API_BASE =
  import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const HEALTH_REFRESH_INTERVAL = 10000;

const TERMINAL_PRESETS = [
  {
    label: "Get Pods",
    command: "kubectl get pods"
  },
  {
    label: "Get Services",
    command: "kubectl get services"
  },
  {
    label: "Get Events",
    command: "kubectl get events"
  },
  {
    label: "Get Deployments",
    command: "kubectl get deployments"
  },
  {
    label: "Get Nodes",
    command: "kubectl get nodes"
  },
  {
    label: "Cluster Info",
    command: "kubectl cluster-info"
  }
];

function getModeLabel(clusterHealth) {
  if (
    clusterHealth?.mode === "live" &&
    clusterHealth?.connected
  ) {
    return "LIVE";
  }

  if (clusterHealth?.mode === "demo") {
    return "DEMO";
  }

  return "OFFLINE";
}

function getModeClasses(clusterHealth) {
  const mode = getModeLabel(clusterHealth);

  if (mode === "LIVE") {
    return {
      badge:
        "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
      dot: "bg-emerald-400",
      border: "border-emerald-500/30",
      background: "bg-emerald-500/[0.04]",
      title: "text-emerald-300"
    };
  }

  if (mode === "DEMO") {
    return {
      badge:
        "bg-blue-500/10 text-blue-400 border-blue-500/20",
      dot: "bg-blue-400",
      border: "border-blue-500/30",
      background: "bg-blue-500/[0.04]",
      title: "text-blue-300"
    };
  }

  return {
    badge:
      "bg-rose-500/10 text-rose-400 border-rose-500/20",
    dot: "bg-rose-400",
    border: "border-rose-500/30",
    background: "bg-rose-500/[0.04]",
    title: "text-rose-300"
  };
}

function getEnvironmentCopy(modeLabel) {
  if (modeLabel === "LIVE") {
    return {
      title: "Live AWS / EKS Environment",
      description:
        "Connected to a real Kubernetes cluster with live node and workload telemetry.",
      detail: "Real Kubernetes data enabled"
    };
  }

  if (modeLabel === "DEMO") {
    return {
      title: "Public Demo Environment",
      description:
        "Using deterministic simulated Kubernetes responses. No AWS resources are connected.",
      detail: "Mock telemetry enabled"
    };
  }

  return {
    title: "Environment Unavailable",
    description:
      "The application could not reach the backend or the live Kubernetes cluster.",
    detail: "Waiting for a connection"
  };
}

export default function App() {
  const [activeTab, setActiveTab] = useState("overview");
  const [scenarios, setScenarios] = useState([]);
  const [selectedScenario, setSelectedScenario] = useState(null);
  const [clusterHealth, setClusterHealth] = useState(null);
  const [lastHealthUpdate, setLastHealthUpdate] = useState(null);
  const [rcaResult, setRcaResult] = useState(null);
  const [rcaLoading, setRcaLoading] = useState(false);
  const [remediating, setRemediating] = useState(false);
  const [remediationSuccess, setRemediationSuccess] =
    useState(false);
  const [terminalCmd, setTerminalCmd] =
    useState("kubectl get pods");
  const [terminalOutput, setTerminalOutput] = useState("");
  const [terminalLoading, setTerminalLoading] =
    useState(false);
  const [toasts, setToasts] = useState([]);
  const [initialLoading, setInitialLoading] =
    useState(true);
  const [scenariosError, setScenariosError] =
    useState(false);

  const healthRequestInFlight = useRef(false);

  const addToast = (type, title, message) => {
    const id = Date.now() + Math.random();

    setToasts((previous) => [
      ...previous,
      {
        id,
        type,
        title,
        message
      }
    ]);

    window.setTimeout(() => {
      setToasts((previous) =>
        previous.filter((toast) => toast.id !== id)
      );
    }, 4500);
  };

  const removeToast = (id) => {
    setToasts((previous) =>
      previous.filter((toast) => toast.id !== id)
    );
  };

  const fetchClusterHealth = async ({ silent = false } = {}) => {
    if (healthRequestInFlight.current) {
      return;
    }

    healthRequestInFlight.current = true;

    try {
      const response = await fetch(`${API_BASE}/health`);

      if (!response.ok) {
        throw new Error(
          `Health request failed with status ${response.status}`
        );
      }

      const data = await response.json();

      setClusterHealth(data.cluster);
      setLastHealthUpdate(new Date());
    } catch (error) {
      setClusterHealth({
        status: "UNAVAILABLE",
        mode: "unavailable",
        connected: false,
        node_count: 0,
        healthy_nodes: 0,
        message:
          "Backend or Kubernetes connection is unavailable."
      });

      if (!silent) {
        addToast(
          "error",
          "Backend Unavailable",
          error.message ||
            "Could not read backend health."
        );
      }
    } finally {
      healthRequestInFlight.current = false;
    }
  };

  const fetchScenarios = async () => {
    try {
      const response = await fetch(`${API_BASE}/scenarios`);

      if (!response.ok) {
        throw new Error(
          `Scenario request failed with status ${response.status}`
        );
      }

      const data = await response.json();

      setScenarios(data);
      setScenariosError(false);

      // Intentionally do not select the first scenario.
      // The dashboard should start with no active incident.
    } catch (error) {
      setScenariosError(true);

      addToast(
        "error",
        "API Connection Failed",
        error.message ||
          "Could not load incident scenarios."
      );
    }
  };

  useEffect(() => {
    Promise.all([
      fetchClusterHealth(),
      fetchScenarios()
    ]).finally(() => {
      setInitialLoading(false);
    });
  }, []);

  useEffect(() => {
    const healthInterval = window.setInterval(() => {
      fetchClusterHealth({ silent: true });
    }, HEALTH_REFRESH_INTERVAL);

    return () => {
      window.clearInterval(healthInterval);
    };
  }, []);

  const handleRunScenario = async (scenario) => {
    setSelectedScenario(scenario);
    setRcaResult(null);
    setRemediationSuccess(false);

    try {
      const response = await fetch(
        `${API_BASE}/scenarios/${scenario.id}/trigger`,
        {
          method: "POST"
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to trigger incident."
        );
      }

      addToast(
        "warning",
        "Incident Triggered",
        `${scenario.title} is active in ${
          data.mode || "the selected environment"
        }.`
      );

      await fetchClusterHealth();
    } catch (error) {
      addToast(
        "error",
        "Incident Trigger Failed",
        error.message ||
          "Could not trigger the incident."
      );
    }
  };

  const clearSelectedIncident = () => {
    setSelectedScenario(null);
    setRcaResult(null);
    setRemediationSuccess(false);
  };

  const fetchAiRca = async () => {
    if (!selectedScenario) {
      return;
    }

    setRcaLoading(true);

    try {
      const response = await fetch(
        `${API_BASE}/scenarios/${selectedScenario.id}/rca`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to analyze telemetry."
        );
      }

      setRcaResult(data);

      addToast(
        "info",
        "Analysis Complete",
        `RCA generated via ${
          data.source || "the diagnostic engine"
        }.`
      );
    } catch (error) {
      addToast(
        "error",
        "RCA Failed",
        error.message ||
          "Unable to analyze telemetry."
      );
    } finally {
      setRcaLoading(false);
    }
  };

  const triggerRemediation = async () => {
    if (!selectedScenario) {
      return;
    }

    setRemediating(true);

    try {
      const response = await fetch(`${API_BASE}/remediate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          incident_id: selectedScenario.id
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Could not apply remediation."
        );
      }

      setRemediationSuccess(true);

      addToast(
        "success",
        "Remediation Successful",
        data.message ||
          "The remediation completed successfully."
      );

      await fetchClusterHealth();
    } catch (error) {
      addToast(
        "error",
        "Remediation Failed",
        error.message ||
          "Could not apply remediation."
      );
    } finally {
      setRemediating(false);
    }
  };

  const executeTerminal = async (
    event = null,
    commandOverride = null
  ) => {
    if (event) {
      event.preventDefault();
    }

    const command = commandOverride || terminalCmd;

    setTerminalCmd(command);
    setTerminalLoading(true);

    try {
      const response = await fetch(
        `${API_BASE}/terminal/execute`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            command
          })
        }
      );

      const data = await response.json();

      if (!response.ok) {
        const detail =
          data.detail || "Command was rejected.";

        setTerminalOutput(
          `[COMMAND ERROR]\n${detail}`
        );

        addToast(
          "error",
          "Command Failed",
          detail
        );

        return;
      }

      setTerminalOutput(
        `[${String(
          data.mode || "unknown"
        ).toUpperCase()} OUTPUT]\n${data.output}`
      );
    } catch (error) {
      setTerminalOutput(
        "[CONNECTION ERROR]\nCould not connect to the terminal API."
      );

      addToast(
        "error",
        "Terminal Unavailable",
        error.message ||
          "Could not connect to backend."
      );
    } finally {
      setTerminalLoading(false);
    }
  };

  const modeLabel = getModeLabel(clusterHealth);
  const modeClasses = getModeClasses(clusterHealth);
  const environmentCopy = getEnvironmentCopy(modeLabel);

  const lastUpdatedLabel = lastHealthUpdate
    ? lastHealthUpdate.toLocaleTimeString()
    : "Waiting for first check";

  const navigationItems = [
    {
      id: "overview",
      label: "System Overview",
      icon: LayoutDashboard
    },
    {
      id: "lab",
      label: "K8s Testing Lab",
      icon: FlaskConical
    },
    {
      id: "ai",
      label: "AI RCA & Patching",
      icon: BrainCircuit
    },
    {
      id: "terminal",
      label: "Zero-Trust Terminal",
      icon: TerminalIcon
    }
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 font-sans text-zinc-100">
      <ToastContainer
        toasts={toasts}
        removeToast={removeToast}
      />

      <aside className="flex w-64 shrink-0 flex-col justify-between border-r border-zinc-800/80 bg-zinc-950">
        <div>
          <div className="flex items-center gap-3 border-b border-zinc-800/80 p-5">
            <div className="shrink-0 rounded-lg border border-blue-500/20 bg-blue-600/10 p-2 text-blue-400">
              <BrainCircuit className="h-5 w-5" />
            </div>

            <div className="min-w-0">
              <h1 className="truncate text-sm font-bold tracking-wide">
                EKS RCA Engine
              </h1>

              <p className="font-mono text-[10px] text-zinc-500">
                v1.0.0 • AI-SRE Control
              </p>
            </div>
          </div>

          <nav className="space-y-1 p-3">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              const active = activeTab === item.id;

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  className={`flex w-full items-center gap-3 rounded-md px-3.5 py-2.5 text-left text-xs font-medium transition ${
                    active
                      ? "border border-zinc-700/50 bg-zinc-800/60 text-zinc-100"
                      : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                  }`}
                >
                  <Icon
                    className={`h-4 w-4 shrink-0 ${
                      active
                        ? "text-blue-400"
                        : "text-zinc-500"
                    }`}
                  />

                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        <div className="border-t border-zinc-800/80 bg-zinc-900/30 p-4">
          <div className="flex items-center justify-between text-xs">
            <span className="text-zinc-400">
              Environment
            </span>

            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[11px] ${modeClasses.badge}`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${modeClasses.dot}`}
              />

              {modeLabel}
            </span>
          </div>

          <p className="mt-2 text-[10px] leading-relaxed text-zinc-600">
            {modeLabel === "LIVE"
              ? "Connected to a live Kubernetes cluster."
              : modeLabel === "DEMO"
                ? "Using deterministic simulated data."
                : "Live cluster is not reachable."}
          </p>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto bg-zinc-950">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-zinc-800/80 bg-zinc-950/90 px-6 backdrop-blur">
          <div className="flex min-w-0 items-center gap-2 font-mono text-xs text-zinc-500">
            <span>cluster</span>
            <span>/</span>

            <span className="truncate text-zinc-200">
              {selectedScenario?.affected_component ||
                "no-active-incident"}
            </span>
          </div>

          <button
            type="button"
            onClick={() => fetchClusterHealth()}
            className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-400 transition hover:border-zinc-700 hover:bg-zinc-800 hover:text-zinc-200"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh State
          </button>
        </header>

        <div className="mx-auto w-full max-w-6xl space-y-8 p-6 md:p-10">
          {activeTab === "overview" && (
            <section className="space-y-6">
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-lg font-bold tracking-tight">
                    System Infrastructure Overview
                  </h2>

                  <span
                    className={`rounded-full border px-2.5 py-1 font-mono text-[10px] ${modeClasses.badge}`}
                  >
                    {modeLabel} ENVIRONMENT
                  </span>
                </div>

                <p className="mt-1 text-xs text-zinc-400">
                  Monitor cluster connectivity, incident scenarios,
                  and diagnostic capabilities from one control plane.
                </p>
              </div>

              <div
                className={`rounded-xl border p-5 ${modeClasses.border} ${modeClasses.background}`}
              >
                <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                  <div className="flex items-start gap-4">
                    <div
                      className={`mt-1 h-3 w-3 shrink-0 rounded-full ${modeClasses.dot} ${
                        modeLabel === "LIVE"
                          ? "shadow-[0_0_12px_rgba(52,211,153,0.8)]"
                          : ""
                      }`}
                    />

                    <div>
                      <div className="flex flex-wrap items-center gap-3">
                        <h3
                          className={`text-sm font-bold ${modeClasses.title}`}
                        >
                          {environmentCopy.title}
                        </h3>

                        <span className="rounded border border-zinc-700/70 bg-zinc-950/40 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
                          {environmentCopy.detail}
                        </span>
                      </div>

                      <p className="mt-2 max-w-2xl text-xs leading-relaxed text-zinc-300">
                        {environmentCopy.description}
                      </p>
                    </div>
                  </div>

                  <div className="shrink-0 text-left sm:text-right">
                    <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                      Last health check
                    </p>

                    <p className="mt-1 font-mono text-xs text-zinc-300">
                      {lastUpdatedLabel}
                    </p>

                    <p className="mt-1 text-[10px] text-zinc-500">
                      Automatic refresh every 10 seconds
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <StatCard
                  title="Kubernetes Nodes"
                  value={
                    initialLoading
                      ? "..."
                      : clusterHealth?.node_count ?? 0
                  }
                  subtitle={
                    modeLabel === "LIVE"
                      ? `${clusterHealth?.healthy_nodes ?? 0} nodes Ready`
                      : modeLabel === "DEMO"
                        ? "Simulated cluster"
                        : "No live data"
                  }
                  icon={Activity}
                  iconClass="text-blue-400"
                />

                <StatCard
                  title="Incident Scenarios"
                  value={scenarios.length}
                  subtitle="OOMKilled, CrashLoop, Routing"
                  icon={FlaskConical}
                  iconClass="text-amber-400"
                />

                <StatCard
                  title="Security Engine"
                  value="Zero-Trust"
                  subtitle="Server-side allowlist active"
                  icon={ShieldCheck}
                  iconClass="text-emerald-400"
                />
              </div>

              <div className="space-y-4 rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-5">
                <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-200">
                      Active Incident
                    </h3>

                    <p className="mt-1 text-[11px] text-zinc-500">
                      The dashboard starts in a healthy state. Select a scenario only when you want to simulate a failure.
                    </p>
                  </div>

                  {selectedScenario && (
                    <button
                      type="button"
                      onClick={clearSelectedIncident}
                      className="self-start rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-[11px] font-medium text-zinc-300 transition hover:bg-zinc-800 hover:text-white sm:self-auto"
                    >
                      Clear Incident
                    </button>
                  )}
                </div>

                {selectedScenario ? (
                  <div className="flex flex-col items-start justify-between gap-4 rounded-lg border border-zinc-800 bg-zinc-950 p-4 sm:flex-row sm:items-center">
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold">
                          {selectedScenario.title}
                        </span>

                        <span className="rounded-full border border-rose-500/20 bg-rose-500/10 px-2 py-0.5 font-mono text-[10px] text-rose-400">
                          {selectedScenario.severity}
                        </span>
                      </div>

                      <p className="max-w-2xl text-xs leading-relaxed text-zinc-400">
                        {selectedScenario.description}
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => setActiveTab("ai")}
                      className="flex shrink-0 items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white transition hover:bg-blue-500"
                    >
                      Inspect RCA
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed border-emerald-500/20 bg-emerald-500/[0.03] p-6">
                    <div className="flex items-start gap-3">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />

                      <div>
                        <p className="text-xs font-semibold text-emerald-300">
                          No Active Incident
                        </p>

                        <p className="mt-1 text-xs leading-relaxed text-zinc-400">
                          The system is ready and no failure scenario is currently selected. Open the K8s Testing Lab to begin a controlled simulation.
                        </p>

                        <button
                          type="button"
                          onClick={() => setActiveTab("lab")}
                          className="mt-3 inline-flex items-center gap-2 rounded-lg bg-zinc-800 px-3 py-2 text-[11px] font-medium text-zinc-200 transition hover:bg-zinc-700"
                        >
                          Open Testing Lab
                          <ArrowRight className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {clusterHealth?.message && (
                <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4 text-xs text-zinc-400">
                  <span className="font-semibold text-zinc-200">
                    Environment status:
                  </span>{" "}
                  {clusterHealth.message}
                </div>
              )}
            </section>
          )}

          {activeTab === "lab" && (
            <section className="space-y-6">
              <div>
                <h2 className="text-lg font-bold tracking-tight">
                  Kubernetes Incident Simulation Lab
                </h2>

                <p className="mt-1 text-xs text-zinc-400">
                  Inject controlled failure scenarios and observe how the diagnostic workflow responds.
                </p>
              </div>

              {!initialLoading &&
              scenariosError &&
              scenarios.length === 0 ? (
                <div className="space-y-3 rounded-xl border border-dashed border-rose-500/30 bg-rose-500/[0.03] p-10 text-center">
                  <AlertOctagon className="mx-auto h-8 w-8 text-rose-400" />

                  <p className="text-sm font-semibold">
                    Could not reach the incident backend
                  </p>

                  <p className="mx-auto max-w-md text-xs text-zinc-400">
                    API endpoint: {API_BASE}
                  </p>

                  <button
                    type="button"
                    onClick={fetchScenarios}
                    className="rounded-lg bg-zinc-800 px-4 py-2 text-xs font-medium text-zinc-200 transition hover:bg-zinc-700"
                  >
                    Retry
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  {initialLoading &&
                    [0, 1, 2].map((item) => (
                      <div
                        key={item}
                        className="h-52 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/30"
                      />
                    ))}

                  {!initialLoading &&
                    scenarios.map((scenario) => {
                      const active =
                        selectedScenario?.id === scenario.id;

                      return (
                        <div
                          key={scenario.id}
                          className={`flex flex-col justify-between gap-5 rounded-xl border p-5 transition ${
                            active
                              ? "border-blue-500/50 bg-zinc-900/80 ring-1 ring-blue-500/20"
                              : "border-zinc-800/80 bg-zinc-900/30 hover:border-zinc-700"
                          }`}
                        >
                          <div className="space-y-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                                {scenario.category}
                              </span>

                              <span className="rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-300">
                                {scenario.severity}
                              </span>
                            </div>

                            <h3 className="text-sm font-semibold">
                              {scenario.title}
                            </h3>

                            <p className="text-xs leading-relaxed text-zinc-400">
                              {scenario.description}
                            </p>
                          </div>

                          <button
                            type="button"
                            onClick={() =>
                              handleRunScenario(scenario)
                            }
                            className={`flex w-full items-center justify-center gap-2 rounded-lg py-2 text-xs font-semibold transition ${
                              active
                                ? "bg-blue-600 text-white"
                                : "bg-zinc-800 text-zinc-200 hover:bg-zinc-700"
                            }`}
                          >
                            <Zap className="h-3.5 w-3.5" />

                            {active
                              ? "Scenario Active"
                              : "Trigger Fault"}
                          </button>
                        </div>
                      );
                    })}
                </div>
              )}
            </section>
          )}

          {activeTab === "ai" && (
            <section className="space-y-6">
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                <div>
                  <h2 className="text-lg font-bold tracking-tight">
                    AI Telemetry & Root Cause Analysis
                  </h2>

                  <p className="mt-1 text-xs text-zinc-400">
                    Analyze Kubernetes logs and events, then review a recommended remediation.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={fetchAiRca}
                  disabled={rcaLoading || !selectedScenario}
                  className="flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {rcaLoading ? (
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <BrainCircuit className="h-3.5 w-3.5" />
                  )}

                  {rcaLoading
                    ? "Analyzing Telemetry..."
                    : "Run AI Investigation"}
                </button>
              </div>

              {!selectedScenario && (
                <EmptyState message="No incident is currently selected. Choose a scenario from the K8s Testing Lab to begin an investigation." />
              )}

              {selectedScenario && !rcaResult && (
                <EmptyState message='Click "Run AI Investigation" to analyze the selected incident.' />
              )}

              {rcaResult && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <InfoCard
                      title="Root Cause Explanation"
                      value={
                        rcaResult.root_cause ||
                        rcaResult.analysis ||
                        "No root cause returned."
                      }
                      icon={AlertOctagon}
                      color="text-rose-400"
                    />

                    <InfoCard
                      title="Operational Impact"
                      value={
                        rcaResult.impact ||
                        "No impact description returned."
                      }
                      icon={Activity}
                      color="text-amber-400"
                    />

                    <InfoCard
                      title="Recommended Fix"
                      value={
                        rcaResult.recommended_fix ||
                        "No remediation recommendation returned."
                      }
                      icon={Check}
                      color="text-emerald-400"
                    />
                  </div>

                  <div className="space-y-4 rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-5">
                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                      <div>
                        <h3 className="text-sm font-semibold">
                          Manifest Delta
                        </h3>

                        <p className="mt-1 text-[11px] text-zinc-500">
                          Faulty state compared with the recommended target state.
                        </p>
                      </div>

                      <button
                        type="button"
                        onClick={triggerRemediation}
                        disabled={
                          remediating || remediationSuccess
                        }
                        className={`flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold transition ${
                          remediationSuccess
                            ? "border border-emerald-500/30 bg-emerald-500/20 text-emerald-400"
                            : "bg-emerald-600 text-white hover:bg-emerald-500"
                        } disabled:cursor-not-allowed disabled:opacity-70`}
                      >
                        {remediationSuccess ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : (
                          <RefreshCw
                            className={`h-3.5 w-3.5 ${
                              remediating
                                ? "animate-spin"
                                : ""
                            }`}
                          />
                        )}

                        {remediationSuccess
                          ? "Remediated"
                          : remediating
                            ? "Applying Patch..."
                            : "Apply One-Click Patch"}
                      </button>
                    </div>

                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                      <YamlPanel
                        title="Active Faulty State"
                        value={selectedScenario.problem_yaml}
                        color="rose"
                      />

                      <YamlPanel
                        title="Recommended Fix Target"
                        value={selectedScenario.fix_yaml}
                        color="emerald"
                      />
                    </div>
                  </div>
                </div>
              )}
            </section>
          )}

          {activeTab === "terminal" && (
            <section className="space-y-6">
              <div>
                <h2 className="text-lg font-bold tracking-tight">
                  Zero-Trust Interactive Terminal
                </h2>

                <p className="mt-1 text-xs text-zinc-400">
                  Run approved, read-only Kubernetes inspection commands. The allowlist is enforced by the backend.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {TERMINAL_PRESETS.map((preset) => (
                  <button
                    key={preset.command}
                    type="button"
                    onClick={() =>
                      executeTerminal(null, preset.command)
                    }
                    className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 font-mono text-[11px] text-zinc-300 transition hover:bg-zinc-800 hover:text-white"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>

              <form
                onSubmit={executeTerminal}
                className="flex flex-col gap-3 sm:flex-row"
              >
                <input
                  type="text"
                  value={terminalCmd}
                  onChange={(event) =>
                    setTerminalCmd(event.target.value)
                  }
                  placeholder="kubectl get pods"
                  className="min-w-0 flex-1 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-2.5 font-mono text-xs text-zinc-100 outline-none transition focus:border-blue-500"
                />

                <button
                  type="submit"
                  disabled={terminalLoading}
                  className="flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-xs font-semibold text-white transition hover:bg-blue-500 disabled:opacity-60"
                >
                  {terminalLoading && (
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  )}

                  Execute
                </button>
              </form>

              <div className="min-h-[320px] overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950 p-5 font-mono text-xs leading-relaxed text-zinc-300 shadow-inner">
                <div className="mb-3 flex items-center gap-2 border-b border-zinc-800/80 pb-3 text-[10px] text-zinc-500">
                  <span className="h-2.5 w-2.5 rounded-full bg-rose-500/80" />
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-500/80" />
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/80" />

                  <span className="ml-2">
                    kubectl inspection terminal
                  </span>
                </div>

                <pre className="whitespace-pre-wrap break-words">
                  {terminalOutput ||
                    "Output will appear here after command execution..."}
                </pre>
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconClass
}) {
  return (
    <div className="space-y-2 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
      <div className="flex items-center justify-between text-xs text-zinc-400">
        <span>{title}</span>
        <Icon className={`h-4 w-4 ${iconClass}`} />
      </div>

      <p className="font-mono text-2xl font-bold text-zinc-100">
        {value}
      </p>

      <p className="text-[11px] text-zinc-400">
        {subtitle}
      </p>
    </div>
  );
}

function InfoCard({
  title,
  value,
  icon: Icon,
  color
}) {
  return (
    <div className="min-w-0 space-y-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-5">
      <span
        className={`flex items-center gap-1.5 text-xs font-semibold ${color}`}
      >
        <Icon className="h-4 w-4 shrink-0" />
        {title}
      </span>

      <p className="whitespace-pre-wrap break-words text-xs leading-relaxed text-zinc-300">
        {value}
      </p>
    </div>
  );
}

function YamlPanel({
  title,
  value,
  color
}) {
  const styles =
    color === "rose"
      ? "border-rose-500/20 text-rose-300/90"
      : "border-emerald-500/20 text-emerald-300/90";

  const titleColor =
    color === "rose"
      ? "text-rose-400"
      : "text-emerald-400";

  return (
    <div
      className={`min-w-0 overflow-x-auto rounded-lg border bg-zinc-950 p-4 font-mono text-[11px] leading-relaxed ${styles}`}
    >
      <div
        className={`mb-2 text-[10px] font-bold uppercase tracking-wider ${titleColor}`}
      >
        {title}
      </div>

      <pre className="whitespace-pre-wrap break-words">
        {value || "No manifest available."}
      </pre>
    </div>
  );
}

function EmptyState({ message }) {
  return (
    <div className="rounded-xl border border-dashed border-zinc-800 p-12 text-center">
      <BrainCircuit className="mx-auto mb-3 h-8 w-8 text-zinc-600" />

      <p className="mx-auto max-w-xl text-xs leading-relaxed text-zinc-400">
        {message}
      </p>
    </div>
  );
}