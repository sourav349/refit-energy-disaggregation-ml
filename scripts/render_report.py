"""Create a polished submission-structured PDF.

Without measured results: an honest detailed PDF guide explaining the built pipeline.
With results.json: an evidence-backed report including measured charts and metrics.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, Image, KeepTogether, HRFlowable, ListFlowable, ListItem)
from reportlab.graphics.shapes import Drawing, Rect, String, Line

DARK=colors.HexColor('#172B43')
TEAL=colors.HexColor('#047B89')
PALE=colors.HexColor('#EAF5F6')
GRAY=colors.HexColor('#546477')
LIGHT=colors.HexColor('#E3E9EF')
GOLD=colors.HexColor('#C58B3C')


def build_styles():
    st=getSampleStyleSheet()
    st.add(ParagraphStyle(name='HeroBrand',fontName='Helvetica-Bold',fontSize=11,leading=14,textColor=TEAL,spaceAfter=14))
    st.add(ParagraphStyle(name='HeroTitleX',fontName='Helvetica-Bold',fontSize=30,leading=36,textColor=DARK,spaceAfter=18))
    st.add(ParagraphStyle(name='HeroSubX',fontName='Helvetica',fontSize=13,leading=20,textColor=GRAY,spaceAfter=20))
    st.add(ParagraphStyle(name='SectionX',fontName='Helvetica-Bold',fontSize=16,leading=21,textColor=DARK,spaceBefore=12,spaceAfter=11,keepWithNext=True))
    st.add(ParagraphStyle(name='SubX',fontName='Helvetica-Bold',fontSize=11.2,leading=16,textColor=TEAL,spaceBefore=11,spaceAfter=5,keepWithNext=True))
    st.add(ParagraphStyle(name='BodyX',fontName='Helvetica',fontSize=9.7,leading=15,textColor=DARK,spaceAfter=8))
    st.add(ParagraphStyle(name='SmallX',fontName='Helvetica',fontSize=8.2,leading=12,textColor=DARK,spaceAfter=5))
    st.add(ParagraphStyle(name='MicroX',fontName='Helvetica',fontSize=7.8,leading=11,textColor=GRAY))
    st.add(ParagraphStyle(name='QuoteX',fontName='Helvetica-Bold',fontSize=10,leading=16,textColor=DARK,spaceAfter=7))
    st.add(ParagraphStyle(name='CenterX',fontName='Helvetica',fontSize=9.5,leading=14,textColor=DARK,alignment=TA_CENTER))
    return st


def build_pdf(dest:Path, results:dict|None=None, figures_dir:Path|None=None):
    dest=Path(dest); dest.parent.mkdir(parents=True,exist_ok=True)
    source_is_real=bool(results and results.get('status')=='official_REFIT_analysis')
    status='REFIT RESULTS INCLUDED' if source_is_real else 'METHOD & IMPLEMENTATION REVIEW  |  REFIT RESULTS PENDING'
    st=build_styles()
    story=[]
    def P(text, style='BodyX'):return Paragraph(text,st[style])
    def H(t):story.append(P(t,'SectionX'))
    def SH(t):story.append(P(t,'SubX'))
    def B(t):story.append(P(t,'BodyX'))
    def BUL(items):
        for item in items:
            story.append(P('<font color="#047B89"><b>\u2022</b></font>  '+item,'BodyX'))
    def T(rows,widths=None,header=True):
        safe=[]
        for row in rows:
            safe.append([P(str(x), 'SmallX') for x in row])
        tbl=Table(safe,colWidths=widths,hAlign='LEFT',repeatRows=1 if header else 0)
        rules=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),
               ('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),
               ('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-1),0.25,LIGHT)]
        if header:
            rules += [('BACKGROUND',(0,0),(-1,0),PALE),('TEXTCOLOR',(0,0),(-1,0),DARK)]
        tbl.setStyle(TableStyle(rules));story.append(tbl); story.append(Spacer(1,9))
    def NEXT():story.append(PageBreak())
    def FIG(filename, caption):
        if not figures_dir: return
        f=figures_dir/filename
        if not f.exists(): return
        from PIL import Image as PILImage
        with PILImage.open(f) as im:
            w,h=im.size
        maxw=170*mm; maxh=100*mm
        factor=min(maxw/w,maxh/h)
        story.append(KeepTogether([Image(str(f),width=w*factor,height=h*factor),P(caption,'MicroX')]))
        story.append(Spacer(1,9))

    # --- COVER ---
    story.extend([Spacer(1,24*mm),P('FLOCK ENERGY  /  DATA SCIENCE TAKE-HOME','HeroBrand'),
     P('Washing-Machine<br/>Load Disaggregation<br/>from REFIT Data','HeroTitleX'),
     P('A reproducible data-cleaning, usage-analysis and machine-learning proof of concept','HeroSubX')])
    story.append(HRFlowable(width='100%',thickness=2,color=TEAL,spaceBefore=10,spaceAfter=18))
    T([['Problem','Estimate washing-machine power from a whole-home smart-meter signal.'],
       ['Data','Official REFIT raw House 1 + cleaned Houses 1, 2, 3, 5.'],
       ['Method','Minute-level quality audit, cycle EDA, always-off baseline, Random Forest.'],
       ['Validation','Disjoint household split: train 1/2, validate 3, test 5.'],
       ['Evidence status',status]],widths=[37*mm,136*mm],header=False)
    B('<b>Important:</b> The assignment requires a <b>public GitHub repository</b> with executable code and four specific Markdown deliverables. This PDF is the companion report. A PDF alone does not meet the stated submission instructions.')
    B('<b>Integrity statement:</b> No measured REFIT data were supplied with the assignment. Until the official archives are downloaded and analysed, measured performance, cycle counts and household quality findings must remain pending.') if not source_is_real else B('<b>Evidence:</b> Plots and statistics in this report were generated from a run labelled official REFIT; verify source file provenance and visually inspect plots before publishing.')
    story.append(Spacer(1,35*mm))
    story.append(P('Prepared with Python, Pandas, scikit-learn, Matplotlib and ReportLab | 2026','SmallX'))
    NEXT()

    H('01  The assignment explained in plain English')
    B('A household electricity meter measures the sum of all appliances operating at that moment. A utility usually does not know whether a washing machine, kettle or dishwasher caused an increase. The challenge is to infer washing-machine power from the aggregate signal; this is known as non-intrusive load monitoring (NILM).')
    T([['Illustrative example (NOT a measured REFIT result)','Power'],
      ['Refrigerator','150 W'],['Washing machine','1,800 W'],['TV, fan, and lights combined','250 W'],
      ['Total observed by whole-house meter','2,200 W']],widths=[137*mm,36*mm])
    B('The model sees the 2,200 W whole-house input. During training it also has a correctly labelled washing-machine submeter channel; during inference it must predict the washing-machine signal without that appliance channel.')
    SH('What the four assignment sections ask for')
    T([['Required stage','Deliverable in this implementation'],
       ['1. Raw cleaning','Audit timestamps, duplicates, nonphysical data, missing minutes; clean raw House 1; make before-and-after plots.'],
       ['2. Usage exploration','Four homes; washer sensor mapping; candidate cycles; hourly/weekly patterns; cross-home figures.'],
       ['3. Model and evaluation','Aggregate-only baseline and RF model; split by household; active/off metrics and actual-versus-predicted plot.'],
       ['4. Utility insight','Customer-facing off-peak opportunity, success criteria, transfer limitations, coarser meter data.']],widths=[41*mm,132*mm])
    B('<b>What matters most:</b> correct data handling and reasoning. The brief explicitly prefers a simple correct analysis to an advanced model that is difficult to justify.')
    NEXT()

    H('02  Official dataset and study design')
    B('REFIT is a University of Strathclyde electricity dataset from 20 UK households, collected across an overall 2013-2015 period. Original readings are about every 8 seconds and are measured in watts. Each home includes an aggregate channel and up to nine appliance submeter channels. Exact availability differs by home; individual study dates are determined from executed data.')
    B('Two dataset editions are deliberately used: the original raw edition for the House 1 quality audit, and the official cleaned edition for cross-home washing-machine analysis and modelling. The latter has already undergone special corrections, including daylight-saving adjustments and imputation.')
    T([['House','Official washer channel','Purpose'],['1','Appliance5','Raw + cleaned; training'],
       ['2','Appliance2','Cleaned; training'],['3','Appliance6','Cleaned; validation'],
       ['5','Appliance3','Cleaned; held-out test']],widths=[30*mm,67*mm,76*mm])
    B('This mapping is not optional. A fixed Appliance5 target across all homes would train on the wrong appliances for Houses 2, 3 and 5. House 4 has two monitored washers and is excluded to keep this example unambiguous.')
    SH('Analysis window and units')
    BUL(['Default requested study period: 2014-09-01 to 2014-12-01, first date inclusive and second exclusive, in UTC.',
         'Resample individual readings to 1-minute mean power, not the sum of watts.',
         'Energy of a 1-minute sample: kWh = power in W / 60,000. Sum this over minutes of a detected cycle.',
         'Official cleaned files may contain artificial zeros used for long outages; a zero can therefore mean missingness instead of genuine appliance inactivity.'])
    NEXT()

    H('03  Raw data cleaning: exact decisions')
    T([['Problem','Professional response'],
       ['Unparseable timestamps','Parse Unix epoch in UTC where present. Count and exclude timestamps that cannot be parsed.'],
       ['Duplicate timestamps','Stable rule: last record in source file wins, then sort ascending.'],
       ['Irregular measurements','Compute differences between consecutive timestamps; log intervals exceeding 20 seconds.'],
       ['Negative values / high IAM spikes','Invalidate negative power; invalidate appliance readings above 4000 W. Note aggregate readings over 25 kW for manual review.'],
       ['Small missing gaps','Only fill entire missing runs of one or two minutes if bounded by valid observations.'],
       ['Long outages','Preserve NaN throughout the outage, not zero or partially filled values.'],
       ['Official Issues flag','If available, discard minutes with a submeter-sum inconsistency.']],widths=[47*mm,126*mm])
    SH('Why not fill every missing gap?')
    B('A 90-minute sensor outage does not mean the washing machine was turned off for 90 minutes. Replacing missing values with zero creates false evidence, biases energy totals and may teach the model that a genuine power-off event occurred.')
    SH('Why the one-minute mean?')
    B('The assignment requests 1-minute power estimates. Average instantaneous power samples within each minute to produce one point per minute. Only afterward convert watts to kWh using the duration. Summing raw watts directly is not a meaningful energy calculation.')
    NEXT()

    H('04  Exploratory analysis: detect washer cycles')
    B('An operating event is not every individual spike: washing machines often pause, fill, agitate and spin. The code uses a transparent heuristic rather than pretending to have labelled ground-truth cycle boundaries.')
    T([['Rule parameter','Chosen working value'],['Appliance considered active','Measured power >20 W'],
       ['Permitted internal pause','Up to 10 minutes, if all intervening minutes are observed'],
       ['Minimum total event span','15 minutes'],['Minimum above-threshold samples','3 one-minute points']],widths=[76*mm,97*mm])
    B('These are initial engineering assumptions, <b>not</b> manufacturer-verified cycle labels. A robust future analysis should compare cycle counts across thresholds (e.g. 10, 20 and 50 W) and inspect visually identified cycles.')
    SH('Questions answered for each home')
    BUL(['How many valid/missing minutes were recorded? What percentage of observed washing-machine minutes were off?',
         'What are the actual coverage start and end dates, and how many candidate cycles were found?',
         'At which hours and weekdays do events begin? The plotting code uses UTC, so local UK behavioural interpretation needs time-zone conversion.',
         'Which homes have larger median cycle duration and estimated energy per detected event?'])
    B('The six output figures include raw versus cleaned signals, a 24-hour whole-home/washing-machine trace, one detected cycle, cross-home comparison, usage timing, and held-out test actual-versus-predicted power.')
    NEXT()

    H('05  Model and honest evaluation')
    B('Target: washing-machine power W at minute t. Features: whole-home aggregate power W at t and earlier minutes, its trailing rolling mean/standard deviation, lagged changes, and calendar encodings. The model never receives the washer submeter as an input feature.')
    T([['Model','Why included'],['Always-off baseline (0 W)','Necessary because off minutes dominate, and low average error may be misleading.'],
      ['Random Forest regression','Works with nonlinear power patterns and numeric engineered features; straightforward to implement and explain.']],widths=[56*mm,117*mm])
    SH('Split before inference: keep whole households apart')
    B('<b>Training</b> = House 1 + House 2. <b>Validation</b> = House 3. <b>Untouched final test</b> = House 5. This tests generalisation to a household that was not part of model fitting. Randomly splitting adjacent one-minute readings would leak very similar, overlapping cycles between train and test.')
    SH('Evaluation metrics and their meanings')
    T([['Metric','Interpretation'],['MAE (W)','Mean magnitude of watt-level error; compare with always-off baseline.'],
      ['RMSE (W)','Larger errors are penalised more heavily; detects missed high peaks.'],
      ['Active-minute MAE (W)','Error when washing machine truly operated; avoids hiding errors in off time.'],
      ['Active precision / recall / F1','Can the predicted watts correctly mark operating minutes (>20 W)?'],
      ['Energy bias (%)','Compare predicted with actual accumulated kWh for observed minutes.']],widths=[57*mm,116*mm])
    B('A Random Forest is not automatically better than the always-off baseline. If it loses, report it and discuss why. Do not tune to House 5 test results; any changes should use training/validation only.')
    NEXT()

    H('06  Realistic customer and utility recommendation')
    SH('Proposed insight')
    B('Use inferred laundry timing and approximate energy to give interested customers optional information: "Your washing-machine use is estimated to occur mostly around these hours. If you have a suitable time-of-use tariff, running it later could reduce peak-hour costs." Confirm tariff eligibility and display uncertainty.')
    SH('How to prove value')
    BUL(['Verify accuracy against real appliance submeter readings in a ground-truth sample.',
         'Run a randomised opt-in pilot, with a comparison group receiving no personalised washing-machine advice.',
         'Track peak-period kWh shifted, energy and bill changes, opt-in/opt-out rates, customer satisfaction and erroneous event notifications.',
         'Make a distinction: shifting a wash to off-peak does not automatically reduce the kWh used.'])
    SH('Where the system can fail')
    BUL(['Two devices switch on at once; their electrical signatures overlap.',
         'A new household owns a different washer with a previously unseen heating/spinning pattern.',
         'Official prefilled zeros, communication dropouts or inconsistent sensor channels make some labels unreliable.',
         'UK data should not be deployed to Indian customers without India-specific sampling, tariff, appliance and validation evidence.'])
    SH('What changes with 15-minute or 30-minute meter data?')
    B('A five-minute high-power phase is averaged with many low-power minutes. Peaks, event boundaries and short pauses disappear, so reconstructing washing-machine cycles accurately becomes substantially harder. Summary-level behavioural signals might remain, but measured 1-minute model performance cannot be assumed to transfer to 15/30-minute data.')
    NEXT()

    H('07  Reproduction and exact submission instructions')
    SH('Step A - install and test')
    B('Use Python 3.10+. From the extracted project directory, create a virtual environment, run <b>pip install -r requirements.txt</b>, then <b>pip install -e .</b>, and finally <b>pytest -q</b>.')
    SH('Step B - download and extract REFIT')
    B('Download REFIT_RAW_081116.7z and CLEAN_REFIT_081116.7z from the official URLs in README.md. Extract raw CSVs under data/raw and official cleaned CSVs under data/cleaned. The raw and cleaned compressed archives are several hundred megabytes each; do not upload the dataset into GitHub.')
    SH('Step C - run the project on measured data')
    B('<font face="Courier">python -m refit_nilm.pipeline --raw-dir data/raw --clean-dir data/cleaned --output-dir outputs --start 2014-09-01 --end 2014-12-01</font>')
    SH('Step D - inspect and finalise')
    B('Open every PNG in outputs/figures. Check coverage, quality flags, event reasonableness and the baseline/model metrics. Then run <b>python scripts/finalize_submission.py --output-dir outputs</b> to populate the required data-backed Markdown files and generate a submission PDF. It intentionally refuses synthetic demo runs.')
    SH('Step E - submit the GitHub repository')
    T([['Required file','What it contains'],['Python source code','Executable ingestion, cleaning, EDA, prediction, evaluation and tests'],
       ['README.md','Reproduction, assumptions, features, data links and AI assistance disclosure'],
       ['DATA.md','Real raw-quality observations and cleaning decisions'],
       ['RESULTS.md','Real EDA, results, validation, failures and plotted evidence'],
       ['Recommendation.md','One-page utility summary and section 4 answers'],
       ['Optional PDF','Full report, with genuine REFIT results only after actual execution']],widths=[49*mm,124*mm])
    NEXT()

    if source_is_real:
        H('08  Measured REFIT experiment outputs')
        r=results
        q=r['raw_house1_quality']
        B(f"Raw House 1 selected-period quality: <b>{q['input_rows']:,} input records</b>; <b>{q['duplicate_timestamps']:,} duplicate timestamps</b>; <b>{q['unparseable_timestamps']:,} invalid timestamps</b>; <b>{q['minutes_without_samples']:,} unobserved minute bins</b>.")
        T([['House','Channel','Observed minutes','Missing minutes','Candidate cycles','Median kWh/event']]+[
           [str(h['house']),h['washing_machine_channel'],f"{h['available_minutes']:,}",
            f"{h['missing_minutes']:,}",str(h['cycles']),str(h['median_cycle_kwh'])] for h in r['households']],
          widths=[22*mm,28*mm,31*mm,30*mm,31*mm,31*mm])
        SH('Model performance, evaluated without test-house training')
        score_rows=[['Split','Method','MAE (W)','RMSE (W)','Active F1','Energy bias %']]
        for split,methods in r['scores'].items():
            for method,m in methods.items():
                score_rows.append([split.replace('_house',' H'),method.replace('_baseline',''),str(m['mae_w']),str(m['rmse_w']),str(m['f1_active']),str(m['energy_bias_percent'])])
        T(score_rows,widths=[29*mm,37*mm,26*mm,27*mm,26*mm,28*mm])
        B('Metric interpretation: overall MAE can favour always-off due to infrequent operation; review active MAE, active F1 and individual cycles before concluding the model is useful.')
        NEXT()
        H('09  REFIT plots: raw/cleaned and usage')
        FIG('01_raw_before_after.png','Figure 1. Actual raw versus processed House 1 signals (same UTC day), for aggregate and two appliance channels.')
        FIG('02_trace_24h.png','Figure 2. One 24-hour reference trace, measured aggregate and washer.')
        NEXT()
        H('10  REFIT plots: cycles and cross-home behaviour')
        FIG('03_detected_cycle.png','Figure 3. Example inferred washing-machine event; event boundaries are heuristic.')
        FIG('04_house_comparison.png','Figure 4. Cross-house event count and median energy per candidate event.')
        NEXT()
        H('11  REFIT plots: usage patterns and test prediction')
        FIG('05_usage_hour_weekday.png','Figure 5. Cycle starts by UTC hour and day of week across four houses.')
        FIG('06_actual_vs_predicted.png','Figure 6. Actual washer versus RF prediction on the untouched House 5 test set.')
        NEXT()
    else:
        H('08  Execution status: what is still required')
        B('<b>Implemented and exercised:</b> Python data loader, raw quality audit, 1-minute cleaning, four-home washer-channel mapping, event rules, cross-house EDA figures, causal model features, baseline, Random Forest, held-out validation, measured-data report generator and unit tests.')
        B('<b>Not completed with measured REFIT evidence:</b> Source archives were not part of the supplied assignment, and measured House 1 quality counts, four-home cycle counts, and real held-out error metrics cannot be responsibly reported yet.')
        B('<b>Testing status:</b> End-to-end execution was checked using an explicitly simulated dataset, which is not appropriate evidence for this take-home. The tests establish program flow, not real-world performance or data provenance.')
        SH('Fill only from actual execution')
        T([['Evidence required','How it is produced'],['Raw records / duplicates / gap counts','outputs/results.json and outputs/DATA_generated.md'],
           ['Four-house coverage and cycle metrics','outputs/household_summary.csv and house*_cycles.csv'],
           ['Real charts','outputs/figures/01...06 PNGs'],
           ['Baseline vs model errors','outputs/RESULTS_generated.md and results.json'],
           ['Evaluated PDF','python scripts/finalize_submission.py --output-dir outputs']],widths=[74*mm,99*mm])
        B('A reviewer may ask: How did you avoid leakage? Why use minute means? What happens if your model loses to all-off? Why cannot you infer real off-time from the dataset authors\' zero-filled outages? Be ready to answer each directly.')
        NEXT()

    H('References, attribution and responsible use')
    BUL(['University of Strathclyde, REFIT: Electrical Load Measurements (Raw). https://pureportal.strath.ac.uk/en/datasets/refit-electrical-load-measurements/',
         'University of Strathclyde, REFIT: Electrical Load Measurements (Cleaned). https://pureportal.strath.ac.uk/en/datasets/refit-electrical-load-measurements-cleaned/',
         'Official cleaned README: https://pure.strath.ac.uk/ws/portalfiles/portal/62090183/CLEAN_READ_ME_081116.txt',
         'Murray, D., Stankovic, L., and Stankovic, V. (2017). An electrical load measurements dataset of United Kingdom households from a two-year longitudinal study. Scientific Data, 4:160122. https://doi.org/10.1038/sdata.2016.122',
         'Dataset licence: Creative Commons Attribution 4.0 (CC BY 4.0).'])
    SH('What the candidate should say about AI assistance')
    B('ChatGPT helped scaffold the Python implementation, draft the explanatory documentation, write unit tests and structure this PDF. The candidate must execute the measured-data experiment, verify every plot, interpret results, document edits, and be prepared to explain all reasoning. Do not present an AI-generated description as personal experimental observation.')
    SH('Suggested technical progression')
    B('This is fundamentally a Data Science / Machine Learning Engineering assignment. The high-value professional skill is the combination of careful data engineering, quantitative evaluation, and reproducible code. A web frontend or elaborate deployment system is not requested and would add risk without strengthening this submission.')

    def decorate(canvas, doc):
        canvas.saveState()
        width,height=A4
        canvas.setFillColor(DARK);canvas.rect(0,height-15*mm,width,15*mm,fill=1,stroke=0)
        canvas.setFont('Helvetica-Bold',8);canvas.setFillColor(colors.white)
        canvas.drawString(19*mm,height-9.5*mm,'FLOCK ENERGY  /  REFIT NILM')
        canvas.setStrokeColor(LIGHT);canvas.line(19*mm,17*mm,width-19*mm,17*mm)
        canvas.setFont('Helvetica',7.5);canvas.setFillColor(GRAY)
        canvas.drawString(19*mm,12.5*mm,status)
        canvas.drawRightString(width-19*mm,12.5*mm,f'Page {doc.page}')
        canvas.restoreState()

    doc=SimpleDocTemplate(str(dest),pagesize=A4,rightMargin=19*mm,leftMargin=19*mm,
                          topMargin=23*mm,bottomMargin=21*mm,title='REFIT Washing Machine Disaggregation | Flock Energy',
                          author='Data Science Take-Home Project',subject=status)
    doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
    return dest

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--dest',type=Path,default=Path('docs/Flock_Energy_Project_Explained.pdf'))
    p.add_argument('--results',type=Path,default=None)
    p.add_argument('--figures',type=Path,default=None)
    args=p.parse_args()
    data=json.loads(args.results.read_text()) if args.results else None
    print('Created:',build_pdf(args.dest,data,args.figures))
