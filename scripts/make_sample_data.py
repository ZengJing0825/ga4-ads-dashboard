#!/usr/bin/env python3
"""Generate dashboard/data.sample.json: SYNTHETIC demo data.

Everything here is invented with a fixed random seed. No number describes a
real property, account, campaign or product. The generator exists so the
sample stays in sync with the data shape produced by fetch_ga4.py /
fetch_google_ads.py and with the landing-type story the docs describe:

  usecase_page   CPA ~ $7-9,  CTR ~ 4.5%   (aggregated scenario pages)
  single_page    CPA in between, unstable  (single content pages)
  pmax           CPA ~ $19-21, CTR ~ 1.8-2.0%

Usage:
  python3 scripts/make_sample_data.py            # rewrites dashboard/data.sample.json
  python3 scripts/make_sample_data.py --out /tmp/x.json
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_ga4 import (  # noqa: E402
    CLONE_EVENTS,
    CONSUMER_FUNNEL_EVENTS,
    CREATOR_FUNNEL_EVENTS,
    SUBSCRIPTION_EVENTS,
    build_funnel_summary,
    classify_channel,
)
from fetch_google_ads import fetch_campaign_summary, fetch_daily_totals  # noqa: E402
from kpi import cpa, cvr  # noqa: E402
from taxonomy import Taxonomy, summarize_by  # noqa: E402

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT_DIR, "dashboard", "data.sample.json")

SEED = 20260912
DAYS = 30
END_DATE = datetime(2026, 9, 12)
GENERATED_AT = "2026-09-12 09:00:00"

# name, daily budget, cpc, ctr %, click->conversion rate, cvr noise (sd), active day range, status
# Names follow <network>-<landing>-<use_case>-<geo>; config/campaign_taxonomy.yaml parses them.
CAMPAIGNS = [
    ("search-usecase-trading-us",        60, 1.10, 4.6, 0.145, 0.10, (0, 30), "ENABLED"),
    ("search-usecase-quant-us",          40, 1.15, 4.4, 0.130, 0.10, (0, 30), "ENABLED"),
    ("search-usecase-research-global",   35, 1.05, 4.5, 0.135, 0.12, (0, 30), "ENABLED"),
    ("search-single-trading-us",         65, 1.20, 3.0, 0.085, 0.45, (0, 30), "ENABLED"),
    ("search-single-research-global",    50, 1.25, 2.7, 0.075, 0.50, (0, 24), "PAUSED"),
    ("pmax-all-us",                     400, 0.80, 1.9, 0.040, 0.08, (0, 30), "ENABLED"),
    ("search-home-brand-us",             75, 1.30, 3.3, 0.090, 0.15, (0, 20), "PAUSED"),
    ("search-skill-quant-global",        50, 1.20, 3.6, 0.100, 0.15, (0, 20), "PAUSED"),
]

# creator funnel shape after homepage_view (step conversion of the previous step)
CREATOR_SHAPE = [
    ("login_click", 0.45), ("login_success", 0.85), ("docs_click", 0.70),
    ("install_copy", 0.65), ("settings_view", 0.75), ("signup", 0.55),
]
POST_SIGNUP = [("feature_use", 0.50), ("content_publish", 0.45), ("ask_send", 0.60)]

CHANNEL_SOURCES = {
    "paid": [("google / cpc", 1.0)],
    "organic": [("google / organic", 0.8), ("bing / organic", 0.2)],
    "direct": [("(direct) / (none)", 1.0)],
    "referral": [("github.com / referral", 0.5), ("t.co / referral", 0.3),
                 ("news.ycombinator.com / referral", 0.2)],
}
# homepage_view users per day for non-paid channels (mean) and their login_click multiplier
ORGANIC_CHANNELS = {"organic": (420, 1.10), "direct": (260, 1.00), "referral": (90, 0.90)}

EVENT_COUNT_MULT = {"_view": 1.5, "_click": 1.3}

GEO = [("United States", 0.34), ("India", 0.12), ("United Kingdom", 0.08), ("Germany", 0.06),
       ("Canada", 0.06), ("Singapore", 0.05), ("Australia", 0.04), ("Brazil", 0.04),
       ("Netherlands", 0.03), ("Japan", 0.03)]

rng = random.Random(SEED)


def _dates():
    start = END_DATE - timedelta(days=DAYS - 1)
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(DAYS)]


def _noisy(mean, sd):
    return max(0.0, rng.gauss(mean, mean * sd))


# ---------------------------------------------------------------------------
# Google Ads
# ---------------------------------------------------------------------------

def gen_campaign_daily(dates):
    rows = []
    for i, name in enumerate(CAMPAIGNS):
        cname, budget, cpc_, ctr_, cvr_, noise, (d0, d1), status = name
        for di, date in enumerate(dates):
            if not (d0 <= di < d1):
                continue
            cost = round(budget * rng.uniform(0.85, 1.05), 2)
            clicks = max(1, int(round(cost / (cpc_ * rng.uniform(0.9, 1.1)))))
            impressions = int(round(clicks / (ctr_ / 100 * rng.uniform(0.92, 1.08))))
            conversions = round(clicks * _noisy(cvr_, noise), 1)
            rows.append({
                "date": date,
                "campaign_name": cname,
                "campaign_id": "c-%03d" % (i + 1),
                "status": status,
                "impressions": impressions,
                "clicks": clicks,
                "cost": cost,
                "ctr": round(clicks / impressions * 100, 2),
                "avg_cpc": round(cost / clicks, 2),
                "conversions": conversions,
                "conversions_value": round(conversions * 38.0, 2),
            })
    return rows


def gen_ads(dates):
    campaign_daily = gen_campaign_daily(dates)
    Taxonomy.load().tag_rows(campaign_daily)
    daily_totals = fetch_daily_totals(campaign_daily)
    campaign_summary = fetch_campaign_summary(campaign_daily)
    total_cost = round(sum(d["cost"] for d in daily_totals), 2)
    total_clicks = sum(d["clicks"] for d in daily_totals)
    total_impr = sum(d["impressions"] for d in daily_totals)
    total_conv = round(sum(d["conversions"] for d in daily_totals), 1)
    for d in daily_totals:
        d["cost"] = round(d["cost"], 2)
        d["conversions"] = round(d["conversions"], 1)
    return {
        "fetched_at": GENERATED_AT,
        "customer_id": "synthetic-demo-customer",
        "date_range": {"days": DAYS},
        "kpi": {
            "total_cost": total_cost,
            "total_clicks": total_clicks,
            "total_impressions": total_impr,
            "total_conversions": total_conv,
            "avg_cpc": round(total_cost / total_clicks, 2),
            "avg_ctr": round(total_clicks / total_impr * 100, 2),
            "cpa": cpa(total_cost, total_conv),
            "cvr": cvr(total_conv, total_clicks),
        },
        "daily_totals": daily_totals,
        "campaign_daily": campaign_daily,
        "campaign_summary": campaign_summary,
        "by_landing_type": summarize_by(campaign_daily, "landing_type"),
        "by_use_case": summarize_by(campaign_daily, "use_case"),
    }


# ---------------------------------------------------------------------------
# GA4
# ---------------------------------------------------------------------------

def _paid_day(clicks, conversions, lag):
    """Creator-funnel users for the paid channel on one day.

    Anchored at both ends: homepage_view follows ad clicks, signup follows
    the conversions Google Ads reported (GA4 sees slightly fewer), and the
    steps in between are interpolated geometrically along CREATOR_SHAPE.
    """
    users = {}
    home = int(round(clicks * 0.88 * lag))
    signup = int(round(conversions * rng.uniform(0.93, 1.0) * lag))
    users["ad_click"] = int(round(clicks * 0.9 * lag))
    users["homepage_view"] = home
    predicted = home
    for _, r in CREATOR_SHAPE:
        predicted *= r
    factor = (signup / predicted) ** (1.0 / len(CREATOR_SHAPE)) if predicted > 0 and signup > 0 else 1.0
    cur = home
    for ev, r in CREATOR_SHAPE:
        cur = cur * r * factor
        users[ev] = int(round(cur))
    users["signup"] = signup
    return users


def _organic_day(mean, login_mult):
    users = {"ad_click": 0, "homepage_view": int(round(_noisy(mean, 0.12)))}
    cur = users["homepage_view"]
    for ev, r in CREATOR_SHAPE:
        r2 = r * (login_mult if ev == "login_click" else 1.0)
        cur = cur * r2 * rng.uniform(0.92, 1.08)
        users[ev] = int(round(cur))
    return users


def _extend_funnels(u):
    """Fill the remaining creator / consumer / clone / subscription events."""
    cur = u["signup"]
    for ev, r in POST_SIGNUP:
        cur = cur * r * rng.uniform(0.9, 1.1)
        u[ev] = int(round(cur))
    lc = u["login_click"]
    u["featured_click"] = int(round(lc * 0.55 * rng.uniform(0.9, 1.1)))
    u["explore_view"] = int(round(u["featured_click"] * 0.80 * rng.uniform(0.9, 1.1)))
    u["explore_item_click"] = int(round(u["explore_view"] * 0.60 * rng.uniform(0.9, 1.1)))
    u["feature_view"] = int(round(u["explore_item_click"] * 1.60 * rng.uniform(0.9, 1.1)))
    u["item_favorite"] = int(round(u["feature_view"] * 0.15 * rng.uniform(0.9, 1.1)))
    u["item_share"] = int(round(u["item_favorite"] * 0.40 * rng.uniform(0.9, 1.1)))
    u["clone_click"] = int(round(u["feature_view"] * 0.12 * rng.uniform(0.9, 1.1)))
    u["clone_copy"] = int(round(u["clone_click"] * 0.70 * rng.uniform(0.9, 1.1)))
    u["clone_publish"] = int(round(u["clone_copy"] * 0.35 * rng.uniform(0.9, 1.1)))
    u["upgrade_click"] = int(round(u["signup"] * 0.25 * rng.uniform(0.9, 1.1)))
    u["upgrade_plan_click"] = int(round(u["upgrade_click"] * 0.60 * rng.uniform(0.9, 1.1)))
    u["upgrade_success"] = int(round(u["upgrade_plan_click"] * 0.30 * rng.uniform(0.9, 1.1)))
    return u


def _event_count(ev, users):
    mult = 1.1
    for suffix, m in EVENT_COUNT_MULT.items():
        if ev.endswith(suffix):
            mult = m
    return int(round(users * mult * rng.uniform(0.95, 1.05)))


def _split(total, shares):
    """Split an integer across (label, share) pairs, remainder to the first."""
    out, used = [], 0
    for label, share in shares[1:]:
        v = int(round(total * share))
        out.append((label, v))
        used += v
    return [(shares[0][0], max(0, total - used))] + out


def gen_ga4(dates, campaign_daily):
    all_events = sorted(set(CREATOR_FUNNEL_EVENTS + CONSUMER_FUNNEL_EVENTS + CLONE_EVENTS + SUBSCRIPTION_EVENTS))
    daily_events, event_by_source, traffic_sources, overall = [], [], [], []
    period_users = {ev: 0 for ev in all_events}
    period_counts = {ev: 0 for ev in all_events}

    for di, date in enumerate(dates):
        # GA4 processing lag: the most recent day is still filling in
        lag = 0.6 if di == DAYS - 1 else (0.9 if di == DAYS - 2 else 1.0)
        day_rows = [r for r in campaign_daily if r["date"] == date]
        clicks = sum(r["clicks"] for r in day_rows)
        conv = sum(r["conversions"] for r in day_rows)

        per_channel = {"paid": _extend_funnels(_paid_day(clicks, conv, lag))}
        for ch, (mean, mult) in ORGANIC_CHANNELS.items():
            per_channel[ch] = _extend_funnels(_organic_day(mean, mult))
        # a few UTM'd shared links fire ad_click from referral traffic
        per_channel["referral"]["ad_click"] = int(round(per_channel["referral"]["homepage_view"] * 0.1))

        day_total_events = 0
        for ev in all_events:
            users = sum(per_channel[ch][ev] for ch in per_channel)
            count = _event_count(ev, users)
            daily_events.append({"date": date, "event_name": ev, "event_count": count, "users": users})
            period_users[ev] += users
            period_counts[ev] += count
            day_total_events += count
            for ch, u in per_channel.items():
                if u[ev] <= 0:
                    continue
                ch_count = int(round(count * u[ev] / users)) if users else 0
                for sm, part in _split(u[ev], CHANNEL_SOURCES[ch]):
                    if part <= 0:
                        continue
                    event_by_source.append({
                        "date": date, "event_name": ev, "source_medium": sm,
                        "channel": classify_channel(sm),
                        "event_count": int(round(ch_count * part / u[ev])), "users": part,
                    })

        # traffic sources: paid rows per campaign, others per source/medium
        for r in day_rows:
            sessions = int(round(r["clicks"] * 0.9 * lag * rng.uniform(0.95, 1.05)))
            active = int(round(sessions * 0.85))
            traffic_sources.append({
                "date": date, "source_medium": "google / cpc", "campaign": r["campaign_name"],
                "sessions": sessions, "active_users": active, "new_users": int(round(active * 0.55)),
            })
        for ch in ORGANIC_CHANNELS:
            for sm, part in _split(per_channel[ch]["homepage_view"], CHANNEL_SOURCES[ch]):
                active = int(round(part * 1.1))
                traffic_sources.append({
                    "date": date, "source_medium": sm, "campaign": "(not set)",
                    "sessions": int(round(active * 1.25)), "active_users": active,
                    "new_users": int(round(active * 0.45)),
                })

        active_total = int(round(sum(per_channel[ch]["homepage_view"] for ch in per_channel) * 1.15))
        overall.append({
            "date": date,
            "active_users": active_total,
            "new_users": int(round(active_total * rng.uniform(0.45, 0.55))),
            "sessions": int(round(active_total * 1.35)),
            "total_events": int(round(day_total_events * 1.6)),
        })

    period_uv = [{"event_name": ev, "event_count": period_counts[ev],
                  "users": int(round(period_users[ev] * 0.82))} for ev in all_events]

    total_active = sum(o["active_users"] for o in overall)
    geo = []
    for country, share in GEO:
        active = int(round(total_active * 0.82 * share))
        geo.append({"country": country, "active_users": active,
                    "new_users": int(round(active * 0.5)), "sessions": int(round(active * 1.35))})

    return {
        "fetched_at": GENERATED_AT,
        "property_id": "synthetic-demo-property",
        "date_range": {"days": DAYS},
        "daily_events": daily_events,
        "overall_metrics": overall,
        "traffic_sources": traffic_sources,
        "event_by_source": event_by_source,
        "period_uv": period_uv,
        "geo": geo,
        "funnels": {
            "creator": build_funnel_summary(daily_events, CREATOR_FUNNEL_EVENTS, "Creator Funnel"),
            "consumer": build_funnel_summary(daily_events, CONSUMER_FUNNEL_EVENTS, "Consumer Funnel"),
            "clone": build_funnel_summary(daily_events, CLONE_EVENTS, "Clone Funnel"),
            "subscription": build_funnel_summary(daily_events, SUBSCRIPTION_EVENTS, "Subscription Funnel"),
        },
    }


def build():
    dates = _dates()
    ads = gen_ads(dates)
    ga4 = gen_ga4(dates, ads["campaign_daily"])
    return {
        "synthetic": True,
        "_note": ("SYNTHETIC DEMO DATA. All numbers are generated by scripts/make_sample_data.py "
                  "with a fixed seed and do not describe any real property, account or product."),
        "generated_at": GENERATED_AT,
        "date_range_days": DAYS,
        "data_sources": {
            "ga4": {
                "name": "Google Analytics 4", "property_id": "synthetic-demo-property",
                "api": "GA4 Data API (v1beta)", "api_version": "v1beta",
                "auth": "Service Account", "auth_method": "service_account_key",
                "last_fetch": GENERATED_AT,
            },
            "google_ads": {
                "name": "Google Ads", "customer_id": "synthetic-demo-customer",
                "mcc_id": "synthetic-demo-manager", "api": "Google Ads API",
                "auth": "OAuth2 Refresh Token", "auth_method": "oauth2_refresh_token",
                "last_fetch": GENERATED_AT,
            },
        },
        "refresh_schedule": "Daily via launchd",
        "ga4": ga4,
        "ads": ads,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic dashboard sample data")
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    data = build()
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("wrote %s (%d bytes)" % (args.out, os.path.getsize(args.out)))
    from taxonomy import format_table
    print(format_table(data["ads"]["by_landing_type"], "landing_type"))
    print("blended CPA (ads): %s" % data["ads"]["kpi"]["cpa"])


if __name__ == "__main__":
    main()
