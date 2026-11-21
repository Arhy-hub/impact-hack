// Plan: when will each room heat today, when is energy cheap, and what's in the calendar?
import { api } from "../api.js";
import { roomName, time12 } from "../format.js";
import { badge, card, empty, ghosts, h, heading, note } from "../ui.js";

export const title = "Plan";

function runs(cells, match) {
  const out = [];
  let start = null;
  cells.forEach((c, i) => {
    if (c === match && start === null) start = i;
    if ((c !== match || i === cells.length - 1) && start !== null) { out.push([start, c === match ? i + 1 : i]); start = null; }
  });
  return out;
}

const EVENT_ICON = { away: ["plane", "calm"], wfh: ["laptop", "hot"], guests: ["people", "hot"] };

export function render({ state, loading, error }) {
  if (loading && !state) return ghosts(4);
  if (error && !state) return empty({ iconName: "offline", title: "Can't load the plan",
    message: "Check the Heatwise server is running, then try again.", actionLabel: "Try again", onAction: api.load });
  const p = state.plan;
  const at = i => time12(p.hours[i] ?? `${String((Number(p.hours[p.hours.length - 1].slice(0, 2)) + 1) % 24).padStart(2, "0")}:00`);
  const spans = rs => rs.map(([a, b]) => `${at(a)}–${at(b)}`).join(", ");
  const cheap = runs(p.price, "cheap");

  return [
    h("div", { class: "top" }, h("div", {}, h("h1", { class: "hello" }, "Today's plan"), h("div", { class: "date" }, `Next 24 hours from ${time12(state.clock.slice(4))}`))),
    // A plain, time-ordered list: when each room heats. No charts.
    (() => {
      const rows = Object.entries(p.rooms)
        .flatMap(([name, cells]) => runs(cells, "heat").map(([a, b]) => ({ name, a, b })))
        .sort((x, y) => x.a - y.a);
      return card(rows.length
        ? rows.map(r => h("div", { class: "event" }, badge("flame", "hot"),
            h("div", { style: "flex:1" }, h("div", { class: "t" }, roomName(r.name)), h("div", { class: "note", style: "margin:0" }, r.a === 0 ? "Heating now" : "Warms up")),
            h("div", { class: "t" }, `${at(r.a)}–${at(r.b)}`)))
        : h("p", { style: "margin:0" }, "Nothing needs heating in the next 24 hours."));
    })(),
    note("Any room not listed rests to save energy."),
    heading("Cheapest times"),
    card(h("div", { class: "event" }, badge("bolt", "calm"),
      h("span", {}, cheap.length ? `Run the washing machine or dishwasher at ${spans(cheap.slice(0, 2))}.` : "No especially cheap times today."))),
    heading("From your calendar"),
    state.calendar.upcoming.length
      ? card(state.calendar.upcoming.map(e => {
          const [ic, tone] = EVENT_ICON[e.kind] || ["calendar", ""];
          return h("div", { class: "event" }, badge(ic, tone),
            h("div", { style: "flex:1" }, h("div", { class: "t" }, e.title), h("div", { class: "note", style: "margin:0" }, e.effect)),
            h("div", { class: "small muted" }, e.now ? "Now" : time12(e.start)));
        }))
      : empty({ iconName: "calendar", title: "Nothing coming up", message: "Trips, working from home and guests will change your heating here." }),
    state.calendar.source === "demo" ? note("This is an example week. Connect your own calendar in Settings.") : null,
  ];
}
