"""
Main entry point (Python-only alternative to refresh.sh).
Fetches GA4 + Google Ads data and merges both into dashboard/data.json.
Run once a day.
"""

import json
import os
import sys
from datetime import datetime

# Add project root to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))


def main():
    days = int(os.environ.get("DATA_DAYS", 30))
    output_dir = os.path.join(ROOT_DIR, os.environ.get("OUTPUT_DIR", "data"))
    dashboard_dir = os.path.join(ROOT_DIR, "dashboard")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(dashboard_dir, exist_ok=True)

    ga4_data = None
    ads_data = None

    # GA4
    try:
        from scripts.fetch_ga4 import run as run_ga4
        ga4_data = run_ga4(
            property_id=os.environ.get("GA4_PROPERTY_ID"),
            days=days,
            output_dir=output_dir,
        )
    except Exception as e:
        print(f"[GA4] Fetch failed: {e}")
        fallback = os.path.join(output_dir, "ga4_data.json")
        if os.path.exists(fallback):
            print(f"[GA4] Using cached data: {fallback}")
            with open(fallback, "r") as f:
                ga4_data = json.load(f)

    # Google Ads
    try:
        from scripts.fetch_google_ads import run as run_ads
        ads_data = run_ads(
            customer_id=os.environ.get("GOOGLE_ADS_CUSTOMER_ID"),
            days=days,
            output_dir=output_dir,
        )
    except Exception as e:
        print(f"[Google Ads] Fetch failed: {e}")
        fallback = os.path.join(output_dir, "google_ads_data.json")
        if os.path.exists(fallback):
            print(f"[Google Ads] Using cached data: {fallback}")
            with open(fallback, "r") as f:
                ads_data = json.load(f)

    dashboard_data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date_range_days": days,
        "ga4": ga4_data,
        "ads": ads_data,
    }

    dashboard_json = os.path.join(dashboard_dir, "data.json")
    with open(dashboard_json, "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, ensure_ascii=False, indent=2)

    print(f"\nDashboard data written to {dashboard_json}")
    print(f"Open {os.path.join(dashboard_dir, 'index.html')} (via a local HTTP server) to view it")


if __name__ == "__main__":
    main()
