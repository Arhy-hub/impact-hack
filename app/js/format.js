// Formatting shared by screens. Sentence case, real units, no filler.

export const ROOM_NAMES = { living: "Living room", kitchen: "Kitchen", bedroom: "Bedroom" };
export const roomName = id => ROOM_NAMES[id] || id[0].toUpperCase() + id.slice(1);
export const temp = c => `${c.toFixed(1)}°`;
export const gbp = x => `£${x.toFixed(2)}`;

// Status line under a room name, e.g. "Heating · in use".
export function roomStatus(r) {
  const status = r.status.toLowerCase();
  return r.heating ? `Heating · ${status}` : r.status;
}

export const priceWord = { cheap: "cheap", normal: "normal", peak: "peak" };

// "Mon 16:00" -> "16:00" when it's today (same day prefix as now), else unchanged.
export function when(label, nowLabel) {
  return label.slice(0, 3) === nowLabel.slice(0, 3) ? label.slice(4) : label;
}
