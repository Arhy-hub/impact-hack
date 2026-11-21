// Plan: when will each room heat today, when is energy cheap, and what's in the calendar?
import { api } from "../api.js";
import { roomName, time12 } from "../format.js";
import { badge, card, empty, ghosts, h, heading, legend, note, strip } from "../ui.js";

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
  const labels = [at(0), at(12), at(23)];
  const spans = rs => rs.map(([a, b]) => `${at(a)}–${at(b)}`).join(", ");
  const cheap = runs(p.price, "cheap");

  return [
    h("div", { class: "top" }, h("div", {}, h("h1", { class: "hello" }, "Today's plan"), h("div", { class: "date" }, `Next 24 hours from ${time12(state.clock.slice(4))}`))),
    Object.entries(p.rooms).map(([name, cells]) => {
      const heat = runs(cells, "heat");
      return card(
        h("div", { class: "room-name" }, roomName(name)),
        h("div", { class: "note", style: "margin:2px 0 0" }, heat.length ? `Heats ${spans(heat)}` : "Resting all day"),
        strip(cells.map(c => (c === "heat" ? "heat" : c === "eco" ? "eco" : "")), labels, `${roomName(name)} heating plan`));
    }),
    legend([["linear-gradient(180deg,var(--accent-2),var(--accent))", "Heating"], ["var(--accent-mid)", "Kept mild"], ["var(--track)", "Resting"]]),
    heading("Cheapest times"),
    card(
      h("div", { style: "font-weight:700" }, cheap.length ? `Best for the washing machine: ${spans(cheap)}` : "No especially cheap times today"),
      strip(p.price.map(l => (l === "cheap" ? "cheap" : l === "peak" ? "eco" : "")), labels, "Electricity prices over the next 24 hours"),
      legend([["var(--calm)", "Cheap and clean"], ["var(--accent-mid)", "Pricey"]])),
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
