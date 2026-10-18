"""Decide whether a model's SQL result matches the hand checked answer.

The model may name columns differently, order columns or rows differently, add extra columns, round a
little, or show a share as a percent. None of that should count as wrong. A different number, a
missing row or an extra row does.
Rules:
  * every gold column must be found in the model's result, matched by its values, not its name
  * numbers match within 0.1% or 0.005; text matches ignoring case, punctuation and underscores
  * rows are matched as a set, so row order does not matter
  * if percent_ok is set, a model value x also matches when x / 100 equals the gold value
  * a question can list alternative gold queries, for example a site id instead of a site name
"""
import itertools
import math
import numbers
import re

import pandas as pd


def _missing(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def _is_number(x):
    # numbers.Number also covers the numpy integers and floats that pandas returns
    return isinstance(x, numbers.Number) and not isinstance(x, (bool, complex)) and type(x).__name__ != 'bool_' and not _missing(x)


def _text(x):
    return re.sub(r'[^a-z0-9]+', ' ', str(x).lower()).strip()


def values_equal(gold, got, scale=1.0):
    if _missing(gold) or _missing(got):
        return _missing(gold) and _missing(got)
    if _is_number(gold) and _is_number(got):
        return math.isclose(gold, got * scale, rel_tol=1e-3, abs_tol=0.0051)
    return _text(gold) == _text(got)


def _sort_key(x):
    if _missing(x):
        return (0, 0.0, '')
    return (1, float(x), '') if _is_number(x) else (2, 0.0, _text(x))


def _column_matches(gold_col, got_col, scale):
    if len(gold_col) != len(got_col):
        return False
    return all(values_equal(g, x, scale) for g, x in zip(sorted(gold_col, key=_sort_key),
                                                         sorted(got_col, key=lambda v: _sort_key(v * scale if _is_number(v) else v))))


def _rows_match(gold_rows, got_rows, scales):
    unused = list(range(len(got_rows)))
    for gold in gold_rows:
        for i in unused:
            if all(values_equal(g, x, s) for g, x, s in zip(gold, got_rows[i], scales)):
                unused.remove(i)
                break
        else:
            return False
    return True


def frames_match(got: pd.DataFrame, gold: pd.DataFrame, percent_ok=False):
    """True when `got` contains the same answer as `gold`. Returns (matched, reason)."""
    if gold.shape[0] != got.shape[0]:
        return False, f'row count {got.shape[0]} but the answer has {gold.shape[0]}'
    if gold.shape[1] == 0:
        return True, 'no columns to compare'
    gold_cols = [list(gold[c]) for c in gold.columns]
    got_cols = [list(got[c]) for c in got.columns]
    scales = [1.0, 0.01] if percent_ok else [1.0]
    options = []
    for g in gold_cols:
        found = [(j, s) for j, c in enumerate(got_cols) for s in scales if _column_matches(g, c, s)]
        if not found:
            return False, 'a needed column of values was not found in the result'
        options.append(found)
    for choice in itertools.product(*options):
        if len({j for j, _ in choice}) < len(choice):
            continue  # two gold columns cannot share one result column
        got_rows = [tuple(got_cols[j][r] for j, _ in choice) for r in range(got.shape[0])]
        gold_rows = list(zip(*gold_cols))
        if _rows_match(gold_rows, got_rows, [s for _, s in choice]):
            return True, 'match'
    return False, 'the values are present but the rows do not line up'


# Scoring the final answer a manager reads, not just the SQL.

MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october',
          'november', 'december']
_ISO = re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b')
_LONG = re.compile(r'\b(' + '|'.join(m[:3] for m in MONTHS) + r')[a-z]*\.? (\d{1,2}),? (\d{4})\b', re.I)
_NUMBER = re.compile(r'(?<![\w.])-?\$?\d[\d,]*(?:\.\d+)?')


def _dates_in(text):
    found = {f'{y}-{m}-{d}' for y, m, d in _ISO.findall(text)}
    for month, day, year in _LONG.findall(text):
        found.add(f'{year}-{MONTHS.index(next(m for m in MONTHS if m.startswith(month.lower()[:3]))) + 1:02d}-{int(day):02d}')
    return found


def _numbers_in(text):
    text = _LONG.sub(' ', _ISO.sub(' ', text))  # a date's digits must not count as numbers
    return [float(n.replace('$', '').replace(',', '')) for n in _NUMBER.findall(text)]


def answer_mentions(answer, gold: pd.DataFrame, percent_ok=False, aliases=None):
    """True when every value in the gold answer appears in the model's final sentence.

    Text may appear as a plural, or as one of the accepted short forms in `aliases` (for example OEWS)."""
    if not answer:
        return False, 'no answer text'
    text, numbers, dates = _text(answer), _numbers_in(answer), _dates_in(answer)
    for value in gold.to_numpy().ravel():
        if _missing(value):
            continue
        if _is_number(value):
            options = [value, value * 100] if percent_ok else [value]
            if not any(math.isclose(n, v, rel_tol=5e-3, abs_tol=0.0051) for n in numbers for v in options):
                return False, f'the answer does not state {value:g}'
        elif _ISO.fullmatch(str(value)):
            if str(value) not in dates:
                return False, f'the answer does not state the date {value}'
        elif not any(re.search(rf'\b{re.escape(_text(form))}(s|es)?\b', text)
                     for form in [value, *(aliases or {}).get(str(value), [])]):
            return False, f'the answer does not name {value}'
    return True, 'match'
