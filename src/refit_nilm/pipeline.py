"""End-to-end CLI: raw quality -> EDA -> NILM baseline/model -> reports.

Run with PYTHONPATH=src python -m refit_nilm.pipeline --raw-dir ... --clean-dir ...
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.utils import shuffle
from .core import (WASHER_CHANNELS, load_csv, assess_and_resample,
                   detect_cycles, create_features, find_house_csv, find_house_csvs, metrics)
from .plots import (save_raw_comparison, save_day_trace, save_cycle_trace,
                    save_cross_home, save_usage, save_predictions)


def max_rows_training(data: pd.DataFrame, max_rows: int, seed=42) -> pd.DataFrame:
    """Subsample within training homes ONLY, keeping active examples visible."""
    if len(data) <= max_rows:
        return data
    active = data.loc[data.target_w > 20]
    inactive = data.loc[data.target_w <= 20]
    n_active = min(len(active), max(1, int(max_rows*.25)))
    n_inactive = min(len(inactive), max_rows-n_active)
    if n_inactive < max_rows-n_active:
        n_active = min(len(active), max_rows-n_inactive)
    parts = []
    if n_active: parts.append(active.sample(n=n_active, random_state=seed))
    if n_inactive: parts.append(inactive.sample(n=n_inactive, random_state=seed))
    return shuffle(pd.concat(parts), random_state=seed)


def run(raw_dir: Path, clean_dir: Path, output_dir: Path, start: str, end: str,
        max_train_rows: int = 120_000, demo: bool = False) -> dict:
    if not demo and ((raw_dir.parent / 'SYNTHETIC_DEMO_ONLY.txt').exists() or (clean_dir.parent / 'SYNTHETIC_DEMO_ONLY.txt').exists()):
        raise ValueError('Synthetic test data detected. Use --demo; never label this official REFIT.')
    output_dir.mkdir(parents=True, exist_ok=True)
    figs = output_dir / 'figures'; figs.mkdir(exist_ok=True)
    report = {
        'run_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'synthetic_demo_DO_NOT_SUBMIT' if demo else 'official_REFIT_analysis',
        'period_requested_utc': {'start_inclusive':start, 'end_exclusive':end},
        'household_channels': WASHER_CHANNELS,
        'roles': {'train':[1,2], 'validation':[3], 'test':[5]},
        'sampling': 'minute average power (W), 1-minute resolution, UTC',
        'event_rule': {'above_w':20,'bridge_off_min':10,'minimum_total_min':15,'minimum_active_min':3},
        'model': 'RandomForestRegressor, aggregate-only trailing + calendar features',
        'baseline': 'always-off = 0 W',
        'notes': [
          'This is a cross-house holdout; no random time-window split is used.',
          'The cleaned data were previously filled by the REFIT authors. Zeros after long outages cannot reliably be distinguished from actual power-off.',
          'Washing-machine events are heuristic and not verified cycle annotations.',
          'House-specific appliance columns come from the official REFIT cleaned README.',
          'No target/appliance-level data are included in model features.',
          'Time, calendar features, and one-minute windows use UTC. Local household patterns shift with UK DST.',
        ],
    }
    print('Stage 1/4: inspecting raw House 1...')
    raw_paths = find_house_csvs(raw_dir, 1, raw=True)
    raw_parts = []
    for raw_path in raw_paths:
        try:
            raw_parts.append(load_csv(raw_path, ['Appliance1','Appliance5'], start, end))
        except ValueError as exc:
            if 'No records within requested period' not in str(exc):
                raise
    if not raw_parts:
        raise ValueError('No raw House 1 observations in selected dates across available parts.')
    raw = pd.concat(raw_parts, ignore_index=True)
    raw_min, raw_quality = assess_and_resample(raw, ['Appliance1','Appliance5'], raw=True)
    raw_quality['source_file'] = ', '.join(p.name for p in raw_paths)
    raw_quality['scope'] = 'Selected period, not necessarily full original house file'
    raw_min.to_csv(output_dir / 'raw_house1_cleaned_1min.csv')
    report['raw_house1_quality'] = raw_quality
    save_raw_comparison(raw, raw_min, figs/'01_raw_before_after.png')
    del raw
    print('Stage 2/4: inspecting four cleaned houses and detecting cycles...')
    summary_rows, frames, events = [], {}, {}
    for house, target in WASHER_CHANNELS.items():
        csv_path = find_house_csv(clean_dir, house)
        original = load_csv(csv_path, [target], start, end)
        minute, quality = assess_and_resample(original, [target], raw=False)
        detected = detect_cycles(minute[target])
        detected.to_csv(output_dir/f'house{house}_cycles.csv', index=False)
        events[house] = detected
        frames[house] = minute
        usable = minute[target].dropna()
        summary_rows.append({
            'house': house, 'washing_machine_channel':target, 'file': csv_path.name,
            'start_utc':str(minute.index.min()), 'end_utc':str(minute.index.max()),
            'available_minutes':int(len(usable)), 'missing_minutes':int(minute[target].isna().sum()),
            'zero_off_fraction':round(float((usable <= 20).mean()),4) if len(usable) else None,
            'cycles':len(detected),
            'median_cycle_min':round(float(detected.duration_min.median()),2) if len(detected) else None,
            'median_cycle_kwh':round(float(detected.energy_kwh.median()),4) if len(detected) else None,
            'quality':quality,
        })
        if house == 1:
            save_day_trace(house, minute, target, detected, figs/'02_trace_24h.png')
            save_cycle_trace(house, minute, target, detected, figs/'03_detected_cycle.png')
        print(f'  House {house}: {len(minute):,} one-minute bins, {len(detected)} candidate cycles')
    summary = pd.DataFrame([{k:v for k,v in s.items() if k!='quality'} for s in summary_rows])
    summary.to_csv(output_dir/'household_summary.csv', index=False)
    report['households'] = summary_rows
    save_cross_home(summary, figs/'04_house_comparison.png')
    save_usage(events, figs/'05_usage_hour_weekday.png')
    print('Stage 3/4: constructing causal features with disjoint household splits...')
    features = {h:create_features(frames[h], WASHER_CHANNELS[h]) for h in WASHER_CHANNELS}
    for h,f in features.items():
        print(f'  House {h}: {len(f):,} model-ready minutes; on fraction {float((f.target_w>20).mean()) if len(f) else 0:.3f}')
        if len(f) < 50:
            raise ValueError(f'House {h}: insufficient clean rows; select a longer period.')
    xcols = [c for c in features[1].columns if c!='target_w']
    train = pd.concat([features[1], features[2]])
    val = features[3]
    test = features[5]
    train_sub = max_rows_training(train, max_train_rows)
    reg = RandomForestRegressor(n_estimators=80, max_depth=14, min_samples_leaf=5,
                                 max_features=0.8, max_samples=0.8, n_jobs=-1, random_state=42)
    reg.fit(train_sub[xcols], train_sub['target_w'])
    def predict(df):
        p = reg.predict(df[xcols]); return np.clip(p, 0, df['aggregate_w'].to_numpy())
    print('Stage 4/4: scoring zero baseline and model on validation and untouched test houses...')
    scores = {}
    for label, df in [('validation_house3',val), ('test_house5',test)]:
        actual = df['target_w'].to_numpy()
        predicted = predict(df)
        zero = np.zeros(len(df))
        scores[label] = {
            'always_off_baseline':metrics(actual, zero),
            'random_forest':metrics(actual, predicted),
        }
        if label=='test_house5':
            preds = predicted
            pd.DataFrame({'timestamp_utc':df.index.astype(str),'actual_w':actual,'predicted_w':predicted,
                          'aggregate_w':df.aggregate_w.to_numpy()}).to_csv(output_dir/'test_predictions.csv', index=False)
            save_predictions(df, predicted, figs/'06_actual_vs_predicted.png')
    report['training'] = {
      'train_rows_total': len(train), 'train_rows_sampled':len(train_sub),
      'validation_rows':len(val),'test_rows':len(test),
      'features':xcols,'train_sampled_active_fraction':round(float((train_sub.target_w>20).mean()),4),
      'target_units':'W','random_seed':42,
    }
    report['scores'] = scores
    try:
        import joblib
        joblib.dump({'model':reg,'features':xcols,'wash_channel_mapping':WASHER_CHANNELS},output_dir/'model.joblib')
    except ImportError:
        report['notes'].append('joblib unavailable: model was not serialized')
    (output_dir/'results.json').write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    make_results_md(report, output_dir/'RESULTS_generated.md')
    make_data_md(report, output_dir/'DATA_generated.md')
    print('\nOutput directory:',output_dir.resolve())
    print('TEST baseline MAE (W):',scores['test_house5']['always_off_baseline']['mae_w'])
    print('TEST model MAE (W):',scores['test_house5']['random_forest']['mae_w'])
    return report


def make_data_md(rep, path):
    q = rep['raw_house1_quality']
    s = [
       '# REFIT data-quality findings - generated',
       f"**Data status:** `{rep['status']}`",
       'Raw House 1 analysis is restricted to the requested timestamp window.',
       f"Source: {q['source_file']}; UTC: {q['date_min_utc']} to {q['date_max_utc']}",
       f"Input rows: {q['input_rows']:,}; invalid timestamps: {q['unparseable_timestamps']:,}; duplicates: {q['duplicate_timestamps']:,}.",
       f"Median sample interval: {q['interval_median_seconds']} s; intervals >20 seconds: {q['intervals_over_20_seconds']:,}; out-of-order source timestamps: {q['out_of_order_adjacent_timestamps']:,}.",
       f"Missing source-readings per column (before cleaning): {q['missing_source_readings_per_channel']}.",
       f"Minute bins with no samples: {q['minutes_without_samples']:,}; long gaps stay missing (NaN).",
       f"Long missing runs (>2 min) by column: {q['long_outage_events_per_column']}. Total missing-run minutes: {q['long_outage_minutes_per_column']}. Example start times: {q['long_outage_examples_per_column']}. These may include sensor-invalidated periods and are not independently verified physical outages.",
       f"Short gap-filled minute bins: {q['short_gap_filled_minutes_per_column']}; unfilled bins: {q['unfilled_minutes_per_column']}.",
       f"Invalid IAM samples: {q['invalid_channel_readings']}. Negative aggregates: {q['negative_aggregate_readings']}.",
       'Duplicate rule: last source-record wins. Negative values and IAM readings over 4000W become missing.',
       'Only fully bounded gaps of 1-2 one-minute bins are forward filled; longer missing runs remain NaN.',
       'Means of readings within each one-minute bin represent power, not total energy.',
       'Official cleaned REFIT is a separate dataset; its prior imputation and zero-filled outages may hide missingness.',
       '', '## Per-house official cleaned-data summaries',
    ]
    for h in rep['households']:
        s.append(f"- House {h['house']}: {h['file']} / {h['washing_machine_channel']} / {h['start_utc']} - {h['end_utc']}; available {h['available_minutes']:,} min; missing {h['missing_minutes']:,} min; off fraction {h['zero_off_fraction']}; cycles {h['cycles']}.")
    path.write_text('\n\n'.join(s)+'\n', encoding='utf-8')


def make_results_md(rep, path):
    rows = ['# REFIT model and usage findings - generated',
       f"**Data status:** `{rep['status']}`",'\n## Study design',
       'Train Houses 1, 2; validation House 3; untouched test House 5. Data from one home cannot leak into another split.',
       'Target: measured washer power. Inputs: aggregate-only causal history + UTC calendar features.',
       'A detected washing-machine cycle has >20W active readings, permits up to 10 min idle within an event, lasts >=15 min and has >=3 active min.',
       '\n## Model performance',
       '|Split|Method|MAE (W)|RMSE (W)|Active MAE (W)|Active F1|Energy bias (%)|',
       '|---|---|---:|---:|---:|---:|---:|']
    for name, comparisons in rep['scores'].items():
        for method, m in comparisons.items():
            rows.append(f"|{name}|{method}|{m['mae_w']}|{m['rmse_w']}|{m['active_mae_w']}|{m['f1_active']}|{m['energy_bias_percent']}|")
    rows += ['', '## Cross-house washing-machine EDA',
       '|House|Actual UTC coverage|Observed minutes|Missing minutes|Off fraction|Detected cycles|Median cycle duration (min)|Median kWh/cycle|',
       '|---|---|---:|---:|---:|---:|---:|---:|']
    for h in rep['households']:
        rows.append(f"|{h['house']}|{h['start_utc']} to {h['end_utc']}|{h['available_minutes']}|{h['missing_minutes']}|{h['zero_off_fraction']}|{h['cycles']}|{h['median_cycle_min']}|{h['median_cycle_kwh']}|")
    model=rep['scores']['test_house5']['random_forest']
    base=rep['scores']['test_house5']['always_off_baseline']
    verdict='lower' if model['mae_w'] < base['mae_w'] else 'higher or equal'
    rows += ['', '## Interpretation of six required figures',
       '1. Raw vs clean: compare aggregate, refrigerator and washer over the same 24-hour period; minute averages smooth high-frequency noise and missing outages should not be mistaken for observed zero.',
       '2. The 24-hour aggregate+washer trace places one appliance load in the context of all other devices. The aggregate may have peaks unrelated to washing.',
       '3. Cycle plot: the shaded interval is a **candidate** cycle defined by the explicit threshold/pause/duration rule; visual inspection is necessary.',
       '4. Cross-home comparison: the absolute event counts and median kWh/event depend on sensor coverage and event thresholds. Do not interpret higher counts as higher monthly consumption without coverage normalization.',
       '5. UTC hour/weekday plot: compare event starts across households. UTC hour is not identical to UK wall-clock hour during daylight saving.',
       f"6. Untouched House 5 actual vs predicted: RF overall MAE={model['mae_w']} W versus always-off baseline={base['mae_w']} W. Model error is {verdict} than the baseline. Inspect missed peak windows and false positives; the highlighted day is the highest-measured-activity evaluation day.",
       '', '## Plots',
       'See figures/01_raw_before_after.png through figures/06_actual_vs_predicted.png.',
       '\n## Known failure modes',
       '1. Dishwasher/kettle/heater signatures may overlap the washer signature, causing false positives.',
       '2. In a new household, washer size/programs and other appliances differ from training homes, degrading performance.',
       '3. Official prefilled zeros and Issues=1 flags can hide or invalidate ground truth.',
       '4. Low-duty-cycle minute averaging can mask short on/off transitions.',
       '\n## Business recommendation',
       'Use cycle timing and kWh estimates to offer an opt-in off-peak shift suggestion only when tariffs support it.',
       'Measure opt-in rate, shifted kWh, bill changes and estimated-usage error against a control group.',
       'Do not imply all load shifting saves energy (kWh); it may only lower cost or peak demand.',
       '\n## Limitations',
       'These houses are UK properties with ~8-second source readings; household differences, missingness and UK-to-India transfer limit generalization.',
       'At 15/30-minute resolution, brief peaks collapse into averages, making event boundaries and precise cycle duration difficult to recover.',
    ]
    path.write_text('\n'.join(rows)+'\n',encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description='Professional REFIT washing-machine NILM pipeline')
    p.add_argument('--raw-dir',type=Path,default=Path('data/raw'))
    p.add_argument('--clean-dir',type=Path,default=Path('data/cleaned'))
    p.add_argument('--output-dir',type=Path,default=Path('outputs'))
    p.add_argument('--start',default='2014-09-01',help='UTC inclusive, e.g. 2014-09-01')
    p.add_argument('--end',default='2014-12-01',help='UTC exclusive, e.g. 2014-12-01')
    p.add_argument('--max-train-rows',type=int,default=120000)
    p.add_argument('--demo',action='store_true', help='Only for synthetic data; visibly marks results NOT FOR SUBMISSION')
    args = p.parse_args()
    run(args.raw_dir,args.clean_dir,args.output_dir,args.start,args.end,args.max_train_rows,args.demo)

if __name__ == '__main__': main()
