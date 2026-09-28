/* Market Dashboard – front end (no build step). Reads data/latest.json produced by
   scripts/fetch_data.py, plus data/series/<SYMBOL>.json on demand, and the encrypted
   data/portfolio.enc.json which is decrypted locally with the Web Crypto API. */
(() => {
  "use strict";

  // ------------------------------------------------------------------ utils
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
  };
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const isNum = (x) => typeof x === "number" && isFinite(x);

  function fmt(n, d) {
    if (!isNum(n)) return "–";
    if (d === undefined) d = Math.abs(n) >= 1000 ? 2 : Math.abs(n) >= 10 ? 2 : Math.abs(n) >= 1 ? 3 : 4;
    return n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  const pct = (n, d = 2) => (isNum(n) ? (n > 0 ? "+" : n < 0 ? "−" : "") + Math.abs(n).toFixed(d) + "%" : "–");
  const dir = (n) => (!isNum(n) || n === 0 ? "" : n > 0 ? "up" : "down");
  const arrow = (n) => (!isNum(n) || n === 0 ? "" : n > 0 ? "▲ " : "▼ ");
  function big(n) {
    if (!isNum(n)) return "–";
    const a = Math.abs(n);
    if (a >= 1e12) return (n / 1e12).toFixed(2) + "T";
    if (a >= 1e9) return (n / 1e9).toFixed(2) + "B";
    if (a >= 1e6) return (n / 1e6).toFixed(2) + "M";
    if (a >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return fmt(n, 0);
  }
  const cur = (s) => (s.market === "MY" || (s.symbol || "").endsWith(".KL") ? "RM " : s.market === "US" ? "$" : "");
  function priceStr(s) {
    if (s.symbol === "MYR=X") return fmt(s.price, 4);
    if (s.symbol === "^TNX") return fmt(s.price, 3) + "%";
    return cur(s) + fmt(s.price);
  }
  function ago(iso) {
    if (!iso) return "";
    const t = new Date(iso).getTime();
    if (!t) return "";
    const m = Math.round((Date.now() - t) / 60000);
    if (m < 60) return `${Math.max(m, 1)}m ago`;
    const h = Math.round(m / 60);
    if (h < 48) return `${h}h ago`;
    return `${Math.round(h / 24)}d ago`;
  }
  function spark(values, cls) {
    if (!values || values.length < 2) return "";
    const w = 100, h = 30, min = Math.min(...values), max = Math.max(...values), r = max - min || 1;
    const pts = values.map((v, i) => `${((i / (values.length - 1)) * w).toFixed(2)},${(h - 2 - ((v - min) / r) * (h - 4)).toFixed(2)}`).join(" ");
    const color = cls === "up" ? "var(--up-mark)" : cls === "down" ? "var(--down-mark)" : "var(--text-3)";
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
  }
  const infoBtn = (term) => `<button class="info" data-term="${term}" aria-label="What is this?"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01" stroke-linecap="round"/></svg></button>`;

  // ------------------------------------------------------------------ glossary (learning mode)
  const G = {
    rsi: ["RSI (14-day)", "Relative Strength Index, 0–100. Measures how fast the price has moved recently. Above 70 = 'overbought' (ran up fast, may pause); below 30 = 'oversold' (sold off hard, may bounce). It is a speed gauge, not a buy/sell button."],
    sma: ["Moving average (SMA)", "The average closing price over the last N days (20, 50, 200). Price above its 200-day average is the classic sign of a long-term uptrend; the 50-day shows the medium-term trend."],
    trend: ["Trend", "Uptrend = price above the 50-day average, which is above the 200-day. Downtrend = the reverse. Mixed = somewhere in between (trend changing or sideways)."],
    hi52: ["52-week high / low", "The highest and lowest prices of the past year. Stocks near their 52-week high have strong momentum; near the low means the market has been selling it."],
    pe: ["P/E ratio", "Price ÷ earnings per share. How many years of current profit you pay for. Lower can mean cheaper – or a business the market expects to shrink. Compare within the same industry."],
    fpe: ["Forward P/E", "Like P/E but using analysts' forecast earnings for the next 12 months."],
    div: ["Dividend yield", "Yearly dividends ÷ share price. A 5% yield pays about RM5 a year for every RM100 invested (if the dividend holds)."],
    mcap: ["Market cap", "Share price × number of shares = what the market values the whole company at."],
    vol: ["Volume ratio", "Today's traded shares ÷ the 20-day average. Above ~2× means unusual interest – often news, earnings, or big funds moving."],
    macd: ["MACD", "Momentum indicator comparing a fast (12-day) and slow (26-day) average. When it turns positive, momentum is improving; negative means fading."],
    volat: ["Volatility", "How much the price swings, annualised. 20% is calm (big banks), 50%+ is wild (small caps, hot tech)."],
    beta: ["Beta", "How much the stock moves vs the overall market. 1 = same as market, 2 = twice as jumpy, 0.5 = half."],
    analyst: ["Analyst view", "Average rating from brokers covering the stock, and their average 12-month price target. Useful context – they are often wrong."],
    vix: ["VIX", "The 'fear index': expected S&P 500 volatility over the next month. Under 15 = calm, over 25 = nervous market."],
    golden: ["Golden / death cross", "Golden cross: 50-day average crosses above the 200-day (bullish sign). Death cross: crosses below (bearish). Slow signals – they confirm trends rather than predict them."],
    theme: ["Themes", "Average move of the watchlist stocks in each group, so you can see where money is flowing (e.g. data-centre plays vs banks)."],
    screen: ["Screens", "Automatic filters over your watchlist – like the stock screener in the Threads post, but rules-based and transparent. They show where to look, not what to buy."],
    ytd: ["YTD", "Year-to-date: change since the last close of the previous year."],
    pl: ["Unrealised P/L", "Profit or loss if you sold at the latest price, before fees and taxes. Currency moves (USD/MYR) are included for US stocks."],
  };

  // ------------------------------------------------------------------ state
  let D = null;
  const seriesCache = new Map();
  const bySym = new Map();
  let wlMarket = "all";
  let newsTopic = "All";

  // ------------------------------------------------------------------ theme
  function applyTheme(t) {
    if (t) document.documentElement.setAttribute("data-theme", t);
    else document.documentElement.removeAttribute("data-theme");
  }
  applyTheme(store.get("theme"));
  function currentDark() {
    const t = document.documentElement.getAttribute("data-theme");
    return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  }

  // ------------------------------------------------------------------ load
  async function getJSON(path) {
    const r = await fetch(`${path}${path.includes("?") ? "&" : "?"}t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return r.json();
  }

  async function load() {
    try {
      D = await getJSON("data/latest.json");
    } catch (e) {
      $("#indexTiles").innerHTML = `<div class="card empty" style="grid-column:1/-1">No data yet. The first scheduled run fills this in – or trigger it from the repo's Actions tab.</div>`;
      return;
    }
    bySym.clear();
    [...D.indices, ...D.stocks].forEach((x) => bySym.set(x.symbol, x));
    const staleH = (Date.now() - new Date(D.generated_at).getTime()) / 3.6e6;
    $("#updated").innerHTML = `<span class="lbl">Updated<br></span><span title="${esc(D.generated_at_myt)}">${esc(D.generated_at_myt.replace(/^\w+ /, "").replace(/ \d{4},/, ","))}</span>${staleH > 30 ? ' <span class="pill warn">stale</span>' : ""}`;
    renderOverview();
    renderWatchlist();
    renderSignals();
    renderNews();
    route();
  }

  // ------------------------------------------------------------------ overview
  function stockRow(s, right = "chg_1d") {
    const d = dir(s[right]);
    return `<div class="row" data-sym="${esc(s.symbol)}" tabindex="0">
      <div><div class="r-name">${esc(s.name)}</div><div class="r-sub">${esc(s.symbol)} · ${esc(s.theme || s.group || "")}</div></div>
      <div class="r-right num"><div class="r-price">${priceStr(s)}</div><div class="${d}" style="font-size:13px;font-weight:600">${arrow(s[right])}${pct(s[right])}</div></div>
    </div>`;
  }

  function renderOverview() {
    // AI summary
    const sm = D.summary;
    if (sm && sm.text && window.marked) {
      const safe = sm.text.replace(/</g, "&lt;");
      $("#summaryWrap").innerHTML = `<h2>Today's brief <span class="pill info">AI · ${esc(sm.model || "")}</span>${sm.stale ? '<span class="pill warn">from earlier run</span>' : ""}</h2>
        <div class="card summary">${marked.parse(safe)}<div class="faint">Written by AI from the data on this page – may contain mistakes.</div></div>`;
    } else if (sm && sm.text) {
      $("#summaryWrap").innerHTML = `<h2>Today's brief</h2><div class="card summary" style="white-space:pre-wrap">${esc(sm.text)}</div>`;
    } else $("#summaryWrap").innerHTML = "";

    // index tiles
    $("#indexTiles").innerHTML = D.indices.map((i) => {
      const d = dir(i.chg_1d);
      return `<div class="card tile" data-sym="${esc(i.symbol)}" tabindex="0">
        <div class="t-name">${esc(i.name)}${i.symbol === "^VIX" ? " " + infoBtn("vix") : ""}</div>
        <div class="t-price num">${priceStr(i)}</div>
        <div class="t-chg num ${d}">${arrow(i.chg_1d)}${pct(i.chg_1d)} <span class="faint" style="font-weight:500">1M ${pct(i.chg_1m, 1)}</span></div>
        ${spark(i.spark, dir((i.spark || []).at(-1) - (i.spark || [])[0]))}
      </div>`;
    }).join("");

    // movers
    const withChg = D.stocks.filter((s) => isNum(s.chg_1d));
    const sorted = [...withChg].sort((a, b) => b.chg_1d - a.chg_1d);
    const gain = sorted.slice(0, 4), lose = sorted.slice(-4).reverse();
    $("#movers").innerHTML =
      `<div class="row" style="cursor:default;background:none"><div class="faint">Gainers</div></div>` + gain.map((s) => stockRow(s)).join("") +
      `<div class="row" style="cursor:default;background:none"><div class="faint">Losers</div></div>` + lose.map((s) => stockRow(s)).join("");

    // themes (diverging bars around zero)
    const mx = Math.max(1, ...D.themes.map((t) => Math.abs(t.chg_1d || 0)));
    $("#themes").innerHTML = D.themes.map((t) => {
      const v = t.chg_1d || 0, w = (Math.abs(v) / mx) * 50;
      const bar = v >= 0 ? `left:50%;width:${w}%;background:var(--up-mark)` : `left:${50 - w}%;width:${w}%;background:var(--down-mark)`;
      return `<div class="theme-row" title="1-month: ${pct(t.chg_1m)} · ${esc(t.members.join(", "))}">
        <div style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><span class="pill">${t.market === "MY" ? "MY" : "US"}</span> ${esc(t.name)}</div>
        <div class="bar-track"><div class="mid"></div><div class="bar" style="${bar}"></div></div>
        <div class="num ${dir(v)}" style="text-align:right;font-weight:600;font-size:13px">${pct(t.chg_1d)}</div></div>`;
    }).join("");

    $("#headlines").innerHTML = D.market_news.slice(0, 12).map(newsHTML).join("") || `<div class="empty">No headlines.</div>`;
  }

  function newsHTML(n) {
    return `<a class="news-item" href="${esc(n.url)}" target="_blank" rel="noopener">
      <div class="n-title">${esc(n.title)}</div>
      <div class="n-meta">${esc(n.source || "")}${n.topic ? " · " + esc(n.topic) : ""}${n.symbol ? " · " + esc(n.symbol) : ""} · ${ago(n.published)}</div></a>`;
  }

  // ------------------------------------------------------------------ watchlist
  function renderWatchlist() {
    const key = $("#sortSel").value, q = $("#wlSearch").value.trim().toLowerCase();
    let rows = D.stocks.filter((s) => (wlMarket === "all" || s.market === wlMarket) &&
      (!q || (s.name + " " + s.symbol + " " + s.theme).toLowerCase().includes(q)));
    rows.sort((a, b) => key === "name" ? a.name.localeCompare(b.name) : (isNum(b[key]) ? b[key] : -1e9) - (isNum(a[key]) ? a[key] : -1e9));
    $("#watchlist").innerHTML = rows.map((s) => {
      const d = dir(s.chg_1d);
      const tr = s.trend === "Uptrend" ? "good" : s.trend === "Downtrend" ? "bad" : "";
      const extra = key === "rsi14" ? `RSI ${fmt(s.rsi14, 0)}` : key === "from_hi_52w" ? `${pct(s.from_hi_52w, 1)} vs high` :
        key !== "chg_1d" && key !== "name" ? `${pct(s[key])}` : "";
      return `<div class="row wl" data-sym="${esc(s.symbol)}" tabindex="0">
        <div><div class="r-name">${esc(s.name)} ${s.stale ? '<span class="pill warn">stale</span>' : ""}</div>
          <div class="r-sub">${esc(s.symbol)} · <span class="pill ${tr}" style="font-size:10.5px;padding:0 6px">${esc(s.trend)}</span> ${extra ? "· " + extra : ""}</div></div>
        ${spark(s.spark, dir((s.spark || []).at(-1) - (s.spark || [])[0]))}
        <div class="r-right num"><div class="r-price">${priceStr(s)}</div><div class="${d}" style="font-size:13px;font-weight:600">${arrow(s.chg_1d)}${pct(s.chg_1d)}</div></div>
      </div>`;
    }).join("") || `<div class="empty">Nothing matches.</div>`;
  }

  // ------------------------------------------------------------------ signals
  function renderSignals() {
    $("#screens").innerHTML = D.screens.map((sc) => `
      <div class="card screen">
        <div class="s-head"><div class="s-name">${esc(sc.name)}</div><span class="pill">${sc.symbols.length}</span></div>
        <div class="s-why">${esc(sc.why)}</div>
        <div class="chips">${sc.symbols.map((sym) => {
          const s = bySym.get(sym); if (!s) return "";
          return `<button class="chip" data-sym="${esc(sym)}">${esc(s.name)} <span class="num ${dir(s.chg_1d)}">${pct(s.chg_1d, 1)}</span></button>`;
        }).join("") || '<span class="faint">None today</span>'}</div>
      </div>`).join("");

    const items = [];
    D.stocks.forEach((s) => (s.signals || []).forEach((g) => items.push({ s, g })));
    const order = { good: 0, bad: 1, warn: 2, info: 3 };
    items.sort((a, b) => order[a.g.type] - order[b.g.type]);
    $("#allSignals").innerHTML = items.map(({ s, g }) => `
      <div class="row" data-sym="${esc(s.symbol)}" tabindex="0">
        <div><div class="r-name">${esc(s.name)} <span class="faint">${esc(s.symbol)}</span></div><div class="r-sub" style="white-space:normal">${sigIcon(g.type)} ${esc(g.text)}</div></div>
        <div class="r-right num ${dir(s.chg_1d)}" style="font-weight:600;font-size:13px">${pct(s.chg_1d)}</div></div>`).join("") ||
      `<div class="empty">No signals today.</div>`;

    $("#glossary").innerHTML = Object.values(G).map(([t, d]) => `<dt>${esc(t)}</dt><dd>${esc(d)}</dd>`).join("");
  }
  const sigIcon = (t) => ({ good: '<span class="up">▲</span>', bad: '<span class="down">▼</span>', warn: '<span style="color:var(--warn)">!</span>', info: '<span style="color:var(--accent)">●</span>' }[t] || "");

  // ------------------------------------------------------------------ news
  function renderNews() {
    const stockNews = [];
    D.stocks.forEach((s) => (s.news || []).forEach((n) => stockNews.push({ ...n, symbol: s.symbol, topic: "Watchlist" })));
    const topics = ["All", ...new Set(D.market_news.map((n) => n.topic)), "Watchlist"];
    $("#newsSeg").innerHTML = topics.map((t) => `<button data-v="${esc(t)}" aria-pressed="${t === newsTopic}">${esc(t)}</button>`).join("");
    $("#newsSeg").style.flexWrap = "wrap";
    let list = newsTopic === "Watchlist" ? stockNews : newsTopic === "All" ? [...D.market_news, ...stockNews] : D.market_news.filter((n) => n.topic === newsTopic);
    const seen = new Set();
    list = list.filter((n) => (seen.has(n.title) ? false : seen.add(n.title)))
      .sort((a, b) => (new Date(b.published).getTime() || 0) - (new Date(a.published).getTime() || 0));
    $("#newsList").innerHTML = list.slice(0, 80).map(newsHTML).join("") || `<div class="empty">No news.</div>`;
  }

  // ------------------------------------------------------------------ detail sheet
  let charts = [];
  let sheetSym = null, sheetRange = store.get("range") || "6M", sheetType = store.get("ctype") || "line";

  async function openSheet(sym) {
    const s = bySym.get(sym);
    if (!s) return;
    sheetSym = sym;
    const isStock = !!s.market;
    const f = s.fundamentals || {};
    const d = dir(s.chg_1d);
    const sheet = $("#sheet");
    sheet.innerHTML = `
      <div class="sheet-head">
        <div style="flex:1;min-width:0">
          <div id="sheetTitle" style="font-weight:700;font-size:18px">${esc(s.name)}</div>
          <div class="faint">${esc(s.symbol)}${f.sector ? " · " + esc(f.sector) : ""}${s.theme ? " · " + esc(s.theme) : ""}</div>
        </div>
        <button class="icon-btn" id="closeSheet" aria-label="Close"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
      </div>
      <div class="sheet-body">
        <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
          <div class="big-price num">${priceStr(s)}</div>
          <div class="num ${d}" style="font-weight:650">${arrow(s.chg_1d)}${pct(s.chg_1d)} today</div>
          <span class="pill ${s.trend === "Uptrend" ? "good" : s.trend === "Downtrend" ? "bad" : ""}">${esc(s.trend)}</span>${infoBtn("trend")}
        </div>
        <div class="faint">Close of ${esc(s.date)}</div>
        <div class="controls" style="margin-top:12px">
          <div class="seg" id="rangeSeg">${["1M", "3M", "6M", "1Y"].map((r) => `<button data-v="${r}" aria-pressed="${r === sheetRange}">${r}</button>`).join("")}</div>
          <div class="seg" id="typeSeg"><button data-v="line" aria-pressed="${sheetType === "line"}">Line</button><button data-v="candle" aria-pressed="${sheetType === "candle"}">Candles</button></div>
        </div>
        <div class="card" style="padding:8px"><div class="chart-box" id="priceChart"><div class="chart-legend" id="priceLegend"></div></div></div>
        <div class="card" style="padding:8px;margin-top:8px"><div class="chart-box small" id="rsiChart"><div class="chart-legend" id="rsiLegend"></div></div></div>

        ${(s.signals || []).length ? `<h2>Signals</h2><div class="signal-list">${s.signals.map((g) => `<div class="signal ${g.type}"><span class="ico">${sigIcon(g.type)}</span><span>${esc(g.text)}</span></div>`).join("")}</div>` : ""}

        <h2>Performance</h2>
        <div class="card stats">
          ${stat("1 week", pct(s.chg_5d), dir(s.chg_5d))}${stat("1 month", pct(s.chg_1m), dir(s.chg_1m))}${stat("3 months", pct(s.chg_3m), dir(s.chg_3m))}
          ${stat("6 months", pct(s.chg_6m), dir(s.chg_6m))}${stat("1 year", pct(s.chg_1y), dir(s.chg_1y))}${stat("YTD", pct(s.chg_ytd), dir(s.chg_ytd), "ytd")}
        </div>
        <h2>Technicals</h2>
        <div class="card stats">
          ${stat("RSI (14)", fmt(s.rsi14, 1), "", "rsi")}${stat("vs 50-day avg", s.sma50 ? pct((s.price / s.sma50 - 1) * 100) : "–", "", "sma")}${stat("vs 200-day avg", s.sma200 ? pct((s.price / s.sma200 - 1) * 100) : "–", "", "sma")}
          ${stat("52w high", fmt(s.hi_52w), "", "hi52")}${stat("52w low", fmt(s.lo_52w), "", "hi52")}${stat("From 52w high", pct(s.from_hi_52w, 1), "", "hi52")}
          ${stat("Volume vs avg", isNum(s.vol_ratio) ? fmt(s.vol_ratio, 2) + "×" : "–", "", "vol")}${stat("MACD hist.", fmt(s.macd_hist, 3), dir(s.macd_hist), "macd")}${stat("Volatility", isNum(s.volatility_60d) ? fmt(s.volatility_60d, 0) + "%" : "–", "", "volat")}
        </div>
        ${isStock ? `<h2>Valuation &amp; business</h2>
        <div class="card stats">
          ${stat("Market cap", big(f.market_cap), "", "mcap")}${stat("P/E", fmt(f.pe, 1), "", "pe")}${stat("Forward P/E", fmt(f.forward_pe, 1), "", "fpe")}
          ${stat("Dividend yield", isNum(f.div_yield) ? fmt(f.div_yield, 2) + "%" : "–", "", "div")}${stat("Profit margin", isNum(f.profit_margin) ? fmt(f.profit_margin, 1) + "%" : "–")}${stat("Revenue growth", pct(f.revenue_growth, 1), dir(f.revenue_growth))}
          ${stat("Beta", fmt(f.beta, 2), "", "beta")}${stat("Analysts", f.analyst_view ? esc(String(f.analyst_view).replace("_", " ")) + (f.analyst_count ? ` (${f.analyst_count})` : "") : "–", "", "analyst")}${stat("Avg target", isNum(f.target_price) ? fmt(f.target_price) + (s.price ? ` <span class="faint">${pct((f.target_price / s.price - 1) * 100, 0)}</span>` : "") : "–", "", "analyst")}
          ${f.next_earnings ? stat("Next earnings", esc(f.next_earnings)) : ""}
        </div>` : ""}
        ${(s.news || []).length ? `<h2>News</h2><div class="card list" style="padding:0">${s.news.map(newsHTML).join("")}</div>` : ""}
      </div>`;
    $("#backdrop").classList.add("open");
    sheet.classList.add("open");
    document.body.style.overflow = "hidden";
    if (location.hash !== "#s=" + encodeURIComponent(sym)) history.pushState(null, "", "#s=" + encodeURIComponent(sym));
    sheet.scrollTop = 0;
    $("#closeSheet").focus({ preventScroll: true });

    try {
      if (!seriesCache.has(sym)) seriesCache.set(sym, await getJSON("data/" + s.file));
      if (sheetSym === sym) drawCharts(seriesCache.get(sym), s);
    } catch (e) {
      $("#priceChart").innerHTML = `<div class="empty">Chart data unavailable.</div>`;
    }
  }
  const stat = (k, v, cls = "", term) => `<div class="stat"><div class="k">${esc(k)}${term ? infoBtn(term) : ""}</div><div class="v num ${cls}">${v}</div></div>`;

  function closeSheet(fromPop) {
    $("#sheet").classList.remove("open");
    $("#backdrop").classList.remove("open");
    document.body.style.overflow = "";
    charts.forEach((c) => c.remove()); charts = [];
    sheetSym = null;
    if (!fromPop && location.hash.startsWith("#s=")) history.back();
  }

  function drawCharts(sr, s) {
    if (!window.LightweightCharts) { setTimeout(() => drawCharts(sr, s), 200); return; }
    charts.forEach((c) => c.remove()); charts = [];
    const n = { "1M": 22, "3M": 66, "6M": 130, "1Y": 1e9 }[sheetRange];
    const start = Math.max(0, sr.d.length - n);
    const idx = [...sr.d.keys()].slice(start);
    const text2 = css("--text-2"), grid = css("--grid"), border = css("--border");
    const base = {
      layout: { background: { type: "solid", color: "transparent" }, textColor: text2, fontFamily: "Inter, system-ui, sans-serif", fontSize: 11 },
      grid: { vertLines: { visible: false }, horzLines: { color: grid } },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.2, bottom: 0.05 } },
      timeScale: { borderColor: border, fixLeftEdge: true, fixRightEdge: true },
      crosshair: { mode: 0 },
      handleScroll: false, handleScale: false,
      localization: { locale: "en-US", priceFormatter: (p) => fmt(p) },
    };
    const LC = window.LightweightCharts;
    const pc = LC.createChart($("#priceChart"), { ...base, autoSize: true });
    charts.push(pc);
    const upC = css("--up-mark"), dnC = css("--down-mark");
    let main;
    if (sheetType === "candle") {
      main = pc.addCandlestickSeries({ upColor: upC, downColor: dnC, wickUpColor: upC, wickDownColor: dnC, borderVisible: false, priceLineVisible: false });
      main.setData(idx.map((i) => ({ time: sr.d[i], open: sr.o[i], high: sr.h[i], low: sr.l[i], close: sr.c[i] })));
    } else {
      main = pc.addLineSeries({ color: css("--series-1"), lineWidth: 2, priceLineVisible: false, crosshairMarkerRadius: 4 });
      main.setData(idx.map((i) => ({ time: sr.d[i], value: sr.c[i] })));
    }
    const lineOf = (key, color) => {
      const ls = pc.addLineSeries({ color, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      ls.setData(idx.filter((i) => sr[key][i] != null).map((i) => ({ time: sr.d[i], value: sr[key][i] })));
      return ls;
    };
    const s50 = lineOf("sma50", css("--series-2"));
    const s200 = lineOf("sma200", css("--series-3"));
    pc.timeScale().fitContent();

    const legend = $("#priceLegend");
    const setLegend = (i) => {
      if (i == null) return;
      const chg = i > 0 ? (sr.c[i] / sr.c[i - 1] - 1) * 100 : null;
      legend.innerHTML = `<span><b>${esc(sr.d[i])}</b></span>
        <span><span class="swatch" style="background:var(--series-1)"></span>Close <b>${fmt(sr.c[i])}</b> <span class="${dir(chg)}">${pct(chg)}</span></span>
        <span><span class="swatch" style="background:var(--series-2)"></span>50d <b>${fmt(sr.sma50[i])}</b></span>
        <span><span class="swatch" style="background:var(--series-3)"></span>200d <b>${fmt(sr.sma200[i])}</b></span>`;
    };
    const lastI = sr.d.length - 1;
    setLegend(lastI);
    const dateIdx = new Map(sr.d.map((d, i) => [d, i]));
    const timeKey = (t) => (typeof t === "string" ? t : t && t.year ? `${t.year}-${String(t.month).padStart(2, "0")}-${String(t.day).padStart(2, "0")}` : null);
    pc.subscribeCrosshairMove((p) => setLegend(p && p.time ? dateIdx.get(timeKey(p.time)) : lastI));

    // RSI panel
    const rc = LC.createChart($("#rsiChart"), { ...base, autoSize: true, localization: { locale: "en-US", priceFormatter: (p) => fmt(p, 0) }, timeScale: { ...base.timeScale, visible: false }, rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.1, bottom: 0.1 } } });
    charts.push(rc);
    const rs = rc.addLineSeries({ color: css("--series-1"), lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
    rs.setData(idx.filter((i) => sr.rsi[i] != null).map((i) => ({ time: sr.d[i], value: sr.rsi[i] })));
    [70, 30].forEach((v) => rs.createPriceLine({ price: v, color: css("--text-3"), lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: v === 70 ? "overbought" : "oversold" }));
    rs.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
    rc.timeScale().fitContent();
    const rl = $("#rsiLegend");
    const setR = (i) => { if (i != null) rl.innerHTML = `RSI (14) <b>${fmt(sr.rsi[i], 1)}</b> ${infoBtnInline()}`; };
    setR(lastI);
    rc.subscribeCrosshairMove((p) => setR(p && p.time ? dateIdx.get(timeKey(p.time)) : lastI));
    pc.subscribeCrosshairMove((p) => setR(p && p.time ? dateIdx.get(timeKey(p.time)) : lastI));
  }
  const infoBtnInline = () => "";

  // ------------------------------------------------------------------ portfolio (encrypted)
  const b64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
  let PF = null;

  function idb() {
    return new Promise((res, rej) => {
      const r = indexedDB.open("mdash", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("keys");
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
  }
  async function idbGet(k) { try { const db = await idb(); return await new Promise((res) => { const t = db.transaction("keys").objectStore("keys").get(k); t.onsuccess = () => res(t.result); t.onerror = () => res(null); }); } catch { return null; } }
  async function idbSet(k, v) { try { const db = await idb(); await new Promise((res) => { const t = db.transaction("keys", "readwrite"); t.objectStore("keys").put(v, k); t.oncomplete = res; t.onerror = res; }); } catch { /* ignore */ } }
  async function idbDel(k) { try { const db = await idb(); db.transaction("keys", "readwrite").objectStore("keys").delete(k); } catch { /* ignore */ } }

  async function deriveKey(pw, blob) {
    const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(pw), "PBKDF2", false, ["deriveKey"]);
    return crypto.subtle.deriveKey({ name: "PBKDF2", salt: b64(blob.salt), iterations: blob.iter, hash: "SHA-256" },
      base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);   // non-extractable: can't be read back out
  }
  async function decryptWith(key, blob) {
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(blob.iv) }, key, b64(blob.ct));
    return JSON.parse(new TextDecoder().decode(pt));
  }

  async function renderPortfolio() {
    const el = $("#portfolio");
    let blob;
    try { blob = await getJSON("data/portfolio.enc.json"); }
    catch {
      el.innerHTML = `<div class="card lock"><div class="lock-ico">${lockSvg}</div><b>Portfolio not set up yet</b>
        <p class="muted" style="font-size:14px">Holdings are read from a private repo and published here only in encrypted form. See the README's “Portfolio setup” section.</p></div>`;
      return;
    }
    if (!window.isSecureContext || !crypto.subtle) { el.innerHTML = `<div class="card empty">Open this page over https to unlock.</div>`; return; }
    const saved = await idbGet("key");
    if (saved && saved.salt === blob.salt) {
      try { PF = await decryptWith(saved.key, blob); return drawPortfolio(); } catch { await idbDel("key"); }
    }
    el.innerHTML = `<div class="card lock">
      <div class="lock-ico">${lockSvg}</div><b>Portfolio is locked</b>
      <p class="muted" style="font-size:14px;margin:6px 0 0">It's encrypted (AES-256). Enter your passphrase – it never leaves this device.</p>
      <form id="unlockForm" autocomplete="off">
        <input type="password" id="pw" placeholder="Passphrase" aria-label="Passphrase" autocomplete="current-password" required>
        <label class="chk"><input type="checkbox" id="remember" checked> Keep unlocked on this device</label>
        <button class="btn" type="submit" id="unlockBtn">Unlock</button>
        <div class="err" id="pwErr"></div>
      </form></div>`;
    $("#unlockForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      $("#unlockBtn").textContent = "Unlocking…"; $("#pwErr").textContent = "";
      try {
        const key = await deriveKey($("#pw").value, blob);
        PF = await decryptWith(key, blob);
        if ($("#remember").checked) await idbSet("key", { salt: blob.salt, key });
        drawPortfolio();
      } catch {
        $("#pwErr").textContent = "Wrong passphrase.";
        $("#unlockBtn").textContent = "Unlock";
      }
    });
  }
  const lockSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>`;

  function drawPortfolio() {
    const p = PF, t = p.totals, bc = p.base_currency === "MYR" ? "RM " : "$";
    const money = (n, d = 2) => (isNum(n) ? (n < 0 ? "−" : "") + bc + fmt(Math.abs(n), d) : "–");
    const signed = (n) => (isNum(n) ? (n > 0 ? "+" : n < 0 ? "−" : "") + bc + fmt(Math.abs(n)) : "–");
    const mx = Math.max(...p.allocation.map((a) => a.pct || 0), 1);
    $("#portfolio").innerHTML = `
      <div class="card">
        <div class="hero">
          <div><div class="h-k">Total value</div><div class="h-v num">${money(t.value)}</div></div>
          <div><div class="h-k">Today</div><div class="h-v sm num ${dir(t.day_pl)}">${signed(t.day_pl)} <span style="font-size:14px">${pct(t.day_pl_pct)}</span></div></div>
          <div><div class="h-k">Unrealised P/L ${infoBtn("pl")}</div><div class="h-v sm num ${dir(t.pl)}">${signed(t.pl)} <span style="font-size:14px">${pct(t.pl_pct)}</span></div></div>
          <div><div class="h-k">Cash</div><div class="h-v sm num">${money(t.cash)}</div></div>
        </div>
        <div class="faint" style="margin-top:8px">Valued ${esc(p.generated_at_myt)} · USD/MYR ${fmt(p.usdmyr, 4)}${p.holdings_updated ? " · holdings as of " + esc(p.holdings_updated) : ""}</div>
      </div>
      ${(p.history || []).length >= 2 ? `<h2>Value over time</h2><div class="card" style="padding:8px"><div class="chart-box" id="pfChart" style="height:220px"></div></div>` : ""}
      <h2>Allocation</h2>
      <div class="card">${p.allocation.map((a) => `<div class="alloc-row"><div>${esc(a.name === "MY" ? "Bursa" : a.name === "US" ? "US" : a.name)}</div>
        <div><div class="alloc-bar" style="width:${((a.pct || 0) / mx) * 100}%"></div></div><div class="num" style="text-align:right">${fmt(a.pct, 1)}%</div></div>`).join("")}</div>
      <h2>Positions</h2>
      <div class="card" style="padding:4px 16px"><div class="tbl-wrap"><table class="tbl num">
        <thead><tr><th>Stock</th><th>Value</th><th>P/L</th><th>P/L %</th><th>Today</th><th>Weight</th><th>Shares</th><th>Avg cost</th><th>Price</th></tr></thead>
        <tbody>${p.positions.map((r) => `<tr ${bySym.has(r.symbol) ? `data-sym="${esc(r.symbol)}"` : ""}>
          <td><b>${esc(r.name)}</b><div class="faint">${esc(r.symbol)}${r.stale_price ? " · old price" : ""}</div></td>
          <td>${money(r.value_base)}</td><td class="${dir(r.pl_base)}">${signed(r.pl_base)}</td><td class="${dir(r.pl_pct)}">${pct(r.pl_pct)}</td>
          <td class="${dir(r.day_chg_pct)}">${pct(r.day_chg_pct)}</td><td>${fmt(r.weight, 1)}%</td><td>${fmt(r.shares, r.shares % 1 ? 3 : 0)}</td>
          <td>${r.currency === "USD" ? "$" : "RM "}${fmt(r.avg_cost)}</td><td>${r.currency === "USD" ? "$" : "RM "}${fmt(r.price)}</td></tr>`).join("")}
        </tbody></table></div></div>
      ${p.cash.length ? `<p class="faint">Cash: ${p.cash.map((c) => `${esc(c.currency)} ${fmt(c.amount)}`).join(" · ")}</p>` : ""}
      <div style="text-align:center;margin-top:16px"><button class="btn ghost" id="lockBtn">Lock on this device</button></div>`;
    $("#lockBtn").addEventListener("click", async () => { await idbDel("key"); PF = null; renderPortfolio(); });

    if ((p.history || []).length >= 2 && window.LightweightCharts) {
      const c = LightweightCharts.createChart($("#pfChart"), {
        autoSize: true, layout: { background: { type: "solid", color: "transparent" }, textColor: css("--text-2"), fontFamily: "Inter, system-ui", fontSize: 11 },
        grid: { vertLines: { visible: false }, horzLines: { color: css("--grid") } }, rightPriceScale: { borderVisible: false },
        timeScale: { borderColor: css("--border"), fixLeftEdge: true, fixRightEdge: true }, handleScroll: false, handleScale: false,
        localization: { locale: "en-US", priceFormatter: (v) => bc + fmt(v, 0) },
      });
      const v = c.addAreaSeries({ lineColor: css("--series-1"), topColor: "rgba(42,120,214,.18)", bottomColor: "rgba(42,120,214,0)", lineWidth: 2, priceLineVisible: false });
      v.setData(p.history.map((h) => ({ time: h.date, value: h.value })));
      const cst = c.addLineSeries({ color: css("--text-3"), lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: "cost" });
      cst.setData(p.history.map((h) => ({ time: h.date, value: (h.cost || 0) + (h.cash || 0) })));
      c.timeScale().fitContent();
    }
  }

  // ------------------------------------------------------------------ routing & events
  const views = ["overview", "watchlist", "signals", "news", "portfolio"];
  function show(view) {
    if (!views.includes(view)) view = "overview";
    $$("section.view").forEach((s) => s.classList.toggle("active", s.id === "view-" + view));
    $$("#tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.view === view)));
    if (view === "portfolio" && !PF) renderPortfolio();
    store.set("view", view);
  }
  function route() {
    const h = decodeURIComponent(location.hash.slice(1));
    if (h.startsWith("s=")) { openSheet(h.slice(2)); return; }
    if ($("#sheet").classList.contains("open")) closeSheet(true);
    show(h || store.get("view") || "overview");
  }
  window.addEventListener("popstate", route);

  $("#tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-view]"); if (!b) return;
    history.pushState(null, "", "#" + b.dataset.view); show(b.dataset.view); window.scrollTo({ top: 0 });
  });

  const pop = $("#pop");
  document.addEventListener("click", (e) => {
    const info = e.target.closest(".info[data-term]");
    if (info) {
      e.stopPropagation();
      const g = G[info.dataset.term]; if (!g) return;
      pop.innerHTML = `<b>${esc(g[0])}</b>${esc(g[1])}`;
      pop.classList.add("open");
      const r = info.getBoundingClientRect(), pw = Math.min(300, innerWidth - 24);
      pop.style.width = pw + "px";
      pop.style.left = Math.max(12, Math.min(r.left - pw / 2, innerWidth - pw - 12)) + "px";
      const top = r.bottom + 8;
      pop.style.top = (top + pop.offsetHeight > innerHeight - 10 ? r.top - pop.offsetHeight - 8 : top) + "px";
      return;
    }
    pop.classList.remove("open");
    const symEl = e.target.closest("[data-sym]");
    if (symEl && !e.target.closest("a")) { openSheet(symEl.dataset.sym); return; }
    const rng = e.target.closest("#rangeSeg button");
    if (rng) { sheetRange = rng.dataset.v; store.set("range", sheetRange); $$("#rangeSeg button").forEach((b) => b.setAttribute("aria-pressed", String(b === rng))); drawCharts(seriesCache.get(sheetSym), bySym.get(sheetSym)); return; }
    const ty = e.target.closest("#typeSeg button");
    if (ty) { sheetType = ty.dataset.v; store.set("ctype", sheetType); $$("#typeSeg button").forEach((b) => b.setAttribute("aria-pressed", String(b === ty))); drawCharts(seriesCache.get(sheetSym), bySym.get(sheetSym)); return; }
    if (e.target.closest("#closeSheet") || e.target === $("#backdrop")) { closeSheet(); return; }
    const m = e.target.closest("#mktSeg button");
    if (m) { wlMarket = m.dataset.v; $$("#mktSeg button").forEach((b) => b.setAttribute("aria-pressed", String(b === m))); renderWatchlist(); return; }
    const nt = e.target.closest("#newsSeg button");
    if (nt) { newsTopic = nt.dataset.v; renderNews(); return; }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { if (pop.classList.contains("open")) pop.classList.remove("open"); else if (sheetSym) closeSheet(); }
    if (e.key === "Enter" && e.target.matches("[data-sym]")) openSheet(e.target.dataset.sym);
  });
  window.addEventListener("scroll", () => pop.classList.remove("open"), { passive: true });
  $("#sheet").addEventListener("scroll", () => pop.classList.remove("open"), { passive: true });
  $("#sortSel").addEventListener("change", renderWatchlist);
  $("#wlSearch").addEventListener("input", renderWatchlist);
  $("#themeBtn").addEventListener("click", () => {
    const next = currentDark() ? "light" : "dark";
    applyTheme(next); store.set("theme", next);
    if (sheetSym && seriesCache.has(sheetSym)) drawCharts(seriesCache.get(sheetSym), bySym.get(sheetSym));
    if (PF && $("#view-portfolio").classList.contains("active")) drawPortfolio();
  });

  // refresh when the tab comes back after a while (phones keep tabs for days)
  let loadedAt = Date.now();
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && Date.now() - loadedAt > 15 * 60 * 1000) { loadedAt = Date.now(); load(); }
  });

  load();
})();
