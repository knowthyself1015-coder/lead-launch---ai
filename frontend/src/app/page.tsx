"use client";

import { useEffect, useState } from "react";
import TradingViewChart from "@/components/TradingViewChart";
import { api, Signal, Health } from "@/lib/api";

export default function Dashboard() {
  const [health, setHealth] = useState<Health | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [h, s] = await Promise.all([api.health(), api.signals.list()]);
        setHealth(h);
        setSignals(s);
      } catch (err) {
        console.error("Failed to fetch dashboard data:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

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
