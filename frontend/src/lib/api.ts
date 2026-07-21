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

  tradersMind: {
    regime: () =>
      request<{
        regime: string;
        vix_level: number;
        trend_strength: number;
        description: string;
        implications: string[];
        config: {
          score_threshold: number;
          risk_per_trade_pct: number;
          min_confluence: number;
          max_positions: number;
        };
      }>("/traders-mind/regime"),

    confluence: (symbol: string) =>
      request<{
        symbol: string;
        regime: string;
        confluence_count: number;
        required: number;
        passed: boolean;
        active_signals: string[];
        missing_signals: string[];
      }>(`/traders-mind/confluence/${symbol}`),

    sitOut: () =>
      request<{
        sit_out: boolean;
        reason: string;
        suggested_action: string;
        regime: string;
        daily_pnl_pct: number;
        consecutive_losses: number;
      }>("/traders-mind/sit-out"),

    journal: (limit?: number) =>
      request<{
        total: number;
        trades: Array<{
          trade_id: string;
          ticker: string;
          entry_date: string;
          exit_date: string | null;
          direction: string;
          entry_price: number;
          exit_price: number | null;
          quantity: number;
          pnl: number | null;
          pnl_pct: number | null;
          regime: string | null;
          confluence_count: number;
          entry_reasoning: string;
          exit_reason: string;
        }>;
      }>("/traders-mind/journal", { params: { limit } }),

    journalStats: () =>
      request<{
        total_trades: number;
        winning_trades: number;
        losing_trades: number;
        win_rate: number;
        avg_hold_hours: number;
        win_rate_by_regime: Record<string, number>;
        win_rate_by_confluence: Record<string, number>;
        win_rate_by_dow: Record<string, number>;
        best_performer: string | null;
        worst_performer: string | null;
      }>("/traders-mind/journal/stats"),

    journalLessons: () =>
      request<{
        lessons: string[];
        count: number;
      }>("/traders-mind/journal/lessons"),
  },
};
