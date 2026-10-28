"""REFIT experiment: calendar + load features versus load features only.

Run from repository root:
  python scripts/compare_feature_groups.py --clean-dir CLEAN_REFIT_081116

Uses official cleaned REFIT Houses 1 and 2 for training, House 3 for validation.
House 5 is intentionally not evaluated: its old test results have already been inspected.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from refit_nilm.core import (
    WASHER_CHANNELS,
    assess_and_resample,
    create_features,
    find_house_csv,
    load_csv,
    metrics,
)
from refit_nilm.pipeline import max_rows_training


def run(clean_dir: Path, start: str, end: str, model_path: Path, max_train_rows: int):
    saved = joblib.load(model_path)
    all_features = list(saved['features'])
    power_features = [name for name in all_features if not name.startswith(('hour_', 'dow_'))]

    houses = {}
    for house in (1, 2, 3):
        washer = WASHER_CHANNELS[house]
        path = find_house_csv(clean_dir, house)
        raw = load_csv(path, [washer], start=start, end=end)
        one_minute, _ = assess_and_resample(raw, [washer], raw=False)
        houses[house] = create_features(one_minute, washer)
        print(f'House {house}: {len(houses[house]):,} model-ready minutes')

    full_train = pd.concat([houses[1], houses[2]])
    train = max_rows_training(full_train, max_train_rows)
    val = houses[3]
    y = val['target_w'].to_numpy()
    limit = val['aggregate_w'].to_numpy()

    original = np.clip(saved['model'].predict(val[all_features]), 0, limit)

    no_calendar = RandomForestRegressor(
        n_estimators=80, max_depth=14, min_samples_leaf=5,
        max_features=0.8, max_samples=0.8, n_jobs=-1, random_state=42,
    )
    print('Training same Random Forest without hour/day features...')
    no_calendar.fit(train[power_features], train['target_w'])
    no_calendar_preds = np.clip(no_calendar.predict(val[power_features]), 0, limit)

    print('\n===== HOUSE 3 VALIDATION ONLY =====')
    print(f"{'Experiment':<29}{'MAE (W)':>10}{'Precision':>12}{'Recall':>10}{'F1':>10}{'Bias %':>11}")
    experiments = [
        ('Always off', np.zeros_like(y)),
        ('Original: all features', original),
        ('No calendar features', no_calendar_preds),
        ('Original + cutoff 50W', np.where(original >= 50, original, 0)),
        ('No calendar + cutoff 50W', np.where(no_calendar_preds >= 50, no_calendar_preds, 0)),
    ]
    for name, pred in experiments:
        m = metrics(y, pred)
        print(
            f"{name:<29}{m['mae_w']:>10.2f}{m['precision_active']:>12.3f}"
            f"{m['recall_active']:>10.3f}{m['f1_active']:>10.3f}"
            f"{m['energy_bias_percent']:>11.2f}"
        )

    print('\nDo not choose a final model based on previously inspected House 5 results.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--clean-dir', type=Path, default=Path('CLEAN_REFIT_081116'))
    p.add_argument('--start', default='2014-09-01')
    p.add_argument('--end', default='2014-12-01')
    p.add_argument('--model-path', type=Path, default=Path('outputs/model.joblib'))
    p.add_argument('--max-train-rows', type=int, default=120000)
    args = p.parse_args()
    run(args.clean_dir, args.start, args.end, args.model_path, args.max_train_rows)
