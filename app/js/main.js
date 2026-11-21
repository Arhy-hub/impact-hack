// App shell: tab bar (TabView), a navigation stack per tab, and rendering from the store.
import { api, store, subscribe } from "./api.js";
import { h, icon } from "./ui.js";
import * as theme from "./theme.js";
import * as home from "./screens/home.js";
import * as room from "./screens/room.js";
import * as budget from "./screens/budget.js";
import * as schedule from "./screens/schedule.js";
import * as settings from "./screens/settings.js";

const TABS = [
  { id: "home", label: "Home", icon: "home", screen: home },
  { id: "budget", label: "Budget", icon: "budget", screen: budget },
  { id: "schedule", label: "Plan", icon: "schedule", screen: schedule },
  { id: "settings", label: "Settings", icon: "settings", screen: settings },
];
const PUSHED = { room };

// Preview helpers for design review: ?theme=dark|light and ?text=xl (largest text size).
const params = new URLSearchParams(location.search);
theme.apply(params.get("theme") || theme.saved());
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => theme.apply(params.get("theme") || theme.saved()));
if (params.get("text") === "xl") document.documentElement.style.fontSize = "160%";

// Each tab keeps its own navigation stack, like a NavigationStack inside each TabView tab.
const nav = { tab: "home", stacks: Object.fromEntries(TABS.map(t => [t.id, []])) };
const stack = () => nav.stacks[nav.tab];
const scroll = {};
const view = document.getElementById("view");
const bar = document.getElementById("tabs");

nav.push = (screen, arg) => { scroll[key()] = window.scrollY; stack().push({ screen, arg }); draw(true); window.scrollTo(0, 0); };
nav.back = () => { stack().pop(); draw(); window.scrollTo(0, scroll[key()] || 0); };
const key = () => nav.tab + stack().map(s => `/${s.screen}:${s.arg}`).join("");

function selectTab(id) {
  if (id === nav.tab && stack().length) nav.stacks[id] = [];  // tapping the current tab pops to root, like iOS
  scroll[key()] = window.scrollY;
  nav.tab = id;
  draw();
  window.scrollTo(0, scroll[key()] || 0);
}

function draw(pushed = false) {
  const tab = TABS.find(t => t.id === nav.tab);
  const top = stack()[stack().length - 1];
  const content = top ? PUSHED[top.screen].render(store, nav, top.arg) : tab.screen.render(store, nav);
  const backBtn = top
    ? h("button", { class: "back", onclick: nav.back, "aria-label": `Back to ${tab.label}` }, icon("back", 20), tab.label)
    : null;
  const page = h("main", { class: pushed ? "enter" : "" }, backBtn, content);
  view.replaceChildren(page);
  document.title = `${tab.label} · Heatwise`;

  bar.replaceChildren(...TABS.map(t => h("button", {
    class: "tab", "aria-current": t.id === nav.tab ? "page" : null, onclick: () => selectTab(t.id),
  }, icon(t.icon, 24), t.label)));
}

// Preview deep links for screenshots and review: ?tab=budget, ?room=living
if (TABS.some(t => t.id === params.get("tab"))) nav.tab = params.get("tab");
if (params.get("room")) nav.stacks[nav.tab].push({ screen: "room", arg: params.get("room") });

subscribe(() => { const y = window.scrollY; draw(); window.scrollTo(0, y); });
draw();
api.load();
