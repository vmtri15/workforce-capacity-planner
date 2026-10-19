"""Test the demand forecasting method on 5 years of daily data.

The 2023 footwear data is too short for yearly patterns, so this runs the same rolling origin
backtest on the Kaggle "Historical Product Demand" file (4 central warehouses, 2012 to 2016) to see
whether the models beat simple baselines when there is enough history.

This is a check of the method on different data, a manufacturing product demand series, not a
forecast of the 2023 footwear operation. Unit volumes are not comparable and are not converted.
Accuracy only: no staffing cost step, because the units do not match the planner's rates.

Needs the file in data/raw/historical_product_demand/ (download it from Kaggle, it is not in the repo).
Run from the project root:
    python3 scripts/forecast_method_check.py
"""
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import forecast_demand as fd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/raw/historical_product_demand/Historical Product Demand.csv'
OUT = ROOT / 'data/processed/demand_forecast'
START, END = '2012-01-01', '2016-12-31'  # the full years; 2011 and 2017 are sparse
MIN_TRAIN = 260                           # one year of weekdays before the first origin
YEAR = pd.Timedelta(days=364)             # 52 weeks, so the same weekday


def load_series():
    raw = pd.read_csv(SOURCE, dtype=str)
    text = raw['Order_Demand'].str.strip()
    negative = text.str.startswith('(')  # values like (100) are returns or cancellations, kept as net
    raw['units'] = pd.to_numeric(text.str.replace(r'[()]', '', regex=True), errors='raise')
    raw.loc[negative, 'units'] *= -1
    raw['date'] = pd.to_datetime(raw['Date'], format='%Y/%m/%d', errors='coerce')
    raw = raw.dropna(subset=['date'])  # about 1% of rows have no date
    raw = raw[(raw['date'] >= START) & (raw['date'] <= END) & (raw['date'].dt.weekday < 5)]
    days = pd.bdate_range(START, END)
    out = {}
    for name, g in list(raw.groupby('Warehouse')) + [('All', raw)]:
        out[name] = g.groupby('date')['units'].sum().reindex(days).astype(float)  # NaN = no records
    return out


def seasonal_naive_year(hist, future):
    """Same weekday 52 weeks ago; falls back to the same weekday last week."""
    last_week = fd.same_weekday_last_week(hist, future)
    out = []
    for day, fallback in zip(future, last_week):
        value = hist.get(pd.Timestamp(day) - YEAR, np.nan)
        out.append(fallback if np.isnan(value) else value)
    return np.array(out)


def prophet_yearly(hist, future):
    from prophet import Prophet
    logging.getLogger('cmdstanpy').setLevel(logging.ERROR)
    logging.getLogger('prophet').setLevel(logging.ERROR)
    known = hist.dropna()
    model = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
    model.fit(pd.DataFrame({'ds': known.index, 'y': known.to_numpy()}))
    predicted = model.predict(pd.DataFrame({'ds': pd.to_datetime(future)}))['yhat'].to_numpy()
    return np.clip(predicted, 0, None)


def xgboost_year(hist, future):
    """XGBoost with the 2023 features plus the value one year ago and the month."""
    from xgboost import XGBRegressor
    lookup = hist.to_dict()
    v = hist.to_numpy(dtype=float)

    def row(values, day):
        return fd.feature_row(values, day.weekday()) + [lookup.get(pd.Timestamp(day) - YEAR, np.nan), day.month]

    rows, target = [], []
    for i in range(20, len(v)):
        if not np.isnan(v[i]):
            rows.append(row(v[:i], hist.index[i]))
            target.append(v[i])
    model = XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=3, random_state=0)
    model.fit(np.array(rows), np.array(target))
    seen, out = list(v), []
    for day in future:
        p = max(0.0, float(model.predict(np.array([row(seen, pd.Timestamp(day))]))[0]))
        out.append(p)
        seen.append(p)
    return np.array(out)


FORECASTERS = {
    'SameWeekdayLastWeek': fd.same_weekday_last_week,
    'Mean20Days': fd.mean_20_days,
    'SameWeekdayLastYear': seasonal_naive_year,
    'Prophet': prophet_yearly,
    'ARIMA': fd.arima_forecast,
    'XGBoost': fd.xgboost_forecast,
    'XGBoostWithYearLag': xgboost_year,
    'Ridge': fd.ridge_forecast,
}


def backtest(series, label):
    rows = []
    for pos in range(MIN_TRAIN - 1, len(series) - fd.HORIZON, fd.HORIZON):  # non overlapping 4 week windows
        hist = series.iloc[:pos + 1]
        future = fd.next_weekdays(hist.index[-1].date(), fd.HORIZON)
        actual = series.iloc[pos + 1:pos + 1 + fd.HORIZON].to_numpy()
        for name, fn in FORECASTERS.items():
            for day, f, a in zip(future, fn(hist, future), actual):
                rows.append(dict(series=label, origin=hist.index[-1].date(), date=day, model=name,
                                 forecast=float(f), actual=a))
    return pd.DataFrame(rows)


def main():
    warnings.filterwarnings('ignore')
    OUT.mkdir(parents=True, exist_ok=True)
    data = load_series()
    scores = []
    for label, series in data.items():
        print(f'{label}: {int(series.notna().sum())} of {len(series)} weekdays recorded', flush=True)
        s = fd.score(backtest(series, label))
        s.insert(0, 'series', label)
        scores.append(s)
    scores = pd.concat(scores)
    scores.to_csv(OUT / 'method_check_product_demand_scores.csv', index=False)
    pd.set_option('display.width', 200)
    wape = scores.pivot(index='model', columns='series', values='WAPE')
    wape['Mean'] = wape.mean(axis=1)
    print('\nDaily WAPE by series (lower is better):\n', wape.sort_values('Mean').round(3).to_string())
    bias = scores.pivot(index='model', columns='series', values='Bias')
    print('\nBias (forecast minus actual, share of demand):\n', bias.round(3).to_string())
    total = scores.pivot(index='model', columns='series', values='Total_4w_abs_pct_error')
    print('\nError on the 4 week total:\n', total.sort_values('All').round(3).to_string())


if __name__ == '__main__':
    main()
