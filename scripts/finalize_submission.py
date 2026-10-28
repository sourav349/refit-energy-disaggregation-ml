"""Prepare actual-refit report only. Refuses synthetic-demo runs."""
from pathlib import Path
import argparse
import json
import shutil
from render_report import build_pdf


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output-dir',type=Path,default=Path('outputs'))
    args=ap.parse_args()
    out=args.output_dir
    result_file=out/'results.json'
    if not result_file.exists():
        raise SystemExit('ERROR: no results.json; run the official REFIT pipeline first.')
    results=json.loads(result_file.read_text(encoding='utf-8'))
    if results.get('status')!='official_REFIT_analysis':
        raise SystemExit('REFUSING: results come from a SYNTHETIC demo and are NOT suitable for submission.')
    root=Path(__file__).resolve().parents[1]
    for file in ('DATA_generated.md','RESULTS_generated.md'):
        if not (out/file).exists(): raise SystemExit('ERROR: missing '+str(out/file))
    for image in ('01_raw_before_after.png','02_trace_24h.png','03_detected_cycle.png','04_house_comparison.png','05_usage_hour_weekday.png','06_actual_vs_predicted.png'):
        if not (out/'figures'/image).exists(): raise SystemExit('ERROR: missing '+image)
    shutil.copyfile(out/'DATA_generated.md',root/'DATA.md')
    shutil.copyfile(out/'RESULTS_generated.md',root/'RESULTS.md')
    # Update utility-facing recommendation with verified metrics, without promising savings.
    recommendation=root/'Recommendation.md'
    doc=recommendation.read_text(encoding='utf-8')
    m=results['scores']['test_house5']
    baseline=m['always_off_baseline']['mae_w']; candidate=m['random_forest']['mae_w']
    status=('improves on' if candidate < baseline else 'does not improve on')
    verified=f'**Measured REFIT status (House 5 held-out test):** RF MAE = {candidate} W; always-off MAE = {baseline} W; the candidate {status} the overall-MAE baseline. Review active F1 = {m["random_forest"]["f1_active"]} before any pilot recommendation.'
    doc=doc.replace('**Status:** Proposed concept. The energy-use patterns and machine-learning metrics must be checked against measured REFIT results before recommending rollout.',verified)
    recommendation.write_text(doc,encoding='utf-8')
    path=build_pdf(out/'Flock_Energy_Final_Report.pdf',results,out/'figures')
    print('Updated DATA.md and RESULTS.md; created',path)
    print('Now review actual coverage, quality, all plots, findings and README, then publish your repo.')

if __name__=='__main__':main()
