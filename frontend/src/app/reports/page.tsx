"use client";

import { useEffect, useState } from "react";
import { api, DailyReport } from "@/lib/api";

export default function ReportsPage() {
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.reports
      .list(30)
      .then(setReports)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Reports</h2>
        <p className="text-surface-200 mt-1">Daily performance summaries and analytics</p>
      </div>

      {/* KPI cards */}
      {reports.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Net P&L (Latest)" value={`$${reports[0].net_pnl.toFixed(2)}`} />
          <KpiCard label="Win Rate" value={`${((reports[0].win_rate ?? 0) * 100).toFixed(0)}%`} />
          <KpiCard label="Total Trades" value={reports[0].total_trades} />
          <KpiCard label="Sharpe" value={reports[0].sharpe_ratio?.toFixed(2) ?? "—"} />
        </div>
      )}

      {/* Report table */}
      <div className="bg-surface-800 rounded-lg border border-surface-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-surface-700">
          <h3 className="text-sm font-semibold">Recent Reports</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-700 text-surface-200 text-left">
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium text-right">P&L</th>
                <th className="px-4 py-2 font-medium text-right">%</th>
                <th className="px-4 py-2 font-medium text-right">Trades</th>
                <th className="px-4 py-2 font-medium text-right">Win Rate</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-surface-200">
                    Loading reports...
                  </td>
                </tr>
              ) : reports.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-surface-200">
                    No reports generated yet
                  </td>
                </tr>
              ) : (
                reports.map((r) => (
                  <tr key={r.id} className="border-b border-surface-700/50 hover:bg-surface-700/50">
                    <td className="px-4 py-2 font-mono">
                      {new Date(r.report_date).toLocaleDateString()}
                    </td>
                    <td
                      className={`px-4 py-2 text-right font-mono ${
                        r.net_pnl >= 0 ? "text-alpha-400" : "text-red-400"
                      }`}
                    >
                      {r.net_pnl >= 0 ? "+" : ""}${r.net_pnl.toFixed(2)}
                    </td>
                    <td
                      className={`px-4 py-2 text-right font-mono ${
                        r.net_pnl_pct >= 0 ? "text-alpha-400" : "text-red-400"
                      }`}
                    >
                      {r.net_pnl_pct >= 0 ? "+" : ""}
                      {r.net_pnl_pct.toFixed(2)}%
                    </td>
                    <td className="px-4 py-2 text-right">{r.total_trades}</td>
                    <td className="px-4 py-2 text-right">
                      {r.win_rate ? `${(r.win_rate * 100).toFixed(0)}%` : "—"}
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

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-surface-700 bg-surface-800 p-4">
      <p className="text-xs text-surface-200 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1 font-mono">{value}</p>
    </div>
  );
}
