"""Signals tests run offline: network calls go to a fake transport."""

from datetime import date

import httpx
import pytest

from heatwise import signals

DAY = date(2026, 11, 21)


def fake_api(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "/products/" in url and "standard-unit-rates" not in url:
        return httpx.Response(200, json={"results": [
            {"code": "AGILE-24-10-01"}, {"code": "AGILE-OUTGOING-19-05-13"}, {"code": "VAR-22-11-01"}]})
    if "standard-unit-rates" in url:
        assert "E-1R-AGILE-24-10-01-C" in url
        # Newest first, with slot 1 missing, like the real API.
        rows = [{"valid_from": f"2026-11-21T{h:02d}:{m:02d}:00Z", "value_inc_vat": float(h)}
                for h in range(23, -1, -1) for m in (30, 0) if (h, m) != (0, 30)]
        return httpx.Response(200, json={"results": rows})
    if "carbonintensity" in url:
        rows = [{"from": f"2026-11-21T{i // 2:02d}:{(i % 2) * 30:02d}Z", "intensity": {"forecast": 100 + i}}
                for i in range(48)]
        return httpx.Response(200, json={"data": rows})
    if "open-meteo" in url:
        return httpx.Response(200, json={"hourly": {"temperature_2m": [float(h) for h in range(24)]}})
    return httpx.Response(404)


@pytest.fixture
def client():
    return httpx.Client(transport=httpx.MockTransport(fake_api))


def test_fetch_live_parses_and_orders_slots(client):
    s = signals.fetch_live(DAY, client=client)
    assert s.source == "live"
    assert len(s.price_p_per_kwh) == 48 and len(s.carbon_g_per_kwh) == 48 and len(s.temp_c) == 24
    assert s.price_p_per_kwh[0] == 0.0 and s.price_p_per_kwh[47] == 23.0
    assert s.price_p_per_kwh[1] == 0.0  # missing slot filled from the previous one
    assert s.carbon_g_per_kwh[10] == 110


def test_per_step_expands_to_96():
    price, carbon, temp = signals.synthetic_day().per_step()
    assert len(price) == len(carbon) == len(temp) == 96


def test_synthetic_day_has_evening_peak():
    s = signals.synthetic_day()
    assert max(s.price_p_per_kwh) == s.price_p_per_kwh[34]  # 17:00
    assert min(s.price_p_per_kwh) < 15


def test_falls_back_to_snapshot_then_synthetic(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(signals, "fetch_live", boom)
    snap = tmp_path / "snap.json"
    assert signals.get_signals(DAY, path=snap).source == "synthetic"
    signals.save_snapshot(signals.synthetic_day("2026-11-21"), snap)
    assert signals.get_signals(DAY, path=snap).source == "snapshot"


def test_fill_rejects_empty():
    with pytest.raises(ValueError):
        signals._fill([None, None])
