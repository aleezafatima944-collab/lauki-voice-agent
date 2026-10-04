"""Pure helper logic for the Lauki agent.

No heavy imports here (no torch, Qdrant, LangChain), so it is fast to test
and safe to run while the voice agent is running.
"""
import re

UPGRADE_AT = 0.85  # at or above this usage -> suggest upgrading
WATCH_AT = 0.60    # at or above this usage -> "keep an eye on it"


# ---------------------------------------------------------------- plans
def plans_by_price(plans: dict) -> list:
    """Return [(name, details), ...] sorted from cheapest to most expensive."""
    return sorted(plans.items(), key=lambda kv: kv[1]["price"])


def find_plan(plans: dict, name: str):
    """Find a plan by exact or partial, case-insensitive name. None if no match."""
    wanted = name.strip().lower()
    for key in plans:
        if key.lower() == wanted:
            return key
    for key in plans:
        if wanted and wanted in key.lower():
            return key
    return None


def next_plan_up(current_plan: str, plans: dict):
    """Return (name, details) of the next more expensive plan, or None."""
    ordered = plans_by_price(plans)
    names = [n for n, _ in ordered]
    if current_plan not in names:
        return None
    i = names.index(current_plan)
    return ordered[i + 1] if i + 1 < len(ordered) else None


# ---------------------------------------------------------------- usage
def _ratio(used, limit) -> float:
    return used / limit if limit else 0.0


def usage_summary(customer: dict) -> dict:
    """Fraction of data, voice and SMS used (0.0 to 1.0+)."""
    return {
        "data": _ratio(customer["data_usage_gb"], customer["data_limit_gb"]),
        "voice": _ratio(customer["voice_usage_min"], customer["voice_limit_min"]),
        "sms": _ratio(customer["sms_usage"], customer["sms_limit"]),
    }


def build_upgrade_advice(customer: dict, plans: dict) -> str:
    """Short, speakable advice on whether the customer should upgrade."""
    usage = usage_summary(customer)
    top = max(usage, key=usage.get)
    label = {"data": "data", "voice": "call minutes", "sms": "SMS"}[top]
    pct = f"{round(usage[top] * 100)} percent"
    current = customer["plan"]

    if usage[top] >= UPGRADE_AT:
        nxt = next_plan_up(current, plans)
        if nxt is None:
            return (f"You have used {pct} of your {label}, and {current} is "
                    f"already our biggest plan.")
        name, p = nxt
        return (f"You have used {pct} of your {label} on {current}. "
                f"An upgrade to {name} gives you {p['data']} data, "
                f"{p['voice']} voice and {p['sms']} for ₹{p['price']}.")
    if usage[top] >= WATCH_AT:
        return (f"You have used {pct} of your {label}. Your {current} plan "
                f"is fine for now, but keep an eye on it.")
    return (f"You have used only {pct} of your {label}, so {current} "
            f"suits your usage well.")


def compare_plans_text(plans: dict, plan_a: str, plan_b: str) -> str:
    """Short, speakable comparison of two plans."""
    ka, kb = find_plan(plans, plan_a), find_plan(plans, plan_b)
    if not ka or not kb:
        missing = plan_a if not ka else plan_b
        return (f"I could not find a plan called {missing}. "
                f"Available plans are: {', '.join(plans)}.")
    if ka == kb:
        return f"Those are the same plan: {ka}."
    pa, pb = plans[ka], plans[kb]
    return (
        f"{ka} costs ₹{pa['price']} for {pa['validity']} with {pa['data']} data, "
        f"{pa['voice']} voice and {pa['sms']}. "
        f"{kb} costs ₹{pb['price']} for {pb['validity']} with {pb['data']} data, "
        f"{pb['voice']} voice and {pb['sms']}. "
        f"The price difference is ₹{abs(pb['price'] - pa['price'])}."
    )


# ---------------------------------------------------- price guardrail
_PRICE_RE = re.compile(
    r"(?:₹|rs\.?|inr)\s?(\d[\d,]*(?:\.\d+)?)"
    r"|(\d[\d,]*(?:\.\d+)?)\s?(?:rupees|rs\b)",
    re.IGNORECASE,
)


def extract_prices(text: str) -> list:
    """Pull rupee amounts out of text, e.g. '₹449', 'Rs. 1,299', '449 rupees'."""
    out = []
    for m in _PRICE_RE.finditer(text):
        raw = m.group(1) or m.group(2)
        out.append(float(raw.replace(",", "")))
    return out


def allowed_prices(plans: dict, customers: dict) -> set:
    """Every rupee amount the agent is allowed to say.

    Plan prices, customer balances, and the difference between any two plan
    prices (used when comparing plans).
    """
    prices = [float(p["price"]) for p in plans.values()]
    allowed = set(prices)
    for a in prices:
        for b in prices:
            allowed.add(abs(a - b))
    for c in customers.values():
        allowed.add(round(float(c["balance_inr"]), 2))
    return allowed


def find_unverified_prices(text: str, allowed: set) -> list:
    """Rupee amounts in `text` that are NOT in the allowed set."""
    allowed = {float(a) for a in allowed}
    return [p for p in extract_prices(text) if p not in allowed]
