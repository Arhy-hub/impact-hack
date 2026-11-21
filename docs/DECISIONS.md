# Decisions log

Every choice made while building Heatwise, and why. Newest at the bottom of each section. "Assumed" means nobody confirmed it. Change it if it's wrong.

## Project and stack

| # | Decision | Why |
|---|---|---|
| D1 | Build the simulation from scratch in this repo | `heatwise-idea.md` describes a simulation, but no code for it exists. One codebase keeps the ML, the controller and the payments wired together. |
| D2 | Python backend (numpy, scikit-learn, FastAPI) with a single static HTML page | The ML is much easier in Python, and SolvaPay ships a Python SDK (`solvapay`). There's no frontend build step to break on the day. *Assumed.* |
| D3 | Toy version first: 3 rooms, 2 people, 1 week | An end-to-end loop that proves every piece in about 1.5 hours. Scale up after. |
| D4 | Branch `heatwise-mvp`, cut from `add-heatwise-idea` | Keeps the idea doc in history. `main` stays clean until the team merges. |

## Simulation (`heatwise/sim.py`)

| # | Decision | Why |
|---|---|---|
| S1 | 15-minute steps | Matches the controller cadence in the idea doc ("every few minutes"). Half-hourly Agile prices split evenly into 2 steps. |
| S2 | A one-node RC thermal model per room, with no heat flowing between rooms | Research (arXiv 2010.12257) finds that simple linear models control as well as or better than complex ones. Heat flowing between rooms is left for later because it adds parameters we can't calibrate today. |
| S3 | Room values: τ 7 to 10 h, C 0.8 to 1.2 kWh/°C | Made up, but in a plausible range for UK terrace rooms. **Synthetic, so say so in the pitch.** |
| S4 | Heater caps raised to 2.5 to 3.0 kW | A test showed that at 5°C outside the kitchen loses about 1.5 kW, so a 1.5 kW heater couldn't hold its temperature. Real radiators are sized for the design cold day, so the caps were raised. |
| S5 | Heat pump with COP 3 | The pitch targets heat-pump homes, where time-of-use prices matter. Gas boilers only benefit from heating fewer rooms. |
| S6 | Heat needed = the exact amount to reach the target this step, clipped to [0, q_max] | It's the simplest controller that is stable on an RC model, and it's easy to test. |
| S7 | Occupancy noise: ±30 min jitter, a 15% chance of working from home on weekdays, a motion sensor that catches 90% of presence and fires falsely on 1% of empty steps | Gives the ML model something real to learn, and makes the "routines break" risk from the idea doc visible. |
| S8 | People are called `alex` and `sam` | Fictional. There's no real household data anywhere in the repo. |

## Safety and publishing

| # | Decision | Why |
|---|---|---|
| P1 | No secrets in git: keys only through `.env`, which is git-ignored. `.env.example` holds names only. | The repo may become public. |
| P2 | `*.pptx` and Office lock files are git-ignored | The event deck belongs to the organisers. Don't republish it. |
| P3 | All data is synthetic. No real household, motion or location data is committed. | Motion data reveals when people are home (privacy risk from the idea doc). |

## Occupancy model (`heatwise/occupancy.py`)

| # | Decision | Why |
|---|---|---|
| O1 | Target is "room used within the next hour" (4 steps) | The controller needs to know whether to start heating *now*. An hour covers a typical warm-up time. |
| O2 | Inputs are sensors only (motion, phones home). Ground-truth occupancy is used only for labels. | A real house only has sensors. A test enforces this: flipping the ground truth must not change predictions. |
| O3 | The model is a **heatmap prior plus a live-sensor correction** (logistic regression on the heatmap's log-odds, motion lags at 0, 15, 30, 60 and 120 min, motion anywhere, and phones home) | The first attempt, logistic regression on time features alone, lost to the heatmap (Brier 0.035 against 0.033) because the toy routines are very regular. Keeping the heatmap as a prior and learning only the correction fixed that: Brier **0.025 against 0.033** (24% lower) on an unseen week. It's also easy to explain: "the routine, adjusted for what the sensors see right now". |
| O4 | Cross-fitting: training data split in two, each half's heatmap feature comes from the other half | Stops the model seeing its own labels through the heatmap feature (leakage), which would make it trust the prior too much. |
| O5 | Logistic regression, not LightGBM | Fast, has no extra dependency, and research suggests it's strong within a single home (arXiv 2604.14841). LightGBM stays a stretch goal. |
| O6 | Time-based split: train on 5 weeks, test on the following week with a new random seed | A random split would leak routines across days and flatter the model. |
| O7 | Laplace smoothing on the heatmap (an unseen cell = 0.5) | Avoids 0 and 1 probabilities, which break the log-odds feature. |

**Results (seed 0, 35 training days, 7 test days):** heatmap Brier 0.0327 / AUC 0.9947; model Brier 0.0250 / AUC 0.9949. AUC is near 1 for both because the toy routines are regular. Real homes will be noisier, so judge on Brier.

## Signals (`heatwise/signals.py`)

| # | Decision | Why |
|---|---|---|
| G1 | Octopus Agile, London region (`C`) | Public, free and half-hourly. Agile is the best-known UK time-of-use tariff. London because the event is in London. |
| G2 | Find the Agile product code from the products list instead of hardcoding it | Octopus releases new Agile versions (`AGILE-24-10-01` today). Hardcoding would break silently. |
| G3 | Match slots by timestamp and fill gaps from neighbouring slots | The real API returns slots newest first and can skip some (46 of 48 today). |
| G4 | Fall back from live data to the committed snapshot, then to a synthetic day, and record which was used in `source` | The demo must survive venue Wi-Fi. The UI should be honest about which data it used. |
| G5 | `data/signals_snapshot.json` is committed | It's public market and weather data, so it's safe to publish, and it lets the repo run offline. |
| G6 | Tests use `httpx.MockTransport` | The test suite never touches the network, so CI and offline runs behave the same. |
| G7 | User-Agent `heatwise-hackathon`, with no personal details | Some public APIs ask clients to identify themselves. We identify the app, not a person. |

**Snapshot taken 2026-11-21:** Agile 28.1 to 53.2 p/kWh; carbon 136 to 226 g/kWh; London 2.8 to 7.7°C.

## Controller (`heatwise/controller.py`)

| # | Decision | Why |
|---|---|---|
| C1 | Comfort 20°C, eco 17°C, away/safety 12°C | Common UK thermostat settings. The 12° floor is from the idea doc and is **never** trimmed below. |
| C2 | Heat to comfort at P(used within the hour) ≥ 0.4 | The idea doc's threshold. |
| C3 | Slot score = price (p/kWh) + 10p/kg × carbon | One number that ranks slots by cost and carbon. 10p/kg (£100/tonne) is close to UK carbon prices. A slider can change it later. |
| C4 | Pre-heat +1° in the best quarter of the day's slots for rooms with P ≥ 0.2. Coast −1° in the worst quarter. | Stores heat when it's cheap and clean, and leans on it at the peak. Quartiles adapt to any day's prices. |
| C5 | Budget trim: +1° for every 10% the projection is over budget, capped at 3° | Gradual, as the idea doc asks. The cap stops comfort falling off a cliff. |
| C6 | The controller only sees what a house can sense (motion, phones, forecasts), not ground truth | Keeps the simulation honest about what is possible in a real house. |
| C7 | Timer baseline: weekdays 06:30 to 08:30 and 17:00 to 22:30, weekends 08:00 to 23:00, every room, 12° otherwise | A typical UK central-heating timer. It's the "usual plan" the judges asked us to compare against. |

## Payments (`heatwise/supplier.py`, `heatwise/wallet.py`)

| # | Decision | Why |
|---|---|---|
| W1 | Energy is bought in **fixed 10p blocks**, one paid call per block | The SolvaPay Python SDK (`solvapay` 0.1.1) records exactly one unit per paid call (`track_usage` sends `units: 1`), so a variable price per call isn't possible. Blocks also keep calls to about 10 per £1 rather than one per 15 minutes per room. The SolvaPay plan must price 1 unit at 10p. |
| W2 | `LocalSupplier` mirrors the paywall (402 plus a checkout link), and `SolvaPaySupplier` is used when `SOLVAPAY_SECRET_KEY` is set | Everything runs and is tested with no account or keys. The real sandbox is a drop-in swap. The SolvaPay path is **not** covered by automated tests because it needs a live sandbox account. |
| W3 | Out of credit means **emergency credit** for safety heating, logged as debt, plus a top-up request with the checkout link | Never let the house freeze because a payment failed (the safety risk in the idea doc). It mirrors how UK prepayment meters work. |
| W4 | The budget is what the human loaded through checkout. The agent never tops up on its own. | Humans approve spending, and the agent spends within what was approved (the "who approves" judging question). |
| W5 | Input validation: `customer_ref` limited to `[A-Za-z0-9_-]{1,64}`, top-ups to £0 to £500, API docs pages turned off | Safe to expose if the repo or demo goes public. Stops injection-style input and silly balances. |
| W6 | Request models defined at module level | With `from __future__ import annotations`, FastAPI couldn't resolve models defined inside a function and treated the body as a query parameter (a test caught this). |

## Week runner and retuning (`heatwise/compare.py`, `heatwise/run_toy.py`)

| # | Decision | Why |
|---|---|---|
| R1 | Every simulated day reuses the same day of signals | Toy simplification: one day of live prices, carbon and weather is enough to test the logic. The MVP should fetch several days or loop over a recorded week. |
| R2 | Comfort % = share of truly occupied room-steps within 1° of that room's comfort temperature | Measures comfort where people actually are. The 1° tolerance lets Heatwise coast −1° at the peak without counting it as a failure. |
| S9 | **Retuned rooms: τ 18 to 24 h, C 1.0 to 1.4 kWh/°C** (was τ 7 to 10 h) | The first toy run cost about £67 a week for 3 rooms, which is far too leaky. Real UK homes cool over roughly 20 to 50 hours. |
| C8 | **Bedroom comfort is 17° from 23:00 to 07:00** | Otherwise Heatwise heated sleepers to 20° all night while the timer left them at 12°, so the comparison was unfair in both directions. |
| C9 | **Timer baseline sets back to 16° overnight and is off (12°) on the weekday daytime** | That's how most UK timer-plus-thermostat setups behave. The first version switched off overnight, which made the timer look cheaper and colder than reality. |
| O8 | **Forecast horizon is 3 hours (12 steps)**, up from 1 hour | A sweep on the toy week (threshold 0.4): 1 h → £39.96 and comfort 83.6%; 2 h → £41.25 and 93.5%; **3 h → £40.79 and 97.8%**. A room at 12° needs several hours to reach 20°, so 1 h was too short. At 3 h the occupancy model still beats the heatmap: Brier 0.021 against 0.029. |
| R3 | Default weekly budget £40 | It's just below what Heatwise would spend unconstrained (£40.79), so the demo shows the trim working: it ends at £38.27 with up to 2° of trim. £3 shows the out-of-credit path. |
| R4 | `web/data.json` is generated **and committed** | The page works straight from the repo (for example on GitHub Pages) with no Python. It's all synthetic or public data. |

**Toy results (offline snapshot from 2026-11-21, seed 0, 1 week, 3 rooms):**

| | Cost | CO₂ | Energy | Comfort |
|---|---|---|---|---|
| Timer | £44.24 | 25.18 kg | 116.7 kWh | 84.6% |
| Heatwise | £40.79 | 23.80 kg | 113.1 kWh | 97.8% |
| Heatwise, £40 budget | £38.27 | — | — | 76.1% |

So Heatwise is **7.8% cheaper with 5.5% less CO₂ at much higher comfort**. These numbers are synthetic; they show the idea works, not what a real home would save. Prices on the snapshot day were high (28 to 53p/kWh), which inflates the £ figures.
