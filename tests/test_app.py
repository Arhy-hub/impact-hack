from functools import partial

import pytest
from fastapi.testclient import TestClient

from heatwise.app import create_app
from heatwise.live import LiveHome
from heatwise.supplier import LocalSupplier


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("SOLVAPAY_SECRET_KEY", raising=False)
    monkeypatch.delenv("HEATWISE_ICAL_URL", raising=False)
    factory = lambda: LiveHome(allow_live_signals=False, supplier=LocalSupplier())  # noqa: E731
    return TestClient(create_app(factory))


def test_page_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Heatwise" in r.text


def test_home_and_tick(client):
    assert client.get("/api/home").json()["clock"] == "Mon 16:00"
    assert client.post("/api/tick", json={"steps": 4}).json()["clock"] == "Mon 17:00"


def test_boost_and_cancel(client):
    s = client.post("/api/boost", json={"room": "bedroom", "hours": 1}).json()
    assert s["rooms"][0]["status"] == "Boost"
    s = client.post("/api/boost/cancel", json={"room": "bedroom"}).json()
    assert s["rooms"][0]["status"] != "Boost"


def test_away_trim_topup(client):
    assert client.post("/api/away", json={"on": True}).json()["away"]
    assert client.post("/api/trim", json={"degrees": 1}).json()["budget"]["manual_trim"] == 1
    s = client.post("/api/topup", json={"pounds": 10}).json()
    assert s["result"]["paid"] and s["budget"]["budget_gbp"] == 50


@pytest.mark.parametrize("path,body", [
    ("/api/boost", {"room": "garage", "hours": 1}),        # unknown room -> 422 from LiveHome
    ("/api/boost", {"room": "Bedroom; drop", "hours": 1}),  # bad pattern
    ("/api/boost", {"room": "bedroom", "hours": 99}),
    ("/api/tick", {"steps": 1000}),
    ("/api/trim", {"degrees": -1}),
    ("/api/topup", {"pounds": 0}),
    ("/api/topup", {"pounds": 10_000}),
])
def test_rejects_bad_input(client, path, body):
    assert client.post(path, json=body).status_code == 422


def test_reset(client):
    client.post("/api/tick", json={"steps": 10})
    assert client.post("/api/reset").json()["clock"] == "Mon 16:00"


def test_no_docs_or_secrets_exposed(client, monkeypatch):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    text = client.get("/api/home").text
    assert "sk_" not in text and "ical" not in text.lower()
