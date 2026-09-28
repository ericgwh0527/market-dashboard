import { $, $$, esc } from "../core/dom.js";
import { arrow, dir, fmt, isNum, pct, priceStr } from "../core/format.js";
import { empty, segmented, spark, trendPill } from "../ui/components.js";
import { View } from "./view.js";

const SORTS = [
  ["chg_1d", "today %"], ["chg_5d", "5-day %"], ["chg_1m", "1-month %"], ["chg_ytd", "YTD %"],
  ["rsi14", "RSI"], ["from_hi_52w", "vs 52w high"], ["name", "name"],
];

/** What the small "extra" column shows for each sort key. */
const EXTRA = {
  chg_1d: () => "", name: () => "",
  rsi14: (s) => `RSI ${fmt(s.rsi14, 0)}`,
  from_hi_52w: (s) => `${pct(s.from_hi_52w, 1)} vs high`,
};

export class WatchlistView extends View {
  id = "watchlist";
  label = "Watchlist";
  icon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>`;
  market = "all";

  template() {
    return `
      <div class="controls">
        ${segmented("mktSeg", [["all", "All"], ["MY", "Bursa"], ["US", "US"]], this.market)}
        <select id="sortSel" aria-label="Sort by">${SORTS.map(([v, l]) => `<option value="${v}">Sort: ${l}</option>`).join("")}</select>
        <input type="search" id="wlSearch" placeholder="Search…" style="flex:1;min-width:120px">
      </div>
      <div class="card list" id="watchlist" style="padding:0"></div>
      <p class="faint" style="margin-top:10px">Edit what's tracked in <code>config.json</code> in the repo.</p>`;
  }

  init(ctx) {
    super.init(ctx);
    const q = (s) => $(s, this.section);
    q("#mktSeg").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      this.market = b.dataset.v;
      $$("button", q("#mktSeg")).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      this.#draw();
    });
    q("#sortSel").addEventListener("change", () => this.#draw());
    q("#wlSearch").addEventListener("input", () => this.#draw());
  }

  render(data) { this.data = data; this.#draw(); }

  #draw() {
    if (!this.data) return;
    const key = $("#sortSel", this.section).value;
    const text = $("#wlSearch", this.section).value.trim().toLowerCase();
    const val = (s) => (isNum(s[key]) ? s[key] : -Infinity);
    const rows = this.data.stocks
      .filter((s) => (this.market === "all" || s.market === this.market) &&
        (!text || `${s.name} ${s.symbol} ${s.theme}`.toLowerCase().includes(text)))
      .sort((a, b) => (key === "name" ? a.name.localeCompare(b.name) : val(b) - val(a)));
    const extra = EXTRA[key] || ((s) => pct(s[key]));
    $("#watchlist", this.section).innerHTML = rows.map((s) => this.#row(s, extra(s))).join("") || empty("Nothing matches.");
  }

  #row(s, extra) {
    return `<div class="row wl" data-sym="${esc(s.symbol)}" tabindex="0">
      <div><div class="r-name">${esc(s.name)} ${s.stale ? '<span class="pill warn">stale</span>' : ""}</div>
        <div class="r-sub">${esc(s.symbol)} · ${trendPill(s.trend, true)} ${extra ? "· " + extra : ""}</div></div>
      ${spark(s.spark)}
      <div class="r-right num"><div class="r-price">${priceStr(s)}</div><div class="${dir(s.chg_1d)}" style="font-size:13px;font-weight:600">${arrow(s.chg_1d)}${pct(s.chg_1d)}</div></div>
    </div>`;
  }
}
