// Home: see each room's temperature and whether it's heating.
// Primary action: the Away switch.
import { api } from "../api.js";
import { priceWord, roomName, roomStatus, temp } from "../format.js";
import { h, largeTitle, placeholderSection, row, section, toggle, unavailable } from "../ui.js";

export const title = "Home";

export function render({ state, loading, error }, nav) {
  if (loading && !state) {
    return [largeTitle(title), placeholderSection(1, false), placeholderSection(3), placeholderSection(3)];
  }
  if (error && !state) {
    return unavailable({ iconName: "offline", title: "Can't reach your heating",
      message: "Check that the Heatwise server is running, then try again.", actionLabel: "Try again", onAction: api.load });
  }
  const s = state;
  if (!s.rooms.length) {
    return [largeTitle(title), unavailable({ iconName: "home", title: "No rooms yet",
      message: "Rooms appear here once their sensors are connected." })];
  }
  return [
    largeTitle(title),
    section({ footer: s.away ? "Every room is held at 12°C until you turn this off." : "Turn on when everyone leaves. Rooms drop to 12°C." },
      row({ title: "Away", trailing: toggle(s.away, on => api.away(on), "Away") })),
    section({ header: "Rooms" },
      s.rooms.map(r => row({
        title: roomName(r.name), sub: roomStatus(r), value: temp(r.temp), strong: true, chevron: true,
        label: `${roomName(r.name)}, ${temp(r.temp)}, ${roomStatus(r)}`,
        onClick: () => nav.push("room", r.name),
      }))),
    section({ header: "Right now", footer: s.tips[0] || null },
      row({ title: "Electricity", value: `${s.price_p.toFixed(0)}p/kWh · ${priceWord[s.price_level]}` }),
      row({ title: "Outside", value: `${s.outside_c.toFixed(1)}°C` }),
      row({ title: "Grid carbon", value: `${s.carbon_g} g/kWh` })),
  ];
}
