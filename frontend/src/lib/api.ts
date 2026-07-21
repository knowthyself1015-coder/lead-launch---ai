const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api/v1";

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | undefined>;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, ...fetchOptions } = options;

  let url = `${API_BASE}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, String(value));
      }
    });
    const qs = searchParams.toString();
    if (qs) url += `?${qs}`;
  }

  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...fetchOptions.headers,
    },
    ...fetchOptions,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

// -----------------------------------------------------------
// Typed API helpers
// -----------------------------------------------------------

export interface Signal {
  id: number;
  ticker: string;
  direction: string;
  confidence: number;
  composite_score: number;
  status: string;
  created_at: string;
}

export interface PortfolioPosition {
  id: number;
  ticker: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number | null;
  market_value: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  is_open: boolean;
}

export interface Trade {
  id: number;
  ticker: string;
  side: string;
  quantity: number;
  price: number;
  notional: number;
  filled_at: string;
}

export interface DailyReport {
  id: number;
  report_date: string;
  net_pnl: number;
  net_pnl_pct: number;
  win_rate: number | null;
  total_trades: number;
  sharpe_ratio: number | null;
}

export interface Health {
  status: string;
  version: string;
  environment: string;
}

export interface PipelineStatus {
  pipeline: {
    running: boolean;
  };
  last_run: {
    run_id: string;
    started_at: string | null;
    completed_at: string | null;
    status: string | null;
    symbols_scanned: number;
    signals_generated: number;
    trades_executed: number;
    error_count: number;
  } | null;
  market: {
    is_open: boolean;
    reason: string;
    current_time_et: string;
  };
}

export interface PipelineRunResult {
  status: string;
  run_id: string;
  started_at: string;
  completed_at: string | null;
  symbols_scanned: number;
  signals_generated: number;
  trades_executed: number;
  errors: string[];
}

// -----------------------------------------------------------
// API functions
// -----------------------------------------------------------

export const api = {
  health: () => request<Health>("/health"),

  signals: {
    list: (status?: string) => request<Signal[]>("/signals", { params: { status } }),
    get: (id: number) => request<Signal>(`/signals/${id}`),
  },

  stocks: {
    list: () => request<Array<{ id: number; ticker: string; name: string }>>("/stocks"),
    get: (ticker: string) => request<{ id: number; ticker: string; name: string }>(`/stocks/${ticker}`),
  },

  watchlist: {
    list: () => request<Array<{ id: number; ticker: string }>>("/watchlist"),
    add: (ticker: string, reason?: string) =>
      request("/watchlist", {
        method: "POST",
        body: JSON.stringify({ ticker, added_reason: reason }),
      }),
  },

  portfolio: {
    snapshot: () => request<{ total_equity: number; cash: number; positions: PortfolioPosition[] }>("/portfolio"),
    positions: () => request<PortfolioPosition[]>("/portfolio/positions"),
  },

  trades: {
    list: () => request<Trade[]>("/trades"),
  },

  reports: {
    list: (limit?: number) => request<DailyReport[]>("/reports", { params: { limit } }),
    latest: () => request<DailyReport>("/reports/latest"),
  },

  pipeline: {
    status: () => request<PipelineStatus>("/pipeline/status"),
    start: (intervalSeconds?: number) =>
      request<{ status: string; message: string }>("/pipeline/start", {
        method: "POST",
        params: intervalSeconds ? { interval_seconds: intervalSeconds } : undefined,
      }),
    stop: () =>
      request<{ status: string; message: string }>("/pipeline/stop", {
        method: "POST",
      }),
    runOnce: () =>
      request<PipelineRunResult>("/pipeline/run-once", {
        method: "POST",
      }),
    history: (limit?: number) =>
      request<{
        total: number;
        runs: Array<{
          run_id: string;
          started_at: string;
          completed_at: string | null;
          status: string;
          symbols_scanned: number;
          signals_generated: number;
          trades_executed: number;
          error_count: number;
          errors: string[];
        }>;
      }>("/pipeline/history", { params: { limit } }),
    marketStatus: () => request<{ is_open: boolean; reason: string; current_time_et: string }>("/pipeline/market-status"),
  },
};
