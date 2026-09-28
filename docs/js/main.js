/** Composition root: builds the services, mounts the tabs, wires global events. */
import { $, $$, esc } from "./core/dom.js";
import { prefs } from "./core/prefs.js";
import { ThemeController } from "./core/theme.js";
import { DataService } from "./data/api.js";
import { KeyStore } from "./data/crypto.js";
import { Router } from "./router.js";
import { GlossaryPopover } from "./ui/glossary.js";
import { StockSheet } from "./ui/sheet.js";
import { createViews } from "./views/index.js";

const REFRESH_AFTER_MS = 15 * 60 * 1000;   // phones keep tabs open for days

class App {
  data = null;

  constructor() {
    this.theme = new ThemeController();
    this.api = new DataService();
    this.keyStore = new KeyStore();
    this.views = createViews();
    this.popover = new GlossaryPopover($("#pop"));
    this.router = new Router((r) => this.#route(r));
    this.sheet = new StockSheet({
      sheet: $("#sheet"), backdrop: $("#backdrop"), dataService: this.api,
      onClose: () => { this.sheet.close(); this.router.back(); },
    });
    this.#mount();
    this.#bindGlobalEvents();
  }

  async start() {
    await this.load();
    this.router.resolve();
  }

  async load() {
    try {
      this.data = await this.api.latest();
    } catch {
      $("#view-overview #indexTiles").innerHTML =
        `<div class="card empty" data-u="grid-column-1-1">No data yet. The first scheduled run fills this in – or trigger it from the repo's Actions tab.</div>`;
      return;
    }
    this.loadedAt = Date.now();
    this.#renderUpdated();
    this.views.forEach((v) => v.render(this.data));
  }

  // ---------------------------------------------------------------- setup
  #mount() {
    $("#tabs").innerHTML = this.views.map((v) =>
      `<button role="tab" data-view="${v.id}" aria-selected="false">${v.icon}${esc(v.label)}</button>`).join("");
    const main = $("main");
    const disclaimer = $(".disclaimer", main);
    for (const v of this.views) {
      const section = document.createElement("section");
      section.className = "view";
      section.id = "view-" + v.id;
      section.innerHTML = v.template();
      main.insertBefore(section, disclaimer);
      v.init({ section, api: this.api, keyStore: this.keyStore, theme: this.theme });
    }
  }

  #bindGlobalEvents() {
    $("#tabs").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-view]");
      if (!b) return;
      this.router.showView(b.dataset.view);
      window.scrollTo({ top: 0 });
    });

    // Any element with data-sym (tiles, rows, chips, table rows) opens the detail sheet.
    document.addEventListener("click", (e) => {
      if (this.popover.handleClick(e)) return;
      const el = e.target.closest("[data-sym]");
      if (el && !e.target.closest("a") && !el.closest("#sheet")) this.router.openSymbol(el.dataset.sym);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (this.popover.isOpen) this.popover.hide();
        else if (this.sheet.isOpen) this.sheet.onClose();
      }
      if (e.key === "Enter" && e.target.matches?.("[data-sym]")) this.router.openSymbol(e.target.dataset.sym);
    });

    $("#themeBtn").addEventListener("click", () => this.theme.toggle());
    this.theme.onChange(() => {
      if (this.sheet.isOpen) this.sheet.redraw();
      this.views.forEach((v) => v.onThemeChange());
    });

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible" && Date.now() - (this.loadedAt || 0) > REFRESH_AFTER_MS) this.load();
    });
  }

  // ---------------------------------------------------------------- routing
  #route({ view, symbol }) {
    if (symbol) {
      const row = this.data?.get(symbol);
      if (row) this.sheet.open(row);
      if (!$("section.view.active")) this.#show(prefs.get("view"));
      return;
    }
    if (this.sheet.isOpen) this.sheet.close();
    this.#show(view || prefs.get("view"));
  }

  #show(id) {
    const view = this.views.find((v) => v.id === id) || this.views[0];
    $$("section.view").forEach((s) => s.classList.toggle("active", s.id === "view-" + view.id));
    $$("#tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.view === view.id)));
    prefs.set("view", view.id);
    view.onShow();
  }

  #renderUpdated() {
    const d = this.data;
    const short = d.generated_at_myt.replace(/^\w+ /, "").replace(/ \d{4},/, ",");
    $("#updated").innerHTML = `<span class="lbl">Updated<br></span><span title="${esc(d.generated_at_myt)}">${esc(short)}</span>${d.ageHours > 30 ? ' <span class="pill warn">stale</span>' : ""}`;
  }
}

// Refuse to run inside someone else's frame (clickjacking: a hidden overlay could
// capture the passphrase). GitHub Pages can't send X-Frame-Options, so do it here.
if (window.top !== window.self) {
  document.body.textContent = "This dashboard can't be shown inside another site.";
} else {
  new App().start();
}
