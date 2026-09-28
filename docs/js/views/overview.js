import { $, esc } from "../core/dom.js";
import { arrow, dir, isNum, pct, priceStr } from "../core/format.js";
import { empty, infoBtn, newsItem, spark, stockRow } from "../ui/components.js";
import { renderSafeMarkdown } from "../ui/markdown.js";
import { View } from "./view.js";

export class OverviewView extends View {
  id = "overview";
  label = "Overview";
  icon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12l3-3 4 4 5-6 6 6"/><path d="M3 20h18"/></svg>`;

  template() {
    return `
      <div id="summaryWrap"></div>
      <h2>Markets</h2>
      <div class="grid tiles" id="indexTiles"><div class="card skeleton" style="height:110px"></div><div class="card skeleton" style="height:110px"></div></div>
      <div class="cols two">
        <div>
          <h2>Top movers today</h2>
          <div class="card list" id="movers" style="padding:0"></div>
          <h2>Themes / sectors ${infoBtn("theme")}</h2>
          <div class="card list" id="themes" style="padding:4px 0"></div>
        </div>
        <div>
          <h2>Headlines</h2>
          <div class="card list" id="headlines" style="padding:0"></div>
        </div>
      </div>`;
  }

  render(data) {
    const q = (s) => $(s, this.section);
    q("#summaryWrap").innerHTML = this.#summary(data.summary);
    q("#indexTiles").innerHTML = data.indices.map((i) => this.#tile(i)).join("");
    q("#movers").innerHTML = this.#movers(data.stocks);
    q("#themes").innerHTML = this.#themes(data.themes);
    q("#headlines").innerHTML = data.market_news.slice(0, 12).map(newsItem).join("") || empty("No headlines.");
  }

  #summary(sm) {
    if (!sm?.text) return "";
    const badges = `<span class="pill info">AI · ${esc(sm.model || "")}</span>${sm.stale ? '<span class="pill warn">from earlier run</span>' : ""}`;
    const body = renderSafeMarkdown(sm.text);   // AI text is untrusted – see ui/markdown.js
    return `<h2>Today's brief ${badges}</h2>
      <div class="card summary">${body}<div class="faint">Written by AI from the data on this page – may contain mistakes.</div></div>`;
  }

  #tile(i) {
    return `<div class="card tile" data-sym="${esc(i.symbol)}" tabindex="0">
      <div class="t-name">${esc(i.name)}${i.symbol === "^VIX" ? " " + infoBtn("vix") : ""}</div>
      <div class="t-price num">${priceStr(i)}</div>
      <div class="t-chg num ${dir(i.chg_1d)}">${arrow(i.chg_1d)}${pct(i.chg_1d)} <span class="faint" style="font-weight:500">1M ${pct(i.chg_1m, 1)}</span></div>
      ${spark(i.spark)}
    </div>`;
  }

  #movers(stocks, n = 4) {
    const sorted = stocks.filter((s) => isNum(s.chg_1d)).sort((a, b) => b.chg_1d - a.chg_1d);
    const head = (t) => `<div class="row" style="cursor:default;background:none"><div class="faint">${t}</div></div>`;
    return head("Gainers") + sorted.slice(0, n).map((s) => stockRow(s)).join("") +
           head("Losers") + sorted.slice(-n).reverse().map((s) => stockRow(s)).join("");
  }

  #themes(themes) {
    const max = Math.max(1, ...themes.map((t) => Math.abs(t.chg_1d || 0)));
    return themes.map((t) => {
      const v = t.chg_1d || 0, w = (Math.abs(v) / max) * 50;
      const bar = v >= 0 ? `left:50%;width:${w}%;background:var(--up-mark)` : `left:${50 - w}%;width:${w}%;background:var(--down-mark)`;
      return `<div class="theme-row" title="1-month: ${pct(t.chg_1m)} · ${esc(t.members.join(", "))}">
        <div style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><span class="pill">${esc(t.market)}</span> ${esc(t.name)}</div>
        <div class="bar-track"><div class="mid"></div><div class="bar" style="${bar}"></div></div>
        <div class="num ${dir(v)}" style="text-align:right;font-weight:600;font-size:13px">${pct(t.chg_1d)}</div></div>`;
    }).join("");
  }
}
