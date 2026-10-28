"""Optional REFIT NILM ablation: active-state classifier + conditional power regression.

Design LOCKED before first use of House 6:
  Training: Houses 1 & 2, validation/tuning: House 3, final holdout: House 6.
  House 5 was already inspected during the original baseline analysis, so DO NOT
  reuse it as an untouched holdout for this additional experiment.

House 6 washing machine = Appliance2, verified from the official cleaned REFIT
readme: https://pure.strath.ac.uk/ws/portalfiles/portal/62090183/CLEAN_READ_ME_081116.txt

From the repo root with its virtual environment activated:
  python scripts/two_stage_experiment.py --clean-dir CLEAN_REFIT_081116 \
    --output-dir outputs/two_stage --model-path outputs/model.joblib

This script DOES NOT modify the original model, results.json, or the main PDF.
The training labels are *submetered* washing-machine power; only aggregate
features are supplied as model inputs. All rolling statistics are trailing.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import average_precision_score

from refit_nilm.core import assess_and_resample, create_features, find_house_csv, load_csv, metrics
from refit_nilm.pipeline import max_rows_training

HOUSE_WASHER = {1: "Appliance5", 2: "Appliance2", 3: "Appliance6", 6: "Appliance2"}
ACTIVITY_W = 20.0
# Fixed before checking the unseen House 6. Values are probability cutoffs.
THRESHOLDS = (0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)


def load_house(clean_dir: Path, house: int, start: str, end: str) -> pd.DataFrame:
    target = HOUSE_WASHER[house]
    source = find_house_csv(clean_dir, house)
    original = load_csv(source, [target], start=start, end=end)
    one_minute, _quality = assess_and_resample(original, [target], raw=False)
    frame = create_features(one_minute, target)
    if len(frame) < 100:
        raise ValueError(f"House {house} has only {len(frame)} usable minutes. Change --start / --end.")
    return frame


def safely_clip(power: np.ndarray, frame: pd.DataFrame) -> np.ndarray:
    return np.clip(power, 0.0, frame["aggregate_w"].to_numpy(dtype=float))


def gate_power(probabilities: np.ndarray, power_if_on: np.ndarray,
               frame: pd.DataFrame, threshold: float) -> np.ndarray:
    # When predicted active, force output strictly above the same >20 W criterion
    # used for the measured activity label; otherwise return exactly zero.
    on_power = safely_clip(np.maximum(ACTIVITY_W + 1, power_if_on), frame)
    return np.where(probabilities >= threshold, on_power, 0.0)


def summary_row(name: str, y: np.ndarray, prediction: np.ndarray) -> dict:
    return {"experiment": name, **metrics(y, prediction, threshold_w=ACTIVITY_W)}


def print_scores(title: str, rows: list[dict]) -> None:
    print("\n" + title)
    print(f"{'Experiment':<31} {'MAE (W)':>9} {'Active MAE':>11} {'Precision':>10} {'Recall':>9} {'F1':>8} {'Bias %':>9}")
    for m in rows:
        print(f"{m['experiment']:<31} {m['mae_w']:>9.2f} "
              f"{str(m['active_mae_w']):>11} {m['precision_active']:>10.3f} "
              f"{m['recall_active']:>9.3f} {m['f1_active']:>8.3f} "
              f"{str(m['energy_bias_percent']):>9}")


def save_plot(df: pd.DataFrame, pred: np.ndarray, dest: Path) -> None:
    # Visualization only, not used for model or threshold selection.
    # Choose a 24h window that contains observable active minutes.
    observed = df["target_w"].gt(ACTIVITY_W)
    n_daily = observed.groupby(df.index.floor("D")).sum()
    selected_day = n_daily.idxmax()
    mask = (df.index >= selected_day) & (df.index < selected_day + pd.Timedelta(days=1))
    sampled = df.loc[mask]
    shown = pred[mask]
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(sampled.index, sampled["target_w"], label="Measured washer (W)", lw=1.3)
    ax.plot(sampled.index, shown, label="Predicted washer (W)", lw=1.1, alpha=0.85)
    ax.set_title("House 6: measured vs predicted washing-machine power (illustrative day)")
    ax.set_xlabel("UTC time")
    ax.set_ylabel("Power (W)")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=180)
    plt.close(fig)


def run(args: argparse.Namespace) -> dict:
    if not args.clean_dir.is_dir():
        raise FileNotFoundError(f"Cleaned REFIT folder not found: {args.clean_dir}")
    is_synthetic = any(
        (path / "SYNTHETIC_DEMO_ONLY.txt").exists()
        for path in (args.clean_dir, args.clean_dir.parent)
    )
    if is_synthetic and not args.demo:
        raise ValueError(
            "Synthetic fixture detected. Add --demo for code testing; "
            "never submit simulated results as actual REFIT findings."
        )
    if not args.model_path.is_file():
        raise FileNotFoundError(f"Original model missing: {args.model_path}. Run the existing pipeline first.")
    if args.output_dir.resolve() == args.model_path.parent.resolve():
        raise ValueError("Use a separate output folder, such as outputs/two_stage, to preserve the original report.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    saved = joblib.load(args.model_path)
    names = list(saved["features"])
    if any(name in ("target_w", HOUSE_WASHER[3]) for name in names):
        raise ValueError("Target leakage detected: washer data must not be a model feature.")

    print("1/4 Loading training Houses 1 & 2, and validation House 3...")
    houses = {house: load_house(args.clean_dir, house, args.start, args.end)
              for house in (1, 2, 3)}
    for house, frame in houses.items():
        print(f"  House {house}: {len(frame):,} usable minutes; active={(frame['target_w'] > ACTIVITY_W).mean():.4%}")
    training_all = pd.concat([houses[1], houses[2]])
    training = max_rows_training(training_all, args.max_train_rows)
    active_train = training.loc[training["target_w"] > ACTIVITY_W]
    if len(active_train) < 100:
        raise ValueError("Less than 100 active minutes in training. Extend period; do not invent observations.")
    y_state = (training["target_w"] > ACTIVITY_W).astype(int)
    if y_state.nunique() < 2:
        raise ValueError("Training lacks both activity classes; cannot train classifier.")
    print(f"  Training sampled: {len(training):,} minutes; active: {len(active_train):,}")

    print("2/4 Fitting classifier and active-only regressor...")
    classifier = RandomForestClassifier(
        n_estimators=100, max_depth=12, min_samples_leaf=10,
        max_features=0.8, max_samples=0.8, class_weight="balanced_subsample",
        n_jobs=-1, random_state=42,
    )
    classifier.fit(training[names], y_state)
    regressor = RandomForestRegressor(
        n_estimators=80, max_depth=12, min_samples_leaf=5,
        max_features=0.8, max_samples=0.8, n_jobs=-1, random_state=42,
    )
    regressor.fit(active_train[names], active_train["target_w"])

    print("3/4 Choosing model and probability cutoff using validation House 3 ONLY...")
    val = houses[3]
    y_val = val["target_w"].to_numpy(dtype=float)
    p_val = classifier.predict_proba(val[names])[:, list(classifier.classes_).index(1)]
    conditional_val = regressor.predict(val[names])
    original_val = safely_clip(saved["model"].predict(val[names]), val)
    original_50_val = np.where(original_val >= 50, original_val, 0)
    candidates: list[dict] = [
        summary_row("Original RF + 50W cutoff", y_val, original_50_val)
    ]
    for cutoff in THRESHOLDS:
        preds = gate_power(p_val, conditional_val, val, cutoff)
        candidates.append(summary_row(f"Two-stage threshold {cutoff:.2f}", y_val, preds))
    # Primary selection: validation F1. Secondary: lower validation MAE.
    # This is a predeclared choice to prioritize detection over all-off MAE.
    chosen = sorted(candidates, key=lambda m: (-m["f1_active"], m["mae_w"]))[0]
    baseline_val = summary_row("Always off", y_val, np.zeros_like(y_val))
    print_scores("===== HOUSE 3 VALIDATION (ALL CANDIDATES) =====", [baseline_val, *candidates])
    print(f"\nLOCKED choice: {chosen['experiment']} (validation F1={chosen['f1_active']:.4f})")

    # This MUST happen after validation selection. One-time fresh holdout assessment.
    print("4/4 Evaluating locked choice ONCE on new House 6 holdout...")
    test = load_house(args.clean_dir, 6, args.start, args.end)
    y_test = test["target_w"].to_numpy(dtype=float)
    zero_test = np.zeros_like(y_test)
    old_test = safely_clip(saved["model"].predict(test[names]), test)
    old_50_test = np.where(old_test >= 50, old_test, 0)
    selected_name = chosen["experiment"]
    if selected_name.startswith("Two-stage"):
        cutoff = float(selected_name.split()[-1])
        p_test = classifier.predict_proba(test[names])[:, list(classifier.classes_).index(1)]
        conditional_test = regressor.predict(test[names])
        chosen_prediction = gate_power(p_test, conditional_test, test, cutoff)
        test_pr_auc = float(average_precision_score(y_test > ACTIVITY_W, p_test)) if (y_test > ACTIVITY_W).any() else None
    else:
        cutoff = None
        chosen_prediction = old_50_test
        test_pr_auc = None  # Not a calibrated probability for the old regression model.
    test_results = [
        summary_row("Always off", y_test, zero_test),
        summary_row("Original RF + 50W cutoff", y_test, old_50_test),
        summary_row("VALIDATION-SELECTED: " + selected_name, y_test, chosen_prediction),
    ]
    print_scores("===== HOUSE 6 NEW HOLDOUT (DO NOT REPEATEDLY TUNE ON IT) =====", test_results)

    report = {
        "execution_utc": datetime.now(timezone.utc).isoformat(),
        "data_status": "synthetic_smoke_test_NOT_FOR_SUBMISSION" if is_synthetic else "official_refit_expected",
        "note": "Demo scores must NEVER be submitted as measured REFIT results." if is_synthetic else "Check official REFIT provenance before final submission.",
        "date_window_utc": {"start_inclusive": args.start, "end_exclusive": args.end},
        "channel_mapping": {str(h): c for h, c in HOUSE_WASHER.items()},
        "roles": {"train": [1,2], "validation": [3], "fresh_holdout": [6], "previously_inspected": [5]},
        "training_sample_rows": len(training),
        "training_active_rows": len(active_train),
        "features": names,
        "selection_rule": "Max validation minute-level F1; tie-break by lower validation MAE",
        "candidate_thresholds": list(THRESHOLDS),
        "validation": {"baseline": baseline_val, "candidates": candidates, "selected": chosen},
        "holdout_house6": test_results,
        "holdout_house6_rows": len(test),
        "holdout_house6_active_fraction": round(float((y_test > ACTIVITY_W).mean()), 6),
        "test_classifier_pr_auc_if_selected": test_pr_auc,
        "limitations": [
            "House 5 was previously examined, therefore only House 6 is treated as a fresh holdout.",
            "House 3 has been used in multiple exploratory experiments; report that iteration transparently.",
            "This is a modest two-stage experiment, not evidence of deployment readiness.",
            "Models infer load from aggregate meter only; other appliances may create confounding signatures.",
            "REFIT cleaned zeros and issue flags may obscure some underlying missingness.",
        ],
    }
    (args.output_dir / "experiment_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    pd.DataFrame([baseline_val, *candidates]).to_csv(args.output_dir / "validation_candidates.csv", index=False)
    pd.DataFrame(test_results).to_csv(args.output_dir / "holdout_house6_metrics.csv", index=False)
    pd.DataFrame({
        "timestamp_utc": test.index.astype(str), "aggregate_w": test.aggregate_w.to_numpy(),
        "measured_w": y_test, "predicted_w": chosen_prediction,
    }).to_csv(args.output_dir / "holdout_house6_predictions.csv", index=False)
    save_plot(test, chosen_prediction, args.output_dir / "house6_actual_vs_predicted.png")
    joblib.dump({
        "classifier": classifier, "active_regressor": regressor,
        "features": names, "activity_cutoff_w": ACTIVITY_W,
        "selection": selected_name, "probability_cutoff_if_selected": cutoff,
        "note": "Deploy only after substantially stronger unseen-household validation.",
    }, args.output_dir / "two_stage_models.joblib")
    def md_table(rows: list[dict]) -> str:
        columns = ("experiment", "mae_w", "precision_active", "recall_active", "f1_active", "energy_bias_percent")
        result = ["|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
        for row in rows:
            result.append("|" + "|".join(str(row[k]) for k in columns) + "|")
        return "\n".join(result)

    md = [
        "# Two-stage REFIT validation experiment", "",
        "**Design:** Train Houses 1/2; validation House 3; new holdout House 6. House 5 was already inspected.", "",
        "**Selection rule:** maximum minute-level validation F1 (MAE tie-break).", "",
        f"**Selected:** {selected_name}", "", "## Validation", "",
        md_table([baseline_val, *candidates]), "", "## Previously uninspected House 6", "",
        md_table(test_results), "",
        "**Interpretation caution:** House 5 was already examined. Do not call House 5 a fresh test for subsequent tuning.",
        "Do not claim improvement unless it actually appears in the House 6 holdout results.",
    ]
    (args.output_dir / "EXPERIMENT_RESULTS.md").write_text("\n".join(md)+"\n", encoding="utf-8")
    print(f"\nSaved: {args.output_dir.resolve()}")
    print("Keep the original outputs/results.json and model.joblib unchanged.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clean-dir", type=Path, default=Path("CLEAN_REFIT_081116"))
    parser.add_argument("--model-path", type=Path, default=Path("outputs/model.joblib"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/two_stage"))
    parser.add_argument("--start", default="2014-09-01")
    parser.add_argument("--end", default="2014-12-01")
    parser.add_argument("--max-train-rows", type=int, default=120000)
    parser.add_argument("--demo", action="store_true", help="Only for synthetic fixture smoke testing; never submit those results")
    run(parser.parse_args())
