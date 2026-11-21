from heatwise.assistant import rule_reply, validate

STATE = {"comfort_c": 20.0, "away": False, "clock": "Mon 18:00", "price_level": "peak",
         "rooms": [{"name": "bedroom", "temp": 16.5, "target": 15.0, "status": "Eco", "why": "Nobody's expected."}],
         "budget": {"spent_gbp": 1.0, "budget_gbp": 30.0, "projected_gbp": 28.0, "manual_trim": 0.0}}


def test_commands_become_proposals():
    assert rule_reply("I'm going away for the weekend", STATE)["action"] == {"type": "away", "value": True}
    assert rule_reply("I'm cold", STATE)["action"] == {"type": "comfort", "value": 21.0}
    assert rule_reply("help me save money", STATE)["action"] == {"type": "trim", "value": 1}


def test_questions_are_answered_from_state():
    r = rule_reply("why is the bedroom cold?", STATE)
    assert r["action"] is None or r["action"]["type"] == "comfort"


def test_validate_rejects_unsafe():
    assert validate({"type": "comfort", "value": 40}) is None
    assert validate({"type": "delete", "value": 1}) is None
    assert validate({"type": "trim", "value": 9}) is None
    assert validate({"type": "away", "value": True}) == {"type": "away", "value": True}


def test_validate_room_action():
    assert validate({"type": "room", "room": "living", "value": 22}) == {"type": "room", "room": "living", "value": 22.0}
    assert validate({"type": "room", "room": "attic", "value": 22}) is None
    assert validate({"type": "room", "room": "living", "value": 30}) is None
    assert validate({"type": "room", "room": "living", "value": True}) is None


def test_rules_propose_one_room_temperature():
    state = {"comfort_c": 20.0, "rooms": [], "budget": {"manual_trim": 0}}
    out = rule_reply("make the living room 22 degrees", state)
    assert out["action"] == {"type": "room", "room": "living", "value": 22.0}
