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

## Docs and publishing (continued)

| # | Decision | Why |
|---|---|---|
| P4 | `.env.example` is un-ignored with `!.env.example` | `.env.*` would otherwise hide the template that tells the team which keys exist. |
| P5 | **No licence file yet** | Choosing a licence is the team's decision. Without one the code is "all rights reserved" even if the repo is public. Add MIT or Apache-2.0 if you want others to reuse it. |
| P6 | A secrets and personal-data scan runs over tracked files before publishing (keys, tokens, email addresses) | A final check that nothing private slips in. |
| P7 | Security issues are reported through private GitHub security advisories | Standard practice for a public repo. |

## Floor plan view (`web/index.html`)

| # | Decision | Why |
|---|---|---|
| V1 | Animated SVG floor plan: timer house and Heatwise house side by side, each room coloured from 12°C (blue) to 22°C (red), showing temperature, target, heater kW, and whether someone is in the room. Slider and play button over the whole week. | Makes the controller's choices visible at a glance (an empty bedroom left at 17°C, rooms coasting at the peak), and gives screenshots for the pitch. |
| V2 | `run_toy` exports the full week per room (`week` in `data.json`), written as compact JSON (about 86 KB) | The page needs every step. Indented JSON would be around 10× larger. |
| V3 | Running £ and CO₂ totals computed in the browser from kWh and the day's prices | They aren't stored twice, and scrubbing stays instant. |
| V4 | Hand-drawn SVG with a fixed layout for the 3 toy rooms; rooms not in the layout are skipped | The simplest thing that works. When the MVP adds rooms, extend `LAYOUT`. |
| V5 | All text set with `textContent`, never `innerHTML` | Safe even if the data file is ever replaced by something untrusted. |

## Phase 2: the household app

### Calendar (`heatwise/calendar.py`)

| # | Decision | Why |
|---|---|---|
| K1 | Read Google Calendar through the user's **secret iCal address**, not OAuth | Chosen by the team. It works in minutes with no Google Cloud project, consent screen or redirect URLs. The trade-off: the URL is a read token, so it's treated like a password. |
| K2 | The URL lives only in `.env` (`HEATWISE_ICAL_URL`). It must be https, it never appears in errors (a test checks this), it's never returned by the API, and downloads are capped at 5 MB. | It grants read access to someone's calendar. |
| K3 | Recurring events (RRULE) are **not expanded** yet | Keeps parsing simple today. The `recurring-ical-events` package can add it later. |
| K4 | Times are converted to UTC | London is UTC in winter. In British Summer Time this is an hour off, so fix it with `zoneinfo` (plus `tzdata` on Windows) before real use. |
| K5 | Keyword classifier: away (trip, flight, holiday…), WFH, guests. Anything else (gym, dentist) is shown but doesn't change the heating. | It works with no LLM. The LLM will replace it for messy titles (the next round). |
| K6 | "Away" events pre-heat for the **last 2 hours** before they end | So you come home to a warm house. That's the welcome-home moment. |
| K7 | The demo calendar is generated for the current week (Gym Mon, WFH Tue, a trip Thu to Fri, friends over Sat), not a fixed `.ics` file | A file with fixed dates would go stale. Generating it keeps the demo week current. |

### Live home (`heatwise/live.py`)

| # | Decision | Why |
|---|---|---|
| L1 | Override priority: controller < calendar < away toggle < Boost < out of credit < the 12° safety floor | Manual actions beat automatic ones, and safety beats everything. |
| L2 | The simulated people follow the calendar (nobody home during an away event; living room in use during WFH or guests) | Keeps the demo consistent: the sensors agree with the calendar. |
| L3 | **Budget projection = spent + expected daily cost × days left. Expected daily cost starts at a prior (a typical simulated week, about £5.68 a day) and moves to observed spend over the first 24 h.** | The first version extrapolated 2 hours of evening warm-up to £112 a week and trimmed 3° straight away. The prior stops that early overreaction. |
| L4 | Boost = comfort for 0.25 to 6 hours. Top-up £0 to £200. Manual trim 0 to 3°. Room names from a fixed list. | Validated input, so the API is safe to expose and a typo can't do anything silly. |
| L5 | The "today's plan" timeline uses the routine heatmap only (future motion is unknown) and assumes someone's home unless the calendar says otherwise | The honest forecast of what it will do. Live motion then refines it as the day happens. |
| L6 | Status chips and "why" sentences are templates built from the controller's reason codes. Probabilities of 95% or more read as "very likely". | Works with no LLM. The LLM can reword these later without changing the API. "100% chance" sounded wrong. |
| L7 | The simulated week starts Monday 16:00, and a demo clock moves time forward | Shows the evening routine straight away. The pitch can fast-forward through a day. |

### App (`heatwise/app.py`, `app/index.html`)

| # | Decision | Why |
|---|---|---|
| U1 | *(Superseded by U9.)* A mobile web app (FastAPI with one static page), styled after the Hive app: greeting, away switch, room cards with actual and target temperatures and a Boost button | Chosen by the team. It works on any phone through a link, with no app store or build step. The Hive layout is familiar to UK smart-heating users. |
| U2 | Every endpoint returns the full home state | The page is a pure render of the server state: no client-side state to get out of sync, and simple to test. |
| U3 | A demo clock (+15m, +1h, Play, Reset) instead of real time | A real week is too slow for a 3-minute pitch. |
| U4 | Demo budget defaults to **£30** a week (`HEATWISE_BUDGET`) | At £30 the projection goes over on Monday evening, so the approval flow (Top up or Trim) shows in the demo. Auto-trim then brings it back on track by Wednesday. The toy run keeps £40. |
| U5 | Top-up and trim are buttons in the budget card, and the top-up goes through the supplier (local, or the SolvaPay checkout URL opened in a new tab) | "Who approves the spend" is visible and one tap away. |
| U6 | The "nobody home" tip shows only when every room really is at frost level | The first version showed it while rooms were warming up for people arriving home, which contradicted the room cards. |
| U7 | No assistant chat yet | The LLM is deferred to the next round (the team's call). The "why" sentences are templates for now. |
| U8 | DOM built with `textContent`, docs/OpenAPI off, one lock around the household, server bound to 127.0.0.1 in the instructions | Safe defaults if the repo or demo goes public. |

### Revised UI (iOS Human Interface Guidelines)

| # | Decision | Why |
|---|---|---|
| U9 | Rebuilt the app to the team's iOS UI standard: four tabs (Home, Budget, Schedule, Settings), a pushed Room screen, inset grouped lists, system font and text styles in `rem` (scales with the browser's text size), iOS semantic colours with light and dark mode, and one accent (system orange). | The first version read as a template (emoji icons, coloured chips, cards inside cards). The standard asks for what Apple's own apps do. |
| U10 | **Boost removed** everywhere (UI, API, engine, tests) | The team's call. |
| U11 | Icons are a small hand-drawn outline set at one weight, not SF Symbols | Apple's licence only allows SF Symbols in apps on Apple platforms, and this is a web app. One consistent set keeps the rule's intent. |
| U12 | One file per screen, plus shared `ui.js`, `api.js`, `format.js` and `styles.css` | Compartmentalised, as asked. Screens can be changed or swapped on their own. |
| U13 | Top up uses an action sheet (£5, £10, £20, Cancel) | The web equivalent of `.confirmationDialog`: one primary action, with the choices kept off the main screen. |
| U14 | Loading uses placeholder rows. Errors and empty states use a centred "content unavailable" view with a Retry action. | The standard asks for all three states on every screen, and for placeholders over spinners. |
| U15 | Each tab keeps its own navigation stack, and tapping the current tab pops to its root | iOS behaviour. A test in the browser found the Room screen staying on top when switching tabs. |
| U16 | At the largest text size, row values stack under their titles | At 160% text, "Electricity" and its value overlapped. iOS stacks rows the same way at accessibility sizes. |
| U17 | Demo time controls moved into Settings, under Demo | Keeps the main screens about the household. The demo controls are still one tap away for the pitch. |
| U18 | Assets are served with `Cache-Control: no-cache` | Browsers kept stale JavaScript modules after edits. Revalidating each load fixes that. |
| U19 | No emoji anywhere, including the demo calendar ("Trip to Manchester") | Part of the standard. |
| U20 | **One splash of colour:** a black → orange-red gradient summary panel at the top of Home (average inside temperature, rooms heating) and Room (temperature and target), plus an orange → red Budget progress bar. Text on the panel is always white, so it reads the same in light and dark. | The team asked for black and orange-red. The standard bans purple, blue and pink gradient backgrounds and gradient text or buttons. One dark gradient panel per screen is in line with Apple's Wallet and Fitness, and keeping everything else plain stops it looking like a template. |
| U21 | `tools/screenshots.py` drives Chrome through the DevTools protocol at exactly 390 × 844 at 2×, and the app accepts `?tab=` and `?room=` deep links | Headless Chrome on Windows won't lay out narrower than about 500px, so `--window-size` screenshots came out clipped. Deep links let each screen be captured directly. |
| U22 | **Appearance setting: System, Light or Dark** (segmented control in Settings), saved in this browser's storage. Storage failures fall back to System. `?theme=` still overrides for previews. | The team wants both modes available. It's a per-device display preference, so browser storage is the right place, not the server. |
| U23 | **Accent moved from system orange to orange-red** (`#f04a1d` light, `#ff6a3d` dark), with a warmer partner (`--tint-2`) used only inside gradients. Heating status text, the tab bar, actions, the switch, gradient chart bars and the progress bar all use it. | The team asked for more orange-red. It's still one accent hue, used on interactive elements and the "heating" state. The light value is darker than pure orange-red so text keeps reasonable contrast on white. |

### Friendly redesign

| # | Decision | Why |
|---|---|---|
| U24 | **Moved away from the iOS look to a warm, friendly style.** Soft rounded cards on a warm off-white background (warm charcoal in dark mode), a floating pill tab bar, and plain-English labels ("Resting to save energy", "Keeping you cosy", "Pricey now"). Supersedes U9's grouped lists and U11's iOS icon intent. | The team found the iOS version too "Apple-esque" and asked for something more intuitive, friendly and simple. |
| U25 | **Typography: Outfit for headings and numbers, Nunito Sans for text** (Google Fonts, falling back to the system font when offline) | Outfit is geometric and rounded, so big temperatures feel friendly. Nunito Sans is soft and very readable at small sizes. Two families, clearly split by role. |
| U26 | **Visuals chosen to be understood in a glance:** a temperature bar per room (filled to now, a marker at the target, 12° to 24° scale), a budget ring, a traffic-light price pill, a 24-hour strip per room, and CO₂ shown as "about the same as driving N km" | Each answers one question without reading numbers. The CO₂ comparison uses about 0.17 kg per km (an average UK car). |
| U27 | Two meaning colours: **orange-red = heating, money and actions**; **sage green = saving, cheap, clean**. A separate mid-orange marks "kept mild" and "pricey" in strips. | Colour carries meaning, so it's easy to read. A screenshot review showed "kept mild" and "resting" looked the same, so the mid tone was added. |
| U28 | Times in 12-hour format ("6pm", "7pm to 11pm") | Friendlier and more natural in everyday British speech than "18:00". |
| U29 | Tab renamed "Schedule" → **"Plan"**. Settings uses "Look", "Comfy temperature" and "Pretend time". | Shorter, everyday words. |

### Assistant (`heatwise/assistant.py`, `app/js/screens/ask.js`)

| # | Decision | Why |
|---|---|---|
| A1 | "Ask Heatwise" turns a message into an answer or **one proposed action** (away, comfort, trim) that the user must tap to confirm | The LLM never controls heating directly. Humans approve changes. |
| A2 | Two engines: keyword rules (always on) and Claude `claude-opus-5-5` at low effort when `ANTHROPIC_API_KEY` is set. Claude's JSON is validated against the same allow-list; any error, refusal or bad output falls back to rules. | The app works offline and without a key; Claude makes it understand messy phrasing. |
| A3 | Numbers in answers come only from the engine state passed in, never from the model | No made-up savings or temperatures. |
| A4 | Input capped at 500 characters; `/api/confirm` re-validates every action | Safe to expose. |

### Real-time demo (branch `heatwise-realtime`)

| # | Decision | Why |
|---|---|---|
| T1 | **Live mode is the default**: the week starts today, the clock follows real time (UTC, which is London time in winter), and the house catches up to "now" on every request | The demo looks live when opened. |
| T2 | A **generated calendar around now** (gym in an hour, WFH tomorrow, a trip in two days, friends over in five) when no real calendar is connected | Always something upcoming to show how the calendar changes heating. |
| T3 | **Fallback to the simulated week** if live mode fails to start (`HEATWISE_MODE=simulated` forces it), plus a Live / Example week switch in Settings → Demo | The demo never dies; the example week can still be fast-forwarded. |
| T4 | Kept on its own branch | So the stable `heatwise-mvp` stays untouched until the team picks one. |

### Demo-friendly version

| # | Decision | Why |
|---|---|---|
| D5 | **The example week is the default** (`HEATWISE_MODE=simulated`); live mode stays a switch in Settings | A whole week can be shown in a minute and it always works offline. Live mode changes too slowly for a pitch. |
| D6 | **Demo tab**: Play (1 h or 6 h per second), jump to any day (restarts the week and fast-forwards, keeping calendar and limits), Luke's notes, and an editable mock calendar | Everything for showing off on one screen. |
| D7 | **Luke, the helper agent**: one named voice (monogram avatar, no emoji). He chats on Home, narrates the week ("Warming the living room. Someone usually comes in soon."), and asks for approval when a limit is hit | A friendly, memorable agent makes the AI + payments story easy to follow. |
| D8 | **Limits**: weekly budget (money loaded through SolvaPay) and an optional daily limit. When it's hit, rooms in use drop to eco and the rest rest (never below 12°), and Luke asks "Allow £2 more?" | The agent-spending-limit moment, made visible. |
| D9 | Purchases are narrated once an hour ("Paid 60p for heat this hour. £19.70 left") | Every 15 minutes was too noisy. |
| D10 | **No heatmaps or strips anywhere.** Room: a line chart (temperature vs target, last 24 h). Budget: spend-per-day bars with the limit as a dashed line. Impact: CO₂ per day, timer vs Heatwise. The analyst page's floor-plan section was removed. | The team found the strip visuals hard to read; simple line and bar charts read at a glance. |
| D11 | **Impact tab**: money and CO₂ saved vs an ordinary timer over the same simulated days, in everyday terms (km driven, phone charges), plus three one-line "why it matters" cards | Sustainability that's easy to digest. CO₂ comparisons: about 0.17 kg per km driven, about 12 Wh per phone charge at about 0.2 kg CO₂ per kWh. |
| D12 | Not done: Luke adding calendar events from chat | Kept scope tight; events are added from the Demo tab. |
| D13 | **Slower playback**: Slow / Normal / Fast = 15 min, 30 min, 2 h of house time every 1.5 s (was 1 h or 6 h per second) | The team found it too fast to follow on stage. |
| D14 | **Per-room comfy temperature** on each Room screen (16–23°, or "use the house setting"). Heatwise still only heats the room when it's likely to be used; the bedroom keeps 17° overnight. | People want the living room warmer than the kitchen; this keeps the smart scheduling. |
| D15 | **Per-room warm-up time from physics.** For a cold room, the engine solves the RC model for how long the heater needs to reach the comfy temperature (plus 15 min), and looks that far ahead in the routine (horizons 0.5–4 h) instead of a fixed 3 h. Shown on each room's screen. | Your idea doc asked for "how long it takes that room to heat up". Over a test week: same comfort (95.3%), £33.25 vs £33.52, a small saving that grows in leakier rooms and colder weather. |
| D16 | **Plan tab leads with "This week"**: a day-by-day agenda (today highlighted) with calendar events as coloured chips, then the heating times, then cheapest times | The calendar was hard to find. |
| D17 | Removed the impact card from Budget | The Impact tab covers it. |
| D18 | **Clock bar on every screen** and a **house drawing** (rooms, people, heating flames) on the Demo/simulation panel. On screens 900px or wider the simulation sits **beside** the app, so you can drive the app while the house runs. | The team found it hard to watch the Demo tab and the other tabs at once. |
| D19 | **Luke's avatar is a friendly flame face** (inline SVG in `.avatar`, 52 × 60 px, centred beside his bubble). Supersedes the monogram in D7. | The team wanted a friendlier, on-theme character than a letter "L". Centring stops the empty gap under him. |
| D20 | **Live temperatures between 15-minute steps (real-time mode).** `LiveHome._live_temps()` runs the current step's physics on a copy of the house and shows the share of it that has happened so far, so a change shows up as "heating" and a rising temperature within seconds. Billing, history and charts still use whole steps. The app refreshes every 15 s (was 30 s). | After confirming a change with Luke, nothing moved for up to 15 minutes, so it looked broken. This is display-only, so costs are unchanged. |
| D21 | **Luke can set one room** (`{"type":"room","room":"living","value":22}`), validated against the room list and 16–23°, applied through `set_room_comfort`. The keyword rules understand "make the living room 22". | "Make the living room 22°" had no matching action, so Luke could only talk about it. |
| D22 | **Luke never claims a change he didn't propose.** His prompt says he can't change anything himself: any change is an action plus a question ("Shall I…?"). After you tap Yes he says what changed, the trimmed target if the budget trim lowers it, and the room's warm-up time from D15. | Claude sometimes said "done" with no action attached, so nothing happened. |
| D23 | **People by name and a routine panel in the simulation.** The simulator now records where each person is (`Occupancy.who`, room per step or -1 for out; calendar away/WFH moves them too). The house drawing shows Alex (orange) and Sam (blue) in their rooms, "Guest" for calendar-added people, and who's out. Below it, **The routine** spells out the usual weekday or weekend timetable, and **Today, step by step** lists every visit today with what Heatwise did: the room's target, when it started being held there, the temperature on arrival and ✓ warm / ✗ still warming. Shown in both live mode and the example week. | The team wanted to see where people are and check the heating matches the routine. `who` is ground truth for display only; the controller and model still only see sensors (O2). |
| D24 | **Realistic temperatures: comfort 21°C (was 20), bedroom overnight 18°C (was 17), eco stays 17°C, rooms start at 18°C. Demo budget £45 a week (was £30, supersedes U4).** Toy-run results refreshed: timer £46.94 / 69.8% comfort, Heatwise £42.99 / 96.4%. | The team found 19° rooms too cold. 21° is the usual UK living-room setting and 18° a common bedroom one. At those settings a week costs about £41, so the old £30 budget kept the full 3° trim on all the time and rooms sat at 18–19°. At £45 nothing is trimmed unless you tighten the budget; the approval moment is shown with the daily limit (D8) instead. |
| D25 | **Routine panel made easier to read, and shows how today varies.** "A usual weekday/weekend" lists each person's day as moments ("7am Gets up, to the kitchen", "7:45am Leaves the house"). "Today, step by step" compares every visit with the usual timetable (`vs_usual`: minutes early/late, or not usual, e.g. working from home), lists the notable ones (30+ min, or not usual) at the top with whether Heatwise had the room warm, and tags them on each visit. Short "out" gaps under an hour (timing noise between two home blocks) are hidden. | The team wanted the routine easier to digest and to see Heatwise adjusting to variations. Shifts under 30 minutes are within the simulated ±30 min wobble, so listing them was noise. |
| D26 | **"Today, step by step" sits beside the house drawing.** When there's room (the panel is 620px or wider, via a container query) the two are side by side and the house stays pinned while you scroll the day. On screens 1360px or wider the simulation panel widens from 420px to 760px to make room. On a phone they stack. "A usual weekday/weekend" follows underneath. | The team wanted to read the day while watching the house, without scrolling between them. |
| D27 | **Luke as a maintenance helper: he spots heating faults and gets them fixed within a repairs allowance** (`heatwise/repairs.py`). Each step the engine compares how much a heated room warmed with what the house model says the heater should have done (after normal cooling). If, over 2 hours of hard heating, a room gets under half the expected warming (and at least 1° was expected), Luke raises an issue, explains it ("+1.4° when I expected +3.4°, the valve may be stuck") and offers a fixed-price engineer (£85). You approve or dismiss; approval pays from a repairs allowance (default £100) and books the first working-hours slot (9am–5pm, 2 h notice); after the visit the heater works again and Luke confirms. A demo button breaks a radiator (it then gives a fifth of its heat, but the electricity is still used and paid for). | The team's product idea: you give Luke money and rules and never think about heating, including repairs. Fault detection is real (from the physics model); **the engineer, quote and repair payment are simulated** (no real booking or payment for repairs yet). In a real home the "actual" warming comes from the room sensor. |
