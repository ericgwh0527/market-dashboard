/** Small HTML building blocks shared by views. All text goes through esc(). */
import { esc } from "../core/dom.js";
import { ago, arrow, dir, pct, priceStr } from "../core/format.js";

export function spark(values) {
  if (!values || values.length < 2) return "";
  const w = 100, h = 30, min = Math.min(...values), max = Math.max(...values), r = max - min || 1;
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * w).toFixed(2)},${(h - 2 - ((v - min) / r) * (h - 4)).toFixed(2)}`).join(" ");
  const trend = dir(values.at(-1) - values[0]);
  const color = trend === "up" ? "var(--up-mark)" : trend === "down" ? "var(--down-mark)" : "var(--text-3)";
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

export const infoBtn = (term) =>
  `<button class="info" data-term="${esc(term)}" aria-label="What is this?"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01" stroke-linecap="round"/></svg></button>`;

export const changeText = (n, d = 2) => `<span class="num ${dir(n)}">${arrow(n)}${pct(n, d)}</span>`;

export const trendPill = (trend, compact = false) =>
  `<span class="pill ${trend === "Uptrend" ? "good" : trend === "Downtrend" ? "bad" : ""}"${compact ? ' style="font-size:10.5px;padding:0 6px"' : ""}>${esc(trend)}</span>`;

const SIGNAL_ICONS = {
  good: '<span class="up">▲</span>', bad: '<span class="down">▼</span>',
  warn: '<span style="color:var(--warn)">!</span>', info: '<span style="color:var(--accent)">●</span>',
};
export const signalIcon = (type) => SIGNAL_ICONS[type] || "";
export const SIGNAL_ORDER = { good: 0, bad: 1, warn: 2, info: 3 };

export function stockRow(s, key = "chg_1d") {
  return `<div class="row" data-sym="${esc(s.symbol)}" tabindex="0">
    <div><div class="r-name">${esc(s.name)}</div><div class="r-sub">${esc(s.symbol)} · ${esc(s.theme || s.group || "")}</div></div>
    <div class="r-right num"><div class="r-price">${priceStr(s)}</div><div class="${dir(s[key])}" style="font-size:13px;font-weight:600">${arrow(s[key])}${pct(s[key])}</div></div>
  </div>`;
}

/** Only http(s) links from feeds – blocks javascript:, data: and other schemes. */
export function safeUrl(url) {
  try {
    const u = new URL(String(url), location.href);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : "#";
  } catch { return "#"; }
}

export function newsItem(n) {
  const meta = [n.source, n.topic, n.symbol].filter(Boolean).map(esc).join(" · ");
  return `<a class="news-item" href="${esc(safeUrl(n.url))}" target="_blank" rel="noopener noreferrer">
    <div class="n-title">${esc(n.title)}</div>
    <div class="n-meta">${meta} · ${ago(n.published)}</div></a>`;
}

/** `valueHtml` must already be safe HTML. */
export const stat = (label, valueHtml, cls = "", term) =>
  `<div class="stat"><div class="k">${esc(label)}${term ? infoBtn(term) : ""}</div><div class="v num ${cls}">${valueHtml}</div></div>`;

export const segmented = (id, options, active) =>
  `<div class="seg" id="${id}">${options.map(([v, label]) =>
    `<button data-v="${esc(v)}" aria-pressed="${v === active}">${esc(label)}</button>`).join("")}</div>`;

export const empty = (text) => `<div class="empty">${esc(text)}</div>`;

export const lockIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>`;
