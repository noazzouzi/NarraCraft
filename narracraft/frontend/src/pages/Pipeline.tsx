import { useState, useEffect, useRef, useCallback } from "react";
import { useTheme } from "@/components/ThemeProvider";
import { toast } from "@/components/Toaster";
import {
  runPipeline,
  stopPipeline,
  pipelineStatus,
  type StepLog,
  type PipelineStatusResponse,
} from "@/api/client";
import {
  Play,
  Square,
  Search,
  PenTool,
  Shield,
  Palette,
  Film,
  Wrench,
  CheckCircle2,
  Upload,
  Loader2,
  Clock,
  AlertTriangle,
  XCircle,
  ChevronDown,
} from "lucide-react";

interface LogEntry {
  time: string;
  type: string;
  message: string;
  step?: string;
}

const STEP_ICONS: Record<string, typeof Search> = {
  research: Search,
  script: PenTool,
  compliance: Shield,
  voice_images: Palette,
  animate: Film,
  assemble: Wrench,
  quality_gate: CheckCircle2,
  publish: Upload,
};

export default function Pipeline() {
  const { theme } = useTheme();

  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState("");
  const [stepsLog, setStepsLog] = useState<StepLog[]>([]);
  const [steps, setSteps] = useState<{ id: string; label: string }[]>([]);
  const [pipelineInfo, setPipelineInfo] = useState<{ topic_id: string; franchise_id: string; status: string }>({
    topic_id: "",
    franchise_id: "",
    status: "idle",
  });
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [showLogs, setShowLogs] = useState(true);
  const [recentRuns, setRecentRuns] = useState<Record<string, unknown>[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  const addLog = useCallback((entry: LogEntry) => {
    setLogs((prev) => [...prev.slice(-200), entry]);
  }, []);

  // Fetch initial status
  useEffect(() => {
    pipelineStatus().then((data) => {
      setIsRunning(data.is_running);
      setSteps(data.steps);
      setStepsLog(data.current.steps_log || []);
      setCurrentStep(data.current.current_step);
      setPipelineInfo({
        topic_id: data.current.topic_id,
        franchise_id: data.current.franchise_id,
        status: data.current.status,
      });
      setRecentRuns(data.runs || []);
    }).catch(() => {});
  }, []);

  // WebSocket connection
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.hostname}:8000/api/pipeline/ws`;

    function connect() {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        addLog({ time: now(), type: "system", message: "WebSocket connected" });
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleWsMessage(data);
        } catch { /* ignore */ }
      };

      ws.onclose = () => {
        addLog({ time: now(), type: "system", message: "WebSocket disconnected — reconnecting..." });
        setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    // Ping to keep alive
    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send("ping");
      }
    }, 30000);

    return () => {
      clearInterval(interval);
      wsRef.current?.close();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleWsMessage = useCallback((data: Record<string, unknown>) => {
    const type = data.type as string;

    switch (type) {
      case "connected":
        setIsRunning(data.is_running as boolean);
        setCurrentStep((data.current_step as string) || "");
        if (data.steps_log) setStepsLog(data.steps_log as StepLog[]);
        break;

      case "step_start":
        setIsRunning(true);
        setCurrentStep(data.step as string);
        setStepsLog((prev) => [
          ...prev.filter((s) => s.step !== data.step),
          { step: data.step as string, status: "running", duration: 0 },
        ]);
        addLog({
          time: now(),
          type: "step",
          message: `Starting: ${data.label}`,
          step: data.step as string,
        });
        break;

      case "step_complete":
        setStepsLog((prev) =>
          prev.map((s) =>
            s.step === data.step
              ? { ...s, status: "completed", duration: data.duration as number }
              : s
          ),
        );
        addLog({
          time: now(),
          type: "success",
          message: `Completed: ${data.step} (${(data.duration as number).toFixed(1)}s)`,
          step: data.step as string,
        });
        break;

      case "step_failed":
        setStepsLog((prev) =>
          prev.map((s) =>
            s.step === data.step
              ? { ...s, status: "failed", duration: data.duration as number, error: data.error as string }
              : s
          ),
        );
        addLog({
          time: now(),
          type: "error",
          message: `Failed: ${data.step} — ${data.error}`,
          step: data.step as string,
        });
        break;

      case "info":
        addLog({ time: now(), type: "info", message: data.message as string });
        break;

      case "warning":
        addLog({ time: now(), type: "warning", message: data.message as string });
        toast.warning(data.message as string);
        break;

      case "error":
        addLog({ time: now(), type: "error", message: data.message as string });
        toast.error(data.message as string);
        break;

      case "pipeline_error":
        addLog({ time: now(), type: "error", message: data.error as string });
        toast.error(`Pipeline error: ${data.error}`);
        break;

      case "pipeline_complete":
        setIsRunning(false);
        setPipelineInfo((prev) => ({ ...prev, status: data.status as string }));
        addLog({
          time: now(),
          type: data.status === "completed" ? "success" : "error",
          message: `Pipeline ${data.status}: ${data.message} (${(data.duration as number).toFixed(1)}s)`,
        });
        // Toast notification
        if (data.status === "completed") {
          toast.success(`Pipeline completed in ${(data.duration as number).toFixed(1)}s`);
        } else {
          toast.error(`Pipeline ${data.status}: ${data.message}`);
        }
        break;

      case "pipeline_aborting":
        addLog({ time: now(), type: "warning", message: "Abort requested..." });
        break;
    }
  }, [addLog]);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleRun = async () => {
    try {
      setLogs([]);
      const resp = await runPipeline();
      if (resp.status === "started") {
        setIsRunning(true);
        addLog({ time: now(), type: "system", message: "Pipeline started" });
      } else {
        addLog({ time: now(), type: "error", message: resp.message });
      }
    } catch (e) {
      addLog({ time: now(), type: "error", message: `Failed to start pipeline: ${e}` });
    }
  };

  const handleStop = async () => {
    try {
      await stopPipeline();
      addLog({ time: now(), type: "warning", message: "Abort requested" });
    } catch (e) {
      addLog({ time: now(), type: "error", message: `Failed to stop pipeline: ${e}` });
    }
  };

  const getStepStatus = (stepId: string): string => {
    const log = stepsLog.find((s) => s.step === stepId);
    return log?.status || "idle";
  };

  const getStepDuration = (stepId: string): number => {
    const log = stepsLog.find((s) => s.step === stepId);
    return log?.duration || 0;
  };

  const stepStatusColor = (status: string) => {
    switch (status) {
      case "completed": return theme.success;
      case "running": return theme.accent;
      case "failed": return theme.danger;
      default: return theme.muted;
    }
  };

  const stepStatusIcon = (status: string) => {
    switch (status) {
      case "completed": return <CheckCircle2 size={14} />;
      case "running": return <Loader2 size={14} className="animate-spin" />;
      case "failed": return <XCircle size={14} />;
      default: return <Clock size={14} />;
    }
  };

  const logTypeColor = (type: string) => {
    switch (type) {
      case "success": return theme.success;
      case "error": return theme.danger;
      case "warning": return "#FF9800";
      case "step": return theme.accent;
      case "system": return theme.muted;
      default: return theme.dim;
    }
  };

  const cardStyle = {
    background: theme.surface,
    border: `1px solid ${theme.border}`,
    borderRadius: theme.card.borderRadius,
    ...theme.card,
  };

  return (
    <div className="flex-1 p-5 overflow-y-auto" style={{ fontFamily: theme.body }}>
      {/* Header */}
      <div className="flex justify-between items-center mb-5">
        <div>
          <h1 className="m-0 mb-1" style={{ fontSize: 22, fontWeight: 700, fontFamily: theme.font, color: theme.text }}>
            Pipeline
          </h1>
          <p className="m-0" style={{ fontSize: 13, color: theme.dim }}>
            Run and monitor the video production pipeline.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleRun}
            disabled={isRunning}
            className="flex items-center gap-2 px-5 py-2.5 text-xs font-bold tracking-wider cursor-pointer disabled:opacity-40"
            style={{
              background: isRunning ? `${theme.muted}30` : `${theme.accent}15`,
              border: `1px solid ${isRunning ? theme.muted : theme.accent}`,
              color: isRunning ? theme.muted : theme.accent,
              fontFamily: theme.mono,
              borderRadius: theme.card.borderRadius,
            }}
          >
            {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {theme.f.deploy}
          </button>
          <button
            onClick={handleStop}
            disabled={!isRunning}
            className="flex items-center gap-2 px-5 py-2.5 text-xs font-bold tracking-wider cursor-pointer disabled:opacity-40"
            style={{
              background: `${theme.danger}15`,
              border: `1px solid ${isRunning ? theme.danger : theme.muted}`,
              color: isRunning ? theme.danger : theme.muted,
              fontFamily: theme.mono,
              borderRadius: theme.card.borderRadius,
            }}
          >
            <Square size={14} />
            {theme.f.abort}
          </button>
        </div>
      </div>

      {/* Pipeline info bar */}
      {pipelineInfo.topic_id && (
        <div
          className="flex items-center gap-4 px-4 py-2.5 mb-4 text-xs"
          style={{
            background: `${theme.accent}08`,
            border: `1px solid ${theme.accent}30`,
            borderRadius: theme.card.borderRadius,
            fontFamily: theme.mono,
          }}
        >
          <span style={{ color: theme.dim }}>
            Topic: <span style={{ color: theme.text }}>{pipelineInfo.topic_id}</span>
          </span>
          <span style={{ color: theme.dim }}>
            Franchise: <span style={{ color: theme.text }}>{pipelineInfo.franchise_id}</span>
          </span>
          <span
            className="ml-auto px-2 py-0.5 font-bold tracking-wider"
            style={{
              background: `${stepStatusColor(pipelineInfo.status === "running" ? "running" : pipelineInfo.status === "completed" ? "completed" : pipelineInfo.status === "failed" ? "failed" : "idle")}20`,
              color: stepStatusColor(pipelineInfo.status === "running" ? "running" : pipelineInfo.status === "completed" ? "completed" : pipelineInfo.status === "failed" ? "failed" : "idle"),
              borderRadius: "3px",
              fontSize: 10,
            }}
          >
            {pipelineInfo.status.toUpperCase()}
          </span>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {/* Steps panel */}
        <div className="col-span-1">
          <div className="p-4" style={cardStyle}>
            <h3 className="m-0 mb-3 text-xs font-bold tracking-wider" style={{ color: theme.dim, fontFamily: theme.mono }}>
              PIPELINE STEPS
            </h3>

            {steps.map((step, i) => {
              const status = getStepStatus(step.id);
              const duration = getStepDuration(step.id);
              const Icon = STEP_ICONS[step.id] || Search;
              const isCurrent = currentStep === step.id && isRunning;

              return (
                <div
                  key={step.id}
                  className="flex items-center gap-3 py-2.5"
                  style={{
                    borderBottom: i < steps.length - 1 ? `1px solid ${theme.border}` : "none",
                    background: isCurrent ? `${theme.accent}08` : "transparent",
                    marginLeft: -16,
                    marginRight: -16,
                    paddingLeft: 16,
                    paddingRight: 16,
                  }}
                >
                  <div style={{ color: stepStatusColor(status) }}>
                    {status === "running" ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <Icon size={16} />
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className="text-xs font-semibold"
                        style={{ color: status === "idle" ? theme.dim : theme.text }}
                      >
                        {step.label.split(" — ")[0]}
                      </span>
                    </div>
                    {step.label.includes(" — ") && (
                      <div className="text-[10px] mt-0.5" style={{ color: theme.muted }}>
                        {step.label.split(" — ")[1]}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    {duration > 0 && (
                      <span className="text-[10px]" style={{ color: theme.dim, fontFamily: theme.mono }}>
                        {duration.toFixed(1)}s
                      </span>
                    )}
                    <span style={{ color: stepStatusColor(status) }}>
                      {stepStatusIcon(status)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Log panel */}
        <div className="col-span-2">
          <div style={cardStyle}>
            <div
              className="flex items-center justify-between px-4 py-3 cursor-pointer"
              style={{ borderBottom: `1px solid ${theme.border}` }}
              onClick={() => setShowLogs(!showLogs)}
            >
              <h3 className="m-0 text-xs font-bold tracking-wider" style={{ color: theme.dim, fontFamily: theme.mono }}>
                {theme.f.log.toUpperCase()}
              </h3>
              <div className="flex items-center gap-2">
                <span className="text-[10px]" style={{ color: theme.muted, fontFamily: theme.mono }}>
                  {logs.length} entries
                </span>
                <ChevronDown
                  size={14}
                  style={{
                    color: theme.dim,
                    transform: showLogs ? "rotate(180deg)" : "none",
                    transition: "transform 0.2s",
                  }}
                />
              </div>
            </div>

            {showLogs && (
              <div
                className="p-3 overflow-y-auto"
                style={{ maxHeight: 400, fontFamily: theme.mono, fontSize: 11 }}
              >
                {logs.length === 0 ? (
                  <div className="text-center py-8" style={{ color: theme.muted }}>
                    No log entries yet. Start the pipeline to see progress.
                  </div>
                ) : (
                  logs.map((entry, i) => (
                    <div key={i} className="flex gap-2 py-1" style={{ lineHeight: 1.5 }}>
                      <span style={{ color: theme.muted, shrink: 0 }} className="shrink-0">
                        {entry.time}
                      </span>
                      <span style={{ color: logTypeColor(entry.type) }}>
                        {entry.type === "error" ? <AlertTriangle size={11} className="inline" /> : null}
                        {" "}{entry.message}
                      </span>
                    </div>
                  ))
                )}
                <div ref={logEndRef} />
              </div>
            )}
          </div>

          {/* Recent runs */}
          {recentRuns.length > 0 && (
            <div className="mt-4 p-4" style={cardStyle}>
              <h3 className="m-0 mb-3 text-xs font-bold tracking-wider" style={{ color: theme.dim, fontFamily: theme.mono }}>
                RECENT RUNS
              </h3>
              <div className="flex flex-col gap-1.5">
                {recentRuns.slice(0, 5).map((run, i) => (
                  <div key={i} className="flex items-center gap-3 text-xs" style={{ color: theme.dim }}>
                    <span
                      className="px-1.5 py-0.5 text-[10px] font-bold tracking-wider"
                      style={{
                        background: `${stepStatusColor(run.status as string || "idle")}20`,
                        color: stepStatusColor(run.status as string || "idle"),
                        borderRadius: "3px",
                        fontFamily: theme.mono,
                      }}
                    >
                      {(run.status as string || "unknown").toUpperCase()}
                    </span>
                    <span style={{ fontFamily: theme.mono }}>
                      {run.topic_id as string || "—"}
                    </span>
                    <span className="ml-auto" style={{ color: theme.muted, fontFamily: theme.mono }}>
                      {run.started_at as string || ""}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function now(): string {
  const d = new Date();
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
}
