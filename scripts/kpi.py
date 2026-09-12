"""KPI definitions shared by the fetch scripts, the CLI tools and the tests.

All rates are returned as percentages rounded to 2 decimals; ratios that
would divide by zero return 0.0 (rates) or None (CPA / CPC), matching what
the dashboard shows as "-".

    CTR             = clicks / impressions
    CVR             = conversions / clicks
    CPC             = cost / clicks
    CPA             = cost / conversions            (Ads-side, per campaign or bucket)
    CPA (paid)      = cost / paid signups           (GA4-side: paid-channel users
                                                     who fired the conversion event)
    Activation rate = paid users who reached the key action / paid signups
"""


def _rate(num, den):
    return round(num / den * 100, 2) if den else 0.0


def ctr(clicks, impressions):
    return _rate(clicks, impressions)


def cvr(conversions, clicks):
    return _rate(conversions, clicks)


def cpc(cost, clicks):
    return round(cost / clicks, 2) if clicks else None


def cpa(cost, conversions):
    return round(cost / conversions, 2) if conversions else None


def activation_rate(paid_key_action_users, paid_signups):
    return _rate(paid_key_action_users, paid_signups)


def step_rate(users, previous_users):
    """Funnel step conversion (users at this step / users at the previous step)."""
    return _rate(users, previous_users)
