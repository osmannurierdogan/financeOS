#!/usr/bin/env python3
"""Regenerate the "history" block of data.json from a Notion "Monthly Budget" CSV export.

Usage:
    python3 scripts/build_history.py path/to/export.csv > history.json

Then paste the "history" key's value into data.json, or merge it programmatically.
Re-run this whenever a fresh CSV export is available so the dashboard's charts
(monthly totals, category-by-category, bank totals, recurring installments)
stay in sync with the real transaction ledger instead of a stale snapshot.
"""
import csv
import json
import re
import sys
from collections import defaultdict, OrderedDict

MONTH_ORDER = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

# Boundary between "gerçekleşen" (actual) and "planlanan" (future/installment-only)
# months. Everything from this Payment Month onward is treated as planned.
CURRENT_MONTH = "July 2026"

TOP_CATEGORY_COUNT = 10


def parse_amount(s):
    if not s:
        return 0.0
    s = s.strip()
    neg = s.startswith("-")
    s = s.replace("-", "").replace("TRY", "").replace("\xa0", "").replace(",", "").strip()
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if neg else v


def month_key(label):
    try:
        name, year = label.split()
        return (int(year), MONTH_ORDER.index(name))
    except Exception:
        return (9999, 99)


def load_rows(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build(path):
    rows = load_rows(path)
    expense_rows = [r for r in rows if r.get("Income/Expense") == "Expense" and r.get("Payment Month")]

    monthly_total = defaultdict(float)
    monthly_by_group = defaultdict(lambda: defaultdict(float))
    group_total_all_time = defaultdict(float)
    bank_total_all_time = defaultdict(float)

    for r in expense_rows:
        month = r["Payment Month"]
        group = r.get("Group") or "Diğer"
        amt = parse_amount(r["Amount"])
        monthly_total[month] += amt
        monthly_by_group[month][group] += amt
        group_total_all_time[group] += amt
        bank = r.get("Bank")
        if bank:
            bank_total_all_time[bank] += amt

    months_sorted = sorted(monthly_total.keys(), key=month_key)

    monthly_expense_history = [
        {"month": m, "expense": round(monthly_total[m], 2)} for m in months_sorted
    ]

    top_categories = [g for g, _ in sorted(group_total_all_time.items(), key=lambda x: -x[1])[:TOP_CATEGORY_COUNT]]

    monthly_category_breakdown = []
    for m in months_sorted:
        cats = monthly_by_group[m]
        items = [{"group": g, "amount": round(v, 2)} for g, v in sorted(cats.items(), key=lambda x: -x[1]) if abs(v) > 0.005]
        monthly_category_breakdown.append({"month": m, "items": items})

    boundary_idx = months_sorted.index(CURRENT_MONTH) if CURRENT_MONTH in months_sorted else len(months_sorted)
    actual_months = months_sorted[:boundary_idx]
    future_months = months_sorted[boundary_idx:]

    recent_months = actual_months[-3:] if len(actual_months) >= 3 else actual_months
    recent_totals = defaultdict(float)
    for m in recent_months:
        for g, v in monthly_by_group[m].items():
            recent_totals[g] += v
    recent_category_breakdown = [
        {"group": g, "amount": round(v, 2)}
        for g, v in sorted(recent_totals.items(), key=lambda x: -x[1]) if abs(v) > 0.005
    ]

    all_time_category_breakdown = [
        {"group": g, "amount": round(v, 2)}
        for g, v in sorted(group_total_all_time.items(), key=lambda x: -x[1]) if abs(v) > 0.005
    ]

    bank_expense_totals = [
        {"bank": b, "amount": round(v, 2)}
        for b, v in sorted(bank_total_all_time.items(), key=lambda x: -x[1])
    ]

    upcoming_committed_expense = [
        {"month": m, "amount": round(monthly_total[m], 2)} for m in future_months
    ]

    # Recurring installment series that still have payments due in a future month.
    inst_rows = [r for r in expense_rows if r.get("Installments") == "Yes" and r.get("Total Installments")]
    series = defaultdict(list)
    for r in inst_rows:
        base = re.sub(r"\s+Part\s*\d+", "", r["Name"])
        base = re.sub(r"\s*-\s*\d+$", "", base).strip()
        series[base].append(r)

    major_recurring_items = []
    for base, rs in series.items():
        future_rows = [r for r in rs if r["Payment Month"] in future_months]
        total = sum(parse_amount(r["Amount"]) for r in rs)
        if future_rows and total >= 15000:
            for r in sorted(future_rows, key=lambda r: month_key(r["Payment Month"])):
                major_recurring_items.append({
                    "name": r["Name"],
                    "month": r["Payment Month"],
                    "amount": round(parse_amount(r["Amount"]), 2),
                })
    major_recurring_items.sort(key=lambda x: (month_key(x["month"]), -x["amount"]))

    return OrderedDict([
        ("monthly_expense_history", monthly_expense_history),
        ("recent_category_breakdown", recent_category_breakdown),
        ("all_time_category_breakdown", all_time_category_breakdown),
        ("bank_expense_totals", bank_expense_totals),
        ("upcoming_committed_expense", upcoming_committed_expense),
        ("major_recurring_items", major_recurring_items),
        ("top_categories", top_categories),
        ("monthly_category_breakdown", monthly_category_breakdown),
        ("current_month", CURRENT_MONTH),
    ])


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "Monthly_Budget_all.csv"
    result = build(csv_path)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
