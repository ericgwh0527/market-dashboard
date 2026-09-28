/** Data access: the only module that knows file paths under docs/data/. */
async function getJSON(path) {
  const r = await fetch(`${path}${path.includes("?") ? "&" : "?"}t=${Date.now()}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json();
}

/** Read-only view over latest.json with symbol lookup. */
export class MarketData {
  constructor(raw) {
    Object.assign(this, raw);
    this.bySymbol = new Map([...raw.indices, ...raw.stocks].map((x) => [x.symbol, x]));
  }
  get(symbol) { return this.bySymbol.get(symbol); }
  get ageHours() { return (Date.now() - new Date(this.generated_at).getTime()) / 3.6e6; }
}

export class DataService {
  #series = new Map();

  constructor(base = "data/") { this.base = base; }

  async latest() { return new MarketData(await getJSON(this.base + "latest.json")); }

  /** Price + indicator series for one instrument (cached per page load). */
  async series(row) {
    if (!this.#series.has(row.symbol)) this.#series.set(row.symbol, await getJSON(this.base + row.file));
    return this.#series.get(row.symbol);
  }

  /** The encrypted portfolio blob, or null when not set up. */
  async portfolioBlob() {
    try { return await getJSON(this.base + "portfolio.enc.json"); } catch { return null; }
  }
}
