"""REFIT ingestion, quality checks, cycle detection, and leakage-safe modelling.

All timestamps use the dataset's Unix epoch (UTC) where present. Power is W.
Data are resampled to one-minute MEAN power; W-min / 60 yields Wh.
"""
from __future__ import annotations
import re
from pathlib import Path
import numpy as np
import pandas as pd

# Verified against official CLEAN_READ_ME_081116.txt. House 4 has TWO washer channels;
# omitted to avoid silently treating two distinct appliances as one.
WASHER_CHANNELS = {1: 'Appliance5', 2: 'Appliance2', 3: 'Appliance6', 5: 'Appliance3'}
CHANNEL_NAMES = [f'Appliance{i}' for i in range(1, 10)]


def _key(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', str(s).lower())


def load_csv(path: str | Path, channels: list[str], start: str | None = None,
             end: str | None = None, chunksize: int = 300_000) -> pd.DataFrame:
    """Stream only needed columns and trim to [start, end) in UTC.

    Supports headers Time/DateTime, Unix/UnixTimestamp, Aggregate,
    Appliance1..9, Issues, with case and spacing differences.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'Missing {path}; extract official .7z archive first.')
    needed = set(channels) | {'Aggregate'}
    read_keys = {_key(s) for s in needed} | {'time','datetime','timestamp','unix','unixtimestamp','issues'}
    def wanted(name):
        return _key(name) in read_keys or _key(name).startswith('unixtimestamp')
    chunks = []
    begin = pd.Timestamp(start, tz='UTC') if start else None
    finish = pd.Timestamp(end, tz='UTC') if end else None
    for chunk in pd.read_csv(path, usecols=wanted,
                             chunksize=chunksize, low_memory=False):
        renames = {}
        for name in chunk.columns:
            key = _key(name)
            if key in ('time', 'datetime', 'timestamp'):
                renames[name] = 'Time'
            elif key == 'unix' or key.startswith('unixtimestamp'):
                renames[name] = 'Unix'
            elif key == 'aggregate':
                renames[name] = 'Aggregate'
            elif key == 'issues':
                renames[name] = 'Issues'
            elif re.fullmatch(r'appliance[1-9]', key):
                renames[name] = 'Appliance' + key[-1]
        chunk = chunk.rename(columns=renames)
        missing = needed - set(chunk.columns)
        if missing:
            raise ValueError(f'{path.name} missing expected columns: {sorted(missing)}')
        if 'Unix' in chunk:
            seconds = pd.to_numeric(chunk['Unix'], errors='coerce')
            stamps = pd.to_datetime(seconds, unit='s', utc=True, errors='coerce')
            if 'Time' in chunk:
                # Timestamp strings are local UK wall-clock, potentially with DST ambiguity.
                # Prefer Unix epoch; fallback here is explicitly a UTC assumption.
                fallback = pd.to_datetime(chunk['Time'], utc=True, errors='coerce')
                stamps = stamps.fillna(fallback)
        elif 'Time' in chunk:
            stamps = pd.to_datetime(chunk['Time'], utc=True, errors='coerce')
        else:
            raise ValueError(f'{path.name}: no Time or Unix column found')
        result = pd.DataFrame({'timestamp': stamps})
        for col in sorted(needed):
            result[col] = pd.to_numeric(chunk[col], errors='coerce').astype('float32')
        if 'Issues' in chunk:
            result['Issues'] = pd.to_numeric(chunk['Issues'], errors='coerce').fillna(0).astype('float32')
        if begin is not None:
            result = result.loc[result['timestamp'] >= begin]
        if finish is not None:
            result = result.loc[result['timestamp'] < finish]
        if not result.empty:
            chunks.append(result)
    if not chunks:
        raise ValueError(f'No records within requested period in {path.name}. Check dates.')
    return pd.concat(chunks, ignore_index=True)


def assess_and_resample(df: pd.DataFrame, channels: list[str], raw: bool = False,
                        max_short_gap: int = 2) -> tuple[pd.DataFrame, dict]:
    """1-minute mean power. Keep long outages as NaN, never call them zero.

    Duplicate timestamps: keep the last occurrence in source row order.
    For raw IAMs, <0 or >4000W are invalidated; negative aggregates invalidated.
    Even on cleaned files, >4000W IAMs are invalidated, not silently clipped.
    """
    n = len(df)
    bad_ts = int(df['timestamp'].isna().sum())
    valid = df.loc[df['timestamp'].notna()].copy()
    dups = int(valid['timestamp'].duplicated().sum())
    valid = valid.drop_duplicates('timestamp', keep='last').sort_values('timestamp')
    intervals = valid['timestamp'].diff().dt.total_seconds().dropna()
    report = {
        'input_rows': int(n), 'unparseable_timestamps': bad_ts,
        'duplicate_timestamps': dups,
        'out_of_order_adjacent_timestamps': int((df['timestamp'].diff().dt.total_seconds() < 0).sum()),
        'missing_source_readings_per_channel': {col: int(df[col].isna().sum()) for col in ['Aggregate'] + channels},
        'interval_median_seconds': float(intervals.median()) if len(intervals) else None,
        'intervals_over_20_seconds': int((intervals > 20).sum()),
        'largest_interval_minutes': float(intervals.max()/60) if len(intervals) else None,
        'date_min_utc': str(valid['timestamp'].min()),
        'date_max_utc': str(valid['timestamp'].max()),
        'negative_aggregate_readings': int((valid['Aggregate'] < 0).sum()),
        'aggregate_over_25000w_review': int((valid['Aggregate'] > 25000).sum()),
        'invalid_channel_readings': {},
    }
    valid.loc[valid['Aggregate'] < 0, 'Aggregate'] = np.nan
    for ch in channels:
        invalid = (valid[ch] < 0) | (valid[ch] > 4000)
        report['invalid_channel_readings'][ch] = int(invalid.sum())
        valid.loc[invalid, ch] = np.nan
    valid = valid.set_index('timestamp')
    cols = ['Aggregate'] + channels
    minute = valid[cols].resample('1min').mean()
    present_count = valid['Aggregate'].resample('1min').size()
    report['minutes_without_samples'] = int((present_count == 0).sum())
    if 'Issues' in valid:
        # Official Issues = 1 means sum of monitored appliances > aggregate.
        # Discard these minutes from both target and aggregate to avoid bad labels.
        issue = valid['Issues'].resample('1min').max().fillna(0).gt(0)
        report['flagged_issue_minutes'] = int(issue.sum())
        minute.loc[issue, cols] = np.nan
    else:
        report['flagged_issue_minutes'] = 0
    report['unfilled_minutes_per_column'] = {}
    report['long_outage_events_per_column'] = {}
    report['long_outage_minutes_per_column'] = {}
    report['long_outage_examples_per_column'] = {}
    report['short_gap_filled_minutes_per_column'] = {}
    for col in cols:
        before = minute[col].isna()
        # Count each consecutive missing run; only interior runs of <= max_short_gap.
        labels = before.ne(before.shift(fill_value=False)).cumsum()
        lengths = before.groupby(labels).transform('sum')
        long = before & lengths.gt(max_short_gap)
        report['long_outage_events_per_column'][col] = int((long & ~long.shift(fill_value=False)).sum())
        report['long_outage_minutes_per_column'][col] = int(long.sum())
        starts = minute.index[long & ~long.shift(fill_value=False)]
        report['long_outage_examples_per_column'][col] = [str(v) for v in starts[:5]]
        short = before & lengths.le(max_short_gap)
        forward = minute[col].ffill()
        backward = minute[col].bfill()
        short &= forward.notna() & backward.notna()
        # Never fill a flagged-inconsistency minute, even if it is an isolated gap.
        if 'Issues' in valid:
            short &= ~issue
        if raw:
            minute.loc[short, col] = forward.loc[short]
        # Official cleaned data already underwent gap filling. Avoid modifying it.
        report['short_gap_filled_minutes_per_column'][col] = int(short.sum()) if raw else 0
        report['unfilled_minutes_per_column'][col] = int(minute[col].isna().sum())
    minute.index.name = 'timestamp_utc'
    report['total_1min_bins'] = int(len(minute))
    report['raw_cleaning_applied'] = bool(raw)
    return minute, report


def detect_cycles(power: pd.Series, threshold_w: float = 20,
                  bridge_off_minutes: int = 10, min_duration_minutes: int = 15,
                  min_active_minutes: int = 3) -> pd.DataFrame:
    """Simple sensitivity-dependent heuristic; not verified cycle labels.

    Active means >20 W; bridge an off gap of <=10 minutes only if no NaN;
    require >=15 min total span and >=3 above-threshold minutes.
    """
    if power.empty:
        return pd.DataFrame(columns=['start_utc','end_utc','duration_min','active_min','peak_w','energy_kwh'])
    good = power.notna().to_numpy()
    above = (power.fillna(0).to_numpy() > threshold_w) & good
    indexes = np.flatnonzero(above)
    cycles = []
    if indexes.size == 0:
        return pd.DataFrame(columns=['start_utc','end_utc','duration_min','active_min','peak_w','energy_kwh'])
    groups = []
    left = int(indexes[0]); right = left
    for current in indexes[1:]:
        current = int(current)
        gap = current-right-1
        if gap <= bridge_off_minutes and bool(good[right+1:current].all()):
            right = current
        else:
            groups.append((left, right))
            left = right = current
    groups.append((left, right))
    for left, right in groups:
        span = power.iloc[left:right+1]
        duration = right-left+1
        active = int((span > threshold_w).sum())
        if duration >= min_duration_minutes and active >= min_active_minutes:
            cycles.append({
                'start_utc': power.index[left].isoformat(),
                'end_utc': power.index[right].isoformat(),
                'duration_min': duration,
                'active_min': active,
                'peak_w': round(float(span.max()), 2),
                'energy_kwh': round(float(span.sum() / 60 / 1000), 5),
            })
    return pd.DataFrame(cycles, columns=['start_utc','end_utc','duration_min','active_min','peak_w','energy_kwh'])


def create_features(frame: pd.DataFrame, target_column: str) -> pd.DataFrame:
    """Features use aggregate only; every rolling feature is trailing/causal."""
    x = frame['Aggregate'].astype('float32')
    out = pd.DataFrame(index=frame.index)
    out['aggregate_w'] = x
    out['lag1'] = x.shift(1)
    out['lag5'] = x.shift(5)
    out['lag15'] = x.shift(15)
    out['mean5'] = x.rolling(5, min_periods=5).mean()
    out['std5'] = x.rolling(5, min_periods=5).std()
    out['mean15'] = x.rolling(15, min_periods=15).mean()
    out['change1'] = x - x.shift(1)
    idx = frame.index
    out['hour_sin'] = np.sin(2*np.pi*(idx.hour + idx.minute/60)/24)
    out['hour_cos'] = np.cos(2*np.pi*(idx.hour + idx.minute/60)/24)
    out['dow_sin'] = np.sin(2*np.pi*idx.dayofweek/7)
    out['dow_cos'] = np.cos(2*np.pi*idx.dayofweek/7)
    out['target_w'] = frame[target_column]
    out = out.replace([np.inf, -np.inf], np.nan).dropna()
    out = out.loc[out['target_w'].ge(0)]
    return out


def metrics(y, pred, threshold_w: float = 20) -> dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, f1_score, precision_score, recall_score
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    actual_active = y > threshold_w
    pred_active = pred > threshold_w
    return {
        'minutes': int(len(y)),
        'mae_w': round(float(mean_absolute_error(y, pred)), 4),
        'rmse_w': round(float(np.sqrt(mean_squared_error(y, pred))), 4),
        'active_mae_w': round(float(mean_absolute_error(y[actual_active], pred[actual_active])),4) if actual_active.any() else None,
        'precision_active': round(float(precision_score(actual_active, pred_active, zero_division=0)),4),
        'recall_active': round(float(recall_score(actual_active, pred_active, zero_division=0)),4),
        'f1_active': round(float(f1_score(actual_active, pred_active, zero_division=0)),4),
        'actual_energy_kwh': round(float(y.sum()/60/1000),4),
        'predicted_energy_kwh': round(float(pred.sum()/60/1000),4),
        'energy_bias_percent': round(float(100*(pred.sum()-y.sum())/y.sum()),2) if y.sum() > 0 else None,
        'actual_active_fraction': round(float(actual_active.mean()),4),
    }


def find_house_csvs(directory: Path, house: int, raw: bool = False) -> list[Path]:
    if not directory.exists():
        raise FileNotFoundError(f'Dataset directory does not exist: {directory}')
    candidates = list(directory.rglob('*.csv'))
    matches = []
    for p in candidates:
        # Avoid matching House1 to House10/11/etc.
        if re.search(rf'(?i)house[_\s-]*{house}(?!\d)', p.stem):
            matches.append(p)
    if not matches:
        raise FileNotFoundError(f'Cannot locate House {house} CSV under {directory}')
    ranked = sorted(matches, key=lambda p: (0 if (('RAW' if raw else 'CLEAN') in p.name.upper()) else 1, len(p.parts)))
    if raw and len(ranked)>1:
        # If _Part1/_Part2 exist, ingest both; if a separate canonical RAW_House1
        # file exists, prefer that to avoid double counting.
        parts = [p for p in ranked if re.search(r'(?i)part[12]', p.stem)]
        non_parts = [p for p in ranked if p not in parts]
        return sorted(parts) if parts and not non_parts else [ranked[0]]
    return [ranked[0]]


def find_house_csv(directory: Path, house: int, raw: bool = False) -> Path:
    return find_house_csvs(directory, house, raw)[0]
