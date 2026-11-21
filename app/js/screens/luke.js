// Luke, the helper agent: ask a question or request; any change needs a tap to confirm.
import { api, store } from "../api.js";
import { button, card, h, haptic } from "../ui.js";

let last = null;  // { q, reply, action, done }

const ROOM_LABEL = { living: "living room" };
function doneText(a) {
  if (a.type === "room") {
    const name = ROOM_LABEL[a.room] || a.room, r = store.state?.rooms?.find(x => x.name === a.room);
    const now = r && r.target < a.value ? ` Right now it's aiming for ${r.target}° because of your budget trim.` : "";
    const m = r?.warmup_min, hrs = m >= 90 ? Math.round(m / 30) / 2 : 0;
    const eta = m > 0 ? ` It should be there in about ${hrs ? `${hrs} hours` : `${m} minutes`}.` : "";
    return `Done! The ${name} is set to ${a.value}°.${now}${eta}`;
  }
  if (a.type === "comfort") return `Done! Rooms in use are set to ${a.value}°. You'll see them warm up over the next hour or so.`;
  if (a.type === "away") return a.value ? "Done! Away mode is on." : "Done! Away mode is off.";
  return `Done! Comfort trim is now ${a.value}°.`;
}

async function send(text) {
  last = { q: text, reply: "Thinking…", action: null };
  store.loading = false; api.load();
  try {
    const r = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    const d = await r.json();
    last = r.ok ? { q: text, reply: d.reply, action: d.action } : { q: text, reply: "Sorry, I couldn't understand that." };
  } catch { last = { q: text, reply: "I can't reach your heating right now." }; }
  api.load();
}

export function lukeCard() {
  const input = h("input", { class: "field", placeholder: "e.g. I'm cold", "aria-label": "Ask Luke", maxlength: 500 });
  const go = () => { const t = input.value.trim(); if (t) send(t); };
  input.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
  const answer = last && h("div", { style: "margin-top:12px" },
    h("p", { class: "note", style: "margin:0" }, `You: ${last.q}`),
    h("p", { style: "margin:6px 0 0;font-weight:600" }, `Luke: ${last.reply}`),
    last.action && !last.done ? h("div", { style: "display:flex;gap:8px;margin-top:10px" },
      button("Yes, do it", async () => { haptic(); last.done = true; const r = await api.confirm(last.action); last.reply = r?.ok ? doneText(last.action) : "Sorry, I couldn't make that change."; api.load(); }),
      button("No thanks", () => { last = null; api.load(); }, "quiet")) : null);
  const intro = h("div", { class: "luke", style: "margin-bottom:12px" }, h("span", { class: "avatar", "aria-hidden": "true" }),
    h("div", { class: "bubble" }, "Hi, I'm Luke. I look after your heating. Ask me anything, or tell me what you need."));
  return card(intro, h("div", { style: "display:flex;gap:8px" }, input, button("Ask", go, "soft")), answer);
}
