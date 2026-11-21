// Friendly building blocks. Text is always set with textContent (never innerHTML).

export function h(tag, props = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "style") e.style.cssText = v;
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) e.append(kid.nodeType ? kid : String(kid));
  return e;
}

const NS = "http://www.w3.org/2000/svg";
const svgEl = (tag, attrs) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
};

// ---------- Icons: one rounded outline set, one weight ----------
const PATHS = {
  home: "M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1z",
  budget: "M15.5 7.5a3.5 3.5 0 0 0-6.5 1.8V12m0 0v3.5c0 1.5-.8 2.5-2 3h10M7 12h6",
  schedule: "M7 3.5v3M17 3.5v3M4.5 9.5h15M5.5 5.5h13a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1z",
  settings: "M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4",
  back: "M14.5 5.5 8 12l6.5 6.5",
  minus: "M6 12h12",
  plus: "M12 6v12M6 12h12",
  flame: "M12 21c3.6 0 6-2.4 6-5.6 0-3.2-2.2-5-3.4-7.4-.4 1.6-1.4 2.6-2.4 3C12.6 8 11.4 5 9 3c.2 3-1.6 4.6-2.6 6.3C5.6 10.7 6 12 6 15.4 6 18.6 8.4 21 12 21z",
  leaf: "M5 19c0-8 5-13 14-14-1 9-6 14-14 14zM5 19l7-7",
  bolt: "M13 3 5 13.5h6L10 21l9-11h-6z",
  thermo: "M10 14.5V5a2 2 0 1 1 4 0v9.5a4 4 0 1 1-4 0zM12 9v7",
  plane: "M3 13.5l7-2.5L6.5 4H9l6 6.5 4-1.5a1.5 1.5 0 0 1 1 2.8L5 17l-2-3.5z",
  laptop: "M5 6h14v9H5zM3 18h18",
  people: "M8.5 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 19c0-3 2.5-5 5.5-5s5.5 2 5.5 5M16 11a2.5 2.5 0 1 0 0-5M17.5 14c2 .4 3.5 2 3.5 5",
  calendar: "M7 3.5v3M17 3.5v3M4.5 9.5h15M5.5 5.5h13a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1z",
  bulb: "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z",
  offline: "M3 3l18 18M8.5 16.5a5 5 0 0 1 7 0M5 13a10 10 0 0 1 4-2.4M19 13a10 10 0 0 0-2.6-1.8M12 20h.01",
};
export function icon(name, size = 22, label = null) {
  const svg = svgEl("svg", { viewBox: "0 0 24 24", width: size, height: size, fill: "none", stroke: "currentColor",
    "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round" });
  if (label) { svg.setAttribute("role", "img"); svg.setAttribute("aria-label", label); } else svg.setAttribute("aria-hidden", "true");
  svg.append(svgEl("path", { d: PATHS[name] }));
  return svg;
}

export const haptic = () => { try { navigator.vibrate?.(8); } catch { /* unsupported */ } };

// ---------- Layout ----------
export const card = (...kids) => h("div", { class: "card" }, kids);
export const heading = text => h("h2", { class: "h2" }, text);
export const note = (text, warn = false) => (text ? h("p", { class: "note" + (warn ? " warn" : "") }, text) : null);
export const line = (label, value) => h("div", { class: "line" }, h("span", {}, label), h("span", { class: "v" }, value));
export const badge = (name, tone = "") => h("span", { class: "icon-badge " + tone }, icon(name, 20));
export const pill = (iconName, text, tone = "") => h("span", { class: "pill " + tone }, iconName ? icon(iconName, 16) : null, text);

// ---------- Visuals ----------

// Temperature bar from `min` to `max`: filled to the current temperature, a marker at the target.
export function meter(current, target, { min = 12, max = 24, heating = false } = {}) {
  const pos = t => `${(100 * (Math.min(max, Math.max(min, t)) - min)) / (max - min)}%`;
  return h("div", { class: "meter", role: "img", "aria-label": `Now ${current.toFixed(1)} degrees, aiming for ${target.toFixed(0)}` },
    h("div", { class: "track" },
      h("div", { class: "fill" + (heating ? "" : " cool"), style: `width:${pos(current)}` }),
      h("div", { class: "target", style: `left:${pos(target)}` })),
    h("div", { class: "scale" }, h("span", {}, `${min}°`), h("span", {}, `aiming for ${target.toFixed(0)}°`), h("span", {}, `${max}°`)));
}

// Donut showing the share of the budget used.
export function ring(fraction, big, small) {
  const r = 52, c = 2 * Math.PI * r, f = Math.max(0, Math.min(1, fraction));
  const svg = svgEl("svg", { viewBox: "0 0 128 128" });
  const grad = svgEl("linearGradient", { id: "ringGrad", x1: 0, y1: 0, x2: 1, y2: 1 });
  grad.append(svgEl("stop", { offset: 0, class: "ring-stop-a" }), svgEl("stop", { offset: 1, class: "ring-stop-b" }));
  const defs = svgEl("defs", {});
  defs.append(grad);
  svg.append(defs,
    svgEl("circle", { class: "track", cx: 64, cy: 64, r, fill: "none", "stroke-width": 14 }),
    svgEl("circle", { class: "used", cx: 64, cy: 64, r, fill: "none", "stroke-width": 14, "stroke-linecap": "round",
      "stroke-dasharray": `${Math.max(f * c, 0.01)} ${c}` }));
  return h("div", { class: "ring", role: "img", "aria-label": `${big} ${small}` }, svg,
    h("div", { class: "center" }, h("div", {}, h("b", {}, big), h("span", {}, small))));
}

// 24 hourly blocks with labels under them.
export function strip(cells, labels, ariaLabel) {
  return h("div", { role: "img", "aria-label": ariaLabel },
    h("div", { class: "strip" }, cells.map(c => h("i", { class: c }))),
    h("div", { class: "strip-labels" }, labels.map(l => h("span", {}, l))));
}

export function legend(items) {
  return h("div", { class: "legend" }, items.map(([colour, text]) => h("span", {}, h("i", { style: `background:${colour}` }), text)));
}

// ---------- Controls ----------
export function toggle(on, onChange, label) {
  return h("button", { class: "toggle", "aria-pressed": String(on), onclick: () => { haptic(); onChange(!on); } },
    label, h("span", { class: "knob", "aria-hidden": "true" }));
}

export function stepper(value, { min, max, step = 1, onChange, label, format = v => v }) {
  const b = (name, delta, text) => h("button", { type: "button", "aria-label": `${text} ${label}`,
    disabled: (delta < 0 ? value <= min : value >= max) || null,
    onclick: () => { haptic(); onChange(Math.min(max, Math.max(min, value + delta))); } }, icon(name, 18));
  return h("div", { class: "stepper", role: "group", "aria-label": label },
    b("minus", -step, "Lower"), h("b", { "aria-live": "polite" }, format(value)), b("plus", step, "Raise"));
}

export function seg(options, selected, onChange, label) {
  return h("div", { class: "seg", role: "radiogroup", "aria-label": label },
    options.map(o => h("button", { type: "button", role: "radio", "aria-checked": String(o.id === selected), class: o.id === selected ? "on" : null,
      onclick: () => { if (o.id !== selected) { haptic(); onChange(o.id); } } }, o.label)));
}

export function button(text, onClick, kind = "", extra = {}) {
  return h("button", { class: `btn ${kind}`, onclick: onClick, ...extra }, text);
}

// Bottom sheet with a few big choices.
export function sheet(title, subtitle, choices) {
  const close = () => scrim.remove();
  const scrim = h("div", { class: "scrim", onclick: e => { if (e.target === scrim) close(); } },
    h("div", { class: "sheet", role: "dialog", "aria-label": title },
      h("h3", {}, title), h("p", { class: "note", style: "margin:0" }, subtitle),
      h("div", { class: "choices" }, choices.map(c => button(c.label, () => { close(); haptic(); c.onSelect(); }, "soft"))),
      button("Not now", close, "quiet wide")));
  scrim.addEventListener("keydown", e => { if (e.key === "Escape") close(); });
  document.body.append(scrim);
  scrim.querySelector("button").focus();
}

// ---------- Empty, error, loading ----------
export function empty({ iconName, title, message, actionLabel, onAction }) {
  return h("div", { class: "empty", role: "status" }, badge(iconName), h("h3", {}, title), message ? h("p", {}, message) : null,
    actionLabel ? button(actionLabel, onAction, "soft") : null);
}
export const ghosts = n => Array.from({ length: n }, () => h("div", { class: "ghost-card", "aria-hidden": "true" }));
