#!/usr/bin/env python3
"""Reconcile GA4 event counts against a first-party export.

    python3 scripts/reconcile.py --export examples/first_party_signups.csv --event signup
    python3 scripts/reconcile.py --data dashboard/data.sample.json \\
        --export examples/first_party_signups.csv --event signup --threshold 10

The export is a CSV with a date column, a count column and optionally an
event column (headers: date, count | events | n, event | event_name). Only
dates present in both sources are compared. The gap is reported per day and
in total as

    gap % = (ga4 - export) / export * 100

so a negative gap means GA4 is missing events. A total gap beyond the
threshold (default 10%) prints a WARN line and exits with status 1, which
is the signal that server-side hits are probably arriving without
client_id / session_id (see docs/tracking-plan.md).
"""

import argparse
import csv
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_THRESHOLD = 10.0

DATE_COLS = ("date", "day")
COUNT_COLS = ("count", "events", "event_count", "n", "total")
EVENT_COLS = ("event", "event_name")


def gap_pct(ga4_count, export_count):
    """(ga4 - export) / export in percent; None when the export count is 0."""
    if not export_count:
        return None
    return round((ga4_count - export_count) / export_count * 100, 2)


def ga4_daily_counts(data, event, start=None, end=None):
    """{date: event_count} for one event from dashboard data."""
    out = {}
    for row in (data.get("ga4") or {}).get("daily_events") or []:
        if row.get("event_name") != event:
            continue
        d = row.get("date", "")
        if (start and d < start) or (end and d > end):
            continue
        out[d] = out.get(d, 0) + int(row.get("event_count", 0))
    return out


def read_export(path, event=None, start=None, end=None):
    """{date: count} from a first-party CSV export."""
    out = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        cols = {c.strip().lower(): c for c in reader.fieldnames or []}
        date_col = next((cols[c] for c in DATE_COLS if c in cols), None)
        count_col = next((cols[c] for c in COUNT_COLS if c in cols), None)
        event_col = next((cols[c] for c in EVENT_COLS if c in cols), None)
        if not date_col or not count_col:
            raise ValueError("export needs a date column and a count column, got %s" % reader.fieldnames)
        for row in reader:
            if event_col and event and row[event_col].strip() != event:
                continue
            d = row[date_col].strip()[:10]
            if (start and d < start) or (end and d > end):
                continue
            out[d] = out.get(d, 0) + int(float(row[count_col] or 0))
    return out


def compare(ga4_counts, export_counts):
    """Per-day rows plus totals for the dates present in both sources."""
    dates = sorted(set(ga4_counts) & set(export_counts))
    rows = []
    for d in dates:
        g, e = ga4_counts[d], export_counts[d]
        rows.append({"date": d, "ga4": g, "export": e, "gap_pct": gap_pct(g, e)})
    total_ga4 = sum(ga4_counts[d] for d in dates)
    total_export = sum(export_counts[d] for d in dates)
    totals = {
        "days": len(dates),
        "ga4": total_ga4,
        "export": total_export,
        "gap_pct": gap_pct(total_ga4, total_export),
        "only_in_ga4": sorted(set(ga4_counts) - set(export_counts)),
        "only_in_export": sorted(set(export_counts) - set(ga4_counts)),
    }
    return rows, totals


def exceeds(totals, threshold):
    return totals["gap_pct"] is not None and abs(totals["gap_pct"]) > threshold


def format_report(event, rows, totals, threshold):
    lines = ["event: %s   days compared: %d   threshold: %.1f%%" % (event, totals["days"], threshold), ""]
    lines.append("%-10s %8s %8s %8s" % ("date", "ga4", "export", "gap%"))
    lines.append("-" * 37)
    for r in rows:
        gap = "-" if r["gap_pct"] is None else "%+.1f" % r["gap_pct"]
        flag = "  <" if r["gap_pct"] is not None and abs(r["gap_pct"]) > threshold else ""
        lines.append("%-10s %8d %8d %8s%s" % (r["date"], r["ga4"], r["export"], gap, flag))
    lines.append("-" * 37)
    gap = "-" if totals["gap_pct"] is None else "%+.1f" % totals["gap_pct"]
    lines.append("%-10s %8d %8d %8s" % ("total", totals["ga4"], totals["export"], gap))
    if totals["only_in_ga4"]:
        lines.append("dates only in GA4:    %s" % ", ".join(totals["only_in_ga4"]))
    if totals["only_in_export"]:
        lines.append("dates only in export: %s" % ", ".join(totals["only_in_export"]))
    lines.append("")
    if exceeds(totals, threshold):
        direction = "fewer" if totals["gap_pct"] < 0 else "more"
        lines.append("WARN  GA4 reports %.1f%% %s '%s' events than the export (threshold %.1f%%)."
                     % (abs(totals["gap_pct"]), direction, event, threshold))
        lines.append("      Check that server-side hits carry client_id and session_id, and that the")
        lines.append("      event fires once per action in both systems (docs/tracking-plan.md).")
    else:
        lines.append("OK    gap within threshold")
    return "\n".join(lines)


def _default_data_path():
    real = os.path.join(ROOT_DIR, "dashboard", "data.json")
    return real if os.path.exists(real) else os.path.join(ROOT_DIR, "dashboard", "data.sample.json")


def main():
    parser = argparse.ArgumentParser(description="GA4 vs first-party export reconciliation")
    parser.add_argument("--data", default=None, help="dashboard data.json (default: data.json, else data.sample.json)")
    parser.add_argument("--export", required=True, help="first-party CSV export")
    parser.add_argument("--event", default="signup", help="event name to compare (default: %(default)s)")
    parser.add_argument("--start", default=None, help="YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="YYYY-MM-DD")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help="warn when |total gap| exceeds this percent (default: %(default)s)")
    args = parser.parse_args()

    data_path = args.data or _default_data_path()
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    ga4 = ga4_daily_counts(data, args.event, args.start, args.end)
    export = read_export(args.export, args.event, args.start, args.end)
    if not ga4:
        print("no GA4 rows for event '%s' in %s" % (args.event, data_path))
        sys.exit(2)
    if not export:
        print("no export rows for event '%s' in %s" % (args.event, args.export))
        sys.exit(2)
    rows, totals = compare(ga4, export)
    print("data: %s   export: %s" % (os.path.relpath(data_path, ROOT_DIR), os.path.relpath(args.export, ROOT_DIR)))
    print(format_report(args.event, rows, totals, args.threshold))
    sys.exit(1 if exceeds(totals, args.threshold) else 0)


if __name__ == "__main__":
    main()
