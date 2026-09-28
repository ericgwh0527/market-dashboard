import { prefs } from "./prefs.js";

/** Light/dark theme with an explicit override on top of the OS setting. */
export class ThemeController {
  #listeners = new Set();

  constructor(root = document.documentElement) {
    this.root = root;
    this.#apply(prefs.get("theme"));
  }

  get isDark() {
    const t = this.root.getAttribute("data-theme");
    return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  }

  toggle() {
    const next = this.isDark ? "light" : "dark";
    this.#apply(next);
    prefs.set("theme", next);
    this.#listeners.forEach((fn) => fn(next));
  }

  onChange(fn) { this.#listeners.add(fn); }

  #apply(t) {
    if (t) this.root.setAttribute("data-theme", t);
    else this.root.removeAttribute("data-theme");
  }
}
