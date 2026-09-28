/** DOM helpers. */
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/** Escape any untrusted text (news titles, names…) before putting it in HTML. */
export const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** Read a CSS custom property (theme token) from :root. */
export const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
