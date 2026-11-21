// Budget: know whether this week's spending stays within budget.
// Primary action: Top up (confirmation dialog, then SolvaPay).
import { api, store } from "../api.js";
import { gbp } from "../format.js";
import { action, actionSheet, h, largeTitle, placeholderSection, row, section, stepper, unavailable } from "../ui.js";

export const title = "Budget";

function topUp(state) {
  const choose = async pounds => {
    const res = await api.topup(pounds);
    // Local demo supplier: credit is added straight away. SolvaPay: pay at its checkout page.
    const result = store.state?.result;
    if (res.ok && result && !result.paid && result.checkout_url) window.open(result.checkout_url, "_blank", "noopener");
  };
  actionSheet("Add credit for this week. You'll pay with SolvaPay.",
    [5, 10, 20].map(p => ({ label: `Top up £${p}`, onSelect: () => choose(p) })));
}

export function render({ state, loading, error }) {
  if (loading && !state) return [largeTitle(title), placeholderSection(1, false), placeholderSection(4)];
  if (error && !state) return unavailable({ iconName: "offline", title: "Can't load your budget",
    message: "Check that the Heatwise server is running, then try again.", actionLabel: "Try again", onAction: api.load });

  const b = state.budget;
  const autoTrim = b.auto_trim, myTrim = b.manual_trim;
  const footer = b.needs_topup
    ? "Out of credit. Rooms are held at 12°C until you top up."
    : b.over_budget
      ? `Heading ${gbp(b.projected_gbp - b.budget_gbp)} over budget this week. Top up, or trim comfort below.`
      : "On track for this week.";
  const pct = Math.min(100, (100 * b.spent_gbp) / b.budget_gbp);
  return [
    largeTitle(title),
    section({ footer, footerWarning: b.needs_topup || b.over_budget },
      h("div", { class: "figure" },
        h("div", { class: "value" }, gbp(b.spent_gbp)),
        h("div", { class: "caption" }, `of ${gbp(b.budget_gbp)} this week`),
        h("div", { class: "progress", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": 100,
          "aria-valuenow": Math.round(pct), "aria-label": "Spent this week" }, h("span", { style: `width:${pct}%` }))),
      row({ title: "On track for", value: gbp(b.projected_gbp) }),
      b.credit_left_gbp != null ? row({ title: "Credit left", value: gbp(b.credit_left_gbp) }) : null,
      row({ title: "CO₂ this week", value: `${b.co2_kg.toFixed(1)} kg` }),
      action("Top up", () => topUp(state))),
    section({ header: "Comfort trim",
      footer: `Lowers every room's target to save money. Heatwise also trims on its own when the week is heading over budget${autoTrim ? ` (now ${autoTrim}°)` : ""}.` },
      row({ title: "Your trim", value: `${myTrim}°`,
        trailing: stepper(myTrim, { min: 0, max: 3, onChange: v => api.trim(v), label: "trim" }) })),
    section({ header: "Payments" },
      row({ title: "Paid with", value: b.supplier === "solvapay" ? "SolvaPay" : "SolvaPay (demo)" })),
  ];
}
