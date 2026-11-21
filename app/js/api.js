// Talks to the Heatwise server and holds the latest home state.
// Every endpoint returns the full state, so screens just re-render from `store.state`.

const listeners = new Set();
export const store = { state: null, error: null, loading: true };

function emit() { for (const fn of listeners) fn(store); }
export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }

async function request(path, body, method) {
  const opts = method ? { method } : body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong. Try again.");
  return data;
}

// Load or act. Returns {ok, message} so screens can show inline errors for form actions.
export async function call(path, body, method) {
  try {
    store.state = await request(path, body, method);
    store.error = null;
    return { ok: true };
  } catch (err) {
    if (!store.state) store.error = err.message || "Can't reach your heating.";
    return { ok: false, message: err.message };
  } finally {
    store.loading = false;
    emit();
  }
}

export const api = {
  load: () => call("/api/home"),
  away: on => call("/api/away", { on }),
  trim: degrees => call("/api/trim", { degrees }),
  topup: pounds => call("/api/topup", { pounds }),
  comfort: temp => call("/api/comfort", { temp }),
  calendar: url => call("/api/calendar", { url }),
  tick: steps => call("/api/tick", { steps }),
  reset: () => call("/api/reset", {}),
  limits: body => call("/api/limits", body),
  roomComfort: (room, temp) => call("/api/room_comfort", { room, temp }),
  allow: () => call("/api/allow", {}),
  addEvent: e => call("/api/events", e),
  removeEvent: i => call(`/api/events/${i}`, undefined, "DELETE"),
  jump: (day, hour) => call("/api/jump", { day, hour }),
  mode: m => call("/api/mode", { mode: m }),
  confirm: action => call("/api/confirm", action),
  repair: (issue, action) => call("/api/repair", { issue, action }),
  breakRoom: room => call("/api/break", { room }),
  repairsAllowance: gbp => call("/api/repairs_allowance", { gbp }),
};
