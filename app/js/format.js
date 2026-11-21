// Plain-English wording and number formats shared by screens.

export const ROOM_NAMES = { living: "Living room", kitchen: "Kitchen", bedroom: "Bedroom" };
export const roomName = id => ROOM_NAMES[id] || id[0].toUpperCase() + id.slice(1);
export const deg = c => `${c.toFixed(1)}°`;
export const gbp = x => `£${x.toFixed(2)}`;

// "18:00" -> "6pm", "18:30" -> "6:30pm", "Mon 18:00" -> "Mon 6pm"
export function time12(label) {
  const m = /(?:(\w{3}) )?(\d{2}):(\d{2})/.exec(label);
  if (!m) return label;
  const [, day, hh, mm] = m;
  const h = Number(hh), suffix = h < 12 ? "am" : "pm", h12 = h % 12 || 12;
  const t = mm === "00" ? `${h12}${suffix}` : `${h12}:${mm}${suffix}`;
  return day ? `${day} ${t}` : t;
}

// A friendly status for a room: what it's doing, in a few words, and a tone for colour.
export function roomMood(r) {
  if (r.status === "Away" || r.status === "Away mode") return { text: "Away, resting at 12°", tone: "calm", icon: "leaf" };
  if (r.status === "No credit") return { text: "Paused until you top up", tone: "", icon: "bolt" };
  if (r.heating) return { text: r.target > r.temp + 0.3 ? `Warming up to ${r.target.toFixed(0)}°` : "Keeping you cosy", tone: "hot", icon: "flame" };
  if (r.status === "Saving" || r.status === "Eco") return { text: "Resting to save energy", tone: "calm", icon: "leaf" };
  if (r.status === "Welcome home") return { text: "Warming up for your return", tone: "hot", icon: "flame" };
  return { text: "Just right", tone: "", icon: "thermo" };
}

// The price right now, as a traffic light.
export const PRICE = {
  cheap: { text: "Cheap now", tone: "calm" },
  normal: { text: "Normal price", tone: "" },
  peak: { text: "Pricey now", tone: "hot" },
};

// CO2 in kg -> something you can picture (average UK car, about 0.17 kg per km).
export const co2Like = kg => `about the same as driving ${Math.max(1, Math.round(kg / 0.17))} km`;

export function greeting(clock) {
  const h = Number(clock.slice(4, 6));
  return h < 5 ? "Good evening" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}
