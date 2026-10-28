# Utility-facing recommendation | One-page summary

**Measured REFIT status (House 5 held-out test):** RF MAE = 18.2012 W; always-off MAE = 10.4598 W; the candidate does not improve on the overall-MAE baseline. Review active F1 = 0.1477 before any pilot recommendation.

## What the electricity distributor could use

A household-level NILM model could *estimate* washing-machine activity and provide contextual consumer feedback where direct appliance metering is unavailable. A useful early-stage product is an **opt-in appliance-usage summary** showing approximate days/times of laundry use and estimated energy per cycle, accompanied by confidence/quality disclaimers.

## The specific business opportunity

If the customer actually has a time-varying tariff and a flexible laundry schedule, the utility can invite them to move washing cycles from peak to off-peak times. The key objective is **lower peak-period demand and potentially lower bills**, not automatically lower energy consumption in kWh. If a single customer shifts one 1-kWh wash to a cheaper period, total energy can stay at 1 kWh; the timing and price change.

## How to prove it works

Recruit consenting households, collect a ground-truth submetered validation sample, compare estimates to actual machine readings, and run a randomized opt-in pilot. Track **peak kWh shifted**, bill savings where applicable, monthly aggregate load, user satisfaction, opt-out, false activity notifications, and per-cycle estimation error against an untreated control group. Evaluate fairness across dwelling types and tariff eligibility. Do not apply a decision if signal quality is poor.

## Technical and data limits

Washing-machine, dishwasher, kettle and heater signatures can overlap, so aggregate-based predictions are uncertain. REFIT contains sensor dropouts, corrections, periods of zero filling, different appliance makes and different home consumption patterns. The trial is UK-derived; Indian households may differ in appliance types, power supply, water-heating habits, usage schedules and tariffs. Transfer to India requires local data collection, validation, retraining and compliance/privacy review.

## What if utilities have only 15/30-minute meter intervals?

A 5-minute power spike can be diluted into a 15- or 30-minute average. Precise washer start times, sub-cycle power changes, peak watts and individual short cycles become harder to identify, while overlapping devices can be impossible to distinguish. Monthly/weekly usage summaries may still be possible, but fine-grained cycle detection and energy attribution need to be evaluated at the coarser resolution rather than extrapolated from 1-minute performance.

## Recommendation decision

**Proceed as a research proof-of-concept, not automated billing or enforcement.** Require a real-data result better than the always-off baseline *and* acceptable active-cycle performance on held-out homes before a customer pilot. Report uncertainty openly and retain a ground-truth monitoring group.

<!-- EXTENDED_REFIT_HOUSE6_EVALUATION -->

## Measured evidence and go/no-go decision

In the new House 6 holdout, the validation-selected original Random Forest + 50 W cutoff has MAE 5.39 W vs 3.12 W for always-off; active F1=0.303, precision=0.217, recall=0.500. The method is not sufficiently reliable for personalised washing-machine event notifications, billing or automated enforcement. Continue research only; perform fresh cross-household validation and collect additional appliance-ground-truth data before proposing any utility pilot. Avoid claiming energy savings from unvalidated NILM estimates.
