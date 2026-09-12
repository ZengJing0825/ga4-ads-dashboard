#!/usr/bin/env python3
"""Experiment log CLI: list experiments and compare them against campaign metrics.

    python3 scripts/experiments.py list
    python3 scripts/experiments.py compare [--data dashboard/data.sample.json]

`compare` joins every experiment in config/experiments.yaml to the
ads.campaign_daily rows of the campaigns it covers, restricted to the
experiment window [date, end_date], and prints cost / CTR / CVR / CPA next
to the verdict its kill / scale rules would give today.
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_loader import load_config, load_yaml  # noqa: E402
from kpi import cpa, ctr, cvr  # noqa: E402

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUSES = ("planned", "running", "killed", "scaled", "baseline")


def _date_str(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime("%Y-%m-%d")
    return None if value is None else str(value)


def load_experiments(path=None):
    """Return the experiment list with dates normalised to YYYY-MM-DD strings."""
    cfg = load_config("experiments.yaml") if path is None else load_yaml(path)
    out = []
    for exp in cfg.get("experiments") or []:
        exp = dict(exp)
        exp["date"] = _date_str(exp.get("date"))
        exp["end_date"] = _date_str(exp.get("end_date"))
        exp["campaigns"] = list(exp.get("campaigns") or [])
        out.append(exp)
    return out


def join_experiment(exp, campaign_daily):
    """Aggregate the campaign rows covered by one experiment inside its window."""
    names = set(exp["campaigns"])
    start, end = exp.get("date"), exp.get("end_date")
    agg = {"cost": 0.0, "clicks": 0, "impressions": 0, "conversions": 0.0, "days": set()}
    for row in campaign_daily:
        if row.get("campaign_name") not in names:
            continue
        d = row.get("date", "")
        if start and d < start:
            continue
        if end and d > end:
            continue
        agg["cost"] += float(row.get("cost", 0.0))
        agg["clicks"] += int(row.get("clicks", 0))
        agg["impressions"] += int(row.get("impressions", 0))
        agg["conversions"] += float(row.get("conversions", 0.0))
        agg["days"].add(d)
    result = dict(exp)
    result.update({
        "days": len(agg["days"]),
        "cost": round(agg["cost"], 2),
        "clicks": agg["clicks"],
        "impressions": agg["impressions"],
        "conversions": round(agg["conversions"], 1),
        "ctr": ctr(agg["clicks"], agg["impressions"]),
        "cvr": cvr(agg["conversions"], agg["clicks"]),
        "cpa": cpa(agg["cost"], agg["conversions"]),
    })
    result["verdict"] = evaluate_rules(result)
    return result


def evaluate_rules(joined):
    """Apply kill_rule / scale_rule to a joined experiment.

    Returns 'LEARNING' until the rule's minimum spend / conversions are met,
    then 'KILL', 'SCALE' or 'HOLD'. Only the metric named in the rule is
    compared (cpa, cvr or ctr).
    """
    kill = joined.get("kill_rule") or {}
    scale = joined.get("scale_rule") or {}

    def metric(rule):
        name = str(rule.get("metric", "cpa")).lower()
        return joined.get(name)

    if kill:
        if joined["cost"] < float(kill.get("min_spend", 0)):
            return "LEARNING"
        value = metric(kill)
        if value is None and joined["clicks"] > 0:
            return "KILL"  # spend without a single conversion
        if value is not None and "above" in kill and value > float(kill["above"]):
            return "KILL"
    if scale:
        if joined["conversions"] < float(scale.get("min_conversions", 0)):
            return "LEARNING" if not kill else "HOLD"
        value = metric(scale)
        if value is not None and "below" in scale and value < float(scale["below"]):
            return "SCALE"
    return "HOLD"


def join_all(experiments, campaign_daily):
    return [join_experiment(exp, campaign_daily) for exp in experiments]


def uncovered_campaigns(experiments, campaign_daily):
    covered = set()
    for exp in experiments:
        covered.update(exp["campaigns"])
    return sorted({r.get("campaign_name") for r in campaign_daily} - covered)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def format_list(experiments):
    lines = ["%-8s %-10s %-10s %-13s %-8s %7s  %s" % (
        "id", "date", "end", "landing_type", "status", "budget", "hypothesis")]
    lines.append("-" * 110)
    for e in experiments:
        hyp = e.get("hypothesis") or ""
        if len(hyp) > 60:
            hyp = hyp[:57] + "..."
        lines.append("%-8s %-10s %-10s %-13s %-8s %7s  %s" % (
            e["id"], e["date"] or "-", e["end_date"] or "open", e["landing_type"],
            e["status"], "$%s" % e.get("daily_budget", "-"), hyp))
    return "\n".join(lines)


def format_compare(joined):
    head = "%-8s %-13s %-8s %4s %9s %7s %7s %6s %6s %7s %8s  %s" % (
        "id", "landing_type", "status", "days", "cost", "clicks", "conv", "CTR%", "CVR%",
        "CPA", "verdict", "rules")
    lines = [head, "-" * len(head)]
    for j in joined:
        rule = "kill %s>%s@$%s / scale %s<%s@%sconv" % (
            (j.get("kill_rule") or {}).get("metric", "cpa"), (j.get("kill_rule") or {}).get("above", "-"),
            (j.get("kill_rule") or {}).get("min_spend", 0),
            (j.get("scale_rule") or {}).get("metric", "cpa"), (j.get("scale_rule") or {}).get("below", "-"),
            (j.get("scale_rule") or {}).get("min_conversions", 0))
        lines.append("%-8s %-13s %-8s %4d %9.2f %7d %7.1f %6.2f %6.2f %7s %8s  %s" % (
            j["id"], j["landing_type"], j["status"], j["days"], j["cost"], j["clicks"],
            j["conversions"], j["ctr"], j["cvr"], "-" if j["cpa"] is None else "%.2f" % j["cpa"],
            j["verdict"], rule))
    lines.append("")
    for j in joined:
        lines.append("%s  %s" % (j["id"], j.get("conclusion") or "(no conclusion yet)"))
    return "\n".join(lines)


def _default_data_path():
    real = os.path.join(ROOT_DIR, "dashboard", "data.json")
    return real if os.path.exists(real) else os.path.join(ROOT_DIR, "dashboard", "data.sample.json")


def main():
    parser = argparse.ArgumentParser(description="Experiment log")
    parser.add_argument("command", nargs="?", default="compare", choices=["list", "compare"])
    parser.add_argument("--data", default=None, help="dashboard data.json (default: data.json, else data.sample.json)")
    parser.add_argument("--experiments", default=None, help="alternative experiments.yaml")
    parser.add_argument("--json", action="store_true", help="print the joined records as JSON")
    args = parser.parse_args()

    experiments = load_experiments(args.experiments)
    if args.command == "list":
        print(format_list(experiments))
        return

    data_path = args.data or _default_data_path()
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = (data.get("ads") or {}).get("campaign_daily") or []
    joined = join_all(experiments, rows)
    if args.json:
        print(json.dumps(joined, indent=2, ensure_ascii=False))
        return
    print("data: %s" % os.path.relpath(data_path, ROOT_DIR))
    print(format_compare(joined))
    extra = uncovered_campaigns(experiments, rows)
    if extra:
        print("\ncampaigns not covered by any experiment: %s" % ", ".join(extra))


if __name__ == "__main__":
    main()
