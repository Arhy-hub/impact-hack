// Budget: am I on track this week? Primary action: Add money.
import { api, store } from "../api.js";
import { co2Like, gbp } from "../format.js";
import { badge, button, card, empty, ghosts, h, heading, line, note, ring, sheet, stepper } from "../ui.js";

export const title = "Budget";

function addMoney() {
  sheet("Add money", "Paid securely with SolvaPay. It's added to this week's heating budget.",
    [5, 10, 20].map(p => ({ label: `£${p}`, onSelect: async () => {
      const res = await api.topup(p);
      const result = store.state?.result;  // SolvaPay: finish paying on its checkout page
      if (res.ok && result && !result.paid && result.checkout_url) window.open(result.checkout_url, "_blank", "noopener");
    } })));
}

export function render({ state, loading, error }) {
  if (loading && !state) return ghosts(3);
  if (error && !state) return empty({ iconName: "offline", title: "Can't load your budget",
    message: "Check the Heatwise server is running, then try again.", actionLabel: "Try again", onAction: api.load });
  const b = state.budget;
  const over = b.projected_gbp - b.budget_gbp;
  const verdict = b.needs_topup
    ? h("div", { class: "status" }, "Out of money. Rooms are resting at 12° until you add some.")
    : over > 0
      ? h("div", { class: "status hot" }, `Heading ${gbp(over)} over`)
      : h("div", { class: "status calm" }, "On track");
  return [
    h("div", { class: "top" }, h("div", {}, h("h1", { class: "hello" }, "Budget"), h("div", { class: "date" }, "This week"))),
    card(
      h("div", { class: "ring-wrap" },
        ring(b.spent_gbp / b.budget_gbp, gbp(b.spent_gbp), `of ${gbp(b.budget_gbp)}`),
        h("div", {}, verdict,
          h("p", { class: "note" }, `By Sunday you'll have spent about ${gbp(b.projected_gbp)}.`),
          b.credit_left_gbp != null ? h("p", { class: "note" }, `${gbp(b.credit_left_gbp)} left to spend.`) : null)),
      h("div", { style: "margin-top:16px" }, button("Add money", addMoney, "wide"))),
    heading("Save a bit more"),
    card(
      h("div", { class: "line" }, h("span", {}, "Turn every room down"),
        stepper(b.manual_trim, { min: 0, max: 3, onChange: v => api.trim(v), label: "turn every room down", format: v => `${v}°` })),
      note(b.auto_trim ? `Heatwise is already turning rooms down ${b.auto_trim}° to keep you on budget.`
        : "Each degree saves roughly 10% on heating.")),
    heading("Your impact"),
    card(h("div", { class: "event" }, badge("leaf", "calm"),
      h("div", {}, h("div", { class: "t" }, `${b.co2_kg.toFixed(1)} kg CO₂ this week`), h("div", { class: "note", style: "margin:0" }, co2Like(b.co2_kg))))),
    card(line("Paid with", b.supplier === "solvapay" ? "SolvaPay" : "SolvaPay (demo)")),
  ];
}
