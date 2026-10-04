"""Tests for agent_logic.py. Run:  uv run python tests/test_agent_logic.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_logic import (
    allowed_prices, build_upgrade_advice, compare_plans_text, extract_prices,
    find_plan, find_unverified_prices, next_plan_up, usage_summary,
)

PLANS = {
    "Lauki Basic 1GB": {"price": 199, "validity": "30 days", "data": "1 GB", "voice": "300 minutes", "sms": "100 SMS"},
    "Lauki Premium 2GB": {"price": 449, "validity": "30 days", "data": "2 GB", "voice": "300 minutes", "sms": "100 SMS"},
    "Lauki Elite 5GB": {"price": 899, "validity": "30 days", "data": "5 GB", "voice": "1000 minutes", "sms": "500 SMS"},
    "Lauki Lite 500MB": {"price": 99, "validity": "7 days", "data": "500 MB", "voice": "100 minutes", "sms": "50 SMS"},
}


def cust(plan, d, v, s, balance=100.0):
    return {"plan": plan, "balance_inr": balance,
            "data_usage_gb": d[0], "data_limit_gb": d[1],
            "voice_usage_min": v[0], "voice_limit_min": v[1],
            "sms_usage": s[0], "sms_limit": s[1]}


RAJESH = cust("Lauki Premium 2GB", (1.2, 2.0), (120, 300), (45, 100), 450.50)
PRIYA = cust("Lauki Basic 1GB", (0.5, 1.0), (50, 300), (20, 100), 199.99)
AMIT = cust("Lauki Elite 5GB", (3.8, 5.0), (250, 1000), (150, 500), 899.00)
HEAVY = cust("Lauki Premium 2GB", (1.9, 2.0), (280, 300), (60, 100), 120.0)
MAXED = cust("Lauki Elite 5GB", (4.9, 5.0), (100, 1000), (10, 500))
CUSTOMERS = {"1": RAJESH, "2": PRIYA, "3": AMIT, "4": HEAVY}


def test_usage_summary():
    u = usage_summary(RAJESH)
    assert round(u["data"], 2) == 0.60
    assert round(u["voice"], 2) == 0.40
    assert round(u["sms"], 2) == 0.45


def test_next_plan_up():
    assert next_plan_up("Lauki Lite 500MB", PLANS)[0] == "Lauki Basic 1GB"
    assert next_plan_up("Lauki Premium 2GB", PLANS)[0] == "Lauki Elite 5GB"
    assert next_plan_up("Lauki Elite 5GB", PLANS) is None
    assert next_plan_up("Nonexistent", PLANS) is None


def test_upgrade_advice_levels():
    assert "only 50 percent" in build_upgrade_advice(PRIYA, PLANS)
    watch = build_upgrade_advice(RAJESH, PLANS)
    assert "60 percent" in watch and "fine for now" in watch
    assert "76 percent" in build_upgrade_advice(AMIT, PLANS)
    up = build_upgrade_advice(HEAVY, PLANS)
    assert "95 percent" in up and "Lauki Elite 5GB" in up and "₹899" in up
    top = build_upgrade_advice(MAXED, PLANS)
    assert "biggest plan" in top and "₹" not in top


def test_find_plan():
    assert find_plan(PLANS, "premium") == "Lauki Premium 2GB"
    assert find_plan(PLANS, "  LAUKI ELITE 5GB ") == "Lauki Elite 5GB"
    assert find_plan(PLANS, "platinum") is None
    assert find_plan(PLANS, "") is None


def test_compare_plans():
    t = compare_plans_text(PLANS, "premium", "elite")
    assert "₹449" in t and "₹899" in t and "₹450" in t
    assert "could not find a plan called platinum" in compare_plans_text(PLANS, "premium", "platinum")
    assert "same plan" in compare_plans_text(PLANS, "elite", "Lauki Elite 5GB")


def test_extract_prices():
    assert extract_prices("It costs ₹449 per month.") == [449.0]
    assert extract_prices("Rs. 1,299 only") == [1299.0]
    assert extract_prices("449 rupees a month") == [449.0]
    assert extract_prices("Your balance is ₹450.50.") == [450.5]
    assert extract_prices("No prices here, 5G is available") == []


def test_price_guardrail():
    allowed = allowed_prices(PLANS, CUSTOMERS)
    assert 450.5 in allowed and 449.0 in allowed
    assert find_unverified_prices("Premium is ₹449.", allowed) == []
    assert find_unverified_prices("Premium is ₹500.", allowed) == [500.0]
    assert find_unverified_prices("The difference is ₹450.", allowed) == []
    assert find_unverified_prices("Balance ₹450.50, plan ₹449", allowed) == []


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {name}  {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)
