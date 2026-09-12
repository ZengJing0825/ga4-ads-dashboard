"""
Google Ads data fetcher.
Pulls daily campaign-level spend, clicks, impressions and conversions,
tags every campaign with landing_type / use_case parsed from its name
(config/campaign_taxonomy.yaml), then aggregates daily totals, per-campaign
summaries and per-dimension summaries.
Writes everything to <OUTPUT_DIR>/google_ads_data.json.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

from google.ads.googleads.client import GoogleAdsClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from taxonomy import Taxonomy, summarize_by  # noqa: E402
from kpi import cpa, cvr  # noqa: E402


def report_tz() -> timezone:
    """Timezone used to compute the date window.

    Set REPORT_TZ_OFFSET_HOURS in .env to match your Google Ads account
    timezone (e.g. -7 for a UTC-7 account). Defaults to -7.
    """
    return timezone(timedelta(hours=float(os.environ.get("REPORT_TZ_OFFSET_HOURS", "-7"))))


def get_client() -> GoogleAdsClient:
    """Create the Google Ads API client from environment variables."""
    config = {
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        "login_customer_id": os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""),
        "use_proto_plus": True,
    }
    # Drop empty values (e.g. no manager account)
    config = {k: v for k, v in config.items() if v}
    return GoogleAdsClient.load_from_dict(config)


def fetch_campaign_daily(client: GoogleAdsClient, customer_id: str, days: int = 30) -> list[dict]:
    """
    Daily campaign-level metrics.
    Returns: [{"date": "2026-04-01", "campaign_name": "...", "impressions": 100, ...}, ...]
    """
    ga_service = client.get_service("GoogleAdsService")
    now = datetime.now(report_tz())
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    query = f"""
        SELECT
            segments.date,
            campaign.name,
            campaign.id,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.ctr,
            metrics.average_cpc,
            metrics.conversions,
            metrics.conversions_value
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND campaign.status != 'REMOVED'
        ORDER BY segments.date
    """

    response = ga_service.search(customer_id=customer_id, query=query)
    results = []
    for row in response:
        results.append({
            "date": row.segments.date,
            "campaign_name": row.campaign.name,
            "campaign_id": str(row.campaign.id),
            "status": row.campaign.status.name,
            "impressions": row.metrics.impressions,
            "clicks": row.metrics.clicks,
            "cost": round(row.metrics.cost_micros / 1_000_000, 2),
            "ctr": round(row.metrics.ctr * 100, 2),
            "avg_cpc": round(row.metrics.average_cpc / 1_000_000, 2),
            "conversions": round(row.metrics.conversions, 1),
            "conversions_value": round(row.metrics.conversions_value, 2),
        })
    return results


def fetch_daily_totals(campaign_daily: list[dict]) -> list[dict]:
    """Aggregate campaign rows into daily totals."""
    by_date = {}
    for row in campaign_daily:
        d = row["date"]
        if d not in by_date:
            by_date[d] = {
                "date": d,
                "impressions": 0,
                "clicks": 0,
                "cost": 0.0,
                "conversions": 0.0,
            }
        by_date[d]["impressions"] += row["impressions"]
        by_date[d]["clicks"] += row["clicks"]
        by_date[d]["cost"] += row["cost"]
        by_date[d]["conversions"] += row["conversions"]

    totals = []
    for d in sorted(by_date.keys()):
        entry = by_date[d]
        entry["ctr"] = round(entry["clicks"] / entry["impressions"] * 100, 2) if entry["impressions"] > 0 else 0.0
        entry["avg_cpc"] = round(entry["cost"] / entry["clicks"], 2) if entry["clicks"] > 0 else 0.0
        totals.append(entry)
    return totals


def fetch_campaign_summary(campaign_daily: list[dict]) -> list[dict]:
    """Aggregate campaign rows into one summary per campaign, sorted by cost."""
    by_campaign = {}
    for row in campaign_daily:
        name = row["campaign_name"]
        if name not in by_campaign:
            by_campaign[name] = {
                "campaign_name": name,
                "campaign_id": row["campaign_id"],
                "status": row["status"],
                "landing_type": row.get("landing_type", "unknown"),
                "use_case": row.get("use_case", "unknown"),
                "impressions": 0,
                "clicks": 0,
                "cost": 0.0,
                "conversions": 0.0,
            }
        by_campaign[name]["impressions"] += row["impressions"]
        by_campaign[name]["clicks"] += row["clicks"]
        by_campaign[name]["cost"] += row["cost"]
        by_campaign[name]["conversions"] += row["conversions"]

    summaries = []
    for camp in sorted(by_campaign.values(), key=lambda x: x["cost"], reverse=True):
        camp["ctr"] = round(camp["clicks"] / camp["impressions"] * 100, 2) if camp["impressions"] > 0 else 0.0
        camp["avg_cpc"] = round(camp["cost"] / camp["clicks"], 2) if camp["clicks"] > 0 else 0.0
        camp["cost"] = round(camp["cost"], 2)
        camp["conversions"] = round(camp["conversions"], 1)
        camp["cvr"] = cvr(camp["conversions"], camp["clicks"])
        camp["cpa"] = cpa(camp["cost"], camp["conversions"])
        summaries.append(camp)
    return summaries


def run(customer_id: str = None, days: int = 30, output_dir: str = "./data"):
    """Fetch all Google Ads data and save it to <output_dir>/google_ads_data.json."""
    if customer_id is None:
        customer_id = os.environ.get("GOOGLE_ADS_CUSTOMER_ID")
    if not customer_id:
        raise ValueError("GOOGLE_ADS_CUSTOMER_ID is required")

    # Strip dashes so the id is digits only
    customer_id = customer_id.replace("-", "")
    os.makedirs(output_dir, exist_ok=True)
    client = get_client()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[Google Ads] Fetching data (customer: {customer_id}, last {days} days)")

    print("[Google Ads] Fetching daily campaign metrics...")
    campaign_daily = fetch_campaign_daily(client, customer_id, days)
    print(f"  -> {len(campaign_daily)} rows")

    print("[Google Ads] Tagging campaigns with landing_type / use_case...")
    Taxonomy.load().tag_rows(campaign_daily)

    daily_totals = fetch_daily_totals(campaign_daily)
    campaign_summary = fetch_campaign_summary(campaign_daily)
    by_landing_type = summarize_by(campaign_daily, "landing_type")
    by_use_case = summarize_by(campaign_daily, "use_case")

    total_cost = sum(d["cost"] for d in daily_totals)
    total_clicks = sum(d["clicks"] for d in daily_totals)
    total_impressions = sum(d["impressions"] for d in daily_totals)
    total_conversions = sum(d["conversions"] for d in daily_totals)

    kpi = {
        "total_cost": round(total_cost, 2),
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "total_conversions": round(total_conversions, 1),
        "avg_cpc": round(total_cost / total_clicks, 2) if total_clicks > 0 else 0.0,
        "avg_ctr": round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0.0,
        "cpa": cpa(total_cost, total_conversions),
        "cvr": cvr(total_conversions, total_clicks),
    }

    ads_data = {
        "fetched_at": timestamp,
        "customer_id": customer_id,
        "date_range": {"days": days},
        "kpi": kpi,
        "daily_totals": daily_totals,
        "campaign_daily": campaign_daily,
        "campaign_summary": campaign_summary,
        "by_landing_type": by_landing_type,
        "by_use_case": by_use_case,
    }

    output_path = os.path.join(output_dir, "google_ads_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ads_data, f, ensure_ascii=False, indent=2)

    print(f"[Google Ads] Saved to {output_path}")
    return ads_data


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    run(
        customer_id=os.environ.get("GOOGLE_ADS_CUSTOMER_ID"),
        days=int(os.environ.get("DATA_DAYS", 30)),
        output_dir=os.environ.get("OUTPUT_DIR", "./data"),
    )
