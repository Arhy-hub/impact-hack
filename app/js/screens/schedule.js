// Plan: when will each room heat today, when is energy cheap, and what's in the calendar?
import { api } from "../api.js";
import { roomName, time12 } from "../format.js";
import { badge, card, empty, ghosts, h, heading, icon, note } from "../ui.js";

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
    h("div", { class: "top" }, h("div", {}, h("h1", { class: "hello" }, "Plan"), h("div", { class: "date" }, "Your week and what Heatwise will do"))),
    heading("This week"),
    // A simple agenda: every day of the week, with its events as coloured chips.
    card(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(day => {
      const evs = state.events.filter(e => e.day === day);
      const today = state.clock.startsWith(day);
      return h("div", { class: "event", style: today ? "background:var(--accent-soft);margin:0 -18px;padding:0 18px" : "" },
        h("div", { style: "min-width:48px;font-weight:800" + (today ? ";color:var(--accent)" : "") }, today ? "Today" : day),
        h("div", { style: "flex:1;display:flex;flex-wrap:wrap;gap:6px;padding:8px 0" }, evs.length
          ? evs.map(e => {
              const [ic, tone] = EVENT_ICON[e.kind] || ["calendar", ""];
              return h("span", { class: `pill ${tone}`, title: e.effect }, icon(ic, 14), `${e.title} · ${time12(e.start_label.slice(4))}`);
            })
          : h("span", { class: "note", style: "margin:0" }, "Nothing planned")));
    })),
    note("Away trips rest the house; working from home and guests keep rooms warm. Add events from the Demo tab."),
    heading("Heating, next 24 hours"),
    // One row per room: when it heats next (and after that), in plain words.
    card(Object.entries(p.rooms).map(([name, cells]) => {
      const rs = runs(cells, "heat");
      const when = rs.length ? rs.slice(0, 2).map(([a, b]) => `${at(a)}–${at(b)}`).join(" and ") : "Resting all day";
      const now = rs.length && rs[0][0] === 0;
      return h("div", { class: "event" }, badge(rs.length ? "flame" : "leaf", rs.length ? "hot" : "calm"),
        h("div", { style: "flex:1" }, h("div", { class: "t" }, roomName(name)),
          h("div", { class: "note", style: "margin:0" }, now ? `Heating now · ${when}` : rs.length ? `Warms ${when}` : when)));
    })),
    note("The rest of the time, rooms rest to save energy."),
    heading("Cheapest times"),
    card(h("div", { class: "event" }, badge("bolt", "calm"),
      h("span", {}, cheap.length ? `Run the washing machine or dishwasher at ${spans(cheap.slice(0, 2))}.` : "No especially cheap times today."))),
    state.calendar.source === "demo" ? note("This is an example week. Connect your own calendar in Settings.") : null,
  ];
}
