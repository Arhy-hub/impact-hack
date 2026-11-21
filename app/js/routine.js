// The simulated household's routine, in words, next to what Heatwise did about it,
// so you can check the heating follows the people (DECISIONS D23).
import { roomName, time12 } from "./format.js";
import { PEOPLE, personName } from "./house.js";
import { card, h, heading } from "./ui.js";

const place = room => room ? roomName(room).toLowerCase().replace(/^living room$/, "living room") : "out";
const span = (a, b) => `${time12(a)}–${time12(b === "24:00" ? "00:00" : b)}`;
const dot = name => h("i", { class: `who ${PEOPLE[name] || "p0"}`, "aria-hidden": "true" });

// "Alex: bedroom until 7am, kitchen 7–7:45am, out, kitchen 6–7:30pm, ..."
function patternLine(name, blocks) {
  const parts = [];
  let last = "00:00";
  for (const b of blocks) {
    if (b.start !== last) parts.push(`out ${span(last, b.start)}`);
    parts.push(`${place(b.room)} ${b.start === "00:00" ? `until ${time12(b.end)}` : span(b.start, b.end)}`);
    last = b.end;
  }
  if (last !== "24:00") parts.push(`out from ${time12(last)}`);
  return h("p", { class: "routine-line" }, dot(name), h("b", {}, personName(name) + ": "), parts.join(", "));
}

// What Heatwise did for one visit, in plain words.
function response(v) {
  if (!v.room) return "Nobody's heating needed here.";
  if (v.target == null) return v.when === "later" ? "Coming up. Heatwise should warm the room just before." : "Before Heatwise started watching.";
  const held = v.since_before ? "already held there for 6+ hours"
    : v.held_from ? `held there from ${time12(v.held_from)}` : "set when they walked in";
  return `Target ${v.target}°, ${held}. ${v.temp}° on arrival ${v.warm ? "✓ warm" : "✗ still warming"}.`;
}

export function routineView(state) {
  const r = state.routine;
  if (!r) return [];
  const rows = r.today.filter(v => v.room || v.when !== "done");
  return [
    heading("The routine"),
    card(
      h("p", { class: "note", style: "margin-top:0" },
        `The usual ${r.day} pattern. Each block starts and ends up to ${r.jitter_min} minutes early or late, `
        + (r.day === "weekday" ? `and on ${Math.round(r.wfh_chance * 100)}% of weekdays someone works from home in the living room. ` : "")
        + "Heatwise never sees this timetable: it learns it from motion sensors and phones."),
      ...Object.entries(r.pattern).map(([name, blocks]) => patternLine(name, blocks))),
    heading("Today, step by step"),
    card(
      h("p", { class: "note", style: "margin-top:0" }, "What actually happened in the simulation today, and what Heatwise did. ✓ means the room was warm when they got there."),
      h("div", { class: "routine" }, rows.map(v => h("div", { class: `visit ${v.when}` },
        h("div", { class: "visit-time" }, span(v.start, v.end), v.when === "now" ? h("span", { class: "now-tag" }, "now") : null),
        h("div", { class: "visit-body" },
          h("div", { class: "visit-who" }, dot(v.person), `${personName(v.person)} · ${v.room ? roomName(v.room) : "Out"}`),
          v.room ? h("div", { class: "small muted" }, response(v)) : null))))),
  ];
}
