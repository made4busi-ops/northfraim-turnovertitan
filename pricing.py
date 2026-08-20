"""
pricing.py — real Turnover Titans job pricing, matching the actual
industry-standard structure: bedroom-scaled base rate, priced add-ons,
service-tier multipliers, same-day surcharge, and a per-account
negotiated volume discount for 5+ property managers.

Every number here is real, sourced pricing given directly, not a guess.
"""
from dataclasses import dataclass, field

BASE_RATES = {
    "studio": 100.0,
    "1br": 100.0,
    "2br": 150.0,
    "3br": 200.0,
    "4br+": 275.0,
}

ADDON_RATES = {
    "laundry": 25.0,          # wash, dry, fold on-site
    "restocking": 15.0,       # toilet paper, soap, coffee, trash bags
    "hot_tub": 35.0,
    "pool_outdoor": 20.0,     # pool / outdoor entertaining area
}

SAME_DAY_FLAT = 35.0
SAME_DAY_PCT = 0.25

# Deep clean and mid-stay refresh are given as ranges (+30-50%, 50-60% of
# base) -- the midpoint is used as the real, single quoted number; a
# human can still override case by case.
TIER_MULTIPLIERS = {
    "standard": 1.0,
    "deep_clean": 1.40,
    "mid_stay_refresh": 0.55,
}

MAX_VOLUME_DISCOUNT_PCT = 0.10  # negotiated per account, 5-10%, never auto-applied above this
VOLUME_DISCOUNT_MIN_PROPERTIES = 5


class PricingError(ValueError):
    pass


@dataclass
class Quote:
    bedroom_tier: str
    service_tier: str
    addons: list
    same_day: bool
    base_rate: float
    tier_multiplier: float
    tier_amount: float
    addons_total: float
    same_day_surcharge: float
    subtotal: float
    volume_discount_pct: float
    volume_discount_amount: float
    total: float
    line_items: list = field(default_factory=list)


def calculate_price(bedroom_tier: str, service_tier: str = "standard",
                     addons=None, same_day: bool = False,
                     volume_discount_pct: float = 0.0) -> Quote:
    bedroom_tier = bedroom_tier.lower().strip()
    service_tier = service_tier.lower().strip()
    addons = addons or []

    if bedroom_tier not in BASE_RATES:
        raise PricingError(f"Unknown bedroom_tier '{bedroom_tier}'. Valid: {list(BASE_RATES)}")
    if service_tier not in TIER_MULTIPLIERS:
        raise PricingError(f"Unknown service_tier '{service_tier}'. Valid: {list(TIER_MULTIPLIERS)}")
    for a in addons:
        if a not in ADDON_RATES:
            raise PricingError(f"Unknown addon '{a}'. Valid: {list(ADDON_RATES)}")
    if not (0.0 <= volume_discount_pct <= MAX_VOLUME_DISCOUNT_PCT):
        raise PricingError(f"volume_discount_pct must be between 0 and {MAX_VOLUME_DISCOUNT_PCT} (negotiated 5-10% range)")

    base_rate = BASE_RATES[bedroom_tier]
    tier_multiplier = TIER_MULTIPLIERS[service_tier]
    tier_amount = round(base_rate * tier_multiplier, 2)

    line_items = [{"label": f"{bedroom_tier.upper()} turnover ({service_tier.replace('_', ' ')})", "amount": tier_amount}]

    addons_total = 0.0
    for a in addons:
        amt = ADDON_RATES[a]
        addons_total += amt
        line_items.append({"label": a.replace("_", " ").title(), "amount": amt})

    pre_surcharge_subtotal = tier_amount + addons_total

    same_day_surcharge = 0.0
    if same_day:
        pct_amount = round(pre_surcharge_subtotal * SAME_DAY_PCT, 2)
        same_day_surcharge = max(SAME_DAY_FLAT, pct_amount)
        line_items.append({"label": "Same-day / rush turnover surcharge", "amount": same_day_surcharge})

    subtotal = round(pre_surcharge_subtotal + same_day_surcharge, 2)

    volume_discount_amount = round(subtotal * volume_discount_pct, 2)
    if volume_discount_amount:
        line_items.append({"label": f"Volume discount ({volume_discount_pct * 100:.1f}%)", "amount": -volume_discount_amount})

    total = round(subtotal - volume_discount_amount, 2)

    return Quote(
        bedroom_tier=bedroom_tier,
        service_tier=service_tier,
        addons=addons,
        same_day=same_day,
        base_rate=base_rate,
        tier_multiplier=tier_multiplier,
        tier_amount=tier_amount,
        addons_total=addons_total,
        same_day_surcharge=same_day_surcharge,
        subtotal=subtotal,
        volume_discount_pct=volume_discount_pct,
        volume_discount_amount=volume_discount_amount,
        total=total,
        line_items=line_items,
    )
