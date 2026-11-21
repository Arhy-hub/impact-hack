// Home: how warm is my home, and what is it doing? Primary action: Away.
import { api } from "../api.js";
import { askCard } from "./ask.js";
import { PRICE, deg, greeting, roomMood, roomName, time12 } from "../format.js";
import { badge, card, empty, ghosts, h, heading, icon, meter, pill, toggle } from "../ui.js";

export const title = "Home";

function sentence(s) {
  if (s.away) return "Away mode is on. Every room is resting at 12° to save energy.";
  const heating = s.rooms.filter(r => r.heating).map(r => roomName(r.name).toLowerCase());
  const what = heating.length ? `Warming the ${heating.join(" and ")}.` : "Nothing needs heating right now.";
  const why = { peak: " Electricity is pricey, so we're keeping things gentle.",
    cheap: " Electricity is cheap, so we're storing a little extra warmth.", normal: "" }[s.price_level];
  return what + why;
}

export function render({ state, loading, error }, nav) {
  if (loading && !state) return ghosts(4);
  if (error && !state) return empty({ iconName: "offline", title: "Can't reach your heating",
    message: "Check the Heatwise server is running, then try again.", actionLabel: "Try again", onAction: api.load });
  const s = state;
  if (!s.rooms.length) return empty({ iconName: "home", title: "No rooms yet", message: "Rooms show up here once their sensors are connected." });

  const avg = s.rooms.reduce((sum, r) => sum + r.temp, 0) / s.rooms.length;
  const price = PRICE[s.price_level];
  const clean = s.carbon_g < 180;
  return [
    h("div", { class: "top" },
      h("div", {}, h("h1", { class: "hello" }, greeting(s.clock)), h("div", { class: "date" }, s.mode === "realtime"
        ? `Live · updated ${new Date().toLocaleTimeString("en-GB", { hour: "numeric", minute: "2-digit", hour12: true }).replace(" ", "")}`
        : `Example week · ${s.clock.slice(0, 3)} ${time12(s.clock.slice(4))}`)),
      toggle(s.away, on => api.away(on), "Away")),
    h("section", { class: "hero", "aria-label": `Inside ${deg(avg)}. ${sentence(s)}` },
      h("div", { class: "label" }, "Inside right now"),
      h("div", { class: "big" }, deg(avg)),
      h("div", { class: "say" }, sentence(s))),
    h("div", { class: "pills" },
      pill("bolt", `${price.text} · ${s.price_p.toFixed(0)}p`, price.tone),
      pill("thermo", `${s.outside_c.toFixed(0)}° outside`),
      pill("leaf", clean ? "Clean energy now" : "Busy grid now", clean ? "calm" : "")),
    heading("Ask Heatwise"),
    askCard(),
    heading("Your rooms"),
    s.rooms.map(r => {
      const mood = roomMood(r);
      return h("button", { class: "card tap", onclick: () => nav.push("room", r.name),
        "aria-label": `${roomName(r.name)}, ${deg(r.temp)}, ${mood.text}. Open details` },
        h("div", { class: "room-head" },
          h("div", {}, h("div", { class: "room-name" }, roomName(r.name)),
            h("div", { class: "status " + mood.tone }, icon(mood.icon, 16), mood.text)),
          h("div", { class: "room-temp" }, deg(r.temp))),
        meter(r.temp, r.target, { heating: r.heating }));
    }),
    s.tips[0] ? [heading("Tip"), card(h("div", { class: "event" }, badge("bulb", "calm"), h("span", {}, s.tips[0])))] : null,
  ];
}
