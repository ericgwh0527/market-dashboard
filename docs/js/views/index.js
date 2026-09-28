/** Tab registry – order here is the order of the tabs. Add a tab by adding a line. */
import { NewsView } from "./news.js";
import { OverviewView } from "./overview.js";
import { PortfolioView } from "./portfolio.js";
import { SignalsView } from "./signals.js";
import { WatchlistView } from "./watchlist.js";

export const createViews = () => [new OverviewView(), new WatchlistView(), new SignalsView(), new NewsView(), new PortfolioView()];
