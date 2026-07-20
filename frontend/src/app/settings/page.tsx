"use client";

import { useEffect, useState } from "react";
import { api, Health } from "@/lib/api";

export default function SettingsPage() {
  const [backendStatus, setBackendStatus] = useState<string>("Checking...");
  const [dbStatus, setDbStatus] = useState<string>("Checking...");

  useEffect(() => {
    api
      .health()
      .then((h: Health) => {
        setBackendStatus(`${h.status} (${h.version}, ${h.environment})`);
        setDbStatus("Connected (checking via health endpoint)");
      })
      .catch(() => {
        setBackendStatus("Unreachable");
        setDbStatus("Unknown");
      });
  }, []);

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
        <p className="text-surface-200 mt-1">System configuration and connection status</p>
      </div>

      {/* System status */}
      <div className="bg-surface-800 rounded-lg border border-surface-700 p-6 space-y-4">
        <h3 className="text-sm font-semibold">System Status</h3>

        <div className="space-y-3">
          <StatusRow label="Backend API" status={backendStatus} />
          <StatusRow label="Database" status={dbStatus} />
          <StatusRow label="Redis" status="Checking..." />
          <StatusRow label="Polygon.io" status="Not configured" />
          <StatusRow label="Alpaca" status="Not configured" />
          <StatusRow label="OpenAI" status="Not configured" />
        </div>
      </div>

      {/* Risk parameters */}
      <div className="bg-surface-800 rounded-lg border border-surface-700 p-6 space-y-4">
        <h3 className="text-sm font-semibold">Risk Parameters</h3>
        <div className="grid grid-cols-2 gap-4">
          <ConfigField label="Max Position Size" value="5% of portfolio" />
          <ConfigField label="Max Portfolio Risk/day" value="2%" />
          <ConfigField label="Default Stop Loss" value="2%" />
          <ConfigField label="Signal Threshold" value="0.70 (70%)" />
        </div>
      </div>

      {/* About */}
      <div className="bg-surface-800 rounded-lg border border-surface-700 p-6 space-y-2">
        <h3 className="text-sm font-semibold">About AlphaSight</h3>
        <p className="text-sm text-surface-200">
          Autonomous AI trading agent v0.1.0. Built with FastAPI, Next.js, PostgreSQL, Redis,
          and powered by XGBoost + LLM scoring models.
        </p>
        <p className="text-xs text-surface-200">
          Data: Polygon.io · Execution: Alpaca (paper) · AI: OpenAI
        </p>
      </div>
    </div>
  );
}

function StatusRow({ label, status }: { label: string; status: string }) {
  const isOk = status.toLowerCase().includes("healthy") || status.toLowerCase().includes("connected");
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-surface-200">{label}</span>
      <span className="flex items-center gap-2 text-sm">
        <span
          className={`w-2 h-2 rounded-full ${
            isOk ? "bg-alpha-500" : status === "Checking..." ? "bg-amber-500 animate-pulse" : "bg-red-500"
          }`}
        />
        <span className="text-surface-100">{status}</span>
      </span>
    </div>
  );
}

function ConfigField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-surface-200">{label}</p>
      <p className="text-sm font-mono mt-0.5">{value}</p>
    </div>
  );
}
