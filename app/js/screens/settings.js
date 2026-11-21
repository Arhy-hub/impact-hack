// Settings: look, calendar, comfort, and the demo clock.
import { api, store } from "../api.js";
import * as theme from "../theme.js";
import { button, card, empty, ghosts, h, haptic, heading, line, note, pill, seg, stepper } from "../ui.js";

export const title = "Settings";
let calendarMessage = null;
let playing = null;

function stopPlaying() { if (playing) { clearInterval(playing); playing = null; } }

function calendarCard(state) {
  if (state.calendar.source === "google") {
    return card(
      h("div", { class: "line" }, h("span", {}, "Google Calendar"), pill(null, "Connected", "calm")),
      note(`Reading ${state.calendar.events_this_week} events. Heatwise can only read your calendar, never change it.`),
      h("div", { style: "margin-top:12px" }, button("Disconnect", async () => { calendarMessage = null; await api.calendar(""); }, "danger")));
  }
  const input = h("input", { class: "field", type: "password", autocomplete: "off", spellcheck: "false",
    placeholder: "Paste your calendar's secret address", "aria-label": "Calendar secret address in iCal format" });
  const connect = async () => {
    const url = input.value.trim();
    if (!url) { calendarMessage = "Paste the secret address first."; return api.load(); }
    const res = await api.calendar(url);
    calendarMessage = res.ok ? null : res.message;
    if (res.ok) haptic();
  };
  input.addEventListener("keydown", e => { if (e.key === "Enter") connect(); });
  return card(
    h("div", { class: "line" }, h("span", {}, "Google Calendar"), pill(null, "Not connected")),
    h("p", { class: "note", style: "margin:4px 0 12px" },
      "Heatwise warms the house before you get home and rests it while you're away. In Google Calendar, open Settings, pick your calendar and copy the “Secret address in iCal format”."),
    input,
    calendarMessage ? note(calendarMessage, true) : null,
    h("div", { style: "margin-top:12px" }, button("Connect calendar", connect, "wide")));
}

export function render({ state, loading, error }) {
  if (loading && !state) return ghosts(4);
  if (error && !state) return empty({ iconName: "offline", title: "Can't load settings",
    message: "Check the Heatwise server is running, then try again.", actionLabel: "Try again", onAction: api.load });
  const toggle = () => {
    if (playing) { stopPlaying(); return api.load(); }
    playing = setInterval(async () => {
      const r = await api.tick(2);
      if (!r.ok || store.state?.finished) stopPlaying();
    }, 700);
    api.load();
  };
  return [
    h("div", { class: "top" }, h("h1", { class: "hello" }, "Settings")),
    heading("Look"),
    card(seg(theme.CHOICES, theme.saved(), choice => { theme.set(choice); api.load(); }, "Light or dark")),
    heading("Calendar"),
    calendarCard(state),
    heading("Comfort"),
    card(
      h("div", { class: "line" }, h("span", {}, "Comfy temperature"),
        stepper(state.comfort_c, { min: 16, max: 23, step: 0.5, onChange: v => api.comfort(v), label: "comfy temperature", format: v => `${v}°` })),
      note("Used in rooms you're in. Bedrooms cool to 17° overnight for better sleep.")),
    heading("Demo"),
    card(
      seg([{ id: "realtime", label: "Live" }, { id: "simulated", label: "Example week" }], state.mode,
        m => { stopPlaying(); api.mode(m); }, "Demo mode"),
      note(state.mode === "realtime"
        ? "Follows the real time and today's prices, with an example calendar."
        : "A made-up week you can fast-forward."),
      h("div", { style: "height:12px" }),
      line(state.mode === "realtime" ? "Time" : "Pretend time", state.finished ? `${state.clock} (end of week)` : state.clock),
      h("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin-top:12px" },
        button("+1 hour", () => api.tick(4), "soft", { disabled: state.finished || null }),
        button(playing ? "Pause" : "Play", toggle, "soft", { disabled: (state.finished && !playing) || null }),
        button("Start again", () => { stopPlaying(); api.reset(); }, "quiet")),
      note("The home and its people are simulated. Prices, grid carbon and weather are real.")),
  ];
}
