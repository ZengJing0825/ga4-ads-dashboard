# The decision loop

Every change to paid acquisition goes through the same five steps. The point
is not ceremony; it is that each step leaves a record the next weekly review
can check, and that money is only added to something that has already proven
it converts.

```
diagnose  ->  hypothesis  ->  small-budget test  ->  compare landing types  ->  kill or scale
  (data)      (one line)       (~$100 / day)        (same window, same goal)     (by rule)
```

## 1. Diagnose

Start from something in the data that does not add up, never from an idea.
Typical triggers:

- The search-term report is dominated by one intent (say, trading and quant
  queries) while the landing page cannot answer that intent.
- Cost is flat but the conversion event is falling: check
  `scripts/reconcile.py` first, it may be tracking, not the ads.
- One landing type's CPA drifts away from the others in the
  "CPA / CTR / CVR by landing_type" table.
- Ads conversions and GA4 paid signups disagree by more than the
  reconciliation threshold (default 10%).

Write the observation down with the numbers. If it cannot be stated with a
number it is not a diagnosis yet.

## 2. Hypothesis

One sentence: *if we change X, metric Y moves because Z*. Name the landing
type it is about:

| landing_type   | what the visitor lands on                                     |
|----------------|---------------------------------------------------------------|
| `homepage`     | the product homepage (or a brand page)                        |
| `skill_page`   | a page about one capability / feature                         |
| `usecase_page` | a page that aggregates the content of one scenario            |
| `single_page`  | one specific content item                                     |
| `pmax`         | Performance Max, Google picks the asset and often the page    |

## 3. Small-budget test

- Budget in the order of **$100 per day** per arm. Enough to collect a few
  dozen conversions in one to two weeks, small enough that a wrong page does
  not hurt.
- Before spending, confirm the conversion event actually arrives: fire a
  test conversion and see it in GA4 realtime **and** in the Google Ads
  conversion column. A campaign optimising towards an event that never
  arrives just teaches the algorithm noise.
- Register the arm in `config/experiments.yaml` before it starts. Each
  record carries:

  | field              | meaning                                                          |
  |--------------------|------------------------------------------------------------------|
  | `id`               | `EXP-nnn`                                                        |
  | `date`, `end_date` | test window; leave `end_date` out while running                  |
  | `hypothesis`       | the sentence from step 2                                         |
  | `landing_type`     | one of the five types above                                      |
  | `campaigns`        | exact campaign names covered                                     |
  | `daily_budget`     | USD / day across those campaigns                                 |
  | `conversion_event` | the GA4 event the campaigns optimise for                         |
  | `kill_rule`        | `{metric, above, min_spend}`: kill when metric > above after spend >= min_spend |
  | `scale_rule`       | `{metric, below, min_conversions}`: scale when metric < below after >= min_conversions |
  | `status`           | `planned`, `running`, `killed`, `scaled`, `baseline`             |
  | `conclusion`       | filled in at the review that closes the arm                      |

## 4. Compare landing types

Arms are only comparable when they share the window, the conversion event
and roughly the budget. `scripts/experiments.py compare` joins every arm to
its campaigns' daily rows and prints one line per arm:

```
id       landing_type  status   days      cost  clicks    conv   CTR%   CVR%     CPA  verdict
EXP-001  homepage      killed     20   1452.91    1125   102.0   3.27   9.07   14.24     KILL
EXP-002  usecase_page  scaled     30   3842.98    3513   491.2   4.49  13.98    7.82    SCALE
EXP-003  single_page   running    30   2986.06    2442   202.5   2.86   8.29   14.75     KILL
EXP-004  pmax          baseline   30  11348.09   13851   565.0   1.86   4.08   20.09     HOLD
```

(Synthetic sample data. The four records are fictional examples.)

Read the table with the daily picture in mind: a `single_page` arm can look
acceptable on the blended number while its daily CPA swings several-fold with
the quality of the individual page. The `usecase_page` arm is the one whose
daily numbers stay in a narrow band.

## 5. Kill or scale

- **Kill** when the kill rule fires. Pausing is cheap: the learning-phase
  data stays in the account and the campaign can be resumed. Continuing to
  spend against the wrong page or the wrong keywords is the expensive
  mistake.
- **Scale** when the scale rule fires: raise the budget in steps (roughly
  +20-30% every few days) so the bidding algorithm does not re-enter
  learning.
- **Hold** otherwise, and revisit at the weekly review
  (`docs/weekly-review.md`).
- Overriding a verdict is allowed, but it has to be written into
  `conclusion` with the reason and a date to re-check, as EXP-003 does.

The verdict column is a suggestion computed from the rules on the numbers of
the day; the log records what was actually decided.
