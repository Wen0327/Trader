import { useEffect, useRef } from "react";
import {
  ColorType, CrosshairMode, LineStyle, createChart,
} from "lightweight-charts";
import type { IChartApi, SeriesMarker, Time } from "lightweight-charts";
import type { TickerSeries } from "../api";

type Props = {
  data: TickerSeries;
  showBreakouts: boolean;
  height?: number;
};

/** K 線圖(TradingView lightweight-charts)+ 200MA / 55日高 / 20日低 疊加。 */
export function CandleChart({ data, showBreakouts, height = 360 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#7d8aa0",
      },
      grid: {
        vertLines: { color: "#2a344644" },
        horzLines: { color: "#2a344644" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#2a3446" },
      timeScale: { borderColor: "#2a3446" },
      autoSize: true,
    });
    chartRef.current = chart;

    const candles = chart.addCandlestickSeries({
      upColor: "#38c172",
      downColor: "#e3546c",
      borderUpColor: "#38c172",
      borderDownColor: "#e3546c",
      wickUpColor: "#38c17299",
      wickDownColor: "#e3546c99",
    });
    candles.setData(data.series.map((p) => ({
      time: p.date as Time,
      open: p.open, high: p.high, low: p.low, close: p.close,
    })));

    const overlay = (
      key: "ma200" | "hi55" | "lo20", color: string, dashed: boolean, title: string,
    ) => {
      const line = chart.addLineSeries({
        color,
        lineWidth: 1,
        lineStyle: dashed ? LineStyle.Dashed : LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        title,
      });
      line.setData(
        data.series
          .filter((p) => p[key] != null)
          .map((p) => ({ time: p.date as Time, value: p[key] as number })),
      );
    };
    overlay("ma200", "#f0b429", false, "200MA");
    overlay("hi55", "#38c172", true, "55日高");
    overlay("lo20", "#e3546c", true, "20日低");

    if (showBreakouts) {
      const markers: SeriesMarker<Time>[] = data.series
        .filter((p) => p.breakout)
        .map((p) => ({
          time: p.date as Time,
          position: "belowBar",
          color: "#38c172",
          shape: "arrowUp",
          size: 1,
        }));
      candles.setMarkers(markers);
    }

    // 預設只顯示最近 ~120 個交易日(全量 K 棒太細),往左拖可看完整歷史
    const n = data.series.length;
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - 120), to: n + 3 });
    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [data, showBreakouts, height]);

  return <div ref={containerRef} style={{ width: "100%", height }} />;
}
