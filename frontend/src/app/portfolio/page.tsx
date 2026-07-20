"use client";

import { useEffect, useState } from "react";
import { api, PortfolioPosition } from "@/lib/api";

export default function PortfolioPage() {
  const [snapshot, setSnapshot] = useState<{
    total_equity: number;
    cash: number;
    positions: PortfolioPosition[];
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.portfolio.snapshot().then(setSnapshot).catch(console.error).finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Portfolio</h2>
        <p className="text-surface-200 mt-1">Real-time position tracking and P&L</p>
      </div>

      {/* Equity summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard label="Total Equity" value={snapshot?.total_equity ?? 0} format="currency" />
        <SummaryCard label="Cash" value={snapshot?.cash ?? 0} format="currency" />
        <SummaryCard
          label="Market Value"
          value={
            snapshot?.positions.reduce((sum, p) => sum + (p.market_value ?? 0), 0) ?? 0
          }
          format="currency"
        />
      </div>

      {/* Positions table */}
      <div className="bg-surface-800 rounded-lg border border-surface-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-surface-700">
          <h3 className="text-sm font-semibold">Open Positions</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-700 text-surface-200 text-left">
                <th className="px-4 py-2 font-medium">Ticker</th>
                <th className="px-4 py-2 font-medium text-right">Qty</th>
                <th className="px-4 py-2 font-medium text-right">Avg Entry</th>
                <th className="px-4 py-2 font-medium text-right">Current</th>
                <th className="px-4 py-2 font-medium text-right">Mkt Value</th>
                <th className="px-4 py-2 font-medium text-right">P&L</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-surface-200">
                    Loading positions...
                  </td>
                </tr>
              ) : (snapshot?.positions ?? []).length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-surface-200">
                    No open positions
                  </td>
                </tr>
              ) : (
                snapshot?.positions.map((p) => (
                  <tr key={p.id} className="border-b border-surface-700/50 hover:bg-surface-700/50">
                    <td className="px-4 py-2 font-mono font-medium">{p.ticker}</td>
                    <td className="px-4 py-2 text-right">{p.quantity}</td>
                    <td className="px-4 py-2 text-right font-mono">${p.avg_entry_price.toFixed(2)}</td>
                    <td className="px-4 py-2 text-right font-mono">
                      ${p.current_price?.toFixed(2) ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-right font-mono">
                      ${p.market_value?.toFixed(2) ?? "—"}
                    </td>
                    <td
                      className={`px-4 py-2 text-right font-mono ${
                        (p.unrealized_pnl ?? 0) >= 0 ? "text-alpha-400" : "text-red-400"
                      }`}
                    >
                      {(p.unrealized_pnl ?? 0) >= 0 ? "+" : ""}
                      {p.unrealized_pnl?.toFixed(2) ?? "—"}
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

function SummaryCard({
  label,
  value,
  format,
}: {
  label: string;
  value: number;
  format: "currency" | "number";
}) {
  const display = format === "currency" ? `$${value.toLocaleString("en-US", { minimumFractionDigits: 2 })}` : value;
  return (
    <div className="rounded-lg border border-surface-700 bg-surface-800 p-4">
      <p className="text-xs text-surface-200 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1 font-mono">{display}</p>
    </div>
  );
}
