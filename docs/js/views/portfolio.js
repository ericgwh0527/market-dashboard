import { $, esc } from "../core/dom.js";
import { dir, fmt, money, pct, signedMoney } from "../core/format.js";
import { cryptoAvailable, decrypt, deriveKey } from "../data/crypto.js";
import { chartsReady, valueChart } from "../ui/charts.js";
import { infoBtn, lockIcon } from "../ui/components.js";
import { View } from "./view.js";

const MARKET_LABEL = { MY: "Bursa", US: "US" };
const prefixFor = (cur) => (cur === "USD" ? "$" : "RM ");

/** Encrypted portfolio: locked -> unlock form -> decrypted view. */
export class PortfolioView extends View {
  id = "portfolio";
  label = "Portfolio";
  icon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`;
  portfolio = null;
  #chart = null;

  template() { return `<div id="portfolio"></div>`; }

  get #root() { return $("#portfolio", this.section); }

  render(data) {
    this.market = data;
    if (this.portfolio) this.#draw();   // refresh links to watchlist rows
  }

  async onShow() {
    if (this.portfolio) return;
    const { api, keyStore } = this.ctx;
    const blob = await api.portfolioBlob();
    if (!blob) return this.#message("Portfolio not set up yet",
      "Holdings are read from a private repo and published here only in encrypted form. See the README's “Portfolio setup” section.");
    if (!cryptoAvailable()) return this.#message("Can't unlock here", "Open this page over https to unlock.");

    const saved = await keyStore.get();
    if (saved && saved.salt === blob.salt) {
      try { this.portfolio = await decrypt(saved.key, blob); return this.#draw(); } catch { await keyStore.clear(); }
    }
    this.#lockForm(blob);
  }

  onThemeChange() { if (this.portfolio) this.#draw(); }

  #message(title, text) {
    this.#root.innerHTML = `<div class="card lock"><div class="lock-ico">${lockIcon}</div><b>${esc(title)}</b>
      <p class="muted" style="font-size:14px">${esc(text)}</p></div>`;
  }

  #lockForm(blob) {
    this.#root.innerHTML = `<div class="card lock">
      <div class="lock-ico">${lockIcon}</div><b>Portfolio is locked</b>
      <p class="muted" style="font-size:14px;margin:6px 0 0">It's encrypted (AES-256). Enter your passphrase – it never leaves this device.</p>
      <form id="unlockForm" autocomplete="off">
        <input type="password" id="pw" placeholder="Passphrase" aria-label="Passphrase" autocomplete="current-password" required>
        <label class="chk"><input type="checkbox" id="remember" checked> Keep unlocked on this device</label>
        <button class="btn" type="submit" id="unlockBtn">Unlock</button>
        <div class="err" id="pwErr" role="alert"></div>
      </form></div>`;
    const q = (s) => $(s, this.#root);
    q("#unlockForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      q("#unlockBtn").textContent = "Unlocking…";
      q("#pwErr").textContent = "";
      try {
        const key = await deriveKey(q("#pw").value, blob);
        this.portfolio = await decrypt(key, blob);
        if (q("#remember").checked) await this.ctx.keyStore.set({ salt: blob.salt, key });
        this.#draw();
      } catch {
        q("#pwErr").textContent = "Wrong passphrase.";
        q("#unlockBtn").textContent = "Unlock";
      }
    });
  }

  async #lock() {
    await this.ctx.keyStore.clear();
    this.portfolio = null;
    this.#chart?.remove(); this.#chart = null;
    this.onShow();
  }

  #draw() {
    const p = this.portfolio, t = p.totals, bc = prefixFor(p.base_currency);
    const hasHistory = (p.history || []).length >= 2;
    const maxPct = Math.max(1, ...p.allocation.map((a) => a.pct || 0));
    this.#root.innerHTML = `
      <div class="card">
        <div class="hero">
          <div><div class="h-k">Total value</div><div class="h-v num">${money(t.value, bc)}</div></div>
          <div><div class="h-k">Today</div><div class="h-v sm num ${dir(t.day_pl)}">${signedMoney(t.day_pl, bc)} <span style="font-size:14px">${pct(t.day_pl_pct)}</span></div></div>
          <div><div class="h-k">Unrealised P/L ${infoBtn("pl")}</div><div class="h-v sm num ${dir(t.pl)}">${signedMoney(t.pl, bc)} <span style="font-size:14px">${pct(t.pl_pct)}</span></div></div>
          <div><div class="h-k">Cash</div><div class="h-v sm num">${money(t.cash, bc)}</div></div>
        </div>
        <div class="faint" style="margin-top:8px">Valued ${esc(p.generated_at_myt)} · USD/MYR ${fmt(p.usdmyr, 4)}${p.holdings_updated ? " · holdings as of " + esc(p.holdings_updated) : ""}</div>
      </div>
      ${hasHistory ? `<h2>Value over time</h2><div class="card" style="padding:8px"><div class="chart-box" id="pfChart" style="height:220px"></div></div>` : ""}
      <h2>Allocation</h2>
      <div class="card">${p.allocation.map((a) => `<div class="alloc-row"><div>${esc(MARKET_LABEL[a.name] || a.name)}</div>
        <div><div class="alloc-bar" style="width:${((a.pct || 0) / maxPct) * 100}%"></div></div><div class="num" style="text-align:right">${fmt(a.pct, 1)}%</div></div>`).join("")}</div>
      <h2>Positions</h2>
      <div class="card" style="padding:4px 16px"><div class="tbl-wrap"><table class="tbl num">
        <thead><tr><th>Stock</th><th>Value</th><th>P/L</th><th>P/L %</th><th>Today</th><th>Weight</th><th>Shares</th><th>Avg cost</th><th>Price</th></tr></thead>
        <tbody>${p.positions.map((r) => this.#positionRow(r, bc)).join("")}</tbody></table></div></div>
      ${p.cash.length ? `<p class="faint">Cash: ${p.cash.map((c) => `${esc(c.currency)} ${fmt(c.amount)}`).join(" · ")}</p>` : ""}
      <div style="text-align:center;margin-top:16px"><button class="btn ghost" id="lockBtn">Lock on this device</button></div>`;
    $("#lockBtn", this.#root).addEventListener("click", () => this.#lock());

    this.#chart?.remove(); this.#chart = null;
    if (hasHistory && chartsReady()) this.#chart = valueChart($("#pfChart", this.#root), p.history, bc);
  }

  #positionRow(r, bc) {
    const link = this.market?.get(r.symbol) ? `data-sym="${esc(r.symbol)}"` : "";
    const cp = prefixFor(r.currency);
    return `<tr ${link}>
      <td><b>${esc(r.name)}</b><div class="faint">${esc(r.symbol)}${r.stale_price ? " · old price" : ""}</div></td>
      <td>${money(r.value_base, bc)}</td><td class="${dir(r.pl_base)}">${signedMoney(r.pl_base, bc)}</td><td class="${dir(r.pl_pct)}">${pct(r.pl_pct)}</td>
      <td class="${dir(r.day_chg_pct)}">${pct(r.day_chg_pct)}</td><td>${fmt(r.weight, 1)}%</td><td>${fmt(r.shares, r.shares % 1 ? 3 : 0)}</td>
      <td>${cp}${fmt(r.avg_cost)}</td><td>${cp}${fmt(r.price)}</td></tr>`;
  }
}
