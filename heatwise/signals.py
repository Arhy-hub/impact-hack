"""Electricity price, grid carbon and outside temperature for one day.

Sources (all public, no API key):

* Octopus Agile half-hourly unit rates, London region (``C``). The current
  Agile product code is discovered from the products list, so this keeps
  working when Octopus launches a new Agile version.
* National Grid ESO Carbon Intensity API, half-hourly forecast for Great Britain.
* Open-Meteo hourly 2 m temperature forecast for London.

Fallback order, so the demo never dies on bad Wi-Fi:

1. Live fetch (short timeouts).
2. ``data/signals_snapshot.json``, a snapshot saved by ``python -m heatwise.signals``.
3. Built-in synthetic day with the usual UK shape (cheap night, 16:00 to 19:00 peak).

``DaySignals.source`` records which one was used, so the UI can say so.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import numpy as np

SNAPSHOT = Path(__file__).resolve().parent.parent / "data" / "signals_snapshot.json"
OCTOPUS = "https://api.octopus.energy/v1"
CARBON = "https://api.carbonintensity.org.uk/intensity/date/{day}"
METEO = "https://api.open-meteo.com/v1/forecast"
REGION = "C"  # London. Agile prices differ by region.
LONDON = (51.5, -0.18)
TIMEOUT = 8.0


@dataclass
class DaySignals:
    """One day of signals. Half-hourly arrays have 48 values, hourly ones 24."""

    day: str
    price_p_per_kwh: list[float]  # 48 half-hours, pence incl. VAT
    carbon_g_per_kwh: list[float]  # 48 half-hours
    temp_c: list[float]  # 24 hours
    source: str = "synthetic"

    def per_step(self, steps_per_day: int = 96) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Price, carbon and temperature expanded to one value per simulation step."""
        half = steps_per_day // 48
        hour = steps_per_day // 24
        return (
            np.repeat(self.price_p_per_kwh, half),
            np.repeat(self.carbon_g_per_kwh, half),
            np.repeat(self.temp_c, hour),
        )


def synthetic_day(day: str = "synthetic") -> DaySignals:
    """A typical winter weekday in the UK. Used when nothing else is available."""
    hours = np.arange(48) / 2
    price = np.where(hours < 6, 14.0, 24.0)
    price = np.where((hours >= 16) & (hours < 19), 38.0, price)
    price = np.where((hours >= 2) & (hours < 5), 10.0, price)
    carbon = 160 + 70 * np.exp(-((hours - 17.5) ** 2) / 8) - 40 * np.exp(-((hours - 3.5) ** 2) / 6)
    temp = 5 + 3 * np.sin((np.arange(24) - 9) / 24 * 2 * np.pi)
    return DaySignals(day, price.round(2).tolist(), carbon.round(1).tolist(), temp.round(1).tolist())


def _fill(values: list[float | None]) -> list[float]:
    """Fill missing slots from the nearest earlier slot, then the nearest later one."""
    out = list(values)
    last = None
    for i, v in enumerate(out):
        if v is None:
            out[i] = last
        else:
            last = v
    nxt = None
    for i in range(len(out) - 1, -1, -1):
        if out[i] is None:
            out[i] = nxt
        else:
            nxt = out[i]
    if any(v is None for v in out):
        raise ValueError("no data at all")
    return [float(v) for v in out]


def _slot(ts: str, day: date) -> int | None:
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    i = int((t - start).total_seconds() // 1800)
    return i if 0 <= i < 48 else None


def fetch_prices(client: httpx.Client, day: date) -> list[float]:
    products = client.get(
        f"{OCTOPUS}/products/",
        params={"is_variable": "true", "brand": "OCTOPUS_ENERGY", "page_size": 100},
    ).json()["results"]
    codes = sorted(p["code"] for p in products if p["code"].startswith("AGILE-") and "OUTGOING" not in p["code"])
    if not codes:
        raise ValueError("no Agile product found")
    code = codes[-1]
    url = f"{OCTOPUS}/products/{code}/electricity-tariffs/E-1R-{code}-{REGION}/standard-unit-rates/"
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    rows = client.get(
        url,
        params={
            "period_from": start.isoformat().replace("+00:00", "Z"),
            "period_to": (start + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        },
    ).json()["results"]
    slots: list[float | None] = [None] * 48
    for row in rows:
        i = _slot(row["valid_from"], day)
        if i is not None:
            slots[i] = row["value_inc_vat"]
    return _fill(slots)


def fetch_carbon(client: httpx.Client, day: date) -> list[float]:
    rows = client.get(CARBON.format(day=day.isoformat())).json()["data"]
    slots: list[float | None] = [None] * 48
    for row in rows:
        i = _slot(row["from"], day)
        if i is not None:
            slots[i] = row["intensity"]["forecast"]
    return _fill(slots)


def fetch_temps(client: httpx.Client, day: date) -> list[float]:
    data = client.get(
        METEO,
        params={
            "latitude": LONDON[0],
            "longitude": LONDON[1],
            "hourly": "temperature_2m",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "timezone": "UTC",
        },
    ).json()
    temps = data["hourly"]["temperature_2m"][:24]
    if len(temps) != 24:
        raise ValueError("expected 24 hourly temperatures")
    return _fill(temps)


def fetch_live(day: date | None = None, client: httpx.Client | None = None) -> DaySignals:
    """Fetch all three live feeds. Raises on any failure (callers fall back)."""
    day = day or datetime.now(timezone.utc).date()
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT, headers={"User-Agent": "heatwise-hackathon"})
    try:
        return DaySignals(
            day.isoformat(),
            fetch_prices(client, day),
            fetch_carbon(client, day),
            fetch_temps(client, day),
            source="live",
        )
    finally:
        if own:
            client.close()


def load_snapshot(path: Path = SNAPSHOT) -> DaySignals:
    data = json.loads(path.read_text())
    data["source"] = "snapshot"
    return DaySignals(**data)


def get_signals(day: date | None = None, allow_live: bool = True, path: Path = SNAPSHOT) -> DaySignals:
    """Live if possible, else the saved snapshot, else a synthetic day. Never raises."""
    if allow_live:
        try:
            return fetch_live(day)
        except Exception:  # noqa: BLE001 - any network or parse failure means "fall back"
            pass
    try:
        return load_snapshot(path)
    except Exception:  # noqa: BLE001
        return synthetic_day()


def save_snapshot(signals: DaySignals, path: Path = SNAPSHOT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(signals)
    data.pop("source")
    path.write_text(json.dumps(data, indent=1))


if __name__ == "__main__":
    s = fetch_live()
    save_snapshot(s)
    print(f"Saved {s.day} to {SNAPSHOT}")
    print(f"price p/kWh: min {min(s.price_p_per_kwh):.1f}  max {max(s.price_p_per_kwh):.1f}")
    print(f"carbon g/kWh: min {min(s.carbon_g_per_kwh):.0f}  max {max(s.carbon_g_per_kwh):.0f}")
    print(f"temp °C: min {min(s.temp_c):.1f}  max {max(s.temp_c):.1f}")
