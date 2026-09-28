/** Learning mode: plain-English definitions + the popover that shows them. */
import { esc } from "../core/dom.js";

export const GLOSSARY = {
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
  screen: ["Screens", "Automatic filters over the watchlist – rules-based and transparent. They show where to look, not what to buy."],
  ytd: ["YTD", "Year-to-date: change since the last close of the previous year."],
  pl: ["Unrealised P/L", "Profit or loss if you sold at the latest price, before fees and taxes. Currency moves (USD/MYR) are included for US stocks."],
};

export const glossaryHTML = () =>
  Object.values(GLOSSARY).map(([t, d]) => `<dt>${esc(t)}</dt><dd>${esc(d)}</dd>`).join("");

/** Shows a definition next to any `.info-btn[data-term]` button that is clicked. */
export class GlossaryPopover {
  constructor(el) {
    this.el = el;
    const hide = () => this.hide();
    window.addEventListener("scroll", hide, { passive: true });
    document.addEventListener("scroll", hide, { passive: true, capture: true });
  }

  get isOpen() { return this.el.classList.contains("open"); }
  hide() { this.el.classList.remove("open"); }

  /** Returns true if the click was on an info button (so callers can stop). */
  handleClick(e) {
    const btn = e.target.closest(".info-btn[data-term]");
    if (!btn) { this.hide(); return false; }
    e.stopPropagation();
    const g = GLOSSARY[btn.dataset.term];
    if (g) this.#showAt(btn, g);
    return true;
  }

  #showAt(anchor, [title, body]) {
    const el = this.el;
    el.innerHTML = `<b>${esc(title)}</b>${esc(body)}`;
    el.classList.add("open");
    const r = anchor.getBoundingClientRect(), w = Math.min(300, innerWidth - 24);
    el.style.width = w + "px";
    el.style.left = Math.max(12, Math.min(r.left - w / 2, innerWidth - w - 12)) + "px";
    const below = r.bottom + 8;
    el.style.top = (below + el.offsetHeight > innerHeight - 10 ? r.top - el.offsetHeight - 8 : below) + "px";
  }
}
