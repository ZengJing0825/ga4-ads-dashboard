#!/usr/bin/env python3
"""Validate dashboard/data.json after a refresh.

Checks:
  - File exists and is valid JSON
  - File size between 1KB and 10MB
  - Required top-level keys present
  - ga4.daily_events is a non-empty array
  - ga4.overall_metrics is a non-empty array
  - generated_at timestamp is within 24 hours of now

Usage:
  python3 scripts/validate_data.py
  python3 scripts/validate_data.py --path ./dashboard/data.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

DEFAULT_PATH = "./dashboard/data.json"

REQUIRED_KEYS = ["generated_at", "date_range_days", "ga4", "ads"]


def validate(path: str) -> list[str]:
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
    if isinstance(ts_str, str):
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
    args = parser.parse_args()

    errors = validate(args.path)
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
