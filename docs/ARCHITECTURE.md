# Architecture

## Data flow, one 15-minute step

```
 sensors (simulated)            forecasts (real)
 motion, phones home      Agile price · grid carbon · temperature
        │                              │
        ▼                              ▼
 occupancy.OccupancyModel        signals.DaySignals
 P(room used in next 3 h)        price, carbon, temp per step
        │                              │
        └──────────────┬───────────────┘
                       ▼
            controller.heatwise_targets
            comfort / eco / away, pre-heat or coast by slot score,
            minus budget trim, floor 12°C
                       │
                       ▼
            sim.House.heat_needed_kw → House.step
            RC model per room → electricity used (kWh)
                       │
                       ▼
            wallet.Wallet.pay
            needs more credit? → supplier.buy_block (one paid call = 10p)
                       │                         │
                     200 receipt           402 PaymentRequired
                                           → emergency credit, top-up request,
                                             rooms held at 12°C until topped up
```

`compare.run_week` loops this over a week (672 steps) and scores it. `run_toy` runs the timer, Heatwise, and Heatwise with a paid budget, then writes `web/data.json` for the page.

## Modules

| Module | Main pieces | Notes |
|---|---|---|
| `sim.py` | `Room`, `House`, `simulate_occupancy`, `Occupancy` | 15-minute steps. One-node RC model per room. Routines with jitter, working-from-home days and noisy motion. |
| `occupancy.py` | `HeatmapBaseline`, `OccupancyModel`, `evaluate`, `train_and_compare` | Model input is the heatmap log-odds plus motion lags, motion anywhere and phones home. Cross-fitted. Sensor-only inputs. |
| `signals.py` | `DaySignals`, `get_signals`, `fetch_live`, `save_snapshot` | Order: live, then snapshot, then synthetic. `source` records which was used. |
| `controller.py` | `Settings`, `heatwise_targets`, `timer_targets`, `comfort_targets`, `budget_trim`, `slot_scores` | Pure functions, easy to unit test. |
| `supplier.py` | `LocalSupplier`, `SolvaPaySupplier`, `make_supplier`, `create_app`, `PaymentRequired` | Same interface (`buy_block`) for both. FastAPI front: `POST /buy_energy`, `POST /checkout` (local only). |
| `wallet.py` | `Wallet`, `Receipt` | Buys blocks as needed. Emergency credit on 402. |
| `compare.py` | `run_week`, `WeekResult` | Cost, CO₂, kWh, comfort %, plus per-step logs. |
| `run_toy.py` | `main` | CLI: `--budget`, `--offline`, `--seed`, `--out`. |

## Interfaces worth knowing

- **Predictor:** any object with `predict_proba(occ, step) -> np.ndarray` (one probability per room). Both `HeatmapBaseline` and `OccupancyModel` qualify, so they can be swapped in `run_week`.
- **Supplier:** any object with `buy_block(customer_ref) -> {"block_id", "pence"}` that raises `PaymentRequired(checkout_url)`. `LocalSupplier` also has `checkout(customer_ref, pounds)` to simulate a human paying.

## Testing

`pytest` runs fully offline (network calls go to `httpx.MockTransport`; payments to `LocalSupplier`):

| File | Covers |
|---|---|
| `test_sim.py` | Cooling, heater caps, COP, occupancy noise, reproducibility |
| `test_occupancy.py` | Label look-ahead, no ground-truth leakage, model beats heatmap |
| `test_signals.py` | API parsing and slot ordering, gap filling, fallback order |
| `test_controller.py` | Every rule, the safety floor, timer schedule, budget trim |
| `test_payments.py` | 402 → checkout → 200, block buying, emergency credit, input validation over HTTP |
| `test_end_to_end.py` | The full toy run: cheaper, cleaner and at least as comfortable as the timer; stays within budget; tiny budget raises a top-up request |

Not covered automatically: the real SolvaPay sandbox (it needs an account). See the README.
