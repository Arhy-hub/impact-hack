"""Toy end-to-end run: learn routines, compare with a timer, pay for every kWh.

    python -m heatwise.run_toy                 # default £40 weekly budget
    python -m heatwise.run_toy --budget 3      # tiny budget: see the 402 and top-up request
    python -m heatwise.run_toy --offline       # skip live prices, use the snapshot

Writes ``web/data.json`` for ``web/index.html``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .compare import run_week
from .occupancy import HeatmapBaseline, OccupancyModel, evaluate
from .signals import get_signals
from .sim import simulate_occupancy
from .supplier import LocalSupplier, make_supplier
from .wallet import Wallet

OUT = Path(__file__).resolve().parent.parent / "web" / "data.json"
CUSTOMER = "demo-house"


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--budget", type=float, default=40.0, help="weekly budget in £ loaded via checkout")
    ap.add_argument("--offline", action="store_true", help="don't fetch live prices")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    signals = get_signals(allow_live=not args.offline)
    train = simulate_occupancy(35, seed=args.seed)
    week = simulate_occupancy(7, seed=args.seed + 1000, start_day=0)
    baseline = HeatmapBaseline().fit(train)
    model = OccupancyModel().fit(train)
    ml = {"baseline": evaluate(baseline, week), "model": evaluate(model, week)}

    timer = run_week("timer", week, signals)
    free = run_week("heatwise", week, signals, predictor=model)

    supplier = make_supplier()
    if isinstance(supplier, LocalSupplier):
        supplier.checkout(CUSTOMER, args.budget)  # the human loads the budget at checkout
    wallet = Wallet(supplier, CUSTOMER)
    paid = run_week("heatwise", week, signals, predictor=model, wallet=wallet, budget_gbp=args.budget)

    def pct(a, b):
        return round(100 * (1 - a / b), 1) if b else 0.0

    report = {
        "signals": {"day": signals.day, "source": signals.source,
                    "price_p_per_kwh": signals.price_p_per_kwh,
                    "carbon_g_per_kwh": signals.carbon_g_per_kwh, "temp_c": signals.temp_c},
        "ml": ml,
        "timer": timer.summary(),
        "heatwise": free.summary(),
        "heatwise_paid": {**paid.summary(), "budget_gbp": args.budget,
                          "spent_gbp": round(wallet.spent_pence / 100, 2),
                          "emergency_gbp": round(wallet.emergency_pence / 100, 2),
                          "blocks_bought": wallet.blocks_bought,
                          "max_trim": float(paid.trims.max()),
                          "topup_requests": paid.topup_requests,
                          "supplier": supplier.name},
        "savings_vs_timer": {"cost_pct": pct(free.cost_gbp, timer.cost_gbp),
                             "carbon_pct": pct(free.carbon_kg, timer.carbon_kg)},
        "rooms": list(week.rooms),
        "series": {  # first 2 days, for the chart
            "living_temp_heatwise": np.round(free.temps[:192, 2], 2).tolist(),
            "living_temp_timer": np.round(timer.temps[:192, 2], 2).tolist(),
            "living_occupied": week.occupied[:192, 2].astype(int).tolist(),
        },
        "receipts": [r.__dict__ for r in wallet.receipts if r.blocks_bought][:50],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1))

    print(f"Signals: {signals.source} ({signals.day})")
    print(f"Occupancy  heatmap Brier {ml['baseline']['brier']:.4f} | model Brier {ml['model']['brier']:.4f}")
    for name, res in (("Timer", timer), ("Heatwise", free)):
        s = res.summary()
        print(f"{name:9s} £{s['cost_gbp']:6.2f}  {s['carbon_kg']:5.2f} kg CO2  {s['kwh']:6.1f} kWh  comfort {s['comfort_pct']:5.1f}%")
    sv = report["savings_vs_timer"]
    print(f"Heatwise saves {sv['cost_pct']}% cost and {sv['carbon_pct']}% carbon vs the timer")
    hp = report["heatwise_paid"]
    print(f"Paid run ({hp['supplier']}): budget £{args.budget:.2f}, spent £{hp['spent_gbp']:.2f}, "
          f"{hp['blocks_bought']} blocks, max trim {hp['max_trim']:.0f}°, comfort {hp['comfort_pct']}%")
    if hp["topup_requests"]:
        first = hp["topup_requests"][0]
        print(f"  Out of credit at step {first['step']}: top-up needed -> {first['checkout_url']}"
              f" (emergency credit used £{hp['emergency_gbp']:.2f})")
    print(f"Wrote {args.out}")
    return report


if __name__ == "__main__":
    main()
