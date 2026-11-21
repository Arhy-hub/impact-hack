// Luke as a helper you hand the heating to: repairs, your rules, and his weekly report (DECISIONS D27, D28).
import { api } from "./api.js";
import { gbp, roomName, time12 } from "./format.js";
import { button, card, h, heading, line, note, stepper } from "./ui.js";

const when = label => label ? `${label.slice(0, 3)} ${time12(label.slice(4))}` : "";
const luke = (...kids) => h("div", { class: "luke" }, h("span", { class: "avatar", "aria-hidden": "true" }), h("div", { class: "bubble" }, kids));

// Home: Luke's repair message for any open problem (found or booked), or the last fix.
export function repairCard(state) {
  const rep = state.repairs;
  if (!rep) return null;
  const open = rep.issues.filter(i => i.status === "found" || i.status === "booked");
  const lastFixed = [...rep.issues].reverse().find(i => i.status === "fixed");
  if (!open.length && !lastFixed) return null;
  return [heading("Repairs"), open.map(i => card(i.status === "found"
    ? luke(
        h("div", {}, h("b", {}, `${roomName(i.room)} radiator: `),
          `it warmed +${i.actual_c}° in 2 hours when it should have warmed +${i.expected_c}°. The valve may be stuck, so you're paying for heat the room isn't getting.`),
        h("div", { class: "small muted", style: "margin-top:6px" }, `${rep.company} can fix it for ${gbp(i.quote_gbp)}. You have ${gbp(rep.left_gbp)} left for repairs.`),
        h("div", { style: "display:flex;gap:8px;margin-top:10px;flex-wrap:wrap" },
          button(`Book engineer · ${gbp(i.quote_gbp)}`, () => api.repair(i.id, "book")),
          button("Not now", () => api.repair(i.id, "dismiss"), "quiet")))
    : luke(h("div", {}, h("b", {}, `${roomName(i.room)} radiator: `),
        `engineer booked for ${when(i.visit)}. Paid ${gbp(i.quote_gbp)} from your repairs allowance (${gbp(rep.left_gbp)} left).`)))),
  !open.length && lastFixed ? card(luke(h("div", {}, h("b", {}, `${roomName(lastFixed.room)} radiator fixed `),
    `on ${when(lastFixed.visit)}. It's warming normally again.`))) : null];
}

// Home: Luke's week in a few numbers.
export function reportCard(state) {
  const r = state.report;
  if (!r) return null;
  const saved = r.saved_gbp == null ? "" : r.saved_gbp >= 0 ? `${gbp(r.saved_gbp)} cheaper than a timer` : "about the same as a timer so far";
  return [heading("Luke's week"), card(
    line("Spent on heating", `${gbp(r.spent_gbp)} of ${gbp(r.budget_gbp)}`),
    saved ? line("Compared with a timer", saved) : null,
    r.saved_kg != null && r.saved_kg > 0 ? line("Less CO₂", `${r.saved_kg.toFixed(1)} kg`) : null,
    line("Problems", r.open ? `${r.open} being handled` : r.fixed ? `${r.fixed} fixed (${gbp(r.repairs_gbp)})` : "None found"),
    note("You set the rules and the money. Luke does the rest."))];
}

// Budget: everything Luke works within, in one place.
export function rulesCard(state) {
  const r = state.rules, rep = state.repairs;
  if (!r) return null;
  return [heading("Your rules for Luke"), card(
    line("Heating money", `${gbp(r.weekly_gbp)} a week`),
    line("Daily limit", r.daily_gbp == null ? "None" : `${gbp(r.daily_gbp)} a day`),
    line("Rooms you're in", `${r.comfort_c}°`),
    line("Bedroom at night", `${r.sleep_c}°`),
    line("Never below", `${r.floor_c}°`),
    h("div", { class: "line" }, h("span", {}, "Repairs allowance"),
      stepper(r.repairs_gbp, { min: 0, max: 500, step: 25, onChange: v => api.repairsAllowance(v), label: "repairs allowance", format: v => `£${v}` })),
    note(rep ? `${gbp(rep.spent_gbp)} spent on repairs. Luke always asks before booking one.` : null))];
}

// Demo: break a radiator so Luke has something to spot.
export function breakCard(state) {
  const broken = new Set((state.repairs?.issues || []).filter(i => i.status !== "fixed" && i.status !== "dismissed").map(i => i.room));
  return [heading("Break something"), card(
    h("p", { class: "note", style: "margin-top:0" }, "Stick a radiator valve so the room only gets a fifth of its heat. Keep playing: Luke should notice within about 2 hours of house time and offer a repair."),
    h("div", { style: "display:flex;gap:8px;flex-wrap:wrap" }, state.rooms.map(r =>
      button(`Break ${roomName(r.name).toLowerCase()}`, () => api.breakRoom(r.name), "quiet", broken.has(r.name) ? { disabled: true } : {}))))];
}
