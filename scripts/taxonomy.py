"""Campaign taxonomy: parse landing_type / use_case out of campaign names
and aggregate Google Ads metrics by those dimensions.

Configuration lives in config/campaign_taxonomy.yaml (ordered regex maps).
Pure functions only; no Google API dependency, so this module is also used
by the tests, the sample-data generator and the CLI:

    python3 scripts/taxonomy.py --data dashboard/data.sample.json
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_loader import load_config  # noqa: E402
from kpi import cpa, ctr, cvr  # noqa: E402

DIMENSIONS = ("landing_type", "use_case")
LANDING_TYPES = ("homepage", "skill_page", "usecase_page", "single_page", "pmax")


class Taxonomy:
    """Compiled regex maps for each dimension."""

    def __init__(self, config):
        self.rules = {}
        self.defaults = dict(config.get("defaults") or {})
        for dim in DIMENSIONS:
            rules = []
            for entry in config.get(dim) or []:
                rules.append((re.compile(entry["pattern"], re.IGNORECASE), str(entry["value"])))
            self.rules[dim] = rules
            self.defaults.setdefault(dim, "unknown")

    @classmethod
    def load(cls, path=None):
        if path is None:
            return cls(load_config("campaign_taxonomy.yaml"))
        from config_loader import load_yaml
        return cls(load_yaml(path))

    def classify(self, campaign_name, dimension):
        for regex, value in self.rules.get(dimension, []):
            if regex.search(campaign_name or ""):
                return value
        return self.defaults[dimension]

    def parse(self, campaign_name):
        """Return {"landing_type": ..., "use_case": ...} for a campaign name."""
        return {dim: self.classify(campaign_name, dim) for dim in DIMENSIONS}

    def tag_rows(self, rows):
        """Add landing_type / use_case to every row in place and return rows."""
        for row in rows:
            row.update(self.parse(row.get("campaign_name", "")))
        return rows


def summarize_by(rows, dimension):
    """Aggregate tagged campaign rows by one dimension.

    Returns a list sorted by cost desc, each item carrying impressions,
    clicks, cost, conversions, ctr (%), cvr (%), cpa and campaign count.
    """
    buckets = {}
    for row in rows:
        key = row.get(dimension, "unknown")
        b = buckets.setdefault(key, {
            dimension: key, "campaigns": set(),
            "impressions": 0, "clicks": 0, "cost": 0.0, "conversions": 0.0,
        })
        b["campaigns"].add(row.get("campaign_name", ""))
        b["impressions"] += int(row.get("impressions", 0))
        b["clicks"] += int(row.get("clicks", 0))
        b["cost"] += float(row.get("cost", 0.0))
        b["conversions"] += float(row.get("conversions", 0.0))

    out = []
    for b in sorted(buckets.values(), key=lambda x: x["cost"], reverse=True):
        b["campaign_count"] = len(b["campaigns"])
        b["campaigns"] = sorted(b["campaigns"])
        b["cost"] = round(b["cost"], 2)
        b["conversions"] = round(b["conversions"], 1)
        b["ctr"] = ctr(b["clicks"], b["impressions"])
        b["cvr"] = cvr(b["conversions"], b["clicks"])
        b["cpa"] = cpa(b["cost"], b["conversions"])
        out.append(b)
    return out


def format_table(rows, dimension):
    """Render a summarize_by() result as a fixed-width text table."""
    head = "%-14s %5s %10s %8s %8s %8s %7s %7s %8s" % (
        dimension, "camps", "cost", "clicks", "impr", "conv", "CTR%", "CVR%", "CPA")
    lines = [head, "-" * len(head)]
    for b in rows:
        lines.append("%-14s %5d %10.2f %8d %8d %8.1f %7.2f %7.2f %8s" % (
            b[dimension], b["campaign_count"], b["cost"], b["clicks"], b["impressions"],
            b["conversions"], b["ctr"], b["cvr"],
            "-" if b["cpa"] is None else "%.2f" % b["cpa"]))
    return "\n".join(lines)


def _main():
    parser = argparse.ArgumentParser(description="Campaign metrics by landing_type / use_case")
    parser.add_argument("--data", default="dashboard/data.sample.json",
                        help="dashboard data.json (default: %(default)s)")
    parser.add_argument("--taxonomy", default=None, help="alternative taxonomy yaml")
    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = (data.get("ads") or {}).get("campaign_daily") or []
    tax = Taxonomy.load(args.taxonomy)
    tax.tag_rows(rows)
    for dim in DIMENSIONS:
        print(format_table(summarize_by(rows, dim), dim))
        print()


if __name__ == "__main__":
    _main()
