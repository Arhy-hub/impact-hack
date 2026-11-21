"""Ask Heatwise: plain-English questions and commands.

The assistant never changes the heating itself. It turns a message into either
an answer, or a *proposal* (an action plus a sentence) that the user confirms
in the app. Supported actions: away on/off, set comfort temperature, set trim.

Two engines with the same output:

* ``rule_reply``: keyword rules, no network. Always available.
* ``claude_reply``: Claude (``claude-opus-5-5``) when ``ANTHROPIC_API_KEY`` is
  set. Its JSON is validated; anything invalid falls back to the rules.
Numbers in answers always come from the engine's state, never from the model.
"""

from __future__ import annotations

import json
import os
import re

from .live import COMFORT_RANGE

ROOMS = {"bedroom": "bedroom", "kitchen": "kitchen", "living": "living", "lounge": "living", "living room": "living"}
ACTIONS = {"away", "comfort", "trim"}


def _room_in(text: str) -> str | None:
    for word, room in ROOMS.items():
        if word in text:
            return room
    return None


def validate(action: dict | None) -> dict | None:
    """Return a safe action dict or None."""
    if not isinstance(action, dict) or action.get("type") not in ACTIONS:
        return None
    t, v = action["type"], action.get("value")
    if t == "away" and isinstance(v, bool):
        return {"type": t, "value": v}
    if t == "comfort" and isinstance(v, (int, float)) and COMFORT_RANGE[0] <= v <= COMFORT_RANGE[1]:
        return {"type": t, "value": round(float(v) * 2) / 2}
    if t == "trim" and isinstance(v, (int, float)) and 0 <= v <= 3:
        return {"type": t, "value": float(round(v))}
    return None


def rule_reply(text: str, state: dict) -> dict:
    t = text.lower().strip()
    comfort = state["comfort_c"]
    if re.search(r"\b(away|leaving|holiday|going out)\b", t) and not re.search(r"\b(back|home now|returned)\b", t):
        return {"reply": "Want me to turn on away mode? Every room rests at 12° until you're back.",
                "action": {"type": "away", "value": True}}
    if re.search(r"\b(i'?m back|home now|returned|turn off away)\b", t):
        return {"reply": "Welcome back! Shall I turn away mode off?", "action": {"type": "away", "value": False}}
    if re.search(r"\b(cold|chilly|warmer|freezing)\b", t):
        new = min(comfort + 1, COMFORT_RANGE[1])
        return {"reply": f"Shall I raise your comfy temperature from {comfort:g}° to {new:g}°?", "action": {"type": "comfort", "value": new}}
    if re.search(r"\b(hot|warm|cooler|stuffy)\b", t):
        new = max(comfort - 1, COMFORT_RANGE[0])
        return {"reply": f"Shall I lower your comfy temperature from {comfort:g}° to {new:g}°?", "action": {"type": "comfort", "value": new}}
    if re.search(r"\b(save|cheaper|budget|money)\b", t):
        trim = min(state["budget"]["manual_trim"] + 1, 3)
        return {"reply": f"I can turn every room down {trim:g}° to save money. Go ahead?", "action": {"type": "trim", "value": trim}}
    room = _room_in(t)
    if room:
        r = next(x for x in state["rooms"] if x["name"] == room)
        return {"reply": f"It's {r['temp']:.1f}°, aiming for {r['target']:.0f}°. {r['why']}", "action": None}
    if re.search(r"\b(spent|cost|bill)\b", t):
        b = state["budget"]
        return {"reply": f"You've spent £{b['spent_gbp']:.2f} of £{b['budget_gbp']:.2f} this week, heading for about £{b['projected_gbp']:.2f}.", "action": None}
    return {"reply": "I'm Luke. I can turn on away mode, make it warmer or cooler, help you save, or explain why a room is at its temperature. Try “I'm cold” or “why is the bedroom cold?”",
            "action": None}


SYSTEM = """You are Luke, Heatwise's friendly helper who looks after the home's heating. Reply in at most two short, warm sentences.
You may propose ONE action for the user to confirm: {"type":"away","value":true|false},
{"type":"comfort","value":16-23}, or {"type":"trim","value":0-3}. Never invent numbers: use only the state given.
Respond with JSON only: {"reply": "...", "action": {...} or null}."""


def claude_reply(text: str, state: dict) -> dict | None:
    """Claude engine. Returns None on any failure so the caller can fall back."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic

        facts = {"comfort_c": state["comfort_c"], "away": state["away"], "clock": state["clock"],
                 "price": state["price_level"], "rooms": [{k: r[k] for k in ("name", "temp", "target", "status", "why")} for r in state["rooms"]],
                 "budget": {k: state["budget"][k] for k in ("spent_gbp", "budget_gbp", "projected_gbp", "manual_trim")}}
        resp = anthropic.Anthropic(timeout=20.0).messages.create(
            model="claude-opus-5-5", max_tokens=1024, system=SYSTEM, output_config={"effort": "low"},
            messages=[{"role": "user", "content": f"State: {json.dumps(facts)}\n\nUser: {text[:500]}"}],
        )
        if resp.stop_reason == "refusal":
            return None
        raw = next((b.text for b in resp.content if b.type == "text"), "")
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        reply = str(data.get("reply", "")).strip()[:400]
        return {"reply": reply, "action": validate(data.get("action"))} if reply else None
    except Exception:  # noqa: BLE001 - any API or parse problem means "use the rules"
        return None


def ask(text: str, state: dict) -> dict:
    out = claude_reply(text, state)
    engine = "claude" if out else "rules"
    out = out or rule_reply(text, state)
    out["action"] = validate(out.get("action"))
    out["engine"] = engine
    return out
