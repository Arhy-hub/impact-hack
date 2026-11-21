# Heatwise: smart home heating

## The idea

Most home heating is old-fashioned and manual. You set one temperature on the thermostat, then turn each radiator up or down by hand depending on how the house is being used. The whole house gets heated all day, even rooms nobody goes into.

Heatwise is an app that works out where people are, and where they are about to be, and only heats those rooms. It also looks at electricity prices and a monthly budget the user sets, and gives tips to hit that budget.

## What it should do

1. **Know where people are.** Motion sensors in each room, plus phones to show who is home or away.
2. **Learn the household routine.** For example: bathroom at 06:45, kitchen at 07:15, living room from 18:00. Weekdays and weekends are learned separately.
3. **Heat the right rooms at the right time.** Warm a room before someone usually arrives, based on how long it takes that room to heat up. Let unused rooms drop to a lower, cheaper temperature.
4. **Save on electricity prices.** Store a little extra warmth during cheap hours. Let occupied rooms coast about 1° lower during peak hours.
5. **Hit a monthly price goal.** The user types in a budget. The app projects the month's spend and lowers comfort targets a little at a time if the month is heading over.
6. **Give simple tips.** Examples:
   - "It's only 9° outside and your budget is tight. Put a jumper on and the living room can drop 2°."
   - "Peak prices start at 16:00. Run the dishwasher now or after 19:00."
   - "Keep the hall door shut."

## How it decides (the rules)

For each room, every few minutes:

1. Is someone in the room now (motion in the last 15 minutes)? Heat to the comfort temperature.
2. Is someone usually in the room soon? Work out how long the room needs to warm up. If the learned chance of use within that time is 40% or more, start heating now.
3. Otherwise: if someone is home, hold the room at a low "eco" temperature. If nobody is home, hold 12° as a safety level.
4. Adjust for price: slightly higher target in cheap hours, slightly lower in peak hours.
5. Subtract a "budget trim" (0 to 3°) when the projected monthly cost is over the goal.

The budget trim comes from a simple projection: recent daily cost multiplied by the days left, added to what has been spent so far.

## Parts of the system

| Part | Job |
|---|---|
| Room sensors | Motion, plus temperature, one per room |
| Phones | Home or away (Wi-Fi or Bluetooth) |
| Smart radiator valves or smart plugs | Let the app control each room's heat |
| Controller (Raspberry Pi or a server) | Runs the learning and the rules above |
| App | Shows rooms, costs, tips; lets the user set comfort temperatures and the budget |
| Electricity price feed | Gives current and upcoming prices, if the user has a time-of-use tariff |

## Hardware ideas

- ESP32 boards with a motion sensor and a temperature sensor in each room (cheap and good for a project)
- Home Assistant as the hub, since it already talks to many valves and smart plugs
- Off-the-shelf smart radiator valves if the house has water radiators (for example Tado, Hive or Aqara)
- Smart plugs if the heaters are electric

## What has been built so far

A working simulation, published as a private page called **Heatwise**. It has:

- A fake house with six rooms and three people following weekday and weekend routines
- A heat model: rooms lose heat outside and share heat through walls and doors
- The smart controller described above, running side by side with an old-style "whole house on a timer" system
- Learning of routines, shown as a heatmap
- Peak, standard and cheap electricity rates
- A monthly budget goal with a live projection and automatic comfort trimming
- Live tips
- Controls for outside temperature, heat source (heat pump or electric heaters), room comfort temperatures, "everyone out for 8 hours", and "forget learned routines"

In the simulation at 6° outside and a £100 goal, the smart system cost about 17 to 20% less than the old setup, and people were comfortable about 95% of the time, compared with about 65% for the old one. These numbers come from made-up house values, so they only show the idea works. Real houses will differ.

## Build plan

1. **Prototype (done):** the simulation, to test the rules.
2. **Real sensors:** build one room's sensor with an ESP32 and send data to Home Assistant.
3. **Logging:** collect real motion and temperature data for a couple of weeks.
4. **Learning on real data:** run the routine learning on that data and check how well it predicts.
5. **Control one radiator:** use a smart valve or plug in one room and run the rules live.
6. **Whole house:** add the other rooms, then the app screens for budget and tips.
7. **Tune:** measure the real heat-up time of each room and replace the guessed numbers.

## Risks and open questions

- **Privacy:** motion data shows when people are home. Keep it on the local network and don't send it to the cloud.
- **Safety:** the system must never let a room freeze, and must keep working (a safe default) if sensors or Wi-Fi fail.
- **Heating type:** water radiators with a boiler behave differently to electric heaters. Boilers like long steady runs, so switching rooms on and off needs care.
- **Guests and pets:** extra people or pets can trigger motion sensors. The rules need to cope.
- **Odd days:** holidays, illness and people working from home break the learned routine. Live motion has to override predictions.
- **Prices:** a time-of-use tariff only helps if the household has one. Without one, the off-peak part does nothing.
- **Comfort:** the app should always let the user override and heat a room now.

## Name and next steps

Working name: **Heatwise**.

Next steps to decide:

1. What heating the real house has (boiler with radiators, or electric).
2. Whether to build on Home Assistant or write the controller from scratch.
3. Which room to start with for the first real sensor.
