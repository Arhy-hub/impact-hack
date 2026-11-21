// Luke, the helper agent: ask a question or request; any change needs a tap to confirm.
import { api, store } from "../api.js";
import { button, card, h, haptic } from "../ui.js";

let last = null;  // { q, reply, action, done }

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
      button("Yes, do it", async () => { haptic(); last.done = true; await api.confirm(last.action); last.reply = "Done!"; api.load(); }),
      button("No thanks", () => { last = null; api.load(); }, "quiet")) : null);
  const intro = h("div", { class: "luke", style: "margin-bottom:12px" }, h("span", { class: "avatar", "aria-hidden": "true" }, "L"),
    h("div", { class: "bubble" }, "Hi, I'm Luke. I look after your heating. Ask me anything, or tell me what you need."));
  return card(intro, h("div", { style: "display:flex;gap:8px" }, input, button("Ask", go, "soft")), answer);
}
