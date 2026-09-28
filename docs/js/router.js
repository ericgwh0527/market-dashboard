/** Hash routing: "#<viewId>" shows a tab, "#s=<SYMBOL>" opens the detail sheet. */
export class Router {
  constructor(onRoute) {
    this.onRoute = onRoute;
    window.addEventListener("popstate", () => this.resolve());
  }

  current() {
    const h = decodeURIComponent(location.hash.slice(1));
    return h.startsWith("s=") ? { symbol: h.slice(2) } : { view: h || null };
  }

  resolve() { this.onRoute(this.current()); }

  go(hash) {
    if (location.hash !== hash) history.pushState(null, "", hash);
    this.resolve();
  }

  showView(id) { this.go("#" + id); }
  openSymbol(sym) { this.go("#s=" + encodeURIComponent(sym)); }
  back() { if (this.current().symbol) history.back(); }
}
