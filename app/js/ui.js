// Shared UI building blocks, modelled on iOS components.
// Text is always set with textContent (never innerHTML), so data can't inject markup.

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

// ---------- Icons: one outline set, one weight (1.75), drawn for this app ----------
const NS = "http://www.w3.org/2000/svg";
const PATHS = {
  home: "M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1z",
  budget: "M15.5 7.5a3.5 3.5 0 0 0-6.5 1.8V12m0 0v3.5c0 1.5-.8 2.5-2 3h10M7 12h6",
  schedule: "M7 3.5v3M17 3.5v3M4.5 9.5h15M5.5 5.5h13a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1z",
  settings: "M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4",
  chevronRight: "M9.5 6l6 6-6 6",
  chevronLeft: "M14.5 5.5 8 12l6.5 6.5",
  minus: "M6 12h12",
  plus: "M12 6v12M6 12h12",
  offline: "M3 3l18 18M8.5 16.5a5 5 0 0 1 7 0M5 13a10 10 0 0 1 4-2.4M19 13a10 10 0 0 0-2.6-1.8M2 9.5a14.5 14.5 0 0 1 4.2-2.6M22 9.5A14.5 14.5 0 0 0 11 6M12 20h.01",
  calendarEmpty: "M7 3.5v3M17 3.5v3M4.5 9.5h15M5.5 5.5h13a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1zM9 14.5h6",
};
export function icon(name, size = 24, label = null) {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.75");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  if (label) { svg.setAttribute("role", "img"); svg.setAttribute("aria-label", label); }
  else svg.setAttribute("aria-hidden", "true");
  const p = document.createElementNS(NS, "path");
  p.setAttribute("d", PATHS[name]);
  svg.append(p);
  return svg;
}

// ---------- Haptics (where the platform supports it) ----------
export const haptic = () => { try { navigator.vibrate?.(8); } catch { /* not supported */ } };

// ---------- List (Form / inset grouped List) ----------
export function section({ header, footer, footerWarning } = {}, ...rows) {
  return h("section", { class: "section" },
    header ? h("h2", { class: "section-header" }, header) : null,
    h("div", { class: "list", role: "list" }, rows),
    footer ? h("p", { class: "section-footer" + (footerWarning ? " warning" : "") }, footer) : null);
}

// A row: title, optional subtitle, optional trailing value, optional chevron (navigation).
export function row({ title, sub, value, strong, onClick, chevron, trailing, label }) {
  const tag = onClick ? "button" : "div";
  return h(tag, { class: "row", role: onClick ? null : "listitem", onclick: onClick, "aria-label": label },
    h("div", { class: "row-main" }, h("div", { class: "row-title" }, title), sub ? h("div", { class: "row-sub" }, sub) : null),
    value != null ? h("span", { class: "row-value" + (strong ? " strong" : "") }, value) : null,
    trailing || null,
    chevron ? h("span", { class: "chevron" }, icon("chevronRight", 16)) : null);
}

// A tappable text action row (tint colour), like a Button inside a Form.
export function action(title, onClick, { destructive = false, disabled = false } = {}) {
  return h("button", { class: "row action" + (destructive ? " destructive" : ""), onclick: onClick, disabled }, title);
}

export function toggle(checked, onChange, label) {
  const input = h("input", { type: "checkbox", role: "switch", "aria-label": label, checked: checked || null,
    onchange: e => { haptic(); onChange(e.target.checked); } });
  return h("label", { class: "switch" }, input, h("span"));
}

export function stepper(value, { min, max, step = 1, onChange, label }) {
  const btn = (name, delta, text) => h("button", {
    type: "button", "aria-label": `${text} ${label}`,
    disabled: (delta < 0 ? value <= min : value >= max) || null,
    onclick: () => { haptic(); onChange(Math.min(max, Math.max(min, value + delta))); },
  }, icon(name, 18));
  return h("div", { class: "stepper", role: "group", "aria-label": label }, btn("minus", -step, "Decrease"), btn("plus", step, "Increase"));
}

// ---------- Action sheet (confirmationDialog) ----------
export function actionSheet(title, choices) {
  const close = () => scrim.remove();
  const scrim = h("div", { class: "scrim", onclick: e => { if (e.target === scrim) close(); } },
    h("div", { class: "sheet", role: "dialog", "aria-label": title },
      h("div", { class: "group" }, h("div", { class: "title" }, title),
        choices.map(c => h("button", { onclick: () => { close(); haptic(); c.onSelect(); } }, c.label))),
      h("div", { class: "group" }, h("button", { class: "cancel", onclick: close }, "Cancel"))));
  document.body.append(scrim);
  scrim.querySelector(".sheet button").focus();
  scrim.addEventListener("keydown", e => { if (e.key === "Escape") close(); });
}

// ---------- Empty / error (ContentUnavailableView) and loading (redacted) ----------
export function unavailable({ iconName, title, message, actionLabel, onAction }) {
  return h("div", { class: "unavailable", role: "status" },
    icon(iconName, 44), h("h2", {}, title), message ? h("p", {}, message) : null,
    actionLabel ? h("button", { onclick: onAction }, actionLabel) : null);
}

export function placeholderSection(rows = 3, header = true) {
  const bar = w => h("span", { class: "redacted", style: `width:${w}` });
  return h("section", { class: "section", "aria-busy": "true" },
    header ? h("div", { class: "section-header" }, bar("72px")) : null,
    h("div", { class: "list" }, Array.from({ length: rows }, (_, i) =>
      h("div", { class: "row" }, h("div", { class: "row-main" }, bar(`${110 + (i % 2) * 40}px`)), bar("44px")))));
}

export function largeTitle(text) {
  return h("h1", { class: "large-title" }, text);
}
