/** Number / text formatting. Pure functions, no DOM. */
export const isNum = (x) => typeof x === "number" && Number.isFinite(x);

export function fmt(n, digits) {
  if (!isNum(n)) return "–";
  const a = Math.abs(n);
  const d = digits ?? (a >= 10 ? 2 : a >= 1 ? 3 : 4);
  return n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

/** Signed percentage with a real minus sign. */
export const pct = (n, d = 2) =>
  isNum(n) ? (n > 0 ? "+" : n < 0 ? "−" : "") + Math.abs(n).toFixed(d) + "%" : "–";

/** "up" | "down" | "" – used as a CSS class. */
export const dir = (n) => (!isNum(n) || n === 0 ? "" : n > 0 ? "up" : "down");
export const arrow = (n) => (!isNum(n) || n === 0 ? "" : n > 0 ? "▲ " : "▼ ");

export function big(n) {
  if (!isNum(n)) return "–";
  const a = Math.abs(n);
  for (const [v, u] of [[1e12, "T"], [1e9, "B"], [1e6, "M"]]) if (a >= v) return (n / v).toFixed(2) + u;
  if (a >= 1e3) return (n / 1e3).toFixed(1) + "K";
  return fmt(n, 0);
}

export const currencyPrefix = (row) =>
  row.market === "MY" || (row.symbol || "").endsWith(".KL") ? "RM " : row.market === "US" ? "$" : "";

/** Price display rules per instrument type. */
const PRICE_RULES = {
  "MYR=X": (r) => fmt(r.price, 4),
  "^TNX": (r) => fmt(r.price, 3) + "%",
};
export const priceStr = (row) => (PRICE_RULES[row.symbol] || ((r) => currencyPrefix(r) + fmt(r.price)))(row);

export function ago(iso, now = Date.now()) {
  const t = iso ? new Date(iso).getTime() : NaN;
  if (!t) return "";
  const m = Math.round((now - t) / 60000);
  if (m < 60) return `${Math.max(m, 1)}m ago`;
  const h = Math.round(m / 60);
  return h < 48 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
}

export const money = (n, prefix, d = 2) => (isNum(n) ? (n < 0 ? "−" : "") + prefix + fmt(Math.abs(n), d) : "–");
export const signedMoney = (n, prefix) => (isNum(n) ? (n > 0 ? "+" : n < 0 ? "−" : "") + prefix + fmt(Math.abs(n)) : "–");
