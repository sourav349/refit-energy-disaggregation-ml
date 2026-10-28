"""Matplotlib figures written with deliberate legends and units."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def save_raw_comparison(raw, clean, outpath: Path):
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True, layout='constrained')
    # Use first day for deterministic review; traces are unaltered above / resampled below.
    t0 = clean.index.min()
    t1 = t0 + pd.Timedelta('24h')
    focus = raw[(raw.timestamp >= t0) & (raw.timestamp < t1)]
    selected = ['Aggregate','Appliance1','Appliance5']
    for channel in selected:
        if channel in focus:
            axes[0].plot(focus['timestamp'], focus[channel], label=channel, linewidth=.6, alpha=.7)
        if channel in clean:
            axes[1].plot(clean.loc[t0:t1].index, clean.loc[t0:t1, channel], label=channel, linewidth=1)
    axes[0].set_title('Raw House 1 | 8-second-class readings (before cleaning)')
    axes[1].set_title('Processed House 1 | minute-mean readings (after cleaning)')
    for a in axes:
        a.set_ylabel('Power (W)'); a.legend(loc='upper right', ncol=3); a.grid(alpha=.15)
    axes[-1].set_xlabel('UTC timestamp')
    fig.savefig(outpath, dpi=170); plt.close(fig)


def save_day_trace(house, minute, target, cycles, outpath):
    if not cycles.empty:
        t = pd.Timestamp(cycles.iloc[0]['start_utc']).floor('D')
    else:
        t = minute.index.min().floor('D')
    sl = minute.loc[(minute.index >= t) & (minute.index < t + pd.Timedelta('1D'))]
    fig, ax = plt.subplots(figsize=(11, 4), layout='constrained')
    ax.plot(sl.index, sl.Aggregate, label='Whole-house', alpha=.75, linewidth=1)
    ax.plot(sl.index, sl[target], label='Washing machine - actual', linewidth=1.25)
    ax.set_title(f'House {house} | 24-hour whole-home vs washing-machine trace ({t.date()})')
    ax.set_xlabel('UTC'); ax.set_ylabel('Power (W)'); ax.grid(alpha=.2); ax.legend()
    fig.savefig(outpath, dpi=170); plt.close(fig)


def save_cycle_trace(house, minute, target, cycles, outpath):
    if cycles.empty:
        fig, ax = plt.subplots(figsize=(10, 3)); ax.text(.5,.5,'No qualifying cycles detected in selected period',ha='center',va='center',transform=ax.transAxes); ax.axis('off')
    else:
        first = cycles.iloc[0]
        t = pd.Timestamp(first['start_utc'])
        a = minute.loc[t-pd.Timedelta('20min'):pd.Timestamp(first['end_utc'])+pd.Timedelta('20min')]
        fig, ax = plt.subplots(figsize=(10, 3.5), layout='constrained')
        ax.plot(a.index, a[target], label='Measured washing-machine power (W)')
        ax.axvspan(t, pd.Timestamp(first['end_utc']), color='lightgray', alpha=.35, label='Detected cycle')
        ax.set_title(f'House {house}: detected cycle ({first["duration_min"]} min, {first["energy_kwh"]:.2f} kWh)')
        ax.set_xlabel('UTC'); ax.set_ylabel('Power (W)'); ax.legend(); ax.grid(alpha=.2)
    fig.savefig(outpath, dpi=170); plt.close(fig)


def save_cross_home(summary: pd.DataFrame, outpath):
    fig, axs = plt.subplots(1, 2, figsize=(10, 4), layout='constrained')
    houses = summary['house'].astype(str)
    axs[0].bar(houses, summary['cycles']); axs[0].set_ylabel('Detected cycles'); axs[0].set_xlabel('House')
    axs[1].bar(houses, summary['median_cycle_kwh'].fillna(0)); axs[1].set_ylabel('Median kWh per detected cycle'); axs[1].set_xlabel('House')
    for a in axs: a.grid(axis='y', alpha=.2)
    fig.suptitle('Cross-house washing-machine comparison')
    fig.savefig(outpath, dpi=170); plt.close(fig)


def save_usage(cycles_by_house: dict, outpath):
    fig, axs = plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    for house, cycles in cycles_by_house.items():
        if cycles.empty: continue
        start = pd.to_datetime(cycles['start_utc'], utc=True)
        axs[0].plot(np.arange(24), start.dt.hour.value_counts().reindex(range(24),fill_value=0).values, marker='.', label=str(house))
        axs[1].plot(np.arange(7), start.dt.dayofweek.value_counts().reindex(range(7),fill_value=0).values, marker='.', label=str(house))
    axs[0].set_title('Cycle starts by hour (UTC)'); axs[0].set_xlabel('Hour'); axs[0].set_xticks(range(0,24,3))
    axs[1].set_title('Cycle starts by weekday (UTC)'); axs[1].set_xlabel('Mon ... Sun'); axs[1].set_xticks(range(7), ['M','T','W','Th','F','Sa','Su'])
    for a in axs: a.set_ylabel('Detected cycle count'); a.grid(alpha=.2)
    axs[1].legend(title='House', fontsize=8)
    fig.savefig(outpath,dpi=170); plt.close(fig)


def save_predictions(test, preds, outpath):
    tindex = test.index
    y = test['target_w'].to_numpy()
    # Day with most actual washing-machine energy for an informative (non-cherry-picked) trace.
    day = pd.Series(y, index=tindex).resample('D').sum().idxmax()
    mask = (tindex >= day) & (tindex < day+pd.Timedelta('1D'))
    fig, ax = plt.subplots(figsize=(11,4), layout='constrained')
    ax.plot(tindex[mask], y[mask], label='Actual', linewidth=1)
    ax.plot(tindex[mask], preds[mask], label='Predicted', linewidth=1.0, alpha=.8)
    ax.set_title(f'Held-out House 5 | Highest-activity evaluation day: {day.date()}')
    ax.set_xlabel('UTC timestamp'); ax.set_ylabel('Washing-machine power (W)'); ax.legend(); ax.grid(alpha=.2)
    fig.savefig(outpath, dpi=170); plt.close(fig)
