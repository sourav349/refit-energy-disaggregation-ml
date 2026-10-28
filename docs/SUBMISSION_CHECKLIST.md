# Submission checklist

- [ ] Download both **official** REFIT archives; verify correct extracted House1 raw file and 4 official cleaned house CSVs.
- [ ] Check data README mapping before running. Current home mapping documented and verified.
- [ ] Run `pytest -q` and log results.
- [ ] Run real-data pipeline, inspect all generated charts, verify real coverage and cycle count.
- [ ] Review leakage safety: test House5 never used for training, model choices or threshold tuning.
- [ ] Compare Random Forest vs always-off baseline on validation AND untouched test, including active F1 and error during active cycles.
- [ ] Check whether detected events are believable via plotted examples; discuss where 20W/10min rule fails.
- [ ] Report model failures truthfully, including if baseline wins overall MAE.
- [ ] Check `DATA.md`, `RESULTS.md`, and `Recommendation.md` correspond to measured data.
- [ ] Run finalization script to generate the real-data PDF and populate required markdown files.
- [ ] State AI tools used and author's own review in README.
- [ ] Add official dataset and paper citations, CC BY 4.0 attribution.
- [ ] Do not include 500MB archives, private info, demo numbers or simulated outputs in submission.
- [ ] Publish public GitHub repository and submit its link; attach final PDF if allowed.
