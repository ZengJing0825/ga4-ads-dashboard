# GA4 + Google Ads Dashboard

[中文版](README.zh.md)

An attribution dashboard and decision loop for **small teams acquiring users with Google Ads whose product has a signup → activation → key-action funnel**: GA4 and Google Ads data in one place, cost and conversion split by landing type, reconciliation against first-party data, and every change run as diagnose → hypothesis → small budget → compare → kill or scale. All sample data is synthetic.

**What problem it solves.** Paid acquisition produces two kinds of waste: money
spent without knowing where the users went, and an ad algorithm trained on
the wrong conversion goal. This repo is a small, self-hosted loop that closes
both gaps: a tracking plan that is written before the first dollar is spent,
a daily pull from the GA4 Data API and the Google Ads API into one static
JSON, a dashboard that splits campaigns by landing type and scenario, a
reconciliation check between GA4 and your own database, and an experiment
log that turns every budget decision into a record with a kill or scale rule.

**Who it is for.** A founder, growth lead or product marketer who runs Google
Ads for a product with a real funnel (signup, activation, publish), works
with an agency or a media buyer, and wants the weekly conversation to be about
numbers both sides can reproduce. Everything runs from a laptop with Python
3.9, no database, no server framework. The sample data is synthetic and the
event names, scenario dimensions and experiment records are all config, so
the structure transfers to your own product.

## Core logic

I did not build this dashboard to have one more chart page. I built it so
that every paid-acquisition decision has data behind it that can be checked.

**Purpose.** Two things go wrong most often with paid acquisition: money is
spent and nobody knows where the users went, and the ad algorithm is trained
on the wrong conversion goal. So the order is fixed: instrument first, spend
second. Before any spend I wrote a complete event specification: two funnels,
creator and consumer; every event labelled as an impression, a click or a
business action; every event carrying the three utm parameters; and a
requirement that both the production and the staging environment are
deployed. Without this step the dashboard, the reviews and the scaling that
come later are empty talk.

**Architecture.** Data comes from two ends: the GA4 Data API for events and
users, the Google Ads API for cost, clicks and conversions. Both are first
aligned to the same timezone, otherwise the spend and the signups of the same
day do not match. A script runs on a schedule every day, merges everything
into one static JSON, and the page renders it directly with no database. The
validation layer has two jobs: is the file fresh and complete, and do the
GA4 event counts agree with our own database. In a real project I hit a case
where server-side reporting was missing the session parameters and GA4 came
in 10 to 15% below the database; the ad algorithm therefore had "nothing to
learn from". That hole has to be plugged with a reconciliation mechanism.

**Why each step.** The dashboard splits campaigns by landing-page type
instead of looking only at totals, because my core experiment was a
comparison of landing strategies: the homepage or a skill page, a template
page that aggregates content by use case, or a single content page. The
conclusion is clear: a single content page depends heavily on content
quality, and on the same budget results can differ by 50% to 100%; sending a
scenario's traffic to one page that aggregates that scenario's content makes
the campaign more stable and the cost lowest. In numbers, the aggregated-page
series had a signup cost of 7 to 9 dollars while Performance Max in the same
period sat at 19 to 21 dollars; the aggregated pages' click-through rate was
about 2.3 times PMax's, and the overall blended CPA was about 15 dollars (the
30-day snapshot of my original dashboard).

**Decision flow.** Every change walks the same path: find something in the
data that does not add up (for example, the search terms are all trading and
quant while the landing page cannot speak to either), state a hypothesis,
verify with a small budget (in the order of 100 dollars a day) that the
conversion event really arrives, compare several landing strategies, stop
what does not work, and add budget to what does. Pausing is not scary; the
learning-phase data is still there. What is scary is continuing to burn money
with the wrong landing page and the wrong keywords.

**Working with the agency.** The agency owns the foundations: account
structure, keyword expansion, bidding. I own the landing pages, the keyword
direction and the definition of the conversion goal, with a fixed weekly
review: cost, conversions, trend of the core events, search terms, landing
page status, next budget moves. The service fee and the monthly fee
structure were negotiated too, not accepted by default.

This repository generalises the logic above: event names, scenario dimensions
and experiment records are configurable, the sample data is synthetic, but
the structure is the one I actually used.

## Quick start

Everything below runs offline against the synthetic data shipped in
`dashboard/data.sample.json`. Python 3.9 or newer, standard library only
(PyYAML is used when present, otherwise a built-in reader handles the
config files).

```bash
git clone <this repo> && cd ga4-ads-dashboard

# 1. validate the sample the way the pipeline validates a real refresh
#    (the sample is old by definition, so skip the 24-hour freshness check)
python3 scripts/validate_data.py --path dashboard/data.sample.json --skip-freshness

# 2. campaign metrics by landing_type and by use_case, parsed from campaign names
python3 scripts/taxonomy.py --data dashboard/data.sample.json

# 3. the experiment log joined to campaign metrics, with kill / scale verdicts
python3 scripts/experiments.py list
python3 scripts/experiments.py compare --data dashboard/data.sample.json

# 4. GA4 vs first-party export for the conversion event (the example export
#    deliberately reproduces the 10-15% gap, so this prints a WARN and exits 1)
python3 scripts/reconcile.py --data dashboard/data.sample.json \
    --export examples/first_party_signups.csv --event signup

# 5. tests
python3 -m unittest discover -s tests

# 6. the dashboard (must be served over HTTP, it fetches the JSON)
python3 -m http.server 8787 -d dashboard
# open http://localhost:8787
```

`dashboard/index.html` loads `data.json` and falls back to `data.sample.json`
when it does not exist. `python3 scripts/make_sample_data.py` regenerates the
sample and the example export from a fixed seed.

### Connecting real data

1. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
2. **GA4**: create a service account in Google Cloud Console, enable the
   Google Analytics Data API, add the service account email as *Viewer* under
   GA4 → Admin → Property access management, save the key as
   `credentials/ga4-service-account.json` (git-ignored).
3. **Google Ads**: get a developer token (Google Ads → Tools → API Center),
   create an OAuth client of type *Desktop app*, put client id / secret in
   `.env`, run `python3 scripts/get_refresh_token.py` and paste the refresh
   token into `.env`. Set `GOOGLE_ADS_LOGIN_CUSTOMER_ID` only if the account is
   reached through a manager account.
4. `cp .env.example .env` and fill in the placeholders. Set
   `REPORT_TZ_OFFSET_HOURS` to the timezone of your GA4 property and Ads
   account (see the timezone note below).
5. Edit `config/campaign_taxonomy.yaml` so the regexes describe your campaign
   names, and `config/tracking_plan.yaml` so it lists your events.
6. Run once: `./refresh.sh` (full pipeline with lock, backup, validation,
   logs to `logs/refresh.log`) or `python3 scripts/run_all.py` (Python only).
7. Schedule (macOS): `./install.sh` hardens credential permissions, fills the
   project path into `com.example.dashboard-refresh.plist`, installs it under
   `~/Library/LaunchAgents/` and loads it. Default 09:00 and 14:00 local time.

```bash
launchctl start com.example.dashboard-refresh          # trigger now
tail -f logs/refresh.log                                 # logs
cat .health | python3 -m json.tool                       # last successful run
launchctl unload ~/Library/LaunchAgents/com.example.dashboard-refresh.plist   # uninstall
```

Never commit `.env`, `credentials/`, `data/`, `backups/`, `logs/` or
`dashboard/data.json`; all of them are in `.gitignore`.

## Data flow and dashboard definitions

```
launchd (09:00 / 14:00 local)
  └─ refresh.sh
       ├─ lock file + 300s watchdog + log rotation
       ├─ backup dashboard/data.json (keep last 7)
       ├─ [1/4] scripts/fetch_ga4.py         GA4 Data API  -> data/ga4_data.json
       ├─ [2/4] scripts/fetch_google_ads.py  Google Ads API -> data/google_ads_data.json
       │        (tags every campaign with landing_type / use_case from config/campaign_taxonomy.yaml)
       ├─ [3/4] merge                        -> dashboard/data.json
       └─ [4/4] scripts/validate_data.py     fail -> restore backup + macOS notification
                                             unknown events -> WARN (config/tracking_plan.yaml)
```

| Source | What is pulled |
|---|---|
| GA4 | daily event counts and users for every funnel event, active / new users, sessions, source / medium and campaign, event × channel (paid / organic / direct / referral), period-level deduplicated users, top countries |
| Google Ads | daily campaign metrics (impressions, clicks, cost, CTR, CPC, conversions), daily totals, per-campaign summary, per-landing_type and per-use_case summary |

**Timezone.** `REPORT_TZ_OFFSET_HOURS` is one setting used by both fetchers to
compute the date window. GA4 reports in the property's timezone and Google
Ads in the account's timezone; if the two pulls are computed in different
zones, one day's cost is compared against a different day's signups, and CPA
by day becomes noise. Keep both sources on the same offset, and set that
offset to match the property and account.

**Scenario dimensions.** `config/campaign_taxonomy.yaml` holds two ordered
regex lists that parse `landing_type` (`homepage | skill_page | usecase_page |
single_page | pmax`) and `use_case` from the campaign name; the first match
wins and unmatched names get `unknown`. The sample campaigns follow
`<network>-<landing>-<use_case>-<geo>`, but any naming scheme works once the
regexes describe it. The Ad Campaigns tab shows "CPA / CTR / CVR by
landing_type" and "by use_case", and the campaign table carries both columns.

**KPI definitions** (`scripts/kpi.py`, also shown on the Data Sources tab):

| KPI | Definition | Source |
|---|---|---|
| Cost | Google Ads spend in the selected window | Ads |
| Conversions | conversions as reported by Google Ads | Ads |
| CPA (cost / conversions) | Ads-side CPA, available per campaign, landing_type and use_case | Ads |
| CPA (cost / paid signups) | cost divided by GA4 users on the paid channel who fired the conversion event (`signup`); what the business actually pays per signup | Ads + GA4 |
| Activation rate | paid users who reached the key action (`feature_use`) / paid signups | GA4 |
| CTR, CVR, CPC | clicks / impressions, conversions / clicks, cost / clicks | Ads |

**Which event is the conversion goal.** Choose an event whose step conversion
from the previous funnel step is roughly 50%: deep enough to mean something,
frequent enough for the bidding algorithm to learn from. A page view is
frequent but says nothing; a publish means a lot but is too rare to train on.
In the sample funnel `settings_view → signup` is that step, so `signup` is the
conversion and `feature_use` the key action. The event names are constants at
the top of `dashboard/index.html` (`CONVERSION_EVENT`, `KEY_ACTION_EVENT`) and
in `config/tracking_plan.yaml` (`conversions`, `key_action`).

**Funnels.** Event names are generic examples; edit the lists at the top of
`scripts/fetch_ga4.py` and `NAME_MAP` in `dashboard/index.html`.

| Funnel | Events |
|---|---|
| Creator | `ad_click → homepage_view → login_click → login_success → docs_click → install_copy → settings_view → signup → feature_use → content_publish → ask_send` |
| Consumer | `ad_click → homepage_view → login_click → featured_click → explore_view → explore_item_click → feature_view → item_favorite → item_share` |
| Clone | `clone_click → clone_copy → clone_publish` |
| Subscription | `upgrade_click → upgrade_plan_click → upgrade_success` |

`validate_data.py` rejects data whose `generated_at` is older than 24 hours
(use `--skip-freshness` for the sample), and GA4 reporting lags 24-48 hours,
so the overview chart shows a hint when recent paid users look low relative
to ad clicks.

## Experiments and the decision loop

`docs/decision-loop.md` describes the loop; `config/experiments.yaml` is the
log; `scripts/experiments.py` reads both.

```
diagnose -> hypothesis -> small-budget test (~$100 / day) -> compare landing types -> kill or scale
```

Each record in `config/experiments.yaml` has `id`, `date` (and optional
`end_date`), `hypothesis`, `landing_type`, `campaigns` covered,
`daily_budget`, `conversion_event`, `kill_rule` (`{metric, above,
min_spend}`), `scale_rule` (`{metric, below, min_conversions}`), `status`
(`planned | running | killed | scaled | baseline`) and `conclusion`. Four
fictional examples ship with the repo, one per landing type in the sample
data.

`python3 scripts/experiments.py compare` joins every record to the daily
rows of the campaigns it covers inside its window and prints cost, clicks,
conversions, CTR, CVR, CPA and the verdict the rules give today (`LEARNING`
until the minimum spend / conversions are reached, then `KILL`, `SCALE` or
`HOLD`), followed by each record's conclusion and any campaigns not covered
by an experiment. The verdict is a suggestion; the log records what was
decided, and an override is written into `conclusion` with a date to
re-check.

## Tracking plan

`docs/tracking-plan.md` is the template, `config/tracking_plan.yaml` the
machine-readable copy. Two funnels (creator, consumer) as
step → event → type (`view | click | action`) → trigger → params, plus the
secondary clone and subscription events. Rules that apply to every event:

- the utm triplet `utm_source`, `utm_medium`, `utm_campaign` on every event;
- the same plan deployed to a staging property first, then to prod; Ads
  conversions are imported from prod only;
- server-side events sent through the Measurement Protocol must carry
  `client_id` and the session id, otherwise they do not join the session,
  carry no source / medium / campaign, and Google Ads cannot learn from them;
- a new event is not a conversion until someone marks it as a key event in
  the GA4 admin UI by hand and imports it into Google Ads.

`scripts/validate_data.py` loads the plan and prints a `WARN` line for every
event present in fetched data that the plan does not list. It never fails the
refresh on that; the point is to catch typos and unplanned events early.

## Reconciliation

`scripts/reconcile.py` compares GA4 event counts with a first-party export
(CSV with `date`, `count` and optionally `event_name` columns) for the same
window and event:

```bash
python3 scripts/reconcile.py --export examples/first_party_signups.csv --event signup --threshold 10
```

It prints per-day and total counts, the gap as `(ga4 − export) / export`, and
a `WARN` (exit status 1) when the absolute total gap exceeds the threshold,
default 10%. A persistent negative gap is the signature of server-side hits
arriving without `client_id` / `session_id`. `examples/first_party_signups.csv`
is a fictional export generated with the sample data, sized so that GA4 comes
in 10 to 15% below it.

## Weekly review

`docs/weekly-review.md` is the fixed agenda for the weekly session with the
agency: cost / conversions / key-event trends, search terms and negatives,
landing-page status, creatives and new scenarios, budget moves, whether to
add Performance Max, and tracking / data health, with a short template table.
Decisions from the review go into `config/experiments.yaml` the same day.

## Layout

```
.
├── config/
│   ├── campaign_taxonomy.yaml   regexes: campaign name -> landing_type / use_case
│   ├── experiments.yaml         experiment log (4 fictional examples)
│   └── tracking_plan.yaml       events, types, triggers, params, environments
├── dashboard/
│   ├── index.html               static Chart.js dashboard
│   └── data.sample.json         synthetic demo data (data.json is generated, git-ignored)
├── docs/
│   ├── decision-loop.md         diagnose -> hypothesis -> test -> compare -> kill / scale
│   ├── tracking-plan.md         tracking plan template
│   └── weekly-review.md         weekly agency review agenda + template
├── examples/
│   └── first_party_signups.csv  fictional first-party export for reconcile.py
├── scripts/
│   ├── fetch_ga4.py             GA4 Data API -> data/ga4_data.json
│   ├── fetch_google_ads.py      Google Ads API -> data/google_ads_data.json (+ taxonomy tags)
│   ├── run_all.py               fetch both + merge (Python-only entry point)
│   ├── validate_data.py         sanity checks + tracking-plan warning
│   ├── taxonomy.py              campaign-name parsing and per-dimension summaries
│   ├── kpi.py                   CTR / CVR / CPA / activation-rate math
│   ├── experiments.py           experiment log CLI (list / compare)
│   ├── reconcile.py             GA4 vs first-party export
│   ├── make_sample_data.py      seeded generator for the sample data and example export
│   ├── config_loader.py         YAML loader (PyYAML if present, built-in subset reader otherwise)
│   └── get_refresh_token.py     one-off OAuth helper for Google Ads
├── tests/                       stdlib unittest suite
├── refresh.sh                   hardened pipeline used by launchd
├── install.sh                   installs the launchd agent
├── harden-permissions.sh        chmod 600 on credentials
├── com.example.dashboard-refresh.plist   launchd template (__PROJECT_DIR__ placeholder)
├── .env.example
├── requirements.txt             Google SDKs + python-dotenv (only needed for real data)
└── LICENSE                      MIT
```
