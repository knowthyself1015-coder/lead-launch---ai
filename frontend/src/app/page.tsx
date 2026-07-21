"use client";

import { useEffect, useState } from "react";
import TradingViewChart from "@/components/TradingViewChart";
import { api, Signal, Health, PipelineStatus } from "@/lib/api";

export default function Dashboard() {
  const [health, setHealth] = useState<Health | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [h, s, p] = await Promise.all([
          api.health(),
          api.signals.list(),
          api.pipeline.status(),
        ]);
        setHealth(h);
        setSignals(s);
        setPipeline(p);
      } catch (err) {
        console.error("Failed to fetch dashboard data:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
    // Poll pipeline status every 15s
    const poll = setInterval(async () => {
      try {
        const p = await api.pipeline.status();
        setPipeline(p);
      } catch {}
    }, 15000);
    return () => clearInterval(poll);
  }, []);

  async function handleStart() {
    setActionLoading(true);
    try {
      await api.pipeline.start();
      const p = await api.pipeline.status();
      setPipeline(p);
    } catch (err) {
      console.error("Failed to start pipeline:", err);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleStop() {
    setActionLoading(true);
    try {
      await api.pipeline.stop();
      const p = await api.pipeline.status();
      setPipeline(p);
    } catch (err) {
      console.error("Failed to stop pipeline:", err);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleRunOnce() {
    setActionLoading(true);
    try {
      await api.pipeline.runOnce();
      const p = await api.pipeline.status();
      setPipeline(p);
    } catch (err) {
      console.error("Failed to run pipeline:", err);
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-surface-200 mt-1">
          {health
            ? `Backend: ${health.status} · Environment: ${health.environment}`
            : "Connecting to backend..."}
        </p>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Active Signals" value={signals.length} color="alpha" />
        <StatCard label="Open Positions" value="0" color="blue" />
        <StatCard label="Daily P&L" value="$0.00" color="emerald" />
        <StatCard label="Win Rate" value="—" color="amber" />
      </div>

      {/* Pipeline status */}
      <PipelineCard
        pipeline={pipeline}
        loading={loading}
        actionLoading={actionLoading}
        onStart={handleStart}
        onStop={handleStop}
        onRunOnce={handleRunOnce}
      />

      {/* Chart */}
      <TradingViewChart ticker="SPY" />

      {/* Signal table */}
      <div className="bg-surface-800 rounded-lg border border-surface-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-surface-700">
          <h3 className="text-sm font-semibold">Recent Signals</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-700 text-surface-200 text-left">
                <th className="px-4 py-2 font-medium">Ticker</th>
                <th className="px-4 py-2 font-medium">Direction</th>
                <th className="px-4 py-2 font-medium">Confidence</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-surface-200">
                    Loading signals...
                  </td>
                </tr>
              ) : signals.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-surface-200">
                    No signals yet. The scanner will populate this table.
                  </td>
                </tr>
              ) : (
                signals.map((s) => (
                  <tr key={s.id} className="border-b border-surface-700/50 hover:bg-surface-700/50">
                    <td className="px-4 py-2 font-mono font-medium">{s.ticker}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          s.direction === "long"
                            ? "bg-alpha-900/30 text-alpha-400"
                            : "bg-red-900/30 text-red-400"
                        }`}
                      >
                        {s.direction.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-2">{(s.confidence * 100).toFixed(0)}%</td>
                    <td className="px-4 py-2">
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="px-4 py-2 text-surface-200">
                      {new Date(s.created_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color: "alpha" | "blue" | "emerald" | "amber";
}) {
  const colorMap = {
    alpha: "border-alpha-800 bg-alpha-950/20",
    blue: "border-blue-800 bg-blue-950/20",
    emerald: "border-emerald-800 bg-emerald-950/20",
    amber: "border-amber-800 bg-amber-950/20",
  };

  return (
    <div className={`rounded-lg border p-4 ${colorMap[color]}`}>
      <p className="text-xs text-surface-200 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-surface-700 text-surface-200",
    accepted: "bg-alpha-900/30 text-alpha-400",
    rejected: "bg-red-900/30 text-red-400",
    executed: "bg-blue-900/30 text-blue-400",
    expired: "bg-amber-900/30 text-amber-400",
  };

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[status] || styles.pending}`}>
      {status}
    </span>
  );
}

function PipelineCard({
  pipeline,
  loading,
  actionLoading,
  onStart,
  onStop,
  onRunOnce,
}: {
  pipeline: PipelineStatus | null;
  loading: boolean;
  actionLoading: boolean;
  onStart: () => void;
  onStop: () => void;
  onRunOnce: () => void;
}) {
  const isRunning = pipeline?.pipeline?.running ?? false;
  const lastRun = pipeline?.last_run;
  const market = pipeline?.market;

  return (
    <div className="bg-surface-800 rounded-lg border border-surface-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold">Pipeline</h3>
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${
              isRunning
                ? "bg-emerald-900/30 text-emerald-400"
                : "bg-surface-700 text-surface-200"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isRunning ? "bg-emerald-400 animate-pulse" : "bg-gray-500"
              }`}
            />
            {isRunning ? "Running" : "Stopped"}
          </span>
          {market && (
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${
                market.is_open
                  ? "bg-blue-900/30 text-blue-400"
                  : "bg-amber-900/30 text-amber-400"
              }`}
            >
              Market: {market.is_open ? "Open" : "Closed"}
              {!market.is_open && ` (${market.reason.replace(/_/g, " ")})`}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onRunOnce}
            disabled={actionLoading}
            className="px-3 py-1.5 text-xs rounded-md bg-surface-700 hover:bg-surface-600 text-surface-100 disabled:opacity-50 transition-colors"
            title="Run pipeline once (manual trigger)"
          >
            Run Once
          </button>
          {isRunning ? (
            <button
              onClick={onStop}
              disabled={actionLoading}
              className="px-3 py-1.5 text-xs rounded-md bg-red-900/30 hover:bg-red-900/50 text-red-400 border border-red-800 disabled:opacity-50 transition-colors"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={onStart}
              disabled={actionLoading}
              className="px-3 py-1.5 text-xs rounded-md bg-emerald-900/30 hover:bg-emerald-900/50 text-emerald-400 border border-emerald-800 disabled:opacity-50 transition-colors"
            >
              Start
            </button>
          )}
        </div>
      </div>

      <div className="p-4">
        {loading ? (
          <p className="text-sm text-surface-200">Loading pipeline status...</p>
        ) : lastRun ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-xs text-surface-200 uppercase">Last Run</p>
              <p className="font-mono">
                {lastRun.completed_at
                  ? new Date(lastRun.completed_at).toLocaleTimeString()
                  : lastRun.started_at
                  ? new Date(lastRun.started_at).toLocaleTimeString()
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-surface-200 uppercase">Symbols Scanned</p>
              <p className="font-mono font-bold">{lastRun.symbols_scanned}</p>
            </div>
            <div>
              <p className="text-xs text-surface-200 uppercase">Signals Generated</p>
              <p className="font-mono font-bold">{lastRun.signals_generated}</p>
            </div>
            <div>
              <p className="text-xs text-surface-200 uppercase">Trades Executed</p>
              <p className="font-mono font-bold">{lastRun.trades_executed}</p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-surface-200">No pipeline runs yet. Click "Run Once" or "Start" to begin.</p>
        )}
        {lastRun && lastRun.error_count > 0 && (
          <p className="text-xs text-red-400 mt-2">
            ⚠️ {lastRun.error_count} error{lastRun.error_count > 1 ? "s" : ""} in last run
          </p>
        )}
      </div>
    </div>
  );
}
