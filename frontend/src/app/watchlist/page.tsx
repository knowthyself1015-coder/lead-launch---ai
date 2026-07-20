"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface WatchlistItem {
  id: number;
  ticker: string;
  added_reason?: string;
  target_buy_price?: number;
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [newTicker, setNewTicker] = useState("");
  const [reason, setReason] = useState("");

  useEffect(() => {
    api.watchlist.list().then(setItems).catch(console.error).finally(() => setLoading(false));
  }, []);

  async function addItem() {
    if (!newTicker.trim()) return;
    try {
      const item = await api.watchlist.add(newTicker.toUpperCase(), reason || undefined);
      setItems((prev) => [...prev, item as WatchlistItem]);
      setNewTicker("");
      setReason("");
    } catch (err) {
      console.error("Failed to add to watchlist:", err);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Watchlist</h2>
        <p className="text-surface-200 mt-1">Stocks you&apos;re watching for potential trades</p>
      </div>

      {/* Add form */}
      <div className="bg-surface-800 rounded-lg border border-surface-700 p-4">
        <div className="flex gap-3">
          <input
            type="text"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            placeholder="Ticker (e.g. AAPL)"
            className="flex-1 bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-50 placeholder-surface-200 focus:outline-none focus:border-alpha-500"
            onKeyDown={(e) => e.key === "Enter" && addItem()}
          />
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason (optional)"
            className="flex-1 bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-50 placeholder-surface-200 focus:outline-none focus:border-alpha-500"
          />
          <button
            onClick={addItem}
            className="px-4 py-2 bg-alpha-600 hover:bg-alpha-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            Add
          </button>
        </div>
      </div>

      {/* Watchlist table */}
      <div className="bg-surface-800 rounded-lg border border-surface-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-surface-700">
          <h3 className="text-sm font-semibold">Watched Stocks</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-700 text-surface-200 text-left">
                <th className="px-4 py-2 font-medium">Ticker</th>
                <th className="px-4 py-2 font-medium">Reason</th>
                <th className="px-4 py-2 font-medium text-right">Target Buy</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-surface-200">
                    Loading watchlist...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-surface-200">
                    No items in watchlist. Add a ticker above.
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id} className="border-b border-surface-700/50 hover:bg-surface-700/50">
                    <td className="px-4 py-3 font-mono font-medium">{item.ticker}</td>
                    <td className="px-4 py-3 text-surface-200">{item.added_reason || "—"}</td>
                    <td className="px-4 py-3 text-right font-mono">
                      {item.target_buy_price ? `$${item.target_buy_price.toFixed(2)}` : "—"}
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
