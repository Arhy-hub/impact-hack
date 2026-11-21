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
