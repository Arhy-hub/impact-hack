# Heatwise

**An AI agent that buys your heating for you.** It learns who uses which room and when, heats only those rooms, does it at the cheapest and cleanest hours of the day, and pays for every kWh itself through SolvaPay. It never spends past the budget you loaded without asking.

Built for Hack for Impact (Imperial College London, 21 Nov 2026): AI + payments + a sustainable angle.

> **Status: toy version / MVP.** Everything runs on a simulated house and simulated people. Prices, grid carbon and weather are real (live or a saved snapshot). The numbers show the idea works; they are not what a real home would save.

## Results (toy run, 1 week, 3 rooms)

| | Cost | CO₂ | Comfort |
|---|---|---|---|
| Old-style timer | £44.24 | 25.2 kg | 84.6% |
| **Heatwise** | **£40.79** | **23.8 kg** | **97.8%** |

That's **7.8% cheaper with 5.5% less CO₂, and people are comfortable far more of the time**. With a £40 weekly budget, the agent trims comfort by up to 2° and finishes at £38.27.

The occupancy model (routine plus live motion) predicts room use better than the routine heatmap alone: Brier score **0.021 vs 0.029**.

## How it works

1. **Learn routines.** Motion sensors and phones give a noisy view of who is home and where. A routine heatmap gives a prior, and a logistic regression corrects it with live sensor signals to predict *"will this room be used in the next 3 hours?"*
2. **Decide targets.** Rooms in use, or about to be, are heated to comfort (20°C, or 17°C for the bedroom overnight). Other rooms hold eco (17°C), or 12°C when nobody's home. That 12° safety floor is never overridden.
3. **Be price- and carbon-aware.** Each half-hour gets a score: price plus a carbon cost. In the best quarter of the day, rooms likely to be used get pre-heated by 1°. In the worst quarter, occupied rooms coast 1° lower.
4. **Pay for it.** The agent buys energy in 10p blocks from a supplier behind a paywall. The human loads the budget once through checkout, and the agent spends within it. If the month is heading over budget, it trims comfort gradually. If credit runs out, it keeps safety heating on from emergency credit and raises a top-up request with a checkout link.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the modules and data flow, and [docs/DECISIONS.md](docs/DECISIONS.md) for **every choice made and why**.

## Quickstart

Needs Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python -m heatwise.run_toy             # full toy run (live prices if online), £40 budget
python -m heatwise.run_toy --offline   # use the saved price/carbon snapshot
python -m heatwise.run_toy --budget 3  # see the agent run out of credit and ask for a top-up

python -m http.server -d web 8000      # then open http://localhost:8000
                                       # "The house, step by step": press Play to watch both houses through the week
```

Other entry points:

```bash
python -m heatwise.occupancy   # train and score the occupancy model vs the heatmap
python -m heatwise.signals     # fetch today's live signals and save them as the offline snapshot
pytest                         # all tests (offline, no keys needed)
```

## Running against the SolvaPay sandbox

By default the agent pays a **local stand-in supplier** that behaves like the SolvaPay paywall (402 plus a checkout link). To use real SolvaPay sandbox payments:

1. Create a SolvaPay sandbox account and a product. Give it a plan where **1 unit = 10p** (one energy block).
2. Copy `.env.example` to `.env` and fill in `SOLVAPAY_SECRET_KEY` (an `sk_sandbox_...` key) and `SOLVAPAY_PRODUCT_REF`.
3. Run `python -m heatwise.run_toy`. The first purchase returns a checkout URL. Pay it in the browser with Stripe's test card, then run again.

The SolvaPay path is not covered by the automated tests because it needs a live sandbox account. Test it by hand before the demo.

## Project layout

```
heatwise/
  sim.py         simulated house: rooms (RC thermal model), people, noisy sensors
  occupancy.py   routine heatmap + live-sensor model, Brier/AUC evaluation
  signals.py     Octopus Agile prices, grid carbon, weather; offline fallbacks
  controller.py  per-room targets, timer baseline, budget trim
  supplier.py    energy supplier behind a paywall (local or SolvaPay)
  wallet.py      agent pays per step, buys blocks, emergency credit, top-up requests
  compare.py     run a week, score cost / CO2 / comfort
  run_toy.py     the end-to-end toy run; writes web/data.json
web/             static results page (index.html + generated data.json)
data/            saved signals snapshot for offline runs
tests/           pytest suite (offline)
docs/            ARCHITECTURE.md, DECISIONS.md
heatwise-idea.md the original idea write-up
```

## Security and privacy

This repo is written to be safe to make public.

- **No secrets in git.** Keys are read from the environment or `.env`, which is git-ignored. `.env.example` contains names only.
- **No personal data.** Every household, person (`alex`, `sam`) and sensor reading is simulated. The only real data is public market and weather data.
- **Privacy by design for the real product.** Motion data reveals when people are home, so the plan is to keep it on the local network and never send it to the cloud (see `heatwise-idea.md`).
- **Fails safe.** The controller never sets a room below 12°C, and losing payment, Wi-Fi or a data feed never switches heating off (emergency credit, then a snapshot, then synthetic data).
- **Validated input.** The supplier API checks `customer_ref` against `[A-Za-z0-9_-]{1,64}`, caps top-ups at £500, and has its docs pages turned off. Run servers on `127.0.0.1` unless you mean to expose them.
- **Minimal third-party code in the browser.** One pinned Chart.js file from cdnjs. No trackers or cookies.
- The event deck (`*.pptx`) is git-ignored and not redistributed.

If you find a security issue, open a private GitHub security advisory on this repo rather than a public issue.

## What's next

- Real sensors: one ESP32 motion and temperature sensor in one room for 2 weeks, logged to Home Assistant, then rerun the occupancy evaluation on real data.
- More rooms and people, heat flowing between rooms, a recorded week of real prices.
- Approval flow in the UI (approve the top-up, or accept a trim), and LLM tips and plain-English overrides ("WFH Tuesday").
