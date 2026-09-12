#!/usr/bin/env python3
"""Validate dashboard/data.json after a refresh.

Checks:
  - File exists and is valid JSON
  - File size between 1KB and 10MB
  - Required top-level keys present
  - ga4.daily_events is a non-empty array
  - ga4.overall_metrics is a non-empty array
  - generated_at timestamp is within 24 hours of now (skip with --skip-freshness)
  - every event in ga4.daily_events exists in config/tracking_plan.yaml
    (unknown events produce a WARN line, not a failure)

Usage:
  python3 scripts/validate_data.py
  python3 scripts/validate_data.py --path ./dashboard/data.json
  python3 scripts/validate_data.py --path ./dashboard/data.sample.json --skip-freshness
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_yaml  # noqa: E402

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = "./dashboard/data.json"
DEFAULT_PLAN = os.path.join(ROOT_DIR, "config", "tracking_plan.yaml")

REQUIRED_KEYS = ["generated_at", "date_range_days", "ga4", "ads"]


def planned_events(plan: dict) -> set:
    """All event names declared in a tracking plan (funnels + extra_events)."""
    events = set()
    for steps in (plan.get("funnels") or {}).values():
        for step in steps or []:
            if step.get("event"):
                events.add(str(step["event"]))
    for entry in plan.get("extra_events") or []:
        if entry.get("event"):
            events.add(str(entry["event"]))
    for ev in plan.get("conversions") or []:
        events.add(str(ev))
    if plan.get("key_action"):
        events.add(str(plan["key_action"]))
    return events


def unknown_events(data: dict, plan: dict) -> list:
    """Events present in ga4.daily_events but missing from the tracking plan."""
    ga4 = data.get("ga4") or {}
    seen = {str(e.get("event_name")) for e in ga4.get("daily_events") or [] if isinstance(e, dict)}
    return sorted(seen - planned_events(plan))


def validate(path: str, check_freshness: bool = True) -> list[str]:
    """Return a list of error strings. Empty list means valid."""
    errors: list[str] = []

    # --- File existence ---
    if not os.path.isfile(path):
        return [f"File not found: {path}"]

    # --- File size ---
    size = os.path.getsize(path)
    if size < 1024:
        errors.append(f"File too small: {size} bytes (minimum 1 KB)")
    if size > 10 * 1024 * 1024:
        errors.append(f"File too large: {size} bytes (maximum 10 MB)")

    # --- Valid JSON ---
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return errors + [f"Invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return errors + ["Top-level value must be a JSON object"]

    # --- Required keys ---
    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"Missing required key: {key}")

    # --- ga4 sub-checks ---
    ga4 = data.get("ga4")
    if isinstance(ga4, dict):
        daily = ga4.get("daily_events")
        if not isinstance(daily, list) or len(daily) == 0:
            errors.append("ga4.daily_events must be a non-empty array")

        overall = ga4.get("overall_metrics")
        if not isinstance(overall, list) or len(overall) == 0:
            errors.append("ga4.overall_metrics must be a non-empty array")
    elif "ga4" in data:
        errors.append("ga4 must be a JSON object")

    # --- generated_at freshness ---
    ts_str = data.get("generated_at")
    if not check_freshness:
        pass
    elif isinstance(ts_str, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                ts = datetime.strptime(ts_str, fmt)
                if datetime.now() - ts > timedelta(hours=24):
                    errors.append(
                        f"generated_at is stale: {ts_str} (older than 24 hours)"
                    )
                break
            except ValueError:
                continue
        else:
            errors.append(f"Cannot parse generated_at timestamp: {ts_str}")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate dashboard data")
    parser.add_argument(
        "--path", default=DEFAULT_PATH, help="Path to data.json (default: %(default)s)"
    )
    parser.add_argument(
        "--tracking-plan", default=DEFAULT_PLAN,
        help="tracking plan yaml used for the unknown-event check (default: config/tracking_plan.yaml)",
    )
    parser.add_argument(
        "--skip-freshness", action="store_true",
        help="do not fail on a stale generated_at (use for the shipped sample file)",
    )
    args = parser.parse_args()

    errors = validate(args.path, check_freshness=not args.skip_freshness)

    # Tracking-plan check: warn only, never fail the refresh
    if not errors and os.path.isfile(args.tracking_plan):
        with open(args.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        unknown = unknown_events(data, load_yaml(args.tracking_plan) or {})
        for ev in unknown:
            print(f"WARN  event '{ev}' is in the data but not in {os.path.relpath(args.tracking_plan)}")
        if unknown:
            print(f"WARN  {len(unknown)} unknown event(s); add them to the tracking plan or fix the event name")

    if errors:
        print(f"FAIL  {args.path}")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        size = os.path.getsize(args.path)
        print(f"OK  {args.path} ({size} bytes)")
        sys.exit(0)


if __name__ == "__main__":
    main()
