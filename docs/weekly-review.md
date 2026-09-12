# Weekly agency review

Fixed agenda, same order every week, 45 minutes. The agency owns account
structure, keyword expansion and bidding; we own landing pages, keyword
direction and the conversion-goal definition. The review is where both sides
look at the same numbers before anyone touches a budget.

Bring: the dashboard (Overview + Ad Campaigns tabs), the output of
`scripts/experiments.py compare`, the search-term report for the week, and
`scripts/reconcile.py` for the conversion event.

## Agenda

1. **Cost, conversions, key-event trend** (7 days vs the previous 7).
   Cost, Ads conversions, CPA (cost / paid signups), activation rate.
   Anything moving more than ~20% needs a named cause before moving on.
2. **Search terms and negatives.** Top terms by cost, terms with zero
   conversions above a spend threshold, new negatives to add, and intents
   the current landing pages cannot answer (input for a new scenario page).
3. **Landing-page status.** The "by landing_type" table, one line per
   experiment arm, page changes shipped this week, pages still missing.
4. **Creatives and new scenarios.** Ad copy variants tested, next
   `use_case` to add, what content the aggregated page needs.
5. **Budget moves.** Verdicts from the experiment table: which arms get
   more, which are paused, and by how much (steps of +20-30%).
6. **Performance Max: add, keep, or hold.** Only add or expand PMax when a
   scenario page exists for it to land on and the search arms have a stable
   CPA to compare against.
7. **Tracking and data.** Reconciliation gap for the conversion event,
   unknown-event warnings from the validator, any new event that still has
   to be marked as a conversion by hand.

## Template

| # | Item                          | This week | Last week | Change | Decision / owner |
|---|-------------------------------|-----------|-----------|--------|------------------|
| 1 | Cost                          |           |           |        |                  |
| 1 | Conversions (Ads)             |           |           |        |                  |
| 1 | CPA (cost / paid signups)     |           |           |        |                  |
| 1 | Activation rate               |           |           |        |                  |
| 2 | Negatives added               |           |           |        |                  |
| 2 | Uncovered intents             |           |           |        |                  |
| 3 | Best landing_type CPA         |           |           |        |                  |
| 3 | Pages shipped / pending       |           |           |        |                  |
| 4 | Creatives tested              |           |           |        |                  |
| 4 | Next scenario                 |           |           |        |                  |
| 5 | Budget moves                  |           |           |        |                  |
| 6 | PMax decision                 |           |           |        |                  |
| 7 | Reconciliation gap (%)        |           |           |        |                  |
| 7 | Unknown events / conversions to mark |    |           |        |                  |

Decisions go into `config/experiments.yaml` (`status`, `conclusion`) the same
day; the next review starts by checking that they were executed.
