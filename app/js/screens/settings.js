// Settings: connect the calendar and set comfort. A plain form that saves as you go.
import { api, store } from "../api.js";
import { action, h, haptic, largeTitle, placeholderSection, row, section, stepper, unavailable } from "../ui.js";

export const title = "Settings";
let calendarMessage = null;  // inline result of the last connect attempt
let playing = null;

function calendarSection(state) {
  const connected = state.calendar.source === "google";
  if (connected) {
    return section({ header: "Calendar", footer: `Reading ${state.calendar.events_this_week} events. Heatwise only reads your calendar.` },
      row({ title: "Google Calendar", value: "Connected" }),
      action("Disconnect", async () => { calendarMessage = null; await api.calendar(""); }, { destructive: true }));
  }
  const input = h("input", { class: "field", type: "password", autocomplete: "off", spellcheck: "false",
    placeholder: "Secret address in iCal format", "aria-label": "Secret address in iCal format" });
  const connect = async () => {
    const url = input.value.trim();
    if (!url) { calendarMessage = "Paste your calendar's secret address first."; return api.load(); }
    const res = await api.calendar(url);
    calendarMessage = res.ok ? null : res.message;
    if (res.ok) haptic();
  };
  input.addEventListener("keydown", e => { if (e.key === "Enter") connect(); });
  return section({
    header: "Calendar",
    footer: calendarMessage || "In Google Calendar, open Settings, choose your calendar, then copy “Secret address in iCal format”. Treat it like a password.",
    footerWarning: Boolean(calendarMessage),
  },
    row({ title: "Google Calendar", value: "Not connected" }),
    h("div", { class: "row" }, input),
    action("Connect", connect));
}

function demoSection(state) {
  const toggle = () => {
    if (playing) { clearInterval(playing); playing = null; return api.load(); }
    playing = setInterval(async () => {
      const r = await api.tick(2);
      if (!r.ok || store.state?.finished) { clearInterval(playing); playing = null; }
    }, 700);
    api.load();
  };
  return section({ header: "Demo", footer: "The home and its people are simulated. Electricity prices, grid carbon and weather are real." },
    row({ title: "Simulated time", value: state.finished ? `${state.clock} · end of week` : state.clock }),
    action("Advance 1 hour", () => api.tick(4), { disabled: state.finished }),
    action(playing ? "Pause" : "Play", toggle, { disabled: state.finished && !playing }),
    action("Restart week", () => { if (playing) { clearInterval(playing); playing = null; } api.reset(); }));
}

export function render({ state, loading, error }) {
  if (loading && !state) return [largeTitle(title), placeholderSection(2), placeholderSection(1), placeholderSection(3)];
  if (error && !state) return unavailable({ iconName: "offline", title: "Can't load settings",
    message: "Check that the Heatwise server is running, then try again.", actionLabel: "Try again", onAction: api.load });
  const c = state.comfort_c;
  return [
    largeTitle(title),
    calendarSection(state),
    section({ header: "Comfort", footer: "Used for rooms that are in use. Bedrooms stay at 17°C overnight." },
      row({ title: "Daytime", value: `${c}°C`,
        trailing: stepper(c, { min: 16, max: 23, step: 0.5, onChange: v => api.comfort(v), label: "daytime temperature" }) })),
    section({ header: "Budget", footer: "Add credit from the Budget tab." },
      row({ title: "This week", value: `£${state.budget.budget_gbp.toFixed(2)}` })),
    demoSection(state),
  ];
}
