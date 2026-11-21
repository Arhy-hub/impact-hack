// Budget: am I on track this week? Primary action: Add money.
import { api, store } from "../api.js";
import { gbp } from "../format.js";
import { barChart, button, card, empty, ghosts, h, heading, line, note, ring, sheet, stepper } from "../ui.js";

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
    heading("Spent each day"),
    card(barChart(state.days.map(d => ({ label: d.day, values: [d.spent_gbp], highlight: d.today })), ["var(--accent)"],
      { refLine: state.limits.daily_gbp, unit: "£", ariaLabel: "Money spent on heating each day" })),
    heading("Your limits"),
    card(
      h("div", { class: "line" }, h("span", {}, "Weekly budget"),
        stepper(state.limits.weekly_gbp, { min: 5, max: 200, step: 5, onChange: v => api.limits({ weekly_gbp: v }), label: "weekly budget", format: v => `£${v}` })),
      h("div", { class: "line" }, h("span", {}, "Daily limit"),
        state.limits.daily_gbp == null
          ? button("Set a daily limit", () => api.limits({ daily_gbp: 3 }), "soft")
          : stepper(state.limits.daily_gbp, { min: 1, max: 10, step: 1, onChange: v => api.limits({ daily_gbp: v }), label: "daily limit", format: v => `£${v}` })),
      state.limits.daily_hit ? h("div", { class: "luke", style: "margin-top:12px" }, h("span", { class: "avatar", "aria-hidden": "true" }),
        h("div", { class: "bubble" }, h("div", {}, "You've hit today's limit. Shall I spend £2 more to keep you comfortable?"),
          h("div", { style: "display:flex;gap:8px;margin-top:8px" }, button("Allow £2", () => api.allow()), button("Keep saving", () => {}, "quiet")))) : null,
      note(`Heatwise never lets a room go below ${state.limits.floor_c}°, whatever the limits.` +
        (state.limits.daily_gbp != null ? ` Today so far: £${state.limits.today_spent_gbp.toFixed(2)}.` : "")),
      state.limits.daily_gbp != null ? h("div", { style: "margin-top:8px" }, button("Turn off daily limit", () => api.limits({ daily_off: true }), "quiet")) : null),
    heading("Save a bit more"),
    card(
      h("div", { class: "line" }, h("span", {}, "Turn every room down"),
        stepper(b.manual_trim, { min: 0, max: 3, onChange: v => api.trim(v), label: "turn every room down", format: v => `${v}°` })),
      note(b.auto_trim ? `Heatwise is already turning rooms down ${b.auto_trim}° to keep you on budget.`
        : "Each degree saves roughly 10% on heating.")),
    card(line("Paid with", b.supplier === "solvapay" ? "SolvaPay" : "SolvaPay (demo)")),
  ];
}
