import { $, esc } from "../core/dom.js";
import { empty, newsItem } from "../ui/components.js";
import { View } from "./view.js";

const ALL = "All", WATCHLIST = "Watchlist";

export class NewsView extends View {
  id = "news";
  label = "News";
  icon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h13v16H6a2 2 0 0 1-2-2V4z"/><path d="M17 8h3v10a2 2 0 0 1-2 2"/><path d="M8 8h5M8 12h5M8 16h3"/></svg>`;
  topic = ALL;

  template() {
    return `<div class="controls"><div class="seg" id="newsSeg" style="flex-wrap:wrap"></div></div>
      <div class="card list" id="newsList" style="padding:0"></div>`;
  }

  init(ctx) {
    super.init(ctx);
    $("#newsSeg", this.section).addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      this.topic = b.dataset.v;
      this.render(this.data);
    });
  }

  render(data) {
    if (!data) return;
    this.data = data;
    const stockNews = data.stocks.flatMap((s) => (s.news || []).map((n) => ({ ...n, symbol: s.symbol, topic: WATCHLIST })));
    const topics = [ALL, ...new Set(data.market_news.map((n) => n.topic)), WATCHLIST];
    $("#newsSeg", this.section).innerHTML = topics.map((t) => `<button data-v="${esc(t)}" aria-pressed="${t === this.topic}">${esc(t)}</button>`).join("");

    const pool = this.topic === WATCHLIST ? stockNews
      : this.topic === ALL ? [...data.market_news, ...stockNews]
      : data.market_news.filter((n) => n.topic === this.topic);
    const seen = new Set();
    const list = pool.filter((n) => !seen.has(n.title) && seen.add(n.title))
      .sort((a, b) => (new Date(b.published).getTime() || 0) - (new Date(a.published).getTime() || 0));
    $("#newsList", this.section).innerHTML = list.slice(0, 80).map(newsItem).join("") || empty("No news.");
  }
}
