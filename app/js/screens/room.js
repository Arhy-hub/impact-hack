// Room: understand why this room is at its target. Read-only, no primary action.
import { roomName, temp } from "../format.js";
import { h, hero, largeTitle, section, unavailable } from "../ui.js";

const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs, text) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
};

// Bar chart of the planned target for each of the next 24 hours.
function planChart(hours, targets, kinds) {
  const W = 320, H = 126, top = 16, bottom = 20, lo = 12, hi = 22;
  const bw = W / targets.length;
  const y = t => top + (H - top - bottom) * (1 - (Math.min(hi, Math.max(lo, t)) - lo) / (hi - lo));
  const chart = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `Planned temperature for the next 24 hours, heating in ${kinds.filter(k => k === "heat").length} of them` });
  const defs = svg("defs", {});
  const grad = svg("linearGradient", { id: "heat", x1: 0, y1: 0, x2: 0, y2: 1 });
  grad.append(svg("stop", { offset: "0", class: "heat-top" }), svg("stop", { offset: "1", class: "heat-bottom" }));
  defs.append(grad);
  chart.append(defs);
  for (const t of [12, 17, 22]) chart.append(svg("line", { class: "grid", x1: 0, x2: W, y1: y(t), y2: y(t) }));
  targets.forEach((t, i) => chart.append(svg("rect", {
    class: "bar" + (kinds[i] === "heat" ? " on" : ""), x: i * bw + 1, width: bw - 2,
    y: y(t), height: Math.max(H - bottom - y(t), 1), rx: 2,
  })));
  // Axis labels last so bars never cover them; left side, like Health charts' leading axis.
  for (const t of [17, 22]) chart.append(svg("text", { class: "axis", x: 2, y: y(t) - 3 }, `${t}°`));
  hours.forEach((label, i) => { if (i % 6 === 0) chart.append(svg("text", { class: "axis", x: i * bw, y: H - 4 }, label)); });
  return h("div", { class: "chart" }, chart);
}

export function render({ state }, nav, roomId) {
  const r = state?.rooms.find(x => x.name === roomId);
  if (!r) return unavailable({ iconName: "home", title: "Room not found", message: "It may have been removed.",
    actionLabel: "Back to Home", onAction: () => nav.back() });
  const p = state.plan;
  return [
    largeTitle(roomName(r.name)),
    hero({ eyebrow: r.heating ? "Heating" : r.status, reading: temp(r.temp), label: `${roomName(r.name)} ${temp(r.temp)}, target ${temp(r.target)}`,
      detail: `Target ${temp(r.target)}` }),
    section({ header: "Why" }, h("div", { class: "text-cell" }, r.why)),
    section({ header: "Next 24 hours", footer: "Coloured hours are when it heats, based on your usual routine and today's electricity prices." },
      planChart(p.hours, p.targets[r.name], p.rooms[r.name])),
  ];
}
