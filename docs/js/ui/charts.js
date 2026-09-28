/** Chart factory on top of lightweight-charts. Reads colours from theme tokens. */
import { cssVar } from "../core/dom.js";
import { fmt } from "../core/format.js";

const LC = () => window.LightweightCharts;
export const chartsReady = () => !!LC();

function baseOptions(overrides = {}) {
  return {
    autoSize: true,
    layout: { background: { type: "solid", color: "transparent" }, textColor: cssVar("--text-2"), fontFamily: "Inter, system-ui, sans-serif", fontSize: 11 },
    grid: { vertLines: { visible: false }, horzLines: { color: cssVar("--grid") } },
    rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.2, bottom: 0.05 } },
    timeScale: { borderColor: cssVar("--border"), fixLeftEdge: true, fixRightEdge: true },
    crosshair: { mode: 0 },
    handleScroll: false, handleScale: false,
    localization: { locale: "en-US", priceFormatter: (p) => fmt(p) },
    ...overrides,
  };
}

const points = (series, idx, key) =>
  idx.filter((i) => series[key][i] != null).map((i) => ({ time: series.d[i], value: series[key][i] }));

/** lightweight-charts gives business-day objects; normalise to "YYYY-MM-DD". */
export const timeKey = (t) =>
  typeof t === "string" ? t : t?.year ? `${t.year}-${String(t.month).padStart(2, "0")}-${String(t.day).padStart(2, "0")}` : null;

export const RANGES = { "1M": 22, "3M": 66, "6M": 130, "1Y": Infinity };

/** Price chart (line or candles) with 50/200-day averages. Returns the chart. */
export function priceChart(el, series, { range = "6M", type = "line" } = {}) {
  const chart = LC().createChart(el, baseOptions());
  const idx = [...series.d.keys()].slice(Math.max(0, series.d.length - RANGES[range]));
  const up = cssVar("--up-mark"), down = cssVar("--down-mark");
  if (type === "candle") {
    chart.addCandlestickSeries({ upColor: up, downColor: down, wickUpColor: up, wickDownColor: down, borderVisible: false, priceLineVisible: false })
      .setData(idx.map((i) => ({ time: series.d[i], open: series.o[i], high: series.h[i], low: series.l[i], close: series.c[i] })));
  } else {
    chart.addLineSeries({ color: cssVar("--series-1"), lineWidth: 2, priceLineVisible: false, crosshairMarkerRadius: 4 })
      .setData(points(series, idx, "c"));
  }
  for (const [key, token] of [["sma50", "--series-2"], ["sma200", "--series-3"]]) {
    chart.addLineSeries({ color: cssVar(token), lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      .setData(points(series, idx, key));
  }
  chart.timeScale().fitContent();
  return chart;
}

/** RSI panel with 70/30 guide lines. */
export function rsiChart(el, series, { range = "6M" } = {}) {
  const base = baseOptions();
  const chart = LC().createChart(el, {
    ...base,
    localization: { locale: "en-US", priceFormatter: (p) => fmt(p, 0) },
    timeScale: { ...base.timeScale, visible: false },
    rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.1, bottom: 0.1 } },
  });
  const idx = [...series.d.keys()].slice(Math.max(0, series.d.length - RANGES[range]));
  const line = chart.addLineSeries({ color: cssVar("--series-1"), lineWidth: 2, priceLineVisible: false });
  line.setData(points(series, idx, "rsi"));
  for (const v of [70, 30]) {
    line.createPriceLine({ price: v, color: cssVar("--text-3"), lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: v === 70 ? "overbought" : "oversold" });
  }
  line.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
  chart.timeScale().fitContent();
  return chart;
}

/** Portfolio value (area) vs money put in (dashed). */
export function valueChart(el, history, prefix) {
  const chart = LC().createChart(el, baseOptions({
    rightPriceScale: { borderVisible: false },
    localization: { locale: "en-US", priceFormatter: (v) => prefix + fmt(v, 0) },
  }));
  chart.addAreaSeries({ lineColor: cssVar("--series-1"), topColor: "rgba(42,120,214,.18)", bottomColor: "rgba(42,120,214,0)", lineWidth: 2, priceLineVisible: false })
    .setData(history.map((h) => ({ time: h.date, value: h.value })));
  chart.addLineSeries({ color: cssVar("--text-3"), lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: "cost" })
    .setData(history.map((h) => ({ time: h.date, value: (h.cost || 0) + (h.cash || 0) })));
  chart.timeScale().fitContent();
  return chart;
}
