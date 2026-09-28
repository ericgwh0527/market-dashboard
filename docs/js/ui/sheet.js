/** Bottom sheet with the full detail for one instrument. */
import { $, $$, esc } from "../core/dom.js";
import { arrow, big, dir, fmt, isNum, pct, priceStr } from "../core/format.js";
import { prefs } from "../core/prefs.js";
import { chartsReady, priceChart, rsiChart, timeKey } from "./charts.js";
import { infoBtn, newsItem, segmented, signalIcon, stat, trendPill } from "./components.js";

const closeIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>`;

export class StockSheet {
  #charts = [];
  #row = null;
  #series = null;

  /** @param {{sheet: Element, backdrop: Element, dataService: import("../data/api.js").DataService, onClose: Function}} deps */
  constructor({ sheet, backdrop, dataService, onClose }) {
    Object.assign(this, { el: sheet, backdrop, api: dataService, onClose });
    this.range = prefs.get("range", "6M");
    this.type = prefs.get("ctype", "line");
    this.el.addEventListener("click", (e) => this.#onClick(e));
    this.backdrop.addEventListener("click", () => this.onClose());
  }

  get isOpen() { return this.el.classList.contains("open"); }
  get symbol() { return this.#row?.symbol ?? null; }

  async open(row) {
    this.#row = row;
    this.#series = null;
    this.el.innerHTML = this.#template(row);
    this.backdrop.classList.add("open");
    this.el.classList.add("open");
    document.body.style.overflow = "hidden";
    this.el.scrollTop = 0;
    $("#closeSheet", this.el).focus({ preventScroll: true });
    try {
      const series = await this.api.series(row);
      if (this.#row === row) { this.#series = series; this.redraw(); }
    } catch {
      $("#priceChart", this.el).innerHTML = `<div class="empty">Chart data unavailable.</div>`;
    }
  }

  close() {
    this.el.classList.remove("open");
    this.backdrop.classList.remove("open");
    document.body.style.overflow = "";
    this.#destroyCharts();
    this.#row = null;
  }

  /** Re-render charts (range/type change, theme change). */
  redraw() {
    if (!this.#series) return;
    if (!chartsReady()) { setTimeout(() => this.redraw(), 200); return; }
    this.#destroyCharts();
    const sr = this.#series, opts = { range: this.range, type: this.type };
    const pc = priceChart($("#priceChart", this.el), sr, opts);
    const rc = rsiChart($("#rsiChart", this.el), sr, opts);
    this.#charts.push(pc, rc);

    const last = sr.d.length - 1, byDate = new Map(sr.d.map((d, i) => [d, i]));
    const at = (p) => (p?.time ? byDate.get(timeKey(p.time)) : last);
    const legend = $("#priceLegend", this.el), rsiLegend = $("#rsiLegend", this.el);
    const setLegends = (i) => {
      if (i == null) return;
      const chg = i > 0 ? (sr.c[i] / sr.c[i - 1] - 1) * 100 : null;
      legend.innerHTML = `<span><b>${esc(sr.d[i])}</b></span>
        <span><span class="swatch" style="background:var(--series-1)"></span>Close <b>${fmt(sr.c[i])}</b> <span class="${dir(chg)}">${pct(chg)}</span></span>
        <span><span class="swatch" style="background:var(--series-2)"></span>50d <b>${fmt(sr.sma50[i])}</b></span>
        <span><span class="swatch" style="background:var(--series-3)"></span>200d <b>${fmt(sr.sma200[i])}</b></span>`;
      rsiLegend.innerHTML = `RSI (14) <b>${fmt(sr.rsi[i], 1)}</b>`;
    };
    setLegends(last);
    pc.subscribeCrosshairMove((p) => setLegends(at(p)));
    rc.subscribeCrosshairMove((p) => setLegends(at(p)));
  }

  #destroyCharts() { this.#charts.forEach((c) => c.remove()); this.#charts = []; }

  #onClick(e) {
    if (e.target.closest("#closeSheet")) return this.onClose();
    const seg = e.target.closest(".seg button");
    if (!seg) return;
    const group = seg.parentElement.id;
    if (group === "rangeSeg") { this.range = seg.dataset.v; prefs.set("range", this.range); }
    if (group === "typeSeg") { this.type = seg.dataset.v; prefs.set("ctype", this.type); }
    $$("button", seg.parentElement).forEach((b) => b.setAttribute("aria-pressed", String(b === seg)));
    this.redraw();
  }

  #template(s) {
    const f = s.fundamentals || {};
    const isStock = !!s.market;
    const perf = [["1 week", "chg_5d"], ["1 month", "chg_1m"], ["3 months", "chg_3m"], ["6 months", "chg_6m"], ["1 year", "chg_1y"], ["YTD", "chg_ytd", "ytd"]];
    const vsAvg = (avg) => (avg ? pct((s.price / avg - 1) * 100) : "–");
    const pctOrDash = (n, d) => (isNum(n) ? fmt(n, d) + "%" : "–");
    const target = isNum(f.target_price) ? fmt(f.target_price) + (s.price ? ` <span class="faint">${pct((f.target_price / s.price - 1) * 100, 0)}</span>` : "") : "–";
    const analysts = f.analyst_view ? esc(String(f.analyst_view).replace("_", " ")) + (f.analyst_count ? ` (${esc(f.analyst_count)})` : "") : "–";

    return `
      <div class="sheet-head">
        <div style="flex:1;min-width:0">
          <div id="sheetTitle" style="font-weight:700;font-size:18px">${esc(s.name)}</div>
          <div class="faint">${[s.symbol, f.sector, s.theme].filter(Boolean).map(esc).join(" · ")}</div>
        </div>
        <button class="icon-btn" id="closeSheet" aria-label="Close">${closeIcon}</button>
      </div>
      <div class="sheet-body">
        <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
          <div class="big-price num">${priceStr(s)}</div>
          <div class="num ${dir(s.chg_1d)}" style="font-weight:650">${arrow(s.chg_1d)}${pct(s.chg_1d)} today</div>
          ${trendPill(s.trend)}${infoBtn("trend")}
        </div>
        <div class="faint">Close of ${esc(s.date)}</div>
        <div class="controls" style="margin-top:12px">
          ${segmented("rangeSeg", ["1M", "3M", "6M", "1Y"].map((r) => [r, r]), this.range)}
          ${segmented("typeSeg", [["line", "Line"], ["candle", "Candles"]], this.type)}
        </div>
        <div class="card" style="padding:8px"><div class="chart-box" id="priceChart"><div class="chart-legend" id="priceLegend"></div></div></div>
        <div class="card" style="padding:8px;margin-top:8px"><div class="chart-box small" id="rsiChart"><div class="chart-legend" id="rsiLegend"></div></div></div>

        ${(s.signals || []).length ? `<h2>Signals</h2><div class="signal-list">${s.signals.map((g) =>
          `<div class="signal ${esc(g.type)}"><span class="ico">${signalIcon(g.type)}</span><span>${esc(g.text)}</span></div>`).join("")}</div>` : ""}

        <h2>Performance</h2>
        <div class="card stats">${perf.map(([label, k, term]) => stat(label, pct(s[k]), dir(s[k]), term)).join("")}</div>

        <h2>Technicals</h2>
        <div class="card stats">
          ${stat("RSI (14)", fmt(s.rsi14, 1), "", "rsi")}${stat("vs 50-day avg", vsAvg(s.sma50), "", "sma")}${stat("vs 200-day avg", vsAvg(s.sma200), "", "sma")}
          ${stat("52w high", fmt(s.hi_52w), "", "hi52")}${stat("52w low", fmt(s.lo_52w), "", "hi52")}${stat("From 52w high", pct(s.from_hi_52w, 1), "", "hi52")}
          ${stat("Volume vs avg", isNum(s.vol_ratio) ? fmt(s.vol_ratio, 2) + "×" : "–", "", "vol")}${stat("MACD hist.", fmt(s.macd_hist, 3), dir(s.macd_hist), "macd")}${stat("Volatility", isNum(s.volatility_60d) ? fmt(s.volatility_60d, 0) + "%" : "–", "", "volat")}
        </div>

        ${isStock ? `<h2>Valuation &amp; business</h2>
        <div class="card stats">
          ${stat("Market cap", big(f.market_cap), "", "mcap")}${stat("P/E", fmt(f.pe, 1), "", "pe")}${stat("Forward P/E", fmt(f.forward_pe, 1), "", "fpe")}
          ${stat("Dividend yield", pctOrDash(f.div_yield, 2), "", "div")}${stat("Profit margin", pctOrDash(f.profit_margin, 1))}${stat("Revenue growth", pct(f.revenue_growth, 1), dir(f.revenue_growth))}
          ${stat("Beta", fmt(f.beta, 2), "", "beta")}${stat("Analysts", analysts, "", "analyst")}${stat("Avg target", target, "", "analyst")}
          ${f.next_earnings ? stat("Next earnings", esc(f.next_earnings)) : ""}
        </div>` : ""}

        ${(s.news || []).length ? `<h2>News</h2><div class="card list" style="padding:0">${s.news.map(newsItem).join("")}</div>` : ""}
      </div>`;
  }
}
