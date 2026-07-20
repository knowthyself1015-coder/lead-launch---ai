"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi } from "lightweight-charts";

interface TradingViewChartProps {
  ticker?: string;
  data?: Array<{ time: string; open: number; high: number; low: number; close: number }>;
  height?: number;
}

export default function TradingViewChart({ ticker, data, height = 400 }: TradingViewChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#0f172a" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      crosshair: {
        mode: 0,
      },
      timeScale: {
        borderColor: "#334155",
      },
      rightPriceScale: {
        borderColor: "#334155",
      },
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      wickUpColor: "#22c55e",
    });

    if (data && data.length > 0) {
      candlestickSeries.setData(data);
    }

    chart.timeScale().fitContent();
    chartRef.current = chart;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, height]);

  return (
    <div className="w-full rounded-lg overflow-hidden border border-surface-700">
      <div className="px-4 py-2 bg-surface-800 border-b border-surface-700 flex items-center gap-2">
        <span className="text-sm font-medium text-surface-50">
          {ticker || "Select a ticker"}
        </span>
        <span className="text-xs text-surface-200">1D</span>
      </div>
      <div ref={containerRef} className="w-full" />
    </div>
  );
}
