# REFIT data-quality findings - generated

**Data status:** `official_REFIT_analysis`

Raw House 1 analysis is restricted to the requested timestamp window.

Source: RAW_House1_Part1.csv, RAW_House1_Part2.csv; UTC: 2014-09-01 16:55:24+00:00 to 2014-11-30 23:59:58+00:00

Input rows: 1,400,757; invalid timestamps: 0; duplicates: 170,622.

Median sample interval: 7.0 s; intervals >20 seconds: 1,764; out-of-order source timestamps: 1.

Missing source-readings per column (before cleaning): {'Aggregate': 66746, 'Appliance1': 143973, 'Appliance5': 259099}.

Minute bins with no samples: 3,334; long gaps stay missing (NaN).

Long missing runs (>2 min) by column: {'Aggregate': 13, 'Appliance1': 23, 'Appliance5': 602}. Total missing-run minutes: {'Aggregate': 3131, 'Appliance1': 3192, 'Appliance5': 10182}. Example start times: {'Aggregate': ['2014-09-02 05:14:00+00:00', '2014-09-08 11:02:00+00:00', '2014-09-08 11:09:00+00:00', '2014-09-29 04:18:00+00:00', '2014-09-29 04:22:00+00:00'], 'Appliance1': ['2014-09-02 05:14:00+00:00', '2014-09-04 13:59:00+00:00', '2014-09-08 11:02:00+00:00', '2014-09-08 11:09:00+00:00', '2014-09-29 04:18:00+00:00'], 'Appliance5': ['2014-09-08 11:02:00+00:00', '2014-09-08 11:09:00+00:00', '2014-09-29 04:06:00+00:00', '2014-09-29 04:15:00+00:00', '2014-09-29 04:43:00+00:00']}. These may include sensor-invalidated periods and are not independently verified physical outages.

Short gap-filled minute bins: {'Aggregate': 223, 'Appliance1': 278, 'Appliance5': 1407}; unfilled bins: {'Aggregate': 3131, 'Appliance1': 3192, 'Appliance5': 10182}.

Invalid IAM samples: {'Appliance1': 36, 'Appliance5': 115}. Negative aggregates: 0.

Duplicate rule: last source-record wins. Negative values and IAM readings over 4000W become missing.

Only fully bounded gaps of 1-2 one-minute bins are forward filled; longer missing runs remain NaN.

Means of readings within each one-minute bin represent power, not total energy.

Official cleaned REFIT is a separate dataset; its prior imputation and zero-filled outages may hide missingness.



## Per-house official cleaned-data summaries

- House 1: CLEAN_House1.csv / Appliance5 / 2014-09-01 16:55:00+00:00 - 2014-11-30 23:59:00+00:00; available 124,390 min; missing 5,635 min; off fraction 0.9856; cycles 17.

- House 2: CLEAN_House2.csv / Appliance2 / 2014-09-01 00:00:00+00:00 - 2014-11-30 23:59:00+00:00; available 120,576 min; missing 10,464 min; off fraction 0.9573; cycles 99.

- House 3: CLEAN_House3.csv / Appliance6 / 2014-09-01 16:55:00+00:00 - 2014-11-30 23:59:00+00:00; available 121,682 min; missing 8,343 min; off fraction 0.9639; cycles 77.

- House 5: CLEAN_House5.csv / Appliance3 / 2014-09-01 00:00:00+00:00 - 2014-11-30 23:59:00+00:00; available 117,080 min; missing 13,960 min; off fraction 0.9181; cycles 131.
