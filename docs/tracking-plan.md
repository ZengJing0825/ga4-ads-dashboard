# Tracking plan

Instrument first, spend second. The plan below is the template behind
`config/tracking_plan.yaml`; `scripts/validate_data.py` checks fetched data
against it and warns about events that are not in the plan.

## Rules that apply to every event

1. **Every event carries the utm triplet** `utm_source`, `utm_medium`,
   `utm_campaign` (GA4 also stores them on the session, but keeping them on
   the event makes the export and the reconciliation self-contained).
2. **Two environments, one plan.** The same events are deployed to a
   staging property first and QA'd there, then to prod. Ads conversions are
   imported from prod only.
3. **Server-side events must carry `client_id` and a session id.** Events
   sent through the Measurement Protocol without the browser's `client_id`
   and `session_id` do not join the user's session: they show up in GA4 with
   no source / medium / campaign, they do not count against the ad click,
   and Google Ads cannot learn from them. This is the failure behind the
   "GA4 shows 10 to 15% fewer than the database" gap, and `reconcile.py`
   exists to catch it.
4. **New events are not conversions until someone marks them.** Creating an
   event does not make it a key event / conversion. Toggle it in the GA4
   admin UI, then import it into Google Ads, then verify a test conversion
   arrives in both. Nothing in this repo does that step for you.
5. **Type every event** as `view`, `click` or `action` so a funnel step can
   be read without opening the code. `action` events describe a business
   outcome and should be confirmed server-side where possible.

## Which event is the conversion goal

Pick the event whose step conversion from the previous funnel step is
**roughly 50%**. Shallower events (a page view) are frequent but mean little;
deeper events (a publish) mean a lot but are too rare for the bidding
algorithm to train on. In the sample funnel `settings_view -> signup` is the
50% step, so `signup` is the conversion and `feature_use` (the next step,
again about 50%) is the key action used for the activation rate.

## Creator funnel

| step | event             | type   | trigger                                      | params                    |
|-----:|-------------------|--------|----------------------------------------------|---------------------------|
| 1    | `ad_click`        | click  | landing with gclid or utm params             | landing_type, use_case    |
| 2    | `homepage_view`   | view   | homepage rendered                            | landing_type              |
| 3    | `login_click`     | click  | Log in button                                |                           |
| 4    | `login_success`   | action | auth callback succeeded                      | method                    |
| 5    | `docs_click`      | click  | docs / repository link                       | target                    |
| 6    | `install_copy`    | click  | copy button on the install command           | os                        |
| 7    | `settings_view`   | view   | settings / credentials page rendered         |                           |
| 8    | `signup`          | action | credential created (server-side)             | plan                      |
| 9    | `feature_use`     | action | first successful use of the core feature     | feature                   |
| 10   | `content_publish` | action | content published (server-side)              | content_type              |
| 11   | `ask_send`        | action | question submitted from the homepage         |                           |

## Consumer funnel

| step | event                | type   | trigger                              | params             |
|-----:|----------------------|--------|--------------------------------------|--------------------|
| 1    | `ad_click`           | click  | landing with gclid or utm params     | landing_type, use_case |
| 2    | `homepage_view`      | view   | homepage rendered                    | landing_type       |
| 3    | `login_click`        | click  | Log in button                        |                    |
| 4    | `featured_click`     | click  | featured card on the homepage        | item_id            |
| 5    | `explore_view`       | view   | explore page rendered                | filter             |
| 6    | `explore_item_click` | click  | card inside explore                  | item_id, position  |
| 7    | `feature_view`       | view   | item detail page rendered            | item_id            |
| 8    | `item_favorite`      | action | favourite toggled on                 | item_id            |
| 9    | `item_share`         | action | share sheet confirmed                | item_id, channel   |

Plus the utm triplet on all of them. `feature_view` can exceed
`explore_view` because detail pages are also reached from search and shared
links.

## Secondary events

`clone_click -> clone_copy -> clone_publish` and
`upgrade_click -> upgrade_plan_click -> upgrade_success` are listed under
`extra_events` in the YAML so the validator knows them.

## Checklist for a new event

- [ ] added to `config/tracking_plan.yaml` with type, trigger and params
- [ ] deployed to staging and seen in GA4 DebugView with the utm triplet
- [ ] server-side hits verified to carry `client_id` and `session_id`
- [ ] deployed to prod
- [ ] if it is a conversion: marked as key event in GA4, imported to Ads,
      test conversion seen in the Ads conversion column
- [ ] `scripts/fetch_ga4.py` event lists and `dashboard/index.html` `NAME_MAP` updated
- [ ] `scripts/validate_data.py` runs without an unknown-event warning
