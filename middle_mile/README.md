# Middle Mile Parcel Impact

**When a truck between sort centers is late, which one puts the most parcels at risk, and what is the cheapest way to save them?**

This is part three of the series in this repo, in two parts:

- **Part 3b, the planner's network** (`connected/`): the planner's real 2023 orders and its two staffing plans, shipped across a Midwest network. This is where the series connects.
- **Part 3a, the method** (the rest of this folder): built and tested first on about 96,000 real parcels from Olist in Brazil, where real delivery promises exist.

## Part 3b: the planner's network

The planner's own staffing model decides on which day each of the 32,634 real 2023 orders is finished. That day sets when the parcel can leave the site, so the staffing decision flows straight into the middle mile. Each parcel then rides a truck to a sort center and a second truck to a delivery station, and is compared with its delivery promise.

| | 6 workers (affordable plan) | 10 workers (safe plan) |
| --- | ---: | ---: |
| Labor cost | $242,253 | $398,222 |
| Late parcels caused by the warehouse | 677 | 0 |
| Late parcels once random truck delays are added | 919 | 32 |
| Late parcels caused by trucks | 242 | 32 |
| Trucks that caused late parcels | 30 | 7 |
| Late parcels after rescuing those trucks | 678 | 0 |
| Cost of rescuing them | $7,327 | $1,514 |

Costs are hypothetical units, the same ones the planner uses.

**What it means**

- **Understaffing makes truck delays far more harmful.** With 6 workers, trucks cause 242 late parcels. With 10 workers, only 32. An order the warehouse finishes on the last day of its window has no time left, so even a small truck delay breaks its promise.
- **The warehouse is the bigger cause.** Under the affordable plan, 677 parcels are late before any truck is late, and trucks add 242.
- **Rescue the at risk trucks first. It is cheap.** Splitting the load on the 30 trucks that cause late parcels costs $7,327 and fixes 241 of the 242, about $30 per parcel.
- **More staff is the expensive fix.** Moving from 6 to 10 workers costs $155,969 more and removes the remaining 678 late parcels, about $221 for each extra on time parcel, even after the trucks are rescued.
- **Which lane looks worst depends on the assumed schedule.** Most truck caused late parcels are on the Chicago to Indianapolis lane, because Indianapolis gets a next day promise and its truck arrives about 40 minutes before the station cutoff.

**What is real and what is assumed**

| Real (from the planner) | Assumed (set in `connected/config.json`) |
| --- | --- |
| 32,634 orders with their time, customer and units | The Midwest network: three sites, two sort centers, six delivery stations |
| The two staffing plans and their cost rates | Which customer ships from which site to which station |
| The day each order is finished, from the planner's service model | Truck schedules, speed, the 07:00 station cutoff and truck delays |
| The site shares (43%, 42%, 15%) | The promise: 2 working days to finish an order, plus 1 day of transit within 300 km or 2 days beyond |

City locations are real places. Station populations are approximate 2020 metro populations, used only as weights. Because a few large customers place thousands of orders, actual route volumes differ from the site shares: O'Hare ships 52% of orders against its 42% share. The planner's service model treats the three sites as one operation, so this changes which routes carry parcels, not when orders are finished.

Run from the repo root, with the planner's raw order data and database in place:

```bash
.venv/bin/python middle_mile/connected/build_connected.py
```

Results are in `connected/results/`.

## Part 3a: the method on real Brazilian data

This part puts about 96,000 real parcels from the Olist marketplace (Brazil, 2016 to 2018) on a simulated hub network. The parcels, routes and delivery promises are real. The trucks, schedules and delays are assumed and labeled. It measures what truck delays, cancelled trucks and closed hubs do to those parcels, and compares ways to recover.

### The answer

- **Hours long truck delays rarely break a real delivery promise.** Of 59,230 parcels that need a truck leg, 1,538 (2.6%) slip by one day when every truck gets a random delay, but only 26 (0.04%) become new late deliveries. Olist's promised delivery dates are generous: the median parcel arrives 13 days before its promise.
- **The São Paulo hub is the critical hub.** If it closes for a day, 68 parcels slip on average and 426 on the worst day. Every other hub is far smaller. Even then, the average is under one new late delivery.
- **Target the trucks that matter.** Only 267 trucks put parcels at risk. Choosing the cheaper of two fixes on each of them saves over 99% of the slipped parcels at about one sixth of the cost of swapping the trailer on every late truck.
- **The recovery choice holds up.** It was the best option under all 3 departure schedules, and in 19 scenarios that change the swap cost, the split cost and the hours a swap recovers (18 outright, 1 tie).
- **One result does not hold up.** Which lane looks worst depends on the assumed departure times, so do not read the lane ranking as a finding about any real carrier.

### What is real and what is assumed

| Real (Olist data) | Assumed (simulated, set in `config/`) |
| --- | --- |
| 96,281 delivered orders, treated as parcels | Six sort centers in a hub and spoke around São Paulo |
| Seller state, customer state and route | Truck departure times, speed, loading time and capacity |
| Handover time to the carrier (with time of day) | A 3 hour sort time and a 20:00 cutoff at the destination |
| Real delivery time and the promised date | Random truck delays and how much they vary by lane |
| Real distances from zip code coordinates | Recovery options and their costs |

The results show how delays move through a network that matches Olist's real totals. They are not facts about any real carrier. All costs are hypothetical units.

### Results

Delays and disruptions on 59,230 parcels with a truck leg. A parcel "slips" when it misses the destination cutoff and goes out a day later. A "new breach" is a slip that pushes a parcel past its real promised date.

| Scenario | Parcels slipped | New breaches |
| --- | ---: | ---: |
| Random delay on every truck, main schedule | 1,538 (2.6%) | 26 |
| Same, trucks leaving at 04:00 and 16:00 | 3,282 (5.5%) | 41 |
| Same, trucks leaving at 08:00 and 22:00 | 1,788 (3.0%) | 24 |
| 1% of lane days cancelled | 491 (0.8%) | 8 |

One hub closed for one whole day, tried for every hub and every day in the data:

| Hub | Parcels slipped per closure day | Worst day | New breaches per day (average, worst) |
| --- | ---: | ---: | ---: |
| São Paulo | 68 | 426 | 0.9, 14 |
| South | 28 | 169 | 0.3, 5 |
| Rio de Janeiro | 24 | 137 | 0.4, 6 |
| Belo Horizonte | 22 | 139 | 0.3, 6 |
| Northeast | 15 | 66 | 0.2, 4 |
| Center West | 6 | 30 | 0.1, 2 |

Recovery options for late trucks, main schedule:

| Policy | Cost | Parcels saved (of 1,538) | Cost per parcel saved |
| --- | ---: | ---: | ---: |
| Do nothing | 0 | 0 | n/a |
| Swap the trailer on every late truck | 568,500 | 1,014 | 561 |
| Split the load on every at risk truck | 299,976 | 1,530 | 196 |
| Cheapest option on each at risk truck | 93,336 | 1,530 | 61 |

The best 10% of rescues save 37% of the parcels for 9% of the cost, so a small budget goes a long way.

### How it works

1. **Prepare the parcels** (`scripts/prep_parcels.py`). Keep delivered orders with consistent times, add the real distance between seller and customer, and export one row per parcel.
2. **Build the journeys** (`scripts/build_journeys.py`). Each parcel reaches its origin hub at its real handover time, waits for the next truck, and goes through the São Paulo hub if it travels between two other regions. Arriving before the cutoff means the next morning delivery wave.
3. **Simulate disruptions** (`scripts/simulate_disruptions.py`). Add random truck delays, cancelled lane days and hub closures. A slip moves the real delivery date by the same number of days, and it is a new breach when the parcel's real slack was smaller than the slip.
4. **Compare recovery options** (`scripts/evaluate_recovery.py`). Test a trailer swap and a split load on every truck that causes slips, then apply four policies to the whole network.
5. **Check the recommendation** (`scripts/recovery_cost_robustness.py`). Change the swap cost, the split cost and how many hours a swap recovers.

`docs/DESIGN.md` explains the design choices. All assumptions are in `config/network.json`, `config/delays.json` and `config/recovery.json`.

### Limits

- **The schedule drives the lane results.** Trucks on a lane arrive at the same time every day, so how close a lane sits to the cutoff comes from the assumed departure times. Moving the departures changes the slip rate between 2.6% and 5.5%. The São Paulo to Northeast lane causes 70% of the slips in the main run because its 18:00 truck arrives only 45 minutes before the cutoff.
- **Olist times are in days.** The real data does not separate the truck leg from the last mile, so the truck leg is simulated and the rest of the real trip is kept as observed.
- **Costs are hypothetical.** The ranking of recovery options holds across the tested costs, but the cost per parcel saved ranges from 30 to 244 units across scenarios, so the absolute numbers mean little.
- **Scope.** Recovery covers routine truck delays only. Truck capacity is not enforced in the disruption runs. The network is scaled to Olist's volumes, about 176 parcels a day, so trucks carry tens of parcels.
- **No real carrier data.** Nothing here uses data from any real carrier.

### Run it

Download the Olist data from Kaggle ("Brazilian E-Commerce Public Dataset by Olist") and unzip it into `middle_mile/archive/`. The raw data is not included in this repo, and the licence is on the Kaggle page. Run from the `middle_mile` folder:

```bash
cd middle_mile
pip install -r requirements.txt
bash run_all.sh
python3 -m unittest discover -s tests
```

Each simulation step takes a few minutes.

## Part of a series

This is part three of the series in this repo: forecast demand and plan warehouse capacity in the [Workforce Capacity Planner](../README.md), then protect parcels on the middle mile here. Part 3b uses the planner's own orders and staffing plans.

## Data credit

Parcel data: Olist, "Brazilian E-Commerce Public Dataset by Olist", on Kaggle.
