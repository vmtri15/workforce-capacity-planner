# Design: which late trucks put the most parcels at risk

Question: when a truck is late, which one pushes the most parcels past their commitment, and what is the cheapest way to save them?

## What is real and what is assumed

Real (Olist, 96,281 delivered orders, Oct 2016 to Sep 2018):
- every parcel, its handover time, delivery time, promised date, seller state, customer state, weight
- great circle distance for each parcel
- the promised date, which gives each parcel real slack: promised date minus actual delivery date

Assumed (every item below is labeled as simulated in the code, the outputs and the dashboard):
- the network of sort centers and the trucks between them
- truck departure times, capacity and delays
- sort times and the cutoff at the destination
- how the real trip is split into truck, sort and delivery time

Results describe how delays move through a network that matches Olist's real totals. They are not facts about Olist's carriers.

## Network (hub and spoke around Sao Paulo)

Six sort centers, chosen from where parcels really start and end:

| Sort center | States | Why |
| --- | --- | --- |
| Sao Paulo (main hub) | SP | 71% of parcels start here, 42% end here |
| Rio de Janeiro | RJ, ES | 12.8% of parcels end in RJ |
| Belo Horizonte | MG | 11.8% of parcels end in MG |
| South (Curitiba) | PR, SC, RS | 13% of parcels end in the south |
| Center West (Brasilia) | DF, GO, MT, MS and the north states | about 7% |
| Northeast (Salvador) | BA, PE, CE and the other northeast states | about 8% |

Parcels between two spokes go through Sao Paulo. Parcels from Sao Paulo to Sao Paulo stay local and have no truck leg. Only the truck legs between sort centers are simulated.

## How one real parcel becomes a simulated journey

1. The real handover time is when the parcel reaches its origin sort center.
2. Assumed sort time: 3 hours. Then the parcel waits for the next truck on its lane.
3. Assumed schedule: 2 departures per lane per direction each day, at 06:00 and 18:00.
4. Truck leg time = the real distance between the two hub cities divided by an assumed 60 km per hour, plus a fixed 1 hour for loading. Because the schedule and lane lengths are fixed, a truck on a given lane arrives at the same clock time every day, so how close each lane sits to the cutoff comes from the assumed schedule. Results should be re-checked with other departure times.
5. Assumed destination cutoff: 20:00. A parcel that arrives before the cutoff goes out on the next morning delivery wave. A parcel that arrives after it waits one more day.
6. Final delivery time stays as observed, so the whole journey still adds up to the real total.

Truck capacity is a rule, not a guess at a number: 1.3 times the busiest day's volume on that lane, divided by the 2 departures. The network is scaled to Olist's volumes (176 parcels a day on average, 406 on the busiest 5% of days), so trucks carry tens of parcels, not thousands.

## Delays

Each truck gets a random delay. The typical delay is small and the tail is heavy. The spread for each lane is scaled by the real variability of that route, meaning how far the real 90th percentile transit time sits above the median. This scaling is an assumption.

## Measuring impact

A delayed truck either still makes the cutoff or misses it. A missed cutoff slips every parcel on that truck by one day. A slipped parcel becomes a new breach when its real slack is smaller than the slip. Real slack comes from the real promised date.

For each truck and day:
- parcels on board
- parcels that miss the cutoff
- new breaches caused by the delay
- trucks ranked by new breaches, not by minutes late

## Recovery options

| Option | Effect | Cost |
| --- | --- | --- |
| Do nothing | the delay stands | none |
| Swap in a faster trailer | removes some hours of delay | assumed cost per swap |
| Split the load and send the urgent parcels by a second truck | the urgent parcels avoid the delay | assumed cost per extra truck |

Compare parcels saved against cost, and report the cheapest option that saves the most parcels.

## Scope

In: the network, the journey model, delays, the impact engine, three recovery options, a dashboard, and a README with the results.
Out: real time operations, routing optimization, the last mile leg, any real carrier or Shopee data.
