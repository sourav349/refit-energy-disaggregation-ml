#!/usr/bin/env python3
"""Finalize REFIT take-home with independently evaluated House 6 holdout.

From the project root:
  python -m pip install pypdf
  python scripts/finalize_refit_with_holdout.py --output-dir outputs

This script does NOT train or tune models. It reads verified experiment outputs,
updates report documentation, and assembles a final PDF. Never submit demo data.
"""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)


def get(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run the appropriate REFIT experiment first.")
    return json.loads(path.read_text(encoding="utf-8"))


def require_results(main: dict, additional: dict) -> None:
    if main.get("status") != "official_REFIT_analysis":
        raise ValueError("Refusing non-official initial experiment results.")
    if additional.get("data_status") != "official_refit_expected":
        raise ValueError("Refusing synthetic/smoke-test ablation results.")
    if main.get("period_requested_utc") != additional.get("date_window_utc"):
        raise ValueError("Date ranges differ; cannot fairly combine reports.")
    if main.get("roles", {}).get("train") != [1, 2] or main.get("roles", {}).get("validation") != [3]:
        raise ValueError("Unexpected original household split.")
    if additional.get("roles", {}).get("fresh_holdout") != [6]:
        raise ValueError("House 6 must be the new holdout.")
    choice = additional.get("validation", {}).get("selected", {}).get("experiment", "")
    if choice != "Original RF + 50W cutoff":
        raise ValueError(f"Unexpected selection {choice!r}; this addendum is written for the logged Original RF + 50W result.")
    rows = additional.get("holdout_house6", [])
    if not any(r.get("experiment", "").startswith("VALIDATION-SELECTED:") for r in rows):
        raise ValueError("Missing House 6 selected-model result.")
    if not any(r.get("experiment") == "Always off" for r in rows):
        raise ValueError("Missing House 6 baseline result.")
    b = next(r for r in rows if r["experiment"] == "Always off")
    m = next(r for r in rows if r["experiment"].startswith("VALIDATION-SELECTED:"))
    if m["mae_w"] <= b["mae_w"]:
        raise ValueError("Unexpected holdout MAE relationship; review/modify fixed conclusions before generating report.")


def metric_row(row: dict) -> list[str]:
    return [
        str(row["experiment"]),
        f"{row['mae_w']:.2f}",
        f"{row['active_mae_w']:.2f}" if row.get("active_mae_w") is not None else "N/A",
        f"{row['precision_active']:.3f}", f"{row['recall_active']:.3f}",
        f"{row['f1_active']:.3f}",
        f"{row['energy_bias_percent']:+.2f}" if row.get("energy_bias_percent") is not None else "N/A",
    ]


def markdown_table(rows: list[dict]) -> str:
    out = ["| Method | MAE (W) | Active MAE (W) | Precision | Recall | F1 | Energy bias (%) |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        out.append("| " + " | ".join(metric_row(r)) + " |")
    return "\n".join(out)


def append_section(path: Path, marker: str, content: str) -> None:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in original:
        original = original.split(marker, 1)[0].rstrip()
    path.write_text(original.rstrip() + "\n\n" + marker + "\n\n" + content.rstrip() + "\n", encoding="utf-8")


def render_appendix(destination: Path, main: dict, additional: dict, plot: Path) -> None:
    navy = colors.HexColor("#20344E")
    cyan = colors.HexColor("#157C88")
    pale = colors.HexColor("#E8F4F6")
    line = colors.HexColor("#DCE4EA")
    st = getSampleStyleSheet()
    st.add(ParagraphStyle(name="AppTitleX", parent=st["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=24, textColor=navy, spaceAfter=16))
    st.add(ParagraphStyle(name="AppHeadX", parent=st["Heading2"], fontSize=11.5, leading=15, textColor=cyan, spaceBefore=9, spaceAfter=5))
    st.add(ParagraphStyle(name="AppBodyX", parent=st["BodyText"], fontSize=9.2, leading=14, textColor=navy, spaceAfter=6))
    st.add(ParagraphStyle(name="AppTinyX", parent=st["BodyText"], fontSize=7.3, leading=10.5, textColor=navy))
    st.add(ParagraphStyle(name="AppCaptionX", parent=st["BodyText"], fontSize=8.2, leading=12, textColor=colors.HexColor("#5F7082"), alignment=TA_CENTER))
    story=[]
    def para(txt,style="AppBodyX"): story.append(Paragraph(txt,st[style]))
    def table(rows,widths):
        content=[[Paragraph(html.escape(str(cell)),st["AppTinyX"]) for cell in row] for row in rows]
        t=Table(content,colWidths=widths,repeatRows=1,hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),pale),
            ("LINEBELOW",(0,0),(-1,-1),0.25,line),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("LEFTPADDING",(0,0),(-1,-1),5),
            ("RIGHTPADDING",(0,0),(-1,-1),5),
            ("TOPPADDING",(0,0),(-1,-1),5),
            ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ]))
        story.append(t)
        story.append(Spacer(1,9))

    chosen=additional["validation"]["selected"]
    rows=additional["holdout_house6"]
    holdout_base=next(r for r in rows if r["experiment"]=="Always off")
    holdout_selected=next(r for r in rows if r["experiment"].startswith("VALIDATION-SELECTED:"))
    val_base=additional["validation"]["baseline"]
    previous=next(r for r in additional["validation"]["candidates"] if r["experiment"]=="Original RF + 50W cutoff")

    para("Appendix A | Post-baseline experiments and fresh holdout", "AppTitleX")
    para("<b>Scope:</b> This appendix updates the main report. The original House 5 plots and test numbers document the initial benchmark. After those results were inspected, additional experiments were selected on House 3 validation and evaluated once on House 6. House 5 is not described as untouched for the later experiments.")
    para("A1. Model selection on House 3", "AppHeadX")
    para(f"Ablations investigated removing calendar features, a 50 W regression output cutoff, and a two-stage activity classifier plus active-only power regressor. The predeclared selection criterion for the two-stage comparison was maximum <b>minute-level F1</b> on House 3, with MAE as tie-break. The selected method was <b>{html.escape(chosen['experiment'])}</b>.")
    table([['House 3 candidate','MAE (W)','Active F1','Recall','Bias (%)'],
        ['Always off',f"{val_base['mae_w']:.2f}",f"{val_base['f1_active']:.3f}",f"{val_base['recall_active']:.3f}",f"{val_base['energy_bias_percent']:.2f}"],
        [previous['experiment'],f"{previous['mae_w']:.2f}",f"{previous['f1_active']:.3f}",f"{previous['recall_active']:.3f}",f"{previous['energy_bias_percent']:.2f}"],
        [chosen['experiment'],f"{chosen['mae_w']:.2f}",f"{chosen['f1_active']:.3f}",f"{chosen['recall_active']:.3f}",f"{chosen['energy_bias_percent']:.2f}"]],
          [58*mm,24*mm,26*mm,26*mm,33*mm])
    para("The two-stage approach was rejected: its explored probability cutoffs all had poorer validation F1 than the selected original Random Forest + 50 W cutoff. No evidence supports claiming that the two-stage classifier improved the problem.")
    para("A2. House 6 independent evaluation", "AppHeadX")
    para(f"The selected configuration was locked before House 6 evaluation. House 6 uses the official cleaned REFIT <b>Appliance2</b> washing-machine channel. It has <b>{additional['holdout_house6_rows']:,}</b> model-ready one-minute readings over the same date range.")
    table([['House 6 method','MAE (W)','Active MAE','Precision','Recall','F1','Bias (%)']]+[metric_row(r) for r in (holdout_base,holdout_selected)],
          [42*mm,20*mm,25*mm,22*mm,19*mm,17*mm,22*mm])
    para(f"The model detected half the active minutes (recall {holdout_selected['recall_active']:.3f}), but precision was only {holdout_selected['precision_active']:.3f}. Active-minute MAE improved from {holdout_base['active_mae_w']:.2f} W to {holdout_selected['active_mae_w']:.2f} W; however overall MAE <b>worsened</b> from {holdout_base['mae_w']:.2f} W to {holdout_selected['mae_w']:.2f} W. Estimated total energy was {holdout_selected['energy_bias_percent']:+.2f}% relative to observed energy. These findings do not justify customer-facing appliance-specific claims.")
    para("A3. Limitations and integrity", "AppHeadX")
    para("House 3 was consulted repeatedly during the investigation; its validation score may be optimistic. House 5 motivated subsequent analysis and is not a fresh test for those later changes. House 6 was evaluated after freezing the selected method; do not repeatedly tune on House 6. Results apply only to the selected three-month REFIT subset, 1-minute averages, and the documented washing-machine labelling assumptions.")
    para("The main report documents raw-data quality, cycle detection and household comparison. The appendix documents post-baseline evaluation, including negative results. Preserve the original results.json and original trained model for auditability.")
    if plot.is_file():
        story.append(PageBreak())
        para("Appendix B | House 6 actual versus predicted trace", "AppTitleX")
        para("Illustrative day selected from the House 6 holdout to show measured and inferred washing-machine power. This figure is not a separate performance test; numeric metrics above cover the full holdout.")
        from PIL import Image as PILImage
        with PILImage.open(plot) as im: w,h=im.size
        maxw=169*mm;maxh=142*mm
        factor=min(maxw/w,maxh/h)
        story.append(KeepTogether([Image(str(plot),width=w*factor,height=h*factor),
                   Paragraph("Figure A1. House 6 observed washing-machine watts and selected-model prediction.",st["AppCaptionX"])]))
        para("<b>Interpretation:</b> Assess both missed peaks and false positive bursts; aggregate-level resemblance alone is insufficient evidence of accurate appliance detection.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    doc=SimpleDocTemplate(str(destination),pagesize=A4,
                         leftMargin=20*mm,rightMargin=20*mm,topMargin=20*mm,bottomMargin=18*mm,
                         title="REFIT updated evaluation | House 6 holdout",
                         author="REFIT NILM Take-Home")
    doc.build(story)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('outputs'))
    args=parser.parse_args()
    out=args.output_dir
    root=Path(__file__).resolve().parents[1]
    secondary=out/'two_stage'
    original=get(out/'results.json')
    extra=get(secondary/'experiment_results.json')
    require_results(original,extra)
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        raise SystemExit("Install pypdf first: python -m pip install pypdf")
    # Existing finalizer retains standard assignment docs and the baseline report.
    subprocess.run([sys.executable,str(root/'scripts'/'finalize_submission.py'),
                    '--output-dir',str(out)],check=True,cwd=str(root))

    selected=extra['validation']['selected']
    base=next(r for r in extra['holdout_house6'] if r['experiment']=='Always off')
    candidate=next(r for r in extra['holdout_house6'] if r['experiment'].startswith('VALIDATION-SELECTED:'))
    rows=[base,candidate]
    marker='<!-- EXTENDED_REFIT_HOUSE6_EVALUATION -->'
    section=(
        '## Extended evaluation: validation-selected method and House 6 holdout\n\n'
        f"Train: Houses 1 and 2; validation/model selection: House 3; new independent holdout: House 6 (Appliance2). Date window: {extra['date_window_utc']['start_inclusive']} through {extra['date_window_utc']['end_exclusive']} (end exclusive, UTC).\n\n"
        f"**Method selected by validation F1:** `{selected['experiment']}`. The two-stage classifier/regressor was **rejected** because no tested threshold beat this F1 on House 3.\n\n"
        '### House 6 results\n\n'
        + markdown_table(rows) + '\n\n'
        f"Interpretation: the selected method improves active-minute MAE ({base['active_mae_w']:.2f} to {candidate['active_mae_w']:.2f} W), but overall MAE is worse ({base['mae_w']:.2f} to {candidate['mae_w']:.2f} W). "
        f"Precision {candidate['precision_active']:.3f}; recall {candidate['recall_active']:.3f}; F1 {candidate['f1_active']:.3f}; energy bias {candidate['energy_bias_percent']:+.2f}%. Not deployment-ready.\n\n"
        '### Scientific caveats\n\n'
        'House 5 was the initial held-out evaluation, but was subsequently examined; it is **not** a fresh holdout for later model changes. House 3 was used in iterative exploratory comparisons, so model-selection optimism is possible. House 6 was evaluated after model selection and should not be used for further tuning. The test set does not establish broad deployment reliability.\n\n'
        '### House 6 actual-versus-predicted plot\n\n'
        '![New House 6 holdout actual-vs-predicted](docs/figures/house6_actual_vs_predicted.png)\n'
    )
    append_section(root/'RESULTS.md',marker,section)
    rec=(
        '## Measured evidence and go/no-go decision\n\n'
        f"In the new House 6 holdout, the validation-selected original Random Forest + 50 W cutoff has MAE {candidate['mae_w']:.2f} W vs {base['mae_w']:.2f} W for always-off; active F1={candidate['f1_active']:.3f}, precision={candidate['precision_active']:.3f}, recall={candidate['recall_active']:.3f}. "
        'The method is not sufficiently reliable for personalised washing-machine event notifications, billing or automated enforcement. Continue research only; perform fresh cross-household validation and collect additional appliance-ground-truth data before proposing any utility pilot. Avoid claiming energy savings from unvalidated NILM estimates.\n'
    )
    append_section(root/'Recommendation.md',marker,rec)
    readme=(
        '## Final evaluation extension\n\n'
        'The additional `scripts/two_stage_experiment.py` compares a two-stage classifier/regressor against the original Random Forest + 50 W cutoff using House 3 for selection, and evaluates the selection once on House 6 (new holdout). The two-stage method did not win model selection. The REFIT dataset is not included in GitHub.\n\n'
        '```bash\n'
        'python scripts/two_stage_experiment.py --clean-dir CLEAN_REFIT_081116 --model-path outputs/model.joblib --output-dir outputs/two_stage --start 2014-09-01 --end 2014-12-01 --max-train-rows 120000\n'
        'python -m pip install pypdf\n'
        'python scripts/finalize_refit_with_holdout.py --output-dir outputs\n'
        '```\n\n'
        'Final submission PDF: `docs/Flock_Energy_Submission_Report.pdf`. See `RESULTS.md` for the new holdout metrics.\n'
    )
    append_section(root/'README.md',marker,readme)

    # Make result images viewable in GitHub, since /outputs is gitignored.
    fig_dest=root/'docs'/'figures'
    fig_dest.mkdir(parents=True, exist_ok=True)
    plot=secondary/'house6_actual_vs_predicted.png'
    for item in (out/'figures').glob('*.png'):
        shutil.copyfile(item,fig_dest/item.name)
    if plot.is_file():
        shutil.copyfile(plot,fig_dest/plot.name)
    appendix=secondary/'_report_house6_appendix.pdf'
    render_appendix(appendix,original,extra,plot)
    base_pdf=out/'Flock_Energy_Final_Report.pdf'
    final_pdf=root/'docs'/'Flock_Energy_Submission_Report.pdf'
    writer=PdfWriter()
    for file in (base_pdf,appendix):
        for page in PdfReader(str(file)).pages:
            writer.add_page(page)
    writer.add_metadata({'/Title':'Flock Energy | REFIT NILM: Reproducible Evaluation',
                         '/Subject':'Raw data, usage EDA, model baselines, model selection, House 6 holdout'})
    with final_pdf.open('wb') as f:writer.write(f)
    print('\nFINAL PDF:',final_pdf.resolve())
    print('Updated README.md, DATA.md, RESULTS.md, Recommendation.md.')
    # The user's extracted REFIT directories are at the repository root. The
    # original .gitignore excluded only data/raw/ and data/cleaned/.
    gitignore = root/'.gitignore'
    existing = gitignore.read_text(encoding='utf-8') if gitignore.exists() else ''
    additions = ['CLEAN_REFIT_081116/', 'REFIT_RAW_081116/', '*.7z']
    for entry in additions:
        if entry not in existing.splitlines():
            existing += ('\n' if existing and not existing.endswith('\n') else '') + entry + '\n'
    gitignore.write_text(existing, encoding='utf-8')
    # Retire the earlier generic PDF with 'results pending' language, if present.
    obsolete = root/'docs'/'Flock_Energy_Project_Explained.pdf'
    if obsolete.is_file():
        shutil.move(str(obsolete), str(out/'original_project_guide_superseded.pdf'))
    print('Copied figures into docs/figures so they can be published on GitHub.')
    print('Updated .gitignore: exclude both root-level REFIT archives and .7z files.')
    print('No models were retrained; no scores were modified. Verify all content and outputs before committing.')


if __name__=='__main__':
    main()
