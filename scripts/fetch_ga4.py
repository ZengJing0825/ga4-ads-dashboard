"""
GA4 data fetcher.
Pulls daily counts for all funnel events plus overall metrics, traffic sources,
event x channel breakdown, period-level unique users and geo distribution.
Writes everything to <OUTPUT_DIR>/ga4_data.json.
"""

import json
import os
from datetime import datetime, timedelta, timezone

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    FilterExpressionList,
    Metric,
    RunReportRequest,
    OrderBy,
)


def report_tz() -> timezone:
    """Timezone used to compute the date window.

    Set REPORT_TZ_OFFSET_HOURS in .env to match your GA4 property timezone
    (e.g. -7 for a UTC-7 property). Defaults to -7.
    """
    return timezone(timedelta(hours=float(os.environ.get("REPORT_TZ_OFFSET_HOURS", "-7"))))


# ============================================================
# Event definitions -- replace these with your own GA4 event names.
# The names below are generic examples so the dashboard works out of the box.
# ============================================================

CREATOR_FUNNEL_EVENTS = [
    "ad_click",          # 1. landed via ad / UTM link
    "homepage_view",     # 2. homepage impression
    "login_click",       # 3. clicked Log in
    "login_success",     # 4. logged in
    "docs_click",        # 5. opened docs / repo
    "install_copy",      # 6. copied install command
    "settings_view",     # 7. opened settings / credentials page
    "signup",            # 8. completed signup / created credential
    "feature_use",       # 9. used the core feature locally
    "content_publish",   # 10. published content
    "ask_send",          # 11. sent a question from the homepage
]

# Consumer funnel: ad -> homepage -> login -> featured click -> explore -> card click -> detail -> favorite -> share
# Note: feature_view may exceed explore_view because users can land on a detail
# page directly via SEO / shared links.
CONSUMER_FUNNEL_EVENTS = [
    "ad_click",            # 1. ad reach
    "homepage_view",       # 2. homepage impression
    "login_click",         # 3. clicked Log in
    "featured_click",      # 4. clicked a featured item on the homepage
    "explore_view",        # 5. viewed Explore
    "explore_item_click",  # 6. clicked a card in Explore
    "feature_view",        # 7. detail page view
    "item_favorite",       # 8. favorited an item
    "item_share",          # 9. shared an item
]

CLONE_EVENTS = [
    "clone_click",
    "clone_copy",
    "clone_publish",
]

SUBSCRIPTION_EVENTS = [
    "upgrade_click",
    "upgrade_plan_click",
    "upgrade_success",
]

ALL_EVENTS = list(set(
    CREATOR_FUNNEL_EVENTS
    + CONSUMER_FUNNEL_EVENTS
    + CLONE_EVENTS
    + SUBSCRIPTION_EVENTS
))


def get_client():
    """Create the GA4 Data API client (REST transport for broader compatibility)."""
    return BetaAnalyticsDataClient(transport="rest")


def _date_window(days: int) -> tuple[str, str]:
    now = datetime.now(report_tz())
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")
    return start_date, end_date


def _ymd(raw: str) -> str:
    """Convert GA4's YYYYMMDD date dimension to YYYY-MM-DD."""
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _event_filter() -> FilterExpression:
    return FilterExpression(
        or_group=FilterExpressionList(
            expressions=[
                FilterExpression(
                    filter=Filter(
                        field_name="eventName",
                        string_filter=Filter.StringFilter(value=event_name),
                    )
                )
                for event_name in ALL_EVENTS
            ]
        )
    )


def fetch_daily_event_counts(client, property_id: str, days: int = 30) -> list[dict]:
    """
    Daily event_count and unique users per event.
    Returns: [{"date": "2026-04-01", "event_name": "login_success", "event_count": 15, "users": 12}, ...]
    """
    start_date, end_date = _date_window(days)

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[
            Dimension(name="date"),
            Dimension(name="eventName"),
        ],
        metrics=[
            Metric(name="eventCount"),
            Metric(name="totalUsers"),
        ],
        dimension_filter=_event_filter(),
        order_bys=[
            OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date")),
        ],
        limit=10000,
    )

    response = client.run_report(request)
    results = []
    for row in response.rows:
        results.append({
            "date": _ymd(row.dimension_values[0].value),
            "event_name": row.dimension_values[1].value,
            "event_count": int(row.metric_values[0].value),
            "users": int(row.metric_values[1].value),
        })
    return results


def fetch_overall_metrics(client, property_id: str, days: int = 30) -> list[dict]:
    """Daily active users, new users, sessions and total events."""
    start_date, end_date = _date_window(days)

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="date")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
            Metric(name="sessions"),
            Metric(name="eventCount"),
        ],
        order_bys=[
            OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date")),
        ],
    )

    response = client.run_report(request)
    results = []
    for row in response.rows:
        results.append({
            "date": _ymd(row.dimension_values[0].value),
            "active_users": int(row.metric_values[0].value),
            "new_users": int(row.metric_values[1].value),
            "sessions": int(row.metric_values[2].value),
            "total_events": int(row.metric_values[3].value),
        })
    return results


def fetch_traffic_source(client, property_id: str, days: int = 30) -> list[dict]:
    """Users and sessions grouped by source/medium and campaign (paid vs organic analysis)."""
    start_date, end_date = _date_window(days)

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[
            Dimension(name="date"),
            Dimension(name="sessionSourceMedium"),
            Dimension(name="sessionCampaignName"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
        ],
        order_bys=[
            OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date")),
        ],
        limit=10000,
    )

    response = client.run_report(request)
    results = []
    for row in response.rows:
        results.append({
            "date": _ymd(row.dimension_values[0].value),
            "source_medium": row.dimension_values[1].value,
            "campaign": row.dimension_values[2].value,
            "sessions": int(row.metric_values[0].value),
            "active_users": int(row.metric_values[1].value),
            "new_users": int(row.metric_values[2].value),
        })
    return results


def classify_channel(source_medium: str) -> str:
    """Bucket a sessionSourceMedium value into paid / organic / direct / referral."""
    sm_lower = source_medium.lower()
    if "cpc" in sm_lower or "paid" in sm_lower or "ppc" in sm_lower:
        return "paid"
    if "organic" in sm_lower:
        return "organic"
    if "(direct)" in sm_lower or source_medium == "(not set)":
        return "direct"
    return "referral"


def fetch_event_by_source(client, property_id: str, days: int = 30) -> list[dict]:
    """
    Event x sessionSourceMedium breakdown, used to split each funnel step
    into paid / organic / direct / referral.
    """
    start_date, end_date = _date_window(days)

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[
            Dimension(name="date"),
            Dimension(name="eventName"),
            Dimension(name="sessionSourceMedium"),
        ],
        metrics=[
            Metric(name="eventCount"),
            Metric(name="totalUsers"),
        ],
        dimension_filter=_event_filter(),
        order_bys=[
            OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date")),
        ],
        limit=10000,
    )

    response = client.run_report(request)
    results = []
    for row in response.rows:
        source_medium = row.dimension_values[2].value
        results.append({
            "date": _ymd(row.dimension_values[0].value),
            "event_name": row.dimension_values[1].value,
            "source_medium": source_medium,
            "channel": classify_channel(source_medium),
            "event_count": int(row.metric_values[0].value),
            "users": int(row.metric_values[1].value),
        })
    return results


def fetch_geo_data(client, property_id: str, days: int = 30) -> list[dict]:
    """Top countries by active users."""
    start_date, end_date = _date_window(days)

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="country")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
            Metric(name="sessions"),
        ],
        order_bys=[
            OrderBy(metric=OrderBy.MetricOrderBy(metric_name="activeUsers"), desc=True),
        ],
        limit=20,
    )

    response = client.run_report(request)
    results = []
    for row in response.rows:
        results.append({
            "country": row.dimension_values[0].value,
            "active_users": int(row.metric_values[0].value),
            "new_users": int(row.metric_values[1].value),
            "sessions": int(row.metric_values[2].value),
        })
    return results


def fetch_period_uv(client, property_id: str, days: int = 30) -> list[dict]:
    """
    Query without the date dimension to get true period-level unique users,
    avoiding double counting users who appear on multiple days.
    """
    start_date, end_date = _date_window(days)

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="eventName")],
        metrics=[
            Metric(name="eventCount"),
            Metric(name="totalUsers"),
        ],
        dimension_filter=_event_filter(),
        limit=10000,
    )

    response = client.run_report(request)
    results = []
    for row in response.rows:
        results.append({
            "event_name": row.dimension_values[0].value,
            "event_count": int(row.metric_values[0].value),
            "users": int(row.metric_values[1].value),
        })
    return results


def build_funnel_summary(daily_events: list[dict], funnel_events: list[str], funnel_name: str) -> dict:
    """
    Build a funnel summary from daily event data: total event_count, users
    and step / overall conversion rates for each step.
    """
    steps = []
    for i, event_name in enumerate(funnel_events):
        total_count = sum(
            e["event_count"] for e in daily_events if e["event_name"] == event_name
        )
        total_users = sum(
            e["users"] for e in daily_events if e["event_name"] == event_name
        )
        step = {
            "step": i + 1,
            "event_name": event_name,
            "event_count": total_count,
            "users": total_users,
        }
        if i > 0 and steps[i - 1]["users"] > 0:
            step["step_conversion_rate"] = round(
                total_users / steps[i - 1]["users"] * 100, 1
            )
        else:
            step["step_conversion_rate"] = 100.0 if i == 0 else 0.0

        if steps and steps[0]["users"] > 0:
            step["overall_conversion_rate"] = round(
                total_users / steps[0]["users"] * 100, 1
            )
        else:
            step["overall_conversion_rate"] = 100.0 if i == 0 else 0.0

        steps.append(step)

    return {"funnel_name": funnel_name, "steps": steps}


def run(property_id: str = None, days: int = 30, output_dir: str = "./data"):
    """Fetch all GA4 data and save it to <output_dir>/ga4_data.json."""
    if property_id is None:
        property_id = os.environ.get("GA4_PROPERTY_ID")
    if not property_id:
        raise ValueError("GA4_PROPERTY_ID is required")

    os.makedirs(output_dir, exist_ok=True)
    client = get_client()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[GA4] Fetching data (property: {property_id}, last {days} days)")

    print("[GA4] Fetching daily event counts...")
    daily_events = fetch_daily_event_counts(client, property_id, days)
    print(f"  -> {len(daily_events)} rows")

    print("[GA4] Fetching overall metrics...")
    overall = fetch_overall_metrics(client, property_id, days)
    print(f"  -> {len(overall)} days")

    print("[GA4] Fetching traffic sources...")
    traffic = fetch_traffic_source(client, property_id, days)
    print(f"  -> {len(traffic)} rows")

    print("[GA4] Fetching event x source breakdown...")
    event_by_source = fetch_event_by_source(client, property_id, days)
    print(f"  -> {len(event_by_source)} rows")

    print("[GA4] Fetching period unique users...")
    period_uv = fetch_period_uv(client, property_id, days)
    print(f"  -> {len(period_uv)} events")

    print("[GA4] Fetching geo distribution...")
    geo = fetch_geo_data(client, property_id, days)
    print(f"  -> {len(geo)} countries")

    print("[GA4] Building funnel summaries...")
    creator_funnel = build_funnel_summary(daily_events, CREATOR_FUNNEL_EVENTS, "Creator Funnel")
    consumer_funnel = build_funnel_summary(daily_events, CONSUMER_FUNNEL_EVENTS, "Consumer Funnel")
    clone_funnel = build_funnel_summary(daily_events, CLONE_EVENTS, "Clone Funnel")
    subscription_funnel = build_funnel_summary(daily_events, SUBSCRIPTION_EVENTS, "Subscription Funnel")

    ga4_data = {
        "fetched_at": timestamp,
        "property_id": property_id,
        "date_range": {"days": days},
        "daily_events": daily_events,
        "overall_metrics": overall,
        "traffic_sources": traffic,
        "event_by_source": event_by_source,
        "period_uv": period_uv,
        "geo": geo,
        "funnels": {
            "creator": creator_funnel,
            "consumer": consumer_funnel,
            "clone": clone_funnel,
            "subscription": subscription_funnel,
        },
    }

    output_path = os.path.join(output_dir, "ga4_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ga4_data, f, ensure_ascii=False, indent=2)

    print(f"[GA4] Saved to {output_path}")
    return ga4_data


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    run(
        property_id=os.environ.get("GA4_PROPERTY_ID"),
        days=int(os.environ.get("DATA_DAYS", 30)),
        output_dir=os.environ.get("OUTPUT_DIR", "./data"),
    )
