// Room: why is this room at this temperature, and when will it heat today?
import { deg, roomMood, roomName, time12 } from "../format.js";
import { card, empty, h, heading, legend, meter, note, strip } from "../ui.js";

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
  const labels = [time12(p.hours[0]), time12(p.hours[12]), time12(p.hours[23])];
  return [
    h("div", { class: "top" }, h("h1", { class: "hello" }, roomName(r.name))),
    h("section", { class: "hero", "aria-label": `${roomName(r.name)} is ${deg(r.temp)}. ${mood.text}` },
      h("div", { class: "label" }, mood.text),
      h("div", { class: "big" }, deg(r.temp)),
      h("div", { class: "say" }, `Aiming for ${r.target.toFixed(0)}°`)),
    card(meter(r.temp, r.target, { heating: r.heating })),
    heading("Why?"),
    card(h("p", { style: "margin:0" }, r.why)),
    heading("Today"),
    card(
      h("div", { style: "font-weight:700" }, nextHeating(cells, p.hours) || "No heating planned in the next 24 hours"),
      strip(cells.map(c => (c === "heat" ? "heat" : c === "eco" ? "eco" : "")), labels, `${roomName(r.name)} over the next 24 hours`),
      legend([["linear-gradient(180deg,var(--accent-2),var(--accent))", "Heating"], ["var(--accent-mid)", "Kept mild"], ["var(--track)", "Resting"]])),
    note("Based on when this room is usually used, your calendar and today's electricity prices."),
  ];
}
