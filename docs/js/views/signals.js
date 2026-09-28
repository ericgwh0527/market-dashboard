import { $, esc } from "../core/dom.js";
import { dir, pct } from "../core/format.js";
import { empty, infoBtn, signalIcon, SIGNAL_ORDER } from "../ui/components.js";
import { glossaryHTML } from "../ui/glossary.js";
import { View } from "./view.js";

export class SignalsView extends View {
  id = "signals";
  label = "Signals";
  icon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>`;

  template() {
    return `
      <h2>Screens ${infoBtn("screen")}</h2>
      <div id="screens"></div>
      <h2>All signals today</h2>
      <div class="card list" id="allSignals" style="padding:0"></div>
      <h2>Learn the terms</h2>
      <div class="card"><dl class="glossary">${glossaryHTML()}</dl></div>`;
  }

  render(data) {
    $("#screens", this.section).innerHTML = data.screens.map((sc) => this.#screen(sc, data)).join("");
    const items = data.stocks.flatMap((s) => (s.signals || []).map((g) => ({ s, g })))
      .sort((a, b) => SIGNAL_ORDER[a.g.type] - SIGNAL_ORDER[b.g.type]);
    $("#allSignals", this.section).innerHTML = items.map(({ s, g }) => `
      <div class="row" data-sym="${esc(s.symbol)}" tabindex="0">
        <div><div class="r-name">${esc(s.name)} <span class="faint">${esc(s.symbol)}</span></div><div class="r-sub" style="white-space:normal">${signalIcon(g.type)} ${esc(g.text)}</div></div>
        <div class="r-right num ${dir(s.chg_1d)}" style="font-weight:600;font-size:13px">${pct(s.chg_1d)}</div></div>`).join("") ||
      empty("No signals today.");
  }

  #screen(sc, data) {
    const chips = sc.symbols.map((sym) => data.get(sym)).filter(Boolean)
      .map((s) => `<button class="chip" data-sym="${esc(s.symbol)}">${esc(s.name)} <span class="num ${dir(s.chg_1d)}">${pct(s.chg_1d, 1)}</span></button>`).join("");
    return `<div class="card screen">
      <div class="s-head"><div class="s-name">${esc(sc.name)}</div><span class="pill">${sc.symbols.length}</span></div>
      <div class="s-why">${esc(sc.why)}</div>
      <div class="chips">${chips || '<span class="faint">None today</span>'}</div>
    </div>`;
  }
}
