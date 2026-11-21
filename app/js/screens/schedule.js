// Schedule: see what heating is planned and which calendar events affect it. No primary action.
import { api } from "../api.js";
import { roomName, when } from "../format.js";
import { largeTitle, placeholderSection, row, section, unavailable } from "../ui.js";

export const title = "Schedule";

// Contiguous runs of `match` in `cells` -> [{from, to}] as hour indices (to is exclusive).
function runs(cells, match) {
  const out = [];
  let start = null;
  cells.forEach((c, i) => {
    if (c === match && start === null) start = i;
    if ((c !== match || i === cells.length - 1) && start !== null) {
      out.push({ from: start, to: c === match ? i + 1 : i });
      start = null;
    }
  });
  return out;
}

const hourAt = (hours, i) => hours[i] ?? `${String((Number(hours[hours.length - 1].slice(0, 2)) + 1) % 24).padStart(2, "0")}:00`;

export function render({ state, loading, error }) {
  if (loading && !state) return [largeTitle(title), placeholderSection(3), placeholderSection(2)];
  if (error && !state) return unavailable({ iconName: "offline", title: "Can't load your schedule",
    message: "Check that the Heatwise server is running, then try again.", actionLabel: "Try again", onAction: api.load });

  const p = state.plan;
  const heating = Object.entries(p.rooms)
    .flatMap(([name, cells]) => runs(cells, "heat").map(r => ({ name, ...r })))
    .sort((a, b) => a.from - b.from);
  const cheap = runs(p.price, "cheap");
  const events = state.calendar.upcoming;
  const span = r => `${hourAt(p.hours, r.from)}–${hourAt(p.hours, r.to)}`;

  const out = [largeTitle(title)];
  out.push(heating.length
    ? section({ header: "Next 24 hours" }, heating.map(r => row({ title: roomName(r.name), sub: `Heating ${span(r)}` })))
    : section({ header: "Next 24 hours", footer: "Nothing needs heating in the next 24 hours." }, row({ title: "No heating planned" })));
  if (cheap.length) {
    out.push(section({ header: "Cheapest hours", footer: "Good times to run the dishwasher or washing machine." },
      cheap.map(r => row({ title: span(r) }))));
  }
  out.push(events.length
    ? section({ header: "From your calendar",
        footer: state.calendar.source === "demo" ? "This is a demo week. Connect your calendar in Settings." : null },
      events.map(e => row({ title: e.title, sub: e.effect,
        value: e.now ? "Now" : `${when(e.start, state.clock)}` })))
    : unavailable({ iconName: "calendarEmpty", title: "Nothing on your calendar",
        message: "Events like trips, working from home or guests will change your heating here." }));
  return out;
}
