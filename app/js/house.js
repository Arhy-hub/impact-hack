// A simple drawing of the simulated house: three rooms, who's in each, and which are heating.
// Not a heatmap: a room is either heating (warm tint + flame) or not, with its temperature written in.
import { roomName } from "./format.js";
import { h } from "./ui.js";

const NS = "http://www.w3.org/2000/svg";
const el = (tag, attrs, text) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
};
// Ground floor: kitchen and living room; upstairs: bedroom.
const LAYOUT = { bedroom: [20, 70, 280, 90], kitchen: [20, 160, 110, 110], living: [130, 160, 170, 110] };

function person(x, y) {
  const g = el("g", { class: "person" });
  g.append(el("circle", { cx: x, cy: y, r: 5 }), el("rect", { x: x - 5, y: y + 7, width: 10, height: 14, rx: 5 }));
  return g;
}

export function houseView(state) {
  const svg = el("svg", { viewBox: "0 0 320 290", role: "img",
    "aria-label": state.rooms.map(r => `${roomName(r.name)} ${r.temp.toFixed(1)} degrees${r.occupied ? ", someone in" : ""}${r.heating ? ", heating" : ""}`).join("; ") });
  svg.append(el("path", { class: "roof", d: "M10 72 L160 12 L310 72" }));
  for (const r of state.rooms) {
    const [x, y, w, hgt] = LAYOUT[r.name] || [0, 0, 0, 0];
    svg.append(el("rect", { class: "room-box" + (r.heating ? " heating" : ""), x, y, width: w, height: hgt, rx: 6 }));
    svg.append(el("text", { class: "room-label", x: x + 10, y: y + 20 }, roomName(r.name)));
    svg.append(el("text", { class: "room-temp", x: x + 10, y: y + 46 }, `${r.temp.toFixed(1)}°`));
    svg.append(el("text", { class: "room-note", x: x + 10, y: y + hgt - 10 },
      r.heating ? "heating" : r.occupied ? "occupied" : "resting"));
    if (r.occupied) svg.append(person(x + w - 22, y + 14));
    if (r.heating) {
      const f = el("g", { transform: `translate(${x + w - (r.occupied ? 44 : 22)} ${y + hgt - 10})` });
      f.append(el("path", { class: "flame", d: "M0 0c5 0 8-3.4 8-7.8 0-4.5-3-7-4.8-10.4-.6 2.2-2 3.6-3.4 4.2.6-2.6-1-6.8-4.4-9.6.3 4.2-2.2 6.4-3.6 8.8C-9.6-12.6-8-9.8-8-7.8-8-3.4-5 0 0 0z" }));
      svg.append(f);
    }
  }
  return h("div", { class: "house" }, svg,
    h("div", { class: "legend" }, h("span", {}, "Person = someone's in the room"), h("span", {}, "Flame = heating now")));
}
