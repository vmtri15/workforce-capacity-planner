"""Reproducible candidate-outbound audit; never overwrites the legacy profile.

Stock-code shape is a transparent screening assumption, not product master data.
No customer identifiers are exported.
"""
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import argparse
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/uci/online_retail_II.xlsx"
OUT = ROOT / "data/processed"
PRODUCT_CODES = set("DCGS0003 DCGS0004 DCGS0037 DCGS0041 DCGS0044 DCGS0058 DCGS0062 DCGS0066N DCGS0068 DCGS0069 DCGS0070 DCGS0072 DCGS0075 DCGS0076 DCGSSBOY DCGSSGIRL PADS SP1002".split())
SERVICE_CODES = set("ADJUST ADJUST2 AMAZONFEE B C2 D DOT M POST TEST001 TEST002".split()) | {"BANK CHARGES"}


def classify(invoice, code, description, quantity, reviewed=False):
    if invoice is None or not str(invoice).strip():
        return "missing_invoice"
    if str(invoice).upper().startswith("C"):
        return "cancellation"
    if quantity is None or quantity <= 0:
        return "nonpositive_quantity"
    normalized = str(code).strip().upper()
    if reviewed:
        if normalized in SERVICE_CODES:
            return "nonmerchandise_excluded"
        if normalized.startswith("GIFT_") or normalized == "S":
            return "fulfillment_mode_review"
        if description is None or not str(description).strip():
            return "missing_description_review"
        if str(description).strip().lower() in {"update", "check", "found", "adjustment", "damaged"}:
            return "administrative_description_review"
        if normalized in PRODUCT_CODES:
            return "candidate_outbound"
    if not re.fullmatch(r"\d{5}[A-Za-z]*", str(code).strip()):
        return "nonstandard_code_review"
    if description is None or not str(description).strip():
        return "missing_description_review"
    return "candidate_outbound"


def describe(values):
    values = sorted(values)
    if not values:
        return {"count": 0}
    return {"count": len(values), "mean": sum(values)/len(values),
            **{f"p{p}": values[max(0, math.ceil(len(values)*p/100)-1)]
               for p in (50, 90, 95, 99, 100)}}


def write_csv(name, rows):
    if not rows:
        return
    with (OUT/name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reviewed', action='store_true', help='Apply reviewed code decisions and write separate v2 outputs')
    args = parser.parse_args()
    prefix = 'reviewed_' if args.reviewed else ''
    OUT.mkdir(parents=True, exist_ok=True)
    workbook = load_workbook(SOURCE, read_only=True, data_only=True)
    daily = defaultdict(lambda: {"invoices": set(), "positive_invoices": set(),
        "source_lines": 0, "positive_lines": 0, "positive_units": 0})
    orders = defaultdict(lambda: {"lines": 0, "units": 0})
    reasons = Counter()
    review = Counter()
    dates_by_invoice = defaultdict(set)
    skipped = Counter()
    for sheet_index, ws in enumerate(workbook.worksheets):
        iterator = ws.iter_rows(values_only=True)
        columns = {name: i for i, name in enumerate(next(iterator))}
        for row in iterator:
            timestamp = row[columns["InvoiceDate"]]
            if timestamp is None:
                skipped["missing_date"] += 1
                continue
            day = timestamp.date().isoformat()
            if sheet_index == 1 and day <= "2010-12-09":
                skipped["second_sheet_overlap"] += 1
                continue
            invoice, code, description, quantity = [row[columns[k]] for k in
                ("Invoice", "StockCode", "Description", "Quantity")]
            d = daily[day]
            d["source_lines"] += 1
            d["invoices"].add(str(invoice))
            if quantity is not None and quantity > 0:
                d["positive_lines"] += 1
                d["positive_units"] += quantity
                d["positive_invoices"].add(str(invoice))
            reason = classify(invoice, code, description, quantity, args.reviewed)
            reasons[reason] += 1
            if reason == "candidate_outbound":
                order = orders[(day, str(invoice))]
                order["lines"] += 1
                order["units"] += quantity
                dates_by_invoice[str(invoice)].add(day)
            elif reason.endswith("review"):
                review[(reason, str(code), str(description))] += 1
        print(f"Read {ws.title}", flush=True)
    workbook.close()
    by_date = defaultdict(list)
    for (day, invoice), order in orders.items():
        by_date[day].append(order)
    rows = []
    for day, d in sorted(daily.items()):
        values = by_date[day]
        rows.append({"source_date": day, "legacy_invoice_count": len(d["invoices"]),
            "positive_quantity_invoice_count": len(d["positive_invoices"]),
            "candidate_outbound_orders": len(values),
            "candidate_lines": sum(v["lines"] for v in values),
            "candidate_units": sum(v["units"] for v in values),
            "legacy_positive_lines": d["positive_lines"],
            "legacy_positive_units": d["positive_units"]})
    # Reconcile against the existing source-derived profile before exporting.
    with (OUT/"uci_daily_workload_profile.csv").open() as f:
        legacy = {r["planning_date"]: r for r in csv.DictReader(f)}
    assert set(legacy) == set(daily), "Date reconciliation failed"
    for day, d in daily.items():
        for actual, key in ((d["source_lines"], "source_lines"),
                            (len(d["invoices"]), "distinct_invoice_ids"),
                            (d["positive_lines"], "positive_quantity_lines"),
                            (d["positive_units"], "positive_units")):
            assert actual == float(legacy[day][key]), (day, key, actual, legacy[day][key])
    assert sum(reasons.values()) == sum(d["source_lines"] for d in daily.values())
    def summary(start="0000", end="9999"):
        selected = [r for r in rows if start <= r["source_date"] <= end]
        chosen = [v for (day, _), v in orders.items() if start <= day <= end]
        totals = {key: sum(r[key] for r in selected) for key in rows[0] if key != "source_date"}
        return {"totals": totals, "units_per_order": describe([v["units"] for v in chosen]),
                "lines_per_order": describe([v["lines"] for v in chosen]),
                "orders_over_100_units": sum(v["units"] > 100 for v in chosen),
                "units_in_orders_over_100": sum(v["units"] for v in chosen if v["units"] > 100)}
    result = {"source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "rule": "Non-C invoice, positive quantity, five-digit stock code with optional letters, nonempty description; candidate physical demand only",
        "reviewed_code_overrides": args.reviewed,
        "classification_counts": dict(reasons), "skipped": dict(skipped),
        "invoices_spanning_dates": sum(len(days)>1 for days in dates_by_invoice.values()),
        "full_history": summary(), "planning_window": summary("2011-10-14", "2011-12-08"),
        "checks": {"legacy_daily_reconciliation": "PASS", "classification_reconciliation": "PASS"}}
    if args.reviewed:
        # Aggregate by date and order size; no invoice/customer identifiers exported.
        mix = Counter((day, v['lines'], v['units']) for (day, _), v in orders.items())
        write_csv('reviewed_order_mix.csv', [dict(source_date=k[0], lines=k[1], units=k[2], orders=n)
            for k, n in sorted(mix.items())])
    write_csv(prefix+"outbound_daily_audit.csv", rows)
    write_csv(prefix+"outbound_code_review.csv", [dict(reason=k[0], code=k[1], description=k[2], rows=n)
        for k, n in review.most_common()])
    (OUT/(prefix+"outbound_audit.json")).write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
