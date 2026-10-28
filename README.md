# Washing-Machine Load Disaggregation from REFIT Smart-Meter Data

**Flock Energy | Data Science Take-Home Assignment | Reproducible Python project**

> **Execution status:** Code has been unit-tested and exercised end-to-end on explicitly SYNTHETIC demo data. **No real REFIT-derived findings are claimed in this starter repository.** Download and run the official data, then replace the pre-run placeholders in `DATA.md` and `RESULTS.md`. The final submission is a **public GitHub repository**; a PDF is an additional report, not a substitute for the repository.

## Problem and proposed solution

A smart meter observes the whole-house active power consumption, but the utility wants to estimate the portion attributable to a washing machine. The task is a simple form of **non-intrusive load monitoring (NILM)**.

`raw House 1 CSV -> quality audit -> one-minute cleaning -> raw comparison figures`

`official cleaned House 1,2,3,5 CSVs -> per-house EDA -> cycle detection -> causal aggregate-only features -> Random Forest -> held-out-house evaluation -> utility recommendation`

The official REFIT dataset covers 20 UK homes with approximately 8-second original sampling and power readings in **watts (W)**. This project works at 1-minute resolution by **averaging power** within the minute. Energy for each minute is `P(W) * (1/60 h) / 1000 = P/60000 kWh`. The measurement and model timestamps use the **Unix epoch in UTC**; this is deliberate because the raw local timestamps may be affected by daylight-saving changes.

## Datasets (download separately; do not commit the large archives)

The dataset is CC BY 4.0. Download:

1. **Official raw REFIT**: https://pureportal.strath.ac.uk/files/62090177/REFIT_RAW_081116.7z (about 666 MB archive). Extract to `data/raw/`.
2. **Official cleaned REFIT**: https://pureportal.strath.ac.uk/files/62090184/CLEAN_REFIT_081116.7z (about 490 MB archive). Extract to `data/cleaned/`.
3. **Official cleaned README / sensor map**: https://pure.strath.ac.uk/ws/portalfiles/portal/62090183/CLEAN_READ_ME_081116.txt
4. Dataset documentation: https://pureportal.strath.ac.uk/en/datasets/refit-electrical-load-measurements/
5. Cleaned dataset page: https://pureportal.strath.ac.uk/en/datasets/refit-electrical-load-measurements-cleaned/

After extraction, the program searches recursively for house-specific CSVs, accepting e.g. `RAW_House1.csv`, `House_1.csv`, `CLEAN_House1.csv`.

**Crucial:** The washer is NOT the same appliance column for every home. Mapping verified from the official cleaned README:

| House | Actual washing-machine column | Role |
|---|---|---|
| 1 | `Appliance5` | Train |
| 2 | `Appliance2` | Train |
| 3 | `Appliance6` | Validation |
| 5 | `Appliance3` | Test (held out) |

House 4 has two washer channels and was intentionally excluded from this four-home baseline to avoid silently combining independent washing machines.

## Installation (macOS / Linux / Windows PowerShell)

From the project root, Python 3.10+:

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
pytest -q
```

To extract `.7z` archives, use 7-Zip (Windows) or install the `7zip` command line (macOS/Linux). You may alternatively use `pip install py7zr` and extract using Python. The code expects extracted **CSVs**, not `.7z` files.

## RUN - official data

```bash
python -m refit_nilm.pipeline \
  --raw-dir data/raw \
  --clean-dir data/cleaned \
  --output-dir outputs \
  --start 2014-09-01 \
  --end 2014-12-01 \
  --max-train-rows 120000
```

On Windows PowerShell, use one line (remove the backslashes). The selected analysis window is **2014-09-01 inclusive to 2014-12-01 exclusive in UTC**, subject to availability in each home's CSV. This is a manageable comparison period, not a claim that all houses contain uninterrupted data. If the period lacks usable data, adjust `--start` and `--end` and record the actual coverage in the report.

Then create the data-backed PDF and update the submission documentation:

```bash
python scripts/finalize_submission.py --output-dir outputs
```

**Do not run that finalization command on demo data**; it checks and refuses synthetic-demo metadata.

The PDF is produced as `outputs/Flock_Energy_Final_Report.pdf`; add it to the GitHub repository only once your genuine REFIT results are present.

## Test with clearly SYNTHETIC files (no REFIT download needed)

```bash
python scripts/make_demo_data.py --root /tmp/refit_demo --days 8
python -m refit_nilm.pipeline --raw-dir /tmp/refit_demo/data/raw --clean-dir /tmp/refit_demo/data/cleaned --output-dir /tmp/refit_demo/outputs --start 2014-09-01 --end 2014-09-09 --max-train-rows 12000 --demo
```

These simulated files are **not observations** and simulated quality/model metrics **must never be submitted as REFIT results**.

## Outputs once official data are processed

```
outputs/
  results.json                     Machine-readable run metadata and metrics
  household_summary.csv            Availability and washer events by house
  raw_house1_cleaned_1min.csv      Raw cleaned 1-minute House 1 subset
  house{1,2,3,5}_cycles.csv        Candidate cycle events
  test_predictions.csv             Actual vs predicted (house 5 test)
  model.joblib                     Serialized regression model
  DATA_generated.md                Findings to copy into DATA.md
  RESULTS_generated.md             Findings to copy into RESULTS.md
  figures/
    01_raw_before_after.png        Raw vs cleaned House 1, 3 channels
    02_trace_24h.png               Whole house vs washer, 24h
    03_detected_cycle.png          Example candidate cycle
    04_house_comparison.png        Cross-house cycle comparison
    05_usage_hour_weekday.png      Cycle starts by UTC hour/weekday
    06_actual_vs_predicted.png     Test-house actual vs predicted
```

## Cleaning rules and assumptions

- Keep last observed record for duplicate UTC timestamp, sort ascending.
- Track unparseable times, duplicates, missing one-minute bins, negative powers, and sample intervals above 20 s.
- For House 1 raw data, mark negative values and appliance measurements above 4,000 W as invalid. Note but do not automatically remove aggregate above 25,000 W (review flag).
- For raw House 1, forward-fill **only bounded missing runs of at most two whole minutes**. Outages of three minutes or longer remain `NaN`, including their beginning. We do **not** fabricate outage power as zero.
- Data originally marked `Issues=1` (if present) are excluded from minute-level training/target. `Issues` indicates appliance readings sum to more than whole-house power.
- Treat official cleaned REFIT as its own input; do not call the raw cleaning output the official cleaned data. The original authors already made corrections, including filling prolonged holes with zeros. This limits missingness detection.
- An active washer cycle is a heuristic: power >20 W, join interruptions <=10 min if *all intervening minutes are observed*, total event >=15 min, >=3 active minutes. Tune/sensitivity-test these rules before claiming a production-grade cycle detector.

## Model and validation

- Baseline: `0 W` always, a strong but uninformative reference because washing machines are mostly off.
- Candidate: `RandomForestRegressor(n_estimators=80, max_depth=14, min_samples_leaf=5)`.
- Inputs: current aggregate W, causal lags at 1/5/15 min, trailing means and standard deviations, aggregate difference, and UTC time-of-day/week encoding.
- Labels: the relevant house's washer submeter measurements. **No washer label ever enters the model feature matrix.**
- Partition by **household**, not randomly by 1-minute row: House 1 + 2 training, House 3 validation, House 5 test. This evaluates transfer to a household not seen during fitting; remaining domain shift is a limitation.
- A reproducible bounded training sample is stratified to include up to 25% positive minutes; this shifts sampling prevalence and can distort calibration. All validation and test minutes are scored at their **natural prevalence**.
- Report overall MAE and RMSE (W), MAE during truly active washing-machine minutes (W), active/on-off precision, recall, F1 (>20W threshold), and energy bias (%). A low all-minute MAE alone may hide useless predictions.
- Energy consistency limit: clip model predictions to [0, aggregate W], without using unseen target labels.

## What the result can / cannot support

The model may support an opt-in estimate of washer usage times, rough energy used per cycle and (with a relevant tariff) shifting usage to off-peak hours. It cannot support appliance-level billing, automated enforcement or precise diagnosis without better validation. Tariff shifting need not reduce kWh; it may reduce cost and/or peak demand.

**Common failure cases:** overlapping power signatures (kettle/dishwasher), unseen appliance types and programs, noisy/zero-filled periods, house-specific sensor differences, and 1-minute smoothing of brief peaks.

## AI assistance disclosure

The project structure, baseline implementation, documentation and report outline were drafted with the assistance of OpenAI ChatGPT. The author remains responsible for reviewing, understanding, executing, verifying and defending every figure, result and decision. Synthetic demos are explicitly separated from official REFIT evidence.

## Academic source and citation

Murray, D., Stankovic, L. & Stankovic, V. (2017), *An electrical load measurements dataset of United Kingdom households from a two-year longitudinal study*, Scientific Data 4:160122, https://doi.org/10.1038/sdata.2016.122. REFIT raw and cleaned releases, University of Strathclyde, CC BY 4.0.

<!-- EXTENDED_REFIT_HOUSE6_EVALUATION -->

## Final evaluation extension

The additional `scripts/two_stage_experiment.py` compares a two-stage classifier/regressor against the original Random Forest + 50 W cutoff using House 3 for selection, and evaluates the selection once on House 6 (new holdout). The two-stage method did not win model selection. The REFIT dataset is not included in GitHub.

```bash
python scripts/two_stage_experiment.py --clean-dir CLEAN_REFIT_081116 --model-path outputs/model.joblib --output-dir outputs/two_stage --start 2014-09-01 --end 2014-12-01 --max-train-rows 120000
python -m pip install pypdf
python scripts/finalize_refit_with_holdout.py --output-dir outputs
```

Final submission PDF: `docs/Flock_Energy_Submission_Report.pdf`. See `RESULTS.md` for the new holdout metrics.
