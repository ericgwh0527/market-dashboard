/**
 * Base class every tab extends. The app only talks to this interface, so adding a
 * tab = write a subclass + add it to views/index.js (nothing else changes).
 *
 *   id / label / icon   tab identity
 *   template()          static markup for the tab's <section>
 *   init(ctx)           once, after the section exists: wire up the tab's own controls
 *   render(data)        every time market data (MarketData) is (re)loaded
 *   onShow()            the tab became visible
 *   onThemeChange()     colours changed (re-draw canvases)
 */
export class View {
  id = "";
  label = "";
  icon = "";
  template() { return ""; }
  init(ctx) { this.ctx = ctx; this.section = ctx.section; }
  render(_data) {}
  onShow() {}
  onThemeChange() {}
}
