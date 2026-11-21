// Room: why is this room at this temperature, and when will it heat today?
import { deg, roomMood, roomName, time12 } from "../format.js";
import { api } from "../api.js";
import { button, card, empty, h, heading, lineChart, meter, note, stepper } from "../ui.js";

function nextHeating(cells, hours) {
  const start = cells.indexOf("heat");
  if (start < 0) return null;
  let end = start;
  while (end < cells.length && cells[end] === "heat") end++;
  const until = hours[end] ?? `${String((Number(hours[hours.length - 1].slice(0, 2)) + 1) % 24).padStart(2, "0")}:00`;
  return start === 0 ? `Heating now until ${time12(until)}` : `Next heating: ${time12(hours[start])} to ${time12(until)}`;
}

export function render({ state }, nav, roomId) {
  const r = state?.rooms.find(x => x.name === roomId);
  if (!r) return empty({ iconName: "home", title: "Room not found", actionLabel: "Back to Home", onAction: () => nav.back() });
  const p = state.plan, mood = roomMood(r);
  const cells = p.rooms[r.name];
  return [
    h("div", { class: "top" }, h("h1", { class: "hello" }, roomName(r.name))),
    h("section", { class: "hero", "aria-label": `${roomName(r.name)} is ${deg(r.temp)}. ${mood.text}` },
      h("div", { class: "label" }, mood.text),
      h("div", { class: "big" }, deg(r.temp)),
      h("div", { class: "say" }, `Aiming for ${r.target.toFixed(0)}°` +
        (r.warmup_min ? ` · takes about ${r.warmup_min >= 60 ? `${Math.floor(r.warmup_min / 60)}h ${r.warmup_min % 60}m` : `${r.warmup_min} min`} to warm up` : ""))),
    card(meter(r.temp, r.target, { heating: r.heating })),
    heading("Set this room"),
    card(
      h("div", { class: "line" }, h("span", {}, "Comfy temperature"),
        stepper(r.comfort, { min: 16, max: 23, step: 0.5, onChange: v => api.roomComfort(r.name, v), label: `${roomName(r.name)} temperature`, format: v => `${v}°` })),
      note(r.custom ? "This room has its own setting. Heatwise still only heats it when someone's likely to be in."
        : "Following the house setting. Change it to give this room its own temperature."),
      r.custom ? h("div", { style: "margin-top:8px" }, button("Use the house setting", () => api.roomComfort(r.name, null), "quiet")) : null),
    heading("Why?"),
    card(h("p", { style: "margin:0" }, r.why)),
    heading("Last 24 hours"),
    card(
      h("div", { style: "font-weight:700;margin-bottom:6px" }, nextHeating(cells, p.hours) || "No heating planned in the next 24 hours"),
      lineChart(state.history.labels.map(time12),
        [{ values: state.history[r.name].temp, colour: "var(--accent)", label: "Temperature" },
         { values: state.history[r.name].target, colour: "var(--muted)", dashed: true, label: "What Heatwise aimed for" }],
        { ariaLabel: `${roomName(r.name)} temperature over the last 24 hours` })),
    note("Based on when this room is usually used, your calendar and today's electricity prices."),
  ];
}
