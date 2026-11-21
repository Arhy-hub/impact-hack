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
