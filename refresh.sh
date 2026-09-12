#!/bin/bash
# GA4 + Google Ads Dashboard - hardened daily data refresh
# Pulls GA4 + Google Ads data -> merges into dashboard/data.json -> validates
#
# Data sources:
#   - GA4 Data API (v1beta) -- Service Account auth
#   - Google Ads API        -- OAuth2 auth
#
# Usage:
#   Manual:  ./refresh.sh
#   launchd: launchctl start com.example.dashboard-refresh
#   Schedule: see com.example.dashboard-refresh.plist (default 09:00 and 14:00 local)
#

set -e
cd "$(dirname "$0")"

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------
mkdir -p logs backups

# ---------------------------------------------------------------------------
# Log rotation: rotate logs/refresh.log if > 5 MB, keep last 5
# ---------------------------------------------------------------------------
LOG_FILE="logs/refresh.log"
MAX_LOG_SIZE=$((5 * 1024 * 1024))

if [ -f "$LOG_FILE" ]; then
    log_size=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$log_size" -gt "$MAX_LOG_SIZE" ]; then
        rotated="${LOG_FILE}.$(date '+%Y%m%d%H%M%S')"
        mv "$LOG_FILE" "$rotated"
        echo "$(date '+%Y-%m-%d %H:%M:%S') Log rotated to $rotated"
        # Keep only the last 5 rotated logs
        ls -1t logs/refresh.log.* 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
    fi
fi

# ---------------------------------------------------------------------------
# Redirect all output to log
# ---------------------------------------------------------------------------
exec >> "$LOG_FILE" 2>&1

# ---------------------------------------------------------------------------
# Lock file (PID-based with stale detection)
# ---------------------------------------------------------------------------
LOCKFILE=".refresh.lock"

if [ -f "$LOCKFILE" ]; then
    old_pid=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Another refresh is running (PID $old_pid). Exiting."
        exit 1
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') WARNING: Removing stale lock (PID $old_pid no longer running)"
        rm -f "$LOCKFILE"
    fi
fi
echo $$ > "$LOCKFILE"

# ---------------------------------------------------------------------------
# Timeout watchdog (300 seconds)
# ---------------------------------------------------------------------------
TIMEOUT=300
( sleep $TIMEOUT && echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Timeout after ${TIMEOUT}s - killing PID $$" >> "$LOG_FILE" && kill -9 $$ 2>/dev/null ) &
WATCHDOG_PID=$!

# ---------------------------------------------------------------------------
# Cleanup trap
# ---------------------------------------------------------------------------
cleanup() {
    rm -f "$LOCKFILE"
    kill $WATCHDOG_PID 2>/dev/null || true
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------
echo ""
echo "$(date '+%Y-%m-%d %H:%M:%S') === Dashboard Refresh ==="

# ---------------------------------------------------------------------------
# Check credential permissions (warn only, don't block)
# ---------------------------------------------------------------------------
check_perms() {
    local file="$1"
    if [ -f "$file" ]; then
        perms=$(stat -f "%Lp" "$file" 2>/dev/null || stat -c "%a" "$file" 2>/dev/null)
        if [ "$perms" != "600" ]; then
            echo "  WARNING: $file has permissions $perms (expected 600)"
        fi
    fi
}

echo "[pre] Checking credential permissions..."
check_perms ".env"
check_perms credentials/*.json 2>/dev/null || true

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------
set -a
source .env
set +a
export GOOGLE_APPLICATION_CREDENTIALS

# gRPC only honours lowercase proxy variables; mirror HTTPS_PROXY if set
if [ -n "$HTTPS_PROXY" ] && [ -z "$https_proxy" ]; then
    export https_proxy="$HTTPS_PROXY"
    export http_proxy="${HTTP_PROXY:-$HTTPS_PROXY}"
    echo "  Proxy: $https_proxy (copied from HTTPS_PROXY for gRPC)"
fi

# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------
retry_with_backoff() {
    local max=3 delay=10 attempt=1
    while [ $attempt -le $max ]; do
        if "$@"; then return 0; fi
        [ $attempt -lt $max ] && echo "  Retry $attempt/$max in ${delay}s..." && sleep $delay
        delay=$((delay * 2)); attempt=$((attempt + 1))
    done
    return 1
}

# ---------------------------------------------------------------------------
# Backup current dashboard data
# ---------------------------------------------------------------------------
if [ -f dashboard/data.json ]; then
    backup_name="backups/data.$(date '+%Y%m%d%H%M%S').json"
    cp dashboard/data.json "$backup_name"
    echo "[pre] Backed up dashboard/data.json -> $backup_name"
    # Keep only the last 7 backups
    ls -1t backups/data.*.json 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Step 1: Fetch GA4 data (REST transport, no proxy needed)
# ---------------------------------------------------------------------------
echo "[1/4] Fetching GA4 data (GA4 Data API v1beta, REST)..."
# GA4 REST may fail SSL through some proxies; clear them for this step
_saved_https_proxy="${https_proxy}"
_saved_http_proxy="${http_proxy}"
unset https_proxy http_proxy
if ! retry_with_backoff python3 scripts/fetch_ga4.py; then
    echo "ERROR: GA4 fetch failed after 3 attempts"
    osascript -e 'display notification "GA4 fetch failed after 3 retries" with title "Dashboard Refresh" subtitle "Refresh Failed" sound name "Basso"' 2>/dev/null || true
    exit 1
fi
# Restore proxy (Google Ads gRPC may need it)
export https_proxy="${_saved_https_proxy}"
export http_proxy="${_saved_http_proxy}"

# ---------------------------------------------------------------------------
# Step 2: Fetch Google Ads data (gRPC)
# ---------------------------------------------------------------------------
echo "[2/4] Fetching Google Ads data (Google Ads API, gRPC)..."
if ! retry_with_backoff python3 scripts/fetch_google_ads.py; then
    echo "  WARNING: Google Ads fetch failed after 3 attempts, using cached data"
fi

# ---------------------------------------------------------------------------
# Step 3: Combine data
# ---------------------------------------------------------------------------
echo "[3/4] Generating dashboard data..."
python3 -c "
import json, os
from datetime import datetime

with open('./data/ga4_data.json', 'r') as f:
    ga4 = json.load(f)

ads_path = './data/google_ads_data.json'
ads = json.load(open(ads_path)) if os.path.exists(ads_path) else {
    'kpi': {'total_cost': 0, 'total_clicks': 0, 'total_impressions': 0, 'total_conversions': 0, 'avg_cpc': 0, 'avg_ctr': 0},
    'daily_totals': [],
    'campaign_summary': [],
}

dashboard = {
    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'date_range_days': int(os.environ.get('DATA_DAYS', 30)),
    'data_sources': {
        'ga4': {
            'name': 'Google Analytics 4',
            'property_id': os.environ.get('GA4_PROPERTY_ID', ''),
            'api': 'GA4 Data API (v1beta)',
            'api_version': 'v1beta',
            'auth': 'Service Account',
            'auth_method': 'service_account_key',
            'last_fetch': ga4.get('fetched_at', ''),
        },
        'google_ads': {
            'name': 'Google Ads',
            'customer_id': os.environ.get('GOOGLE_ADS_CUSTOMER_ID', ''),
            'mcc_id': os.environ.get('GOOGLE_ADS_LOGIN_CUSTOMER_ID', ''),
            'api': 'Google Ads API',
            'auth': 'OAuth2 Refresh Token',
            'auth_method': 'oauth2_refresh_token',
            'last_fetch': ads.get('fetched_at', ''),
        },
    },
    'refresh_schedule': 'Daily via launchd',
    'ga4': ga4,
    'ads': ads,
}

with open('./dashboard/data.json', 'w') as f:
    json.dump(dashboard, f, ensure_ascii=False, indent=2)
print(f'  dashboard/data.json updated ({os.path.getsize(\"./dashboard/data.json\")} bytes)')
"

# ---------------------------------------------------------------------------
# Step 4: Validate data; restore backup on failure
# ---------------------------------------------------------------------------
echo "[4/4] Validating dashboard/data.json..."
if ! python3 scripts/validate_data.py; then
    echo "ERROR: Validation failed"
    if [ -n "$backup_name" ] && [ -f "$backup_name" ]; then
        echo "  Restoring backup: $backup_name"
        cp "$backup_name" dashboard/data.json
    fi
    osascript -e 'display notification "Data validation failed - backup restored" with title "Dashboard Refresh" subtitle "Refresh Failed" sound name "Basso"' 2>/dev/null || true
    exit 1
fi

# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------
echo "$(date '+%Y-%m-%d %H:%M:%S') === Refresh Complete ==="

# Write health file
python3 -c "
import json
from datetime import datetime
health = {
    'status': 'ok',
    'last_success': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'dashboard_size': $(stat -f%z dashboard/data.json 2>/dev/null || stat -c%s dashboard/data.json 2>/dev/null || echo 0),
}
with open('.health', 'w') as f:
    json.dump(health, f, indent=2)
print('  .health updated')
"
