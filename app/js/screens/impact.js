// Impact: what Heatwise has saved compared with an ordinary heating timer, in plain words.
import { api } from "../api.js";
import { barChart, badge, card, empty, ghosts, h, heading, note } from "../ui.js";

export const title = "Impact";

export function render({ state, loading, error }) {
  if (loading && !state) return ghosts(3);
  if (error && !state) return empty({ iconName: "offline", title: "Can't load your impact", actionLabel: "Try again", onAction: api.load });
  const m = state.impact;
  const head = h("div", { class: "top" }, h("div", {}, h("h1", { class: "hello" }, "Your impact"), h("div", { class: "date" }, "Compared with an ordinary heating timer")));
  if (!m.ready) return [head, empty({ iconName: "leaf", title: "Nothing to show yet", message: "Let the week run for a bit (Demo tab), then check back." })];
  const km = Math.max(1, Math.round(m.saved_kg / 0.17));
  const phones = Math.max(1, Math.round((m.saved_kg / 0.2) * 1000 / 12));  // ~12 Wh a charge, grid ~0.2 kg/kWh
  const fact = (icon, tone, big, small) => card(h("div", { class: "fact" }, badge(icon, tone), h("div", {}, h("div", { class: "big-num" }, big), h("div", { class: "note", style: "margin:2px 0 0" }, small))));
  return [
    head,
    fact("budget", "hot", `£${Math.max(0, m.saved_gbp).toFixed(2)}`, "saved on your heating so far"),
    fact("leaf", "calm", `${Math.max(0, m.saved_kg).toFixed(1)} kg`, `less CO₂, like not driving ${km} km or charging your phone ${phones} times`),
    fact("bolt", "calm", `${m.clean_share}%`, "of your heat was bought in the cheaper, cleaner half of the day"),
    heading("CO₂ each day"),
    card(barChart(m.days.map(d => ({ label: d.day, values: [d.timer_kg, d.heatwise_kg] })), ["var(--faint)", "var(--calm)"],
      { ariaLabel: "CO2 per day, ordinary timer versus Heatwise", names: ["Ordinary timer", "Heatwise"] })),
    heading("Why it matters"),
    card(h("div", { class: "event" }, badge("home"), h("span", {}, "Most homes heat every room all day. Heating only the rooms you use is the biggest saving."))),
    card(h("div", { class: "event" }, badge("bolt", "calm"), h("span", {}, "Electricity is cleaner and cheaper at some hours. Heatwise stores warmth then, and eases off at the evening peak."))),
    card(h("div", { class: "event" }, badge("people", "hot"), h("span", {}, "About 4 million UK homes prepay for energy. Making each top-up go further keeps people warm."))),
    note("The house and people are simulated; prices, grid carbon and weather are real."),
  ];
}
