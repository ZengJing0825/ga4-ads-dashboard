# GA4 + Google Ads Dashboard

[中文版](README.zh.md)

An ad-spend dashboard and decision log for **small teams acquiring users with Google Ads**.

**When it applies.** Your product has a signup → activation → key-action funnel, you run Google Ads, and you may work with an agency or a media buyer. The two usual kinds of waste are money spent without knowing where the users went, and an ad algorithm learning from the wrong conversion goal. This repository chains a tracking plan written before spending, a daily pull from GA4 and Google Ads merged into one file, cost and conversion split by landing-page type, a reconciliation against your own database, and every budget decision recorded as an experiment, into one closed loop.

**Who it is for.** Founders, growth leads and product marketers who want the weekly review with the agency to be about numbers both sides can reproduce. It runs on a laptop with Python 3.9, no database.

**What you get.** A static dashboard page (cost, conversions, CPA on two definitions, activation rate, both funnels), cost and conversion split by landing-page type and by use case, a day-by-day reconciliation of GA4 against your own database that warns when the gap is too big, and an experiment log that returns a KILL / SCALE / HOLD verdict for every budget decision. The offline demo needs Python 3.9 and the standard library; the Google SDKs are only for real data.

**Scope and limits.** Google Ads + GA4 only, no Meta or TikTok; the sample data is synthetic, and event names, scenario dimensions and experiment records are all configuration, so the structure transfers to your own product.

## What you get (preview)

Everything below runs offline on the synthetic sample (30 days, 8 campaigns, two funnels). The numbers illustrate the definitions and represent no real account.

**The dashboard.** Cost, conversions, CPA on two definitions (Ads-reported, and cost per paid signup seen in GA4), activation rate, every funnel event with its paid share, and daily actives against paid users.

![dashboard overview: key metrics and daily actives](docs/preview/dashboard.png)

**Cost and conversion by landing-page type and by use case**, parsed from campaign names, next to the campaign table. In the sample the use-case pages come in at about $8 per conversion against $20 for Performance Max, which is the comparison the whole repository was built around.

![Ad Campaigns tab: CPA by landing_type and use_case, campaign table](docs/preview/campaigns.png)

**The two command-line checks** behind the weekly review: the experiment log joined to actual metrics with a KILL / SCALE / HOLD verdict from each record's own rules, and GA4 reconciled against your own signup export day by day. The sample reproduces the 10% gap that means server-side hits are missing their session parameters.

![experiments compare and reconcile output](docs/preview/experiments.png)

## Five things the built-in GA4 reports do not do

GA4 and Google Ads each have their own reports, and Looker Studio can stitch them together. What this repository adds is five things at the decision level:

1. **Landing-page type is a first-class dimension.** Campaign names are parsed into homepage / skill page / use-case page / single page / PMax plus a use case, and cost and conversions are split by both, instead of account totals only.
2. **Reconciliation between GA4 and your own database.** The same conversion event is compared day by day in GA4 and in your database; a gap over the threshold raises a warning. A persistently negative gap is the classic symptom of server-side events missing session parameters, which leaves the ad algorithm with nothing to learn from.
3. **Every budget decision is an experiment record with rules.** Hypothesis, landing type, daily budget, conversion event, kill rule, scale rule, conclusion; the script joins the record to actual metrics and says whether today's verdict is KILL, SCALE or HOLD.
4. **The conversion goal is chosen by the "about 50% step conversion" rule.** Too shallow an event (page view) means nothing; too deep an event (publish) is too sparse to train on. The rule is written into the config and the docs.
5. **Instrument first, spend second; fully static, no database.** The tracking plan is machine-readable config, and the fetch warns on any event not in the plan; each day's data is merged into one JSON that the page renders directly, on a laptop.

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

## How it works

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

| Step | What it does | Files |
|---|---|---|
| Fetch | GA4 Data API for events and users, Google Ads API for cost, clicks and conversions; both aligned to one timezone first | `scripts/fetch_ga4.py`, `scripts/fetch_google_ads.py` |
| Tag | Parse every campaign name into `landing_type` and `use_case` with ordered regexes | `config/campaign_taxonomy.yaml`, `scripts/taxonomy.py` |
| Merge and validate | One static JSON; freshness and completeness checks, a warning for any event not in the tracking plan; restore the backup on failure | `scripts/run_all.py`, `scripts/validate_data.py` |
| Dashboard | A static page reads the JSON and shows CPA / CTR / CVR by landing type and by use case | `dashboard/index.html`, `scripts/kpi.py` |
| Reconcile | GA4 event counts against your own export, day by day; warn when the gap exceeds the threshold | `scripts/reconcile.py` |
| Experiments | Join the experiment log to campaign metrics and print kill / scale verdicts | `config/experiments.yaml`, `scripts/experiments.py` |

## Design decisions

I did not build this dashboard to have one more chart page. I built it so that every paid-acquisition decision has data behind it that can be checked. These are the decisions that matter and where they came from in real campaigns.

**Instrument first, spend second.** Before any spend I wrote a complete event specification: two funnels, creator and consumer; every event labelled as an impression, a click or a business action; every event carrying the three utm parameters; and both production and staging deployed. Without this step the dashboard, the reviews and the scaling that come later are empty talk.

**Align timezones before trusting any daily number.** GA4 reports in the property's timezone, Google Ads in the account's; compute dates with different zones and one day's spend gets compared with another day's signups, and daily CPA becomes noise. Both fetchers therefore share one timezone offset.

**Reconciliation is not optional.** In a real project server-side reporting was missing the session parameters, so day after day GA4 came in 10 to 15% below the database - always in the same direction, which is what makes a reporting gap different from noise. The ad algorithm had that much less to learn from. The validation layer's two jobs, is the file fresh and complete and do the GA4 counts agree with our database, exist to plug that hole.

**How the conversion goal is chosen.** Pick an event whose step conversion from the previous funnel step is about 50%: deep enough to mean something, frequent enough for the algorithm to learn from. In the sample funnel that step is `settings_view → signup`, so `signup` is the conversion event and `feature_use` is the key action.

**The landing-page comparison: my core experiment.** The dashboard splits campaigns by landing type because the central experiment was a comparison of landing strategies. Over the three months that experiment ran, cost per signup came down to about a third of where it started. Inside a 30-day window of the live dashboard the ranking was stable: a single content page lives or dies by the quality of that one page and swings widely on the same budget; Performance Max was the most expensive way to buy a signup; and sending a use case's traffic to one page that aggregates that use case's content was both the cheapest and the steadiest, at roughly double the click-through rate of Performance Max.

The account's own cost figures are deliberately not in this repository. What transfers is the comparison and the dimension the dashboard is built on - your numbers will be your own, and the sample data here is synthetic.

**Decision flow.** Every change walks the same path: find something in the data that does not add up (the search terms are all trading and quant while the landing page cannot speak to either), state a hypothesis, verify with a small budget (in the order of $100 a day) that the conversion event really arrives, compare several landing strategies, stop what does not work, add budget to what does. Pausing is not scary; the learning-phase data is still there. Burning money with the wrong landing page and the wrong keywords is.

**Working with the agency.** The agency owns the foundations: account structure, keyword expansion, bidding. I own the landing pages, the keyword direction and the definition of the conversion goal, with a fixed weekly review: cost, conversions, trend of the core events, search terms, landing page status, next budget moves. The service fee and the monthly fee structure were negotiated too, not accepted by default.

## Connecting real data

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

## Out of scope

- Google Ads and GA4 only; Meta, TikTok and other channels need their own fetch scripts.
- Attribution is what Google Ads reports plus GA4's paid-channel users; there is no multi-touch attribution model.
- Runs on one machine; scheduling uses macOS launchd, and on Linux cron does the same job, the scripts do not depend on the OS.
- The sample data is synthetic; its numbers only demonstrate the definitions and represent no real account.

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

## License

MIT - see `LICENSE`.
