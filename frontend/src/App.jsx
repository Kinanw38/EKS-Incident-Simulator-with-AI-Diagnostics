import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  FlaskConical,
  BrainCircuit,
  Terminal as TerminalIcon,
  ShieldCheck,
  Activity,
  CheckCircle2,
  AlertOctagon,
  RefreshCw,
  ArrowRight,
  Zap,
  Check
} from 'lucide-react';
import ToastContainer from './components/Notifications';

// In production (Vercel/Netlify), set VITE_API_URL to your deployed backend's URL.
// Locally, it falls back to localhost so nothing changes for local development.
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export default function App() {
  const [activeTab, setActiveTab] = useState("overview");
  const [scenarios, setScenarios] = useState([]);
  const [selectedScenario, setSelectedScenario] = useState(null);
  const [clusterHealth, setClusterHealth] = useState(null);
  const [rcaResult, setRcaResult] = useState(null);
  const [rcaLoading, setRcaLoading] = useState(false);
  const [remediating, setRemediating] = useState(false);
  const [remediationSuccess, setRemediationSuccess] = useState(false);
  const [terminalCmd, setTerminalCmd] = useState("kubectl get pods");
  const [terminalOutput, setTerminalOutput] = useState("");
  const [toasts, setToasts] = useState([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [scenariosError, setScenariosError] = useState(false);

  // Toast Helper
  const addToast = (type, title, message) => {
    const id = Date.now();

    setToasts(prev => [
      ...prev,
      {
        id,
        type,
        title,
        message
      }
    ]);

    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  // Fetch initial cluster health & scenarios
  useEffect(() => {
    Promise.all([fetchClusterHealth(), fetchScenarios()]).finally(() => {
      setInitialLoading(false);
    });
  }, []);

  const fetchClusterHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      const data = await res.json();

      setClusterHealth(data.cluster);
    } catch {
      setClusterHealth({
        status: "DEMO_MODE",
        connected: false,
        node_count: 2,
        healthy_nodes: 2
      });
    }
  };

  const fetchScenarios = async () => {
    try {
      const res = await fetch(`${API_BASE}/scenarios`);
      const data = await res.json();

      setScenarios(data);
      setScenariosError(false);

      if (data.length > 0) {
        setSelectedScenario(data[0]);
      }
    } catch {
      setScenariosError(true);
      addToast(
        "error",
        "API Connection Failed",
        "Could not load incident scenarios from backend."
      );
    }
  };

  // Trigger the selected incident in Kubernetes
  const handleRunScenario = async (sc) => {
    setSelectedScenario(sc);
    setRcaResult(null);
    setRemediationSuccess(false);

    try {
      const res = await fetch(
        `${API_BASE}/scenarios/${sc.id}/trigger`,
        {
          method: "POST"
        }
      );

      const data = await res.json();

      if (!res.ok) {
        throw new Error(
          data.detail || "Failed to trigger incident."
        );
      }

      addToast(
        "warning",
        "Incident Triggered",
        `${sc.title} is now active in Kubernetes.`
      );
    } catch (error) {
      addToast(
        "error",
        "Incident Trigger Failed",
        error.message || "Could not trigger the Kubernetes incident."
      );
    }
  };

  const fetchAiRca = async () => {
    if (!selectedScenario) return;

    setRcaLoading(true);

    try {
      const res = await fetch(
        `${API_BASE}/scenarios/${selectedScenario.id}/rca`
      );

      const data = await res.json();

      if (!res.ok) {
        throw new Error(
          data.detail || "Unable to analyze telemetry."
        );
      }

      setRcaResult(data);

      addToast(
        "info",
        "AI Analysis Complete",
        `Root cause generated via ${data.source || 'Engine'}`
      );
} catch (error) {
      addToast(
        "error",
        "RCA Failed",
        error.message || "Unable to analyze telemetry."
      );
    } finally {
      setRcaLoading(false);
    }
  };

  const triggerRemediation = async () => {
    if (!selectedScenario) return;

    setRemediating(true);

    try {
      const res = await fetch(`${API_BASE}/remediate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          incident_id: selectedScenario.id
        })
      });

      const data = await res.json();

      if (res.ok) {
        setRemediationSuccess(true);

        addToast(
          "success",
          "Remediation Successful",
          data.message || "Patch reconciled and workload recovered!"
        );
      } else {
        throw new Error(
          data.detail || "Could not apply YAML patch."
        );
      }
    } catch (error) {
      addToast(
        "error",
        "Remediation Failed",
        error.message || "Could not apply YAML patch."
      );
    } finally {
      setRemediating(false);
    }
  };

  const executeTerminal = async (e) => {
    e.preventDefault();

    try {
      const res = await fetch(`${API_BASE}/terminal/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          command: terminalCmd
        })
      });

      const data = await res.json();

      if (res.ok) {
        setTerminalOutput(data.output);
      } else {
        setTerminalOutput(
          `[SECURITY BLOCK]: ${data.detail}`
        );

        addToast(
          "error",
          "Command Blocked",
          data.detail
        );
      }
    } catch {
      setTerminalOutput(
        "Error connecting to command processor."
      );
    }
  };

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100 overflow-hidden font-sans">

      <ToastContainer
        toasts={toasts}
        removeToast={removeToast}
      />

      {/* Sidebar Navigation */}
      <aside className="w-64 border-r border-zinc-800/80 bg-zinc-950 flex flex-col justify-between select-none shrink-0">

        <div>

          {/* Header Branding */}
          <div className="p-5 border-b border-zinc-800/80 flex items-center gap-3">

            <div className="p-2 bg-blue-600/10 border border-blue-500/20 rounded-lg text-blue-400 shrink-0">
              <BrainCircuit className="w-5 h-5" />
            </div>

            <div className="min-w-0">
              <h1 className="font-bold text-sm tracking-wide text-zinc-100 truncate">
                EKS RCA Engine
              </h1>

              <p className="text-[10px] text-zinc-500 font-mono">
                v1.0.0 • AI-SRE Control
              </p>
            </div>

          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">

            {[
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
            ].map(item => {

              const Icon = item.icon;
              const isActive = activeTab === item.id;

              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-md text-xs font-medium transition-all duration-200 ease-out active:scale-[0.98] ${
                    isActive
                      ? "bg-zinc-800/60 text-zinc-100 border border-zinc-700/50 shadow-sm"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/80 hover:translate-x-0.5"
                  }`}
                >
                  <Icon
                    className={`w-4 h-4 shrink-0 ${
                      isActive
                        ? "text-blue-400"
                        : "text-zinc-500"
                    }`}
                  />

                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}

          </nav>

        </div>

        {/* Cluster Status Footer Badge */}
        <div className="p-4 border-t border-zinc-800/80 bg-zinc-900/30">

          <div className="flex items-center justify-between text-xs">

            <span className="text-zinc-400">
              EKS Status
            </span>

            <span
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-mono border ${
                clusterHealth?.connected
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/20"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  clusterHealth?.connected
                    ? "bg-emerald-400"
                    : "bg-amber-400"
                }`}
              />

              {clusterHealth?.connected
                ? "ONLINE"
                : "DEMO MODE"}
            </span>

          </div>

        </div>

      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto bg-zinc-950">

        {/* Top Navbar */}
        <header className="h-14 border-b border-zinc-800/80 px-6 flex items-center justify-between bg-zinc-950/50 backdrop-blur-sm sticky top-0 z-10 shrink-0">

          <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono min-w-0">
            <span>cluster</span>
            <span>/</span>

            <span className="text-zinc-100 font-semibold truncate">
              {selectedScenario
                ? selectedScenario.affected_component
                : "default"}
            </span>
          </div>

          <button
            onClick={fetchClusterHealth}
            className="group flex items-center gap-2 text-xs text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 hover:bg-zinc-900 active:scale-[0.97] transition-all duration-200 bg-zinc-900/60 border border-zinc-800 px-3 py-1.5 rounded-md shrink-0"
          >
            <RefreshCw className="w-3.5 h-3.5 transition-transform duration-500 group-hover:rotate-180" />
            Refresh State
          </button>

        </header>

        <div
          key={activeTab}
          className="animate-tab-in p-6 md:p-10 max-w-6xl w-full mx-auto space-y-8 min-w-0"
        >

          {/* TAB 1: SYSTEM OVERVIEW */}
          {activeTab === "overview" && (
            <div className="space-y-6">

              <div>
                <h2 className="text-lg font-bold text-zinc-100 tracking-tight">
                  System Infrastructure Overview
                </h2>

                <p className="text-xs text-zinc-400 mt-1">
                  Real-time status of connected Amazon EKS nodes and workload deployments.
                </p>
              </div>

              {/* Stat Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">

                <div className="p-4 bg-zinc-900/40 border border-zinc-800/80 rounded-xl space-y-2 transition-all duration-200 hover:border-zinc-700 hover:bg-zinc-900/70 hover:-translate-y-0.5">

                  <div className="flex justify-between text-xs text-zinc-400">
                    <span>EKS Nodes</span>
                    <Activity className="w-4 h-4 text-blue-400" />
                  </div>

                  {initialLoading ? (
                    <>
                      <div className="skeleton h-7 w-10" />
                      <div className="skeleton h-3 w-24" />
                    </>
                  ) : (
                    <>
                      <p className="text-2xl font-mono font-bold text-zinc-100">
                        {clusterHealth?.node_count || 2}
                      </p>

                      <p className="text-[11px] text-emerald-400">
                        All nodes Ready
                      </p>
                    </>
                  )}

                </div>

                <div className="p-4 bg-zinc-900/40 border border-zinc-800/80 rounded-xl space-y-2 transition-all duration-200 hover:border-zinc-700 hover:bg-zinc-900/70 hover:-translate-y-0.5">

                  <div className="flex justify-between text-xs text-zinc-400">
                    <span>Simulated Scenarios</span>
                    <FlaskConical className="w-4 h-4 text-amber-400" />
                  </div>

                  {initialLoading ? (
                    <>
                      <div className="skeleton h-7 w-10" />
                      <div className="skeleton h-3 w-32" />
                    </>
                  ) : (
                    <>
                      <p className="text-2xl font-mono font-bold text-zinc-100">
                        {scenarios.length}
                      </p>

                      <p className="text-[11px] text-zinc-400">
                        OOMKilled, CrashLoop, Routing
                      </p>
                    </>
                  )}

                </div>

                <div className="p-4 bg-zinc-900/40 border border-zinc-800/80 rounded-xl space-y-2 transition-all duration-200 hover:border-zinc-700 hover:bg-zinc-900/70 hover:-translate-y-0.5">

                  <div className="flex justify-between text-xs text-zinc-400">
                    <span>Security Engine</span>
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  </div>

                  <p className="text-2xl font-mono font-bold text-zinc-100">
                    Zero-Trust
                  </p>

                  <p className="text-[11px] text-zinc-400">
                    Regex Allowlist Active
                  </p>

                </div>

              </div>

              {/* Active Incident Overview */}
              <div className="p-5 bg-zinc-900/30 border border-zinc-800/80 rounded-xl space-y-4">

                <h3 className="text-sm font-semibold text-zinc-200">
                  Active Selected Incident
                </h3>

                {selectedScenario ? (

                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 bg-zinc-950 border border-zinc-800/80 rounded-lg">

                    <div className="space-y-1 min-w-0">

                      <div className="flex items-center gap-2 flex-wrap">

                        <span className="text-xs font-semibold text-zinc-100">
                          {selectedScenario.title}
                        </span>

                        <span className="px-2 py-0.5 text-[10px] bg-rose-500/10 text-rose-400 border border-rose-500/20 rounded-full font-mono">
                          {selectedScenario.severity}
                        </span>

                      </div>

                      <p className="text-xs text-zinc-400 max-w-xl break-words">
                        {selectedScenario.description}
                      </p>

                    </div>

                    <button
                      onClick={() => setActiveTab("ai")}
                      className="group flex items-center gap-2 text-xs bg-blue-600 hover:bg-blue-500 active:scale-[0.97] text-white font-medium px-4 py-2 rounded-lg transition-all duration-200 shadow-lg shadow-blue-600/10 hover:shadow-blue-600/25 shrink-0"
                    >
                      Inspect RCA
                      <ArrowRight className="w-3.5 h-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
                    </button>

                  </div>

                ) : (

                  <p className="text-xs text-zinc-500">
                    No incident selected. Select one in the K8s Testing Lab.
                  </p>

                )}

              </div>

            </div>
          )}

          {/* TAB 2: K8S TESTING LAB */}
          {activeTab === "lab" && (

            <div className="space-y-6">

              <div>

                <h2 className="text-lg font-bold text-zinc-100 tracking-tight">
                  Kubernetes Incident Simulation Lab
                </h2>

                <p className="text-xs text-zinc-400 mt-1">
                  Inject real fault conditions into active EKS deployments to evaluate AI detection.
                </p>

              </div>

              {!initialLoading && scenariosError && scenarios.length === 0 ? (

                <div className="p-10 text-center border border-dashed border-rose-500/20 bg-rose-500/[0.03] rounded-xl space-y-3">

                  <AlertOctagon className="w-8 h-8 text-rose-400/70 mx-auto" />

                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-zinc-200">
                      Couldn't reach the incident backend
                    </p>
                    <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                      The API at {API_BASE} didn't respond. Check that the backend is running, then retry.
                    </p>
                  </div>

                  <button
                    onClick={fetchScenarios}
                    className="inline-flex items-center gap-2 text-xs bg-zinc-800 hover:bg-zinc-700 active:scale-[0.97] text-zinc-200 font-medium px-4 py-2 rounded-lg transition-all duration-200"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    Retry
                  </button>

                </div>

              ) : (

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

                {initialLoading &&
                  [0, 1, 2].map(i => (
                    <div
                      key={`sk-${i}`}
                      className="p-5 rounded-xl border bg-zinc-900/30 border-zinc-800/80 flex flex-col justify-between gap-4"
                    >
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="skeleton h-3 w-16" />
                          <div className="skeleton h-4 w-14 rounded-full" />
                        </div>
                        <div className="skeleton h-4 w-3/4" />
                        <div className="skeleton h-3 w-full" />
                        <div className="skeleton h-3 w-2/3" />
                      </div>
                      <div className="skeleton h-9 w-full rounded-lg" />
                    </div>
                  ))}

                {!initialLoading && scenarios.map(sc => (

                  <div
                    key={sc.id}
                    className={`p-5 rounded-xl border transition-all duration-200 flex flex-col justify-between gap-4 ${
                      selectedScenario?.id === sc.id
                        ? "bg-zinc-900/80 border-blue-500/50 ring-1 ring-blue-500/20"
                        : "bg-zinc-900/30 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/50 hover:-translate-y-0.5"
                    }`}
                  >

                    <div className="space-y-2">

                      <div className="flex items-center justify-between">

                        <span className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider">
                          {sc.category}
                        </span>

                        <span className="px-2 py-0.5 text-[10px] font-mono bg-zinc-800 text-zinc-300 rounded border border-zinc-700">
                          {sc.severity}
                        </span>

                      </div>

                      <h3 className="text-sm font-semibold text-zinc-100">
                        {sc.title}
                      </h3>

                      <p className="text-xs text-zinc-400 line-clamp-3 leading-relaxed break-words">
                        {sc.description}
                      </p>

                    </div>

                    <button
                      onClick={() => handleRunScenario(sc)}
                      className={`w-full py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition-all duration-200 active:scale-[0.97] ${
                        selectedScenario?.id === sc.id
                          ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
                          : "bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
                      }`}
                    >
                      <Zap className="w-3.5 h-3.5 shrink-0" />

                      {selectedScenario?.id === sc.id
                        ? "Scenario Active"
                        : "Trigger Fault"}
                    </button>

                  </div>

                ))}

              </div>

              )}

            </div>
          )}

          {/* TAB 3: AI RCA & REMEDIATION */}
          {activeTab === "ai" && (

            <div className="space-y-6 min-w-0">

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">

                <div>

                  <h2 className="text-lg font-bold text-zinc-100 tracking-tight">
                    AI Telemetry & Root Cause Analysis
                  </h2>

                  <p className="text-xs text-zinc-400 mt-1">
                    Autonomous investigation of Kubernetes events, pod exit codes, and logs.
                  </p>

                </div>

                <button
                  onClick={fetchAiRca}
                  disabled={rcaLoading || !selectedScenario}
                  className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 active:scale-[0.97] disabled:opacity-50 disabled:active:scale-100 text-white text-xs font-semibold rounded-lg transition-all duration-200 shrink-0"
                >

                  {rcaLoading
                    ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    : <BrainCircuit className="w-3.5 h-3.5" />}

                  {rcaLoading
                    ? "Analyzing Telemetry..."
                    : "Run AI Investigation"}

                </button>

              </div>

              {/* RCA Details Grid */}
              {rcaResult ? (

                <div className="space-y-6 min-w-0">

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

                    <div className="p-5 bg-zinc-900/40 border border-zinc-800/80 rounded-xl space-y-2 min-w-0">

                      <span className="text-xs font-semibold text-rose-400 flex items-center gap-1.5">
                        <AlertOctagon className="w-4 h-4 shrink-0" />
                        Root Cause Explanation
                      </span>

                      <p className="text-xs text-zinc-300 leading-relaxed font-sans break-words whitespace-pre-wrap">
                        {rcaResult.root_cause || rcaResult.analysis}
                      </p>

                    </div>

                    <div className="p-5 bg-zinc-900/40 border border-zinc-800/80 rounded-xl space-y-2 min-w-0">

                      <span className="text-xs font-semibold text-amber-400 flex items-center gap-1.5">
                        <Activity className="w-4 h-4 shrink-0" />
                        Operational Impact
                      </span>

                      <p className="text-xs text-zinc-300 leading-relaxed font-sans break-words whitespace-pre-wrap">
                        {rcaResult.impact || "Service degraded."}
                      </p>

                    </div>

                    <div className="p-5 bg-zinc-900/40 border border-zinc-800/80 rounded-xl space-y-2 min-w-0">

                      <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
                        <Check className="w-4 h-4 shrink-0" />
                        Recommended Fix
                      </span>

                      <p className="text-xs text-zinc-300 leading-relaxed font-sans break-words whitespace-pre-wrap">
                        {rcaResult.recommended_fix || "See manifest delta below."}
                      </p>

                    </div>

                  </div>

                  {/* YAML Split View & Remediation */}
                  <div className="p-5 bg-zinc-900/30 border border-zinc-800/80 rounded-xl space-y-4 min-w-0">

                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">

                      <h3 className="text-sm font-semibold text-zinc-200">
                        Manifest Delta (Problem vs Ground Truth Fix)
                      </h3>

                      <button
                        onClick={triggerRemediation}
                        disabled={remediating || remediationSuccess}
                        className={`flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all duration-200 active:scale-[0.97] disabled:active:scale-100 shrink-0 ${
                          remediationSuccess
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                            : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/10 hover:shadow-emerald-600/25"
                        }`}
                      >

                        {remediationSuccess
                          ? <Check className="w-3.5 h-3.5" />
                          : <RefreshCw
                              className={`w-3.5 h-3.5 ${
                                remediating
                                  ? "animate-spin"
                                  : ""
                              }`}
                            />}

                        {remediationSuccess
                          ? "Remediated & Reconciled"
                          : remediating
                            ? "Applying Patch..."
                            : "Apply One-Click Patch"}

                      </button>

                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-[11px] min-w-0">

                      {/* Problem YAML */}
                      <div className="bg-zinc-950 border border-rose-500/20 rounded-lg p-4 overflow-x-auto text-rose-300/90 leading-relaxed min-w-0">

                        <div className="text-[10px] text-rose-500 mb-2 font-bold uppercase tracking-wider">
                          Active Faulty State
                        </div>

                        <pre className="whitespace-pre-wrap break-all">
                          {selectedScenario?.problem_yaml}
                        </pre>

                      </div>

                      {/* Fix YAML */}
                      <div className="bg-zinc-950 border border-emerald-500/20 rounded-lg p-4 overflow-x-auto text-emerald-300/90 leading-relaxed min-w-0">

                        <div className="text-[10px] text-emerald-500 mb-2 font-bold uppercase tracking-wider">
                          Recommended Fix Target
                        </div>

                        <pre className="whitespace-pre-wrap break-all">
                          {selectedScenario?.fix_yaml}
                        </pre>

                      </div>

                    </div>

                  </div>

                </div>

              ) : (

                <div className="p-12 text-center border border-dashed border-zinc-800 rounded-xl space-y-3">

                  <BrainCircuit className="w-8 h-8 text-zinc-600 mx-auto" />

                  <p className="text-xs text-zinc-400">
                    Click "Run AI Investigation" to analyze logs and compute root cause analysis.
                  </p>

                </div>

              )}

            </div>
          )}

          {/* TAB 4: ZERO-TRUST TERMINAL */}
          {activeTab === "terminal" && (

            <div className="space-y-6 min-w-0">

              <div>

                <h2 className="text-lg font-bold text-zinc-100 tracking-tight">
                  Zero-Trust Interactive Terminal
                </h2>

                <p className="text-xs text-zinc-400 mt-1">
                  Execute safe inspection commands against EKS. Strictly guarded by Regex Allowlist.
                </p>

              </div>

              <form
                onSubmit={executeTerminal}
                className="flex gap-3"
              >

                <input
                  type="text"
                  value={terminalCmd}
                  onChange={(e) => setTerminalCmd(e.target.value)}
                  placeholder="e.g. kubectl get pods"
                  className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2.5 text-xs font-mono text-zinc-100 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 transition-all duration-200 min-w-0"
                />

                <button
                  type="submit"
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 active:scale-[0.97] text-white text-xs font-semibold rounded-lg transition-all duration-200 shadow-lg shadow-blue-600/10 hover:shadow-blue-600/25 shrink-0"
                >
                  Execute
                </button>

              </form>

              {/* Terminal Display */}
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-5 font-mono text-xs text-zinc-300 min-h-[300px] overflow-x-auto leading-relaxed shadow-inner min-w-0">

                <div className="flex items-center gap-2 text-zinc-500 text-[10px] mb-3 pb-2 border-b border-zinc-800/80">

                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80 shrink-0" />
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80 shrink-0" />
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80 shrink-0" />

                  <span className="ml-2">
                    bash - kubectl shell
                  </span>

                </div>

                <pre className="whitespace-pre-wrap break-all">
                  {terminalOutput || "Output will appear here after command execution..."}
                </pre>

              </div>

            </div>
          )}

        </div>

      </main>

    </div>
  );
}