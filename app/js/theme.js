// Appearance: System, Light or Dark. Remembered on this device only (browser storage),
// which is fine for a display preference. Storage can be unavailable (private mode),
// so every access is wrapped and the app falls back to System.

const KEY = "heatwise-appearance";
export const CHOICES = [
  { id: "system", label: "System" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
];

export function saved() {
  try { return localStorage.getItem(KEY) || "system"; } catch { return "system"; }
}

export function apply(choice) {
  const root = document.documentElement;
  if (choice === "light" || choice === "dark") root.dataset.theme = choice;
  else delete root.dataset.theme;
  const dark = choice === "dark" || (choice === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.querySelector('meta[name="theme-color"]:not([media])')?.setAttribute("content", dark ? "#000000" : "#f2f2f7");
}

export function set(choice) {
  try { localStorage.setItem(KEY, choice); } catch { /* not stored; still applies for this visit */ }
  apply(choice);
}
