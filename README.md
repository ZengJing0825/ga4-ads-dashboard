# GA4 + Google Ads Dashboard

A small, self-hosted growth dashboard. Once a day it pulls data from the
**GA4 Data API** and the **Google Ads API**, validates the result, and renders a
static **Chart.js** dashboard (funnels, channel breakdown, traffic sources, geo,
ad spend, campaign table). Scheduling is done with **macOS launchd**; no
database, no server-side framework.

> **The data shipped in this repo is synthetic.** `dashboard/data.sample.json`
> is randomly generated demo data (`"synthetic": true`) so the dashboard renders
> out of the box. It does not describe any real property, account or product.

## What it does

```
launchd (09:00 / 14:00 local)
  └─ refresh.sh
       ├─ lock file + 300s watchdog + log rotation
       ├─ backup dashboard/data.json (keep last 7)
       ├─ [1/4] scripts/fetch_ga4.py         GA4 Data API  -> data/ga4_data.json
       ├─ [2/4] scripts/fetch_google_ads.py  Google Ads API -> data/google_ads_data.json
       ├─ [3/4] merge                        -> dashboard/data.json
       └─ [4/4] scripts/validate_data.py     fail -> restore backup + macOS notification
```

`dashboard/index.html` is a static page. It loads `data.json` from the same
directory and falls back to `data.sample.json` if `data.json` does not exist.

### Data pulled

| Source | What |
|---|---|
| GA4 | daily event counts + users for every funnel event, active/new users, sessions, source/medium, event x channel breakdown (paid / organic / direct / referral), period-level deduplicated users, top countries |
| Google Ads | daily campaign metrics (impressions, clicks, cost, CTR, CPC, conversions), daily totals, per-campaign summary |

### Funnels

Event names are generic examples. Edit the lists at the top of
`scripts/fetch_ga4.py` and the `NAME_MAP` / funnel arrays in
`dashboard/index.html` to match your own GA4 events.

| Funnel | Events |
|---|---|
| Creator | `ad_click -> homepage_view -> login_click -> login_success -> docs_click -> install_copy -> settings_view -> signup -> feature_use -> content_publish -> ask_send` |
| Consumer | `ad_click -> homepage_view -> login_click -> featured_click -> explore_view -> explore_item_click -> feature_view -> item_favorite -> item_share` |
| Clone | `clone_click -> clone_copy -> clone_publish` |
| Subscription | `upgrade_click -> upgrade_plan_click -> upgrade_success` |

## Quick start (demo data only)

```bash
python3 -m http.server 8787 -d dashboard
# open http://localhost:8787
```

The page must be served over HTTP (not opened as `file://`) because it fetches
the JSON with `fetch()`.

## Setup with real data

### 1. Install dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. GA4 (service account)

1. In Google Cloud Console create a service account and download its JSON key.
2. Enable the **Google Analytics Data API** for the project.
3. In GA4 -> Admin -> Property access management, add the service account
   email as **Viewer**.
4. Save the key as `credentials/ga4-service-account.json` (the `credentials/`
   directory is git-ignored).

### 3. Google Ads (OAuth2)

1. Get a **developer token** (Google Ads -> Tools -> API Center).
2. In Google Cloud Console create an OAuth client of type **Desktop app**.
3. Put the client id / secret in `.env`, then run
   `python3 scripts/get_refresh_token.py` and paste the printed refresh token
   into `.env` as `GOOGLE_ADS_REFRESH_TOKEN`.
4. If the account is managed through an MCC, set
   `GOOGLE_ADS_LOGIN_CUSTOMER_ID` to the manager id; otherwise leave it empty.

### 4. Configure

```bash
cp .env.example .env
# fill in the placeholders
```

`REPORT_TZ_OFFSET_HOURS` should match the timezone of your GA4 property and
Google Ads account so that a given calendar day covers the same period in both
sources.

### 5. Run once

```bash
./refresh.sh            # full pipeline, logs to logs/refresh.log
# or
python3 scripts/run_all.py   # Python-only, no lock/backup/validation
python3 -m http.server 8787 -d dashboard
```

### 6. Schedule (macOS launchd)

```bash
./install.sh
```

`install.sh` hardens credential permissions, substitutes the project path into
`com.example.dashboard-refresh.plist`, copies it to `~/Library/LaunchAgents/`
and loads it. Default schedule is 09:00 and 14:00 local time; edit the plist
to change it.

```bash
launchctl start com.example.dashboard-refresh          # trigger now
tail -f logs/refresh.log                                 # logs
cat .health | python3 -m json.tool                       # last successful run
launchctl unload ~/Library/LaunchAgents/com.example.dashboard-refresh.plist   # uninstall
```

## Layout

```
.
├── dashboard/
│   ├── index.html            static Chart.js dashboard
│   └── data.sample.json      synthetic demo data (data.json is generated, git-ignored)
├── scripts/
│   ├── fetch_ga4.py          GA4 Data API -> data/ga4_data.json
│   ├── fetch_google_ads.py   Google Ads API -> data/google_ads_data.json
│   ├── run_all.py            fetch both + merge (Python-only entry point)
│   ├── validate_data.py      sanity checks on dashboard/data.json
│   └── get_refresh_token.py  one-off OAuth helper for Google Ads
├── refresh.sh                hardened pipeline used by launchd
├── install.sh                installs the launchd agent
├── harden-permissions.sh     chmod 600 on credentials
├── com.example.dashboard-refresh.plist   launchd template (__PROJECT_DIR__ placeholder)
├── .env.example
└── requirements.txt
```

## Notes

- `validate_data.py` rejects data whose `generated_at` is older than 24 hours;
  this is intended for freshly generated `data.json`, not for the sample file.
- GA4 reporting typically lags 24-48 hours; the overview chart shows a hint
  when recent paid users look low relative to ad clicks.
- Never commit `.env`, `credentials/`, `data/`, `backups/`, `logs/` or
  `dashboard/data.json` (all are in `.gitignore`).
