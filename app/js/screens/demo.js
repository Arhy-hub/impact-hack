// Demo: everything needed to show Heatwise off in a couple of minutes.
// The mock calendar, a big Play button, jump to any day, and Luke's running commentary.
import { api, store } from "../api.js";
import { time12 } from "../format.js";
import { houseView } from "../house.js";
import { simView } from "../routine.js";
import { button, card, empty, ghosts, h, heading, icon, note, seg } from "../ui.js";

export const title = "Demo";
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const KINDS = [{ id: "away", label: "Away" }, { id: "wfh", label: "Working from home" }, { id: "guests", label: "Guests" }];
let playing = null, speed = 1, form = null;  // steps of 15 min per tick

function stop() { if (playing) { clearInterval(playing); playing = null; } }
function play() {
  if (playing) { stop(); return api.load(); }
  playing = setInterval(async () => {
    const r = await api.tick(speed);
    if (!r.ok || store.state?.finished) { stop(); api.load(); }
  }, 1500);
  api.load();
}

function addForm() {
  form = form || { title: "", kind: "guests", day: 5, start: 19, end: 23 };
  const t = h("input", { class: "field", value: form.title, placeholder: "e.g. Friends over", "aria-label": "Event name", maxlength: 60,
    oninput: e => { form.title = e.target.value; } });
  const num = (key, label) => h("label", { class: "small", style: "flex:1" }, label,
    h("input", { class: "field", type: "number", min: 0, max: 24, value: form[key], oninput: e => { form[key] = Number(e.target.value); } }));
  return card(
    h("div", { style: "font-weight:700;margin-bottom:8px" }, "Add something to the week"),
    t,
    h("div", { style: "margin-top:10px" }, seg(KINDS, form.kind, k => { form.kind = k; api.load(); }, "Event type")),
    h("div", { class: "days", style: "margin-top:10px" }, DAYS.map((d, i) => h("button", { class: form.day === i ? "on" : null,
      onclick: () => { form.day = i; api.load(); } }, d))),
    h("div", { style: "display:flex;gap:10px;margin-top:10px" }, num("start", "From (hour)"), num("end", "Until (hour)")),
    h("div", { style: "margin-top:12px" }, button("Add to the week", async () => {
      if (!form.title.trim()) return;
      const r = await api.addEvent({ title: form.title, kind: form.kind, day: form.day, start_h: form.start, end_h: Math.max(form.end, form.start + 1) });
      if (r.ok) form = null;
    }, "wide")));
}

export function render({ state, loading, error }) {
  if (loading && !state) return ghosts(3);
  if (error && !state) return empty({ iconName: "offline", title: "Can't reach Heatwise", actionLabel: "Try again", onAction: api.load });
  if (state.mode === "realtime") {
    return [h("div", { class: "top" }, h("h1", { class: "hello" }, "Demo")),
      empty({ iconName: "play", title: "You're in live mode", message: "Switch to the example week to play through a whole week in a minute.",
        actionLabel: "Use the example week", onAction: () => api.mode("simulated") }),
      simView(state, card(houseView(state)))];
  }
  const day = Math.floor(state.events.length >= 0 ? 0 : 0);
  return [
    h("div", { class: "top" }, h("div", {}, h("h1", { class: "hello" }, "Demo"), h("div", { class: "date" }, `Example week · ${state.clock.slice(0, 3)} ${time12(state.clock.slice(4))}`))),
    card(
      h("div", { style: "display:flex;gap:10px;align-items:center" },
        button([icon(playing ? "pause" : "play", 18), playing ? " Pause" : " Play the week"], play, "", { style: "flex:1" }),
        button("Restart", () => { stop(); api.reset(); }, "quiet")),
      h("div", { style: "margin-top:12px" }, seg([{ id: 1, label: "Slow" }, { id: 2, label: "Normal" }, { id: 8, label: "Fast" }].map(o => ({ ...o, id: String(o.id) })),
        String(speed), v => { speed = Number(v); api.load(); }, "Speed")),
      h("div", { class: "small muted", style: "margin:12px 0 6px" }, "Jump to"),
      h("div", { class: "days" }, DAYS.map((d, i) => button(d, () => { stop(); api.jump(i, 7); }, "quiet")))),
    simView(state, card(houseView(state))),
    heading("Luke's notes"),
    card(state.log.length
      ? h("div", { class: "feed" }, [...state.log].reverse().slice(0, 12).map(l => h("div", { class: `item ${l.kind}` },
          h("span", { class: "time" }, `${l.time.slice(0, 3)} ${time12(l.time.slice(4))}`), h("span", { class: "text" }, l.text))))
      : h("div", { class: "luke" }, h("span", { class: "avatar", "aria-hidden": "true" }), h("div", { class: "bubble" }, "Press Play and I'll tell you what I'm doing as the week goes by."))),
    heading("This week's calendar"),
    card(state.events.length ? state.events.map(e => h("div", { class: "event" },
      h("div", { style: "flex:1" }, h("div", { class: "t" }, e.title), h("div", { class: "note", style: "margin:0" }, `${e.start_label.slice(0, 3)} ${time12(e.start_label.slice(4))}`)),
      button("Remove", () => api.removeEvent(e.index), "danger")))
      : h("p", {}, "Nothing in the calendar.")),
    addForm(),
    note("The house and people are simulated. Prices, grid carbon and weather are real."),
  ];
}
