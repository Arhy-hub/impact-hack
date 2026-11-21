// The simulated household's routine, in plain words, next to what Heatwise did about it,
// so you can check the heating follows the people (DECISIONS D23, D25).
import { roomName, time12 } from "./format.js";
import { PEOPLE, personName } from "./house.js";
import { card, h, heading } from "./ui.js";

const t12 = hhmm => time12(hhmm === "24:00" ? "00:00" : hhmm);
const lower = room => roomName(room).toLowerCase();
const dot = name => h("i", { class: `who ${PEOPLE[name] || "p0"}`, "aria-hidden": "true" });

// The usual day as a short list of moments: "7am Gets up, to the kitchen", "7:45am Leaves the house", ...
function moments(blocks) {
  const out = [];
  let prev = null, last = "00:00";
  for (const b of blocks) {
    if (b.start !== last) {  // a gap in the timetable = out of the house
      out.push([last, "Leaves the house"]);
      prev = null;
    }
    if (b.start !== "00:00") {
      const text = b.room === "bedroom" && b.end === "24:00" ? "Goes to bed"
        : prev === "bedroom" ? `Gets up, to the ${lower(b.room)}`
        : prev === null ? `Home, to the ${lower(b.room)}`
        : `Moves to the ${lower(b.room)}`;
      out.push([b.start, text]);
    }
    prev = b.room;
    last = b.end;
  }
  if (last !== "24:00") out.push([last, "Leaves the house"]);
  return out;
}

function personPattern(name, blocks) {
  return h("div", { class: "pattern" },
    h("div", { class: "visit-who" }, dot(name), personName(name)),
    h("div", { class: "moments" }, moments(blocks).map(([at, text]) =>
      h("div", { class: "moment" }, h("span", { class: "m-time" }, t12(at)), h("span", {}, text)))));
}

// "30 min later than usual", "Working from home", "Not in the usual routine". Shifts under 30 min are normal wobble.
function variation(v) {
  const u = v.vs_usual;
  if (!u) return null;
  if (u.unusual) return { text: u.wfh ? "Working from home" : "Not in the usual routine", tone: "off" };
  if (Math.abs(u.shift_min) < 30) return null;
  return { text: `${Math.abs(u.shift_min)} min ${u.shift_min > 0 ? "later" : "earlier"} than usual`, tone: "shift" };
}

// What Heatwise did for one visit, in one short line.
function response(v) {
  if (v.target == null) return v.when === "later" ? "Coming up" : "Before Heatwise started watching";
  const when = v.since_before ? ", held there for hours" : v.held_from ? `, heated from ${t12(v.held_from)}` : ", started when they walked in";
  return `${v.warm ? "✓ Warm" : "✗ Still warming"}: ${v.temp}° on arrival (aiming for ${v.target}°${when})`;
}

export function routineView(state) {
  const r = state.routine;
  if (!r) return [];
  // Short "out" gaps between two home blocks are just timing noise; hide them unless happening now.
  const mins = (a, b) => (Number(b.slice(0, 2)) * 60 + Number(b.slice(3))) - (Number(a.slice(0, 2)) * 60 + Number(a.slice(3)));
  const rows = r.today.filter(v => v.room || v.when === "now" || mins(v.start, v.end) >= 60);
  const changes = r.today.filter(v => v.room && variation(v) && v.when !== "later");
  return [
    heading(`A usual ${r.day}`),
    card(
      h("div", { class: "patterns" }, Object.entries(r.pattern).map(([name, blocks]) => personPattern(name, blocks))),
      h("p", { class: "note", style: "margin-bottom:0" },
        `Real days vary: times shift by up to ${r.jitter_min} minutes`
        + (r.day === "weekday" ? `, and on ${Math.round(r.wfh_chance * 100)}% of weekdays someone works from home` : "")
        + ". Heatwise never sees this timetable. It learns it from motion sensors and phones.")),
    heading("Today, step by step"),
    card(
      changes.length
        ? h("div", { class: "changes" }, h("b", {}, "Different from usual so far"),
            changes.map(v => h("div", { class: "change" }, dot(v.person),
              `${personName(v.person)}, ${lower(v.room)} ${t12(v.start)}: ${variation(v).text.toLowerCase()}. `,
              h("span", { class: "muted" }, v.warm == null ? "" : v.warm ? "Heatwise still had it warm." : "Heatwise caught up after they arrived."))))
        : h("p", { class: "note", style: "margin-top:0" }, "Nothing out of the ordinary so far today."),
      h("div", { class: "routine" }, rows.map(v => {
        const vary = v.room && variation(v);
        return h("div", { class: `visit ${v.when}` },
          h("div", { class: "visit-time" }, `${t12(v.start)}–${t12(v.end)}`, v.when === "now" ? h("span", { class: "now-tag" }, "now") : null),
          h("div", { class: "visit-body" },
            h("div", { class: "visit-who" }, dot(v.person), `${personName(v.person)} · ${v.room ? roomName(v.room) : "Out"}`,
              vary ? h("span", { class: `vary ${vary.tone}` }, vary.text) : null),
            v.room ? h("div", { class: "small muted" }, response(v)) : null));
      }))),
  ];
}
