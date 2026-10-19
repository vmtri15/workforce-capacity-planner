"""Forecast daily warehouse demand 4 weeks ahead and measure what forecast error costs.

Observed data: units per day from the 2023 footwear order export (Monday to Friday only; the few
Sunday records are left out). Dates with no source records are unknown, not zero, so they are never
used for training or scoring.

Method (same no leakage rules as the Walmart forecasting project):
  * Rolling origin backtest. Each Friday is a forecast origin. Every model only sees days up to the
    origin and forecasts the next 20 weekdays.
  * Two baselines (same weekday last week, mean of the last 20 weekdays) against Prophet, ARIMA and
    XGBoost. There is under one year of data, so there is no yearly seasonality and no "same week
    last year" baseline.
  * Score with WAPE (total absolute error / total demand) and bias, not MAPE, because low demand days
    make MAPE unstable.
  * Low and high band: the 10th and 90th percentile of actual / forecast from the backtest. The band
    is calibrated on the first 60% of origins and its coverage is checked on the rest.
  * Cost of forecast error: at each origin, choose the smallest headcount that reaches the on time
    target on the forecast, replay that headcount on the actual demand with the planner's own
    service simulation, and compare with the headcount an exact forecast would have chosen.
    Staffing is fixed headcount only (no overtime or temporary shifts). Rates and costs are the
    hypothetical scenario inputs in config/, not observed. Because a point forecast smooths away
    spikes, the sizing is also tried on forecast * 1.25, 1.5 and 2.0 (fixed buffers, not fitted).

Run from the project root:
    python3 scripts/forecast_demand.py
"""
import csv
import json
import logging
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from workforce_planner.service_scenarios import simulate

SOURCE = ROOT / 'data/raw/warehouse_picking/Customer_Order.csv'
OUT = ROOT / 'data/processed/demand_forecast'
HORIZON = 20          # weekdays, about 4 weeks
MIN_TRAIN_WEEKS = 12
CALIBRATION_SHARE = 0.6
LOW_Q, HIGH_Q = 0.10, 0.90
RATE = 40             # units per productive hour, the base case in config/staffing_cost_scenarios.json
SERVICE_DAYS = 2
MODELS = ['SameWeekdayLastWeek', 'Mean20Days', 'Prophet', 'ARIMA', 'XGBoost', 'Ridge', 'QuantileP90']
P90_MODEL = 'QuantileP90'  # a high case, not a point forecast: judged by coverage, never picked as best by WAPE
BUFFERS = [1.0, 1.25, 1.5, 2.0]  # fixed in advance: headcount is sized on forecast * buffer


def load_daily():
    """Units per calendar date from the retained order records."""
    units = defaultdict(int)
    with SOURCE.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle, delimiter=';'):
            day = datetime.strptime(row['creationDate'], '%d/%m/%Y %H:%M').date()
            quantity = int(row['quantity (units)'])
            if quantity < 0:
                raise ValueError('Negative order quantity requires review')
            units[day] += quantity
    return units


def weekday_grid(units):
    """Every Monday to Friday between the first and last record; NaN where no records exist."""
    start, end = min(units), max(units)
    days = [start + timedelta(n) for n in range((end - start).days + 1)]
    days = [d for d in days if d.weekday() < 5]
    return pd.Series([units.get(d, np.nan) for d in days], index=pd.to_datetime(days), dtype=float)


def next_weekdays(last, n):
    out, day = [], last
    while len(out) < n:
        day += timedelta(1)
        if day.weekday() < 5:
            out.append(day)
    return out


def _nanmean(values):
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    return values.mean() if len(values) else np.nan


# Each forecaster gets only the history up to the origin and the future dates to predict.

def same_weekday_last_week(hist, future):
    latest = {}
    for stamp, value in hist.dropna().items():
        latest[stamp.weekday()] = value  # history is ascending, so the most recent value wins
    fallback = hist.mean()
    return np.array([latest.get(d.weekday(), fallback) for d in future])


def mean_20_days(hist, future):
    level = _nanmean(hist.to_numpy()[-20:])
    return np.full(len(future), level if not np.isnan(level) else hist.mean())


def prophet_forecast(hist, future):
    from prophet import Prophet
    logging.getLogger('cmdstanpy').setLevel(logging.ERROR)
    logging.getLogger('prophet').setLevel(logging.ERROR)
    known = hist.dropna()
    model = Prophet(yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=False)
    model.fit(pd.DataFrame({'ds': known.index, 'y': known.to_numpy()}))
    predicted = model.predict(pd.DataFrame({'ds': pd.to_datetime(future)}))['yhat'].to_numpy()
    return np.clip(predicted, 0, None)


def arima_forecast(hist, future):
    from statsmodels.tsa.arima.model import ARIMA
    # ponytail: recorded days are treated as consecutive, so gaps in the records are ignored.
    # Upgrade to a state space model with missing values if gaps matter.
    fit = ARIMA(hist.dropna().to_numpy(), order=(1, 0, 1)).fit()
    return np.clip(np.asarray(fit.forecast(len(future))), 0, None)


def feature_row(values, weekday):
    v = np.asarray(values, dtype=float)
    return [v[-1], v[-5], _nanmean(v[-5:]), _nanmean(v[-20:]), weekday]


def xgboost_forecast(hist, future):
    from xgboost import XGBRegressor
    v = hist.to_numpy(dtype=float)
    weekdays = hist.index.dayofweek
    rows, target = [], []
    for i in range(20, len(v)):
        if not np.isnan(v[i]):
            rows.append(feature_row(v[:i], weekdays[i]))
            target.append(v[i])
    if len(rows) < 10:
        return mean_20_days(hist, future)
    model = XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=3, random_state=0)
    model.fit(np.array(rows), np.array(target))
    seen, out = list(v), []
    for day in future:
        p = max(0.0, float(model.predict(np.array([feature_row(seen, day.weekday())]))[0]))
        out.append(p)
        seen.append(p)  # later steps rely on earlier predictions, never on actual future values
    return np.array(out)


def ridge_forecast(hist, future):
    """Regularized linear regression on the XGBoost lag features, with an indicator for each weekday."""
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    v = hist.to_numpy(dtype=float)
    fill = float(np.nanmean(v))

    def row(values, weekday):  # a linear model cannot take missing values, so they become the history mean
        lags = [fill if np.isnan(x) else x for x in feature_row(values, weekday)[:4]]
        return lags + [float(weekday == d) for d in range(5)]

    weekdays = hist.index.dayofweek
    rows, target = [], []
    for i in range(20, len(v)):
        if not np.isnan(v[i]):
            rows.append(row(v[:i], weekdays[i]))
            target.append(v[i])
    if len(rows) < 10:
        return mean_20_days(hist, future)
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(np.array(rows), np.array(target))
    seen, out = list(v), []
    for day in future:
        p = max(0.0, float(model.predict(np.array([row(seen, day.weekday())]))[0]))
        out.append(p)
        seen.append(p)
    return np.array(out)


def quantile_p90_forecast(hist, future):
    """Direct 90th percentile forecast: for each step ahead, the demand level 90% of days stay at or below.

    Trained on every past origin and step ahead (1 to 20 weekdays), using only what was known at that origin:
    the last recorded value and the mean of the last 5 and 20 weekdays, plus the step and the target weekday."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    v = hist.to_numpy(dtype=float)
    weekdays = hist.index.dayofweek

    def known_at(i):
        past = v[:i + 1]
        recorded = past[~np.isnan(past)]
        return [recorded[-1] if len(recorded) else np.nan, _nanmean(past[-5:]), _nanmean(past[-20:])]

    rows, target = [], []
    for t in range(19, len(v) - 1):
        state = known_at(t)
        for h in range(1, HORIZON + 1):
            if t + h < len(v) and not np.isnan(v[t + h]):
                rows.append([h, weekdays[t + h], *state])
                target.append(v[t + h])
    if len(rows) < 50:
        return np.full(len(future), np.nanpercentile(v, 90))
    model = HistGradientBoostingRegressor(loss='quantile', quantile=0.9, max_iter=200, learning_rate=0.05,
                                          max_depth=3, random_state=0)
    model.fit(np.array(rows), np.array(target))
    state = known_at(len(v) - 1)
    return np.clip(model.predict(np.array([[h, d.weekday(), *state] for h, d in enumerate(future, 1)])), 0, None)


FORECASTERS = {
    'SameWeekdayLastWeek': same_weekday_last_week,
    'Mean20Days': mean_20_days,
    'Prophet': prophet_forecast,
    'ARIMA': arima_forecast,
    'XGBoost': xgboost_forecast,
    'Ridge': ridge_forecast,
    'QuantileP90': quantile_p90_forecast,
}


def forecast_at(series, pos, names):
    """Forecasts made at series position `pos`, using history up to and including it."""
    hist = series.iloc[:pos + 1]
    future = next_weekdays(hist.index[-1].date(), HORIZON)
    return future, {name: FORECASTERS[name](hist, future) for name in names}


def origin_positions(series):
    return [i for i, d in enumerate(series.index)
            if d.weekday() == 4 and i >= MIN_TRAIN_WEEKS * 5 - 1 and i + HORIZON <= len(series) - 1]


def backtest(series):
    rows = []
    for pos in origin_positions(series):
        future, preds = forecast_at(series, pos, MODELS)
        actual = series.iloc[pos + 1:pos + 1 + HORIZON].to_numpy()
        for name, values in preds.items():
            for day, f, a in zip(future, values, actual):
                rows.append(dict(origin=series.index[pos].date(), date=day, model=name,
                                 forecast=float(f), actual=a))
    return pd.DataFrame(rows)


def score(bt):
    known = bt.dropna(subset=['actual'])
    rows = []
    for name, g in known.groupby('model'):
        totals = g.groupby('origin').agg(f=('forecast', 'sum'), a=('actual', 'sum'))
        rows.append(dict(
            model=name, origins=g['origin'].nunique(), scored_days=len(g),
            WAPE=(g['forecast'] - g['actual']).abs().sum() / g['actual'].sum(),
            Bias=(g['forecast'] - g['actual']).sum() / g['actual'].sum(),
            Total_4w_abs_pct_error=((totals['f'] - totals['a']).abs() / totals['a']).mean()))
    return pd.DataFrame(rows).sort_values('WAPE').reset_index(drop=True)


def band_ratios(bt_model, origins):
    g = bt_model[bt_model['origin'].isin(origins)].dropna(subset=['actual'])
    g = g[g['forecast'] > 0]
    ratio = g['actual'] / g['forecast']
    return ratio.quantile(LOW_Q), ratio.quantile(HIGH_Q)


def size_headcount(demand, config):
    """Smallest tested headcount that reaches the on time target on this demand."""
    for workers in sorted(config['scheduled_workers']):
        summary, _ = simulate(demand, workers, 0, RATE, SERVICE_DAYS, config)
        share = summary['on_time_unit_share']
        if share is None or share >= config['target_on_time_unit_share']:
            return workers
    return max(config['scheduled_workers'])


def forecast_error_cost(bt, config, costs):
    rows = []
    daily_cost = config['paid_hours'] * costs['regular_hourly_cost']
    for origin, g in bt.groupby('origin'):
        known = g.dropna(subset=['actual'])
        if known['date'].nunique() < 10:
            continue
        actual = {d: int(a) for d, a in known.drop_duplicates('date')[['date', 'actual']].values}
        oracle = size_headcount(actual, config)
        for name, m in known.groupby('model'):
            for buffer in BUFFERS:
                predicted = {d: max(0, int(round(f * buffer))) for d, f in zip(m['date'], m['forecast'])}
                workers = size_headcount(predicted, config)
                summary, _ = simulate(actual, workers, 0, RATE, SERVICE_DAYS, config)
                rows.append(dict(origin=origin, model=name, buffer=buffer, workers=workers, oracle_workers=oracle,
                                 on_time_share=summary['on_time_unit_share'],
                                 met_target=summary['on_time_unit_share'] >= config['target_on_time_unit_share'],
                                 labor_cost_vs_oracle=(workers - oracle) * daily_cost * HORIZON))
    detail = pd.DataFrame(rows)
    summary = []
    for (name, buffer), g in detail.groupby(['model', 'buffer']):
        over, under = g[g['workers'] > g['oracle_workers']], g[g['workers'] < g['oracle_workers']]
        summary.append(dict(
            model=name, buffer=buffer, origins=len(g), mean_workers_minus_oracle=(g['workers'] - g['oracle_workers']).mean(),
            share_overstaffed=len(over) / len(g), share_understaffed=len(under) / len(g),
            mean_extra_labor_cost_when_overstaffed=over['labor_cost_vs_oracle'].mean() if len(over) else 0.0,
            mean_on_time_share=g['on_time_share'].mean(), share_missing_target=1 - g['met_target'].mean()))
    return detail, pd.DataFrame(summary)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    warnings.filterwarnings('ignore')
    config = json.loads((ROOT / 'config/footwear_scenarios.json').read_text())
    costs = json.loads((ROOT / 'config/staffing_cost_scenarios.json').read_text())
    units = load_daily()
    series = weekday_grid(units)
    weekend_units = sum(v for d, v in units.items() if d.weekday() >= 5)

    bt = backtest(series)
    scores = score(bt)
    best = scores.loc[scores['model'] != P90_MODEL, 'model'].iloc[0]
    p90 = bt[bt['model'] == P90_MODEL].dropna(subset=['actual'])
    p90_coverage = float((p90['actual'] <= p90['forecast']).mean())

    best_bt = bt[bt['model'] == best]
    origins = sorted(best_bt['origin'].unique())
    split = int(len(origins) * CALIBRATION_SHARE)
    low, high = band_ratios(best_bt, origins[:split])
    test = best_bt[best_bt['origin'].isin(origins[split:])].dropna(subset=['actual'])
    coverage = ((test['actual'] >= test['forecast'] * low) & (test['actual'] <= test['forecast'] * high)).mean()

    # latest forecast with the band calibrated on every origin
    low_all, high_all = band_ratios(best_bt, origins)
    future = next_weekdays(series.index[-1].date(), HORIZON)
    latest_values = FORECASTERS[best](series, future)
    latest = pd.DataFrame({'date': future, 'forecast': latest_values,
                           'low': latest_values * low_all, 'high': latest_values * high_all,
                           'p90': FORECASTERS[P90_MODEL](series, future)})

    detail, cost_summary = forecast_error_cost(bt, config, costs)

    bt.to_csv(OUT / 'backtest_forecasts.csv', index=False)
    scores.to_csv(OUT / 'model_scores.csv', index=False)
    detail.to_csv(OUT / 'forecast_error_cost_by_origin.csv', index=False)
    cost_summary.to_csv(OUT / 'forecast_error_cost_summary.csv', index=False)
    latest.to_csv(OUT / 'latest_forecast.csv', index=False)
    summary = dict(
        data=dict(recorded_weekdays=int(series.notna().sum()), weekdays_in_range=len(series),
                  first_date=str(series.index[0].date()), last_date=str(series.index[-1].date()),
                  units=int(series.sum()), weekend_units_excluded=int(weekend_units)),
        backtest=dict(origins=len(origins), horizon_weekdays=HORIZON, min_train_weeks=MIN_TRAIN_WEEKS),
        best_model_by_wape=best,
        p90=dict(share_of_days_at_or_below=round(p90_coverage, 3), target=0.9),
        band=dict(low_ratio=round(float(low), 3), high_ratio=round(float(high), 3),
                  nominal_coverage=HIGH_Q - LOW_Q, holdout_coverage=round(float(coverage), 3),
                  calibration_origins=split, holdout_origins=len(origins) - split),
        evidence_status='forecast of observed 2023 demand; headcount costs use hypothetical scenario inputs')
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')

    pd.set_option('display.width', 200)
    print(json.dumps(summary, indent=2))
    print('\nModel scores (lower WAPE is better):\n', scores.round(3).to_string(index=False))
    print('\nCost of forecast error, headcount sized on each forecast:\n', cost_summary.round(3).to_string(index=False))


if __name__ == '__main__':
    main()
