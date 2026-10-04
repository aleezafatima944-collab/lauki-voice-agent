"""Benchmark for the Lauki voice agent (text mode).

Measures, for each test question:
  - did the agent call a sensible tool?
  - does the answer contain the expected facts?
  - did the answer avoid made-up prices? (price guardrail)
  - how long did it take?

Run from the project root (close other terminals using Qdrant first):
    uv run python eval_agent.py

Results are printed and saved to eval_results.json. Re-run after switching
models (Groq -> Nebius) to compare them.
Note: latency here is LLM + tools time in text mode, not time-to-first-audio.
"""
import json
import statistics
import time

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import AIMessage  # noqa: E402

from agent_logic import allowed_prices, find_unverified_prices  # noqa: E402
from config import settings  # noqa: E402
from langchain_agent import lauki_agent  # noqa: E402
from langchain_agent.tools import MOCK_CUSTOMER_DB, MOCK_PLANS_DB  # noqa: E402

# tools_any: at least one of these tools must be called ([] = no requirement)
# must:      every one of these strings must appear in the answer
# must_any:  at least one of these strings must appear ([] = no requirement)
CASES = [
    {"q": "How much is the Lauki Premium 2GB plan?",
     "tools_any": ["get_plan_details", "search_plans"], "must": ["449"], "must_any": []},
    {"q": "What is the balance for 9876543210?",
     "tools_any": ["check_account_balance"], "must": ["450"], "must_any": []},
    {"q": "Check the balance for 12345",
     "tools_any": [], "must": [], "must_any": ["10", "ten"]},
    {"q": "Is 5G available in Mumbai?",
     "tools_any": ["check_network_status"], "must": [], "must_any": ["available"]},
    {"q": "I'm a heavy user, which plan should I take?",
     "tools_any": ["get_plan_recommendation", "search_plans", "get_plan_details"],
     "must": [], "must_any": ["Premium", "Elite"]},
    {"q": "Should I upgrade my plan? My number is 9000000001.",
     "tools_any": ["suggest_upgrade"], "must": [], "must_any": ["Elite"]},
    {"q": "Compare the Premium and Elite plans for me.",
     "tools_any": ["compare_plans", "search_plans", "get_plan_details"],
     "must": ["449", "899"], "must_any": []},
    {"q": "My bill is wrong and I want to make a complaint.",
     "tools_any": ["escalate_to_support"], "must": [], "must_any": ["ticket", "LAUKI"]},
    {"q": "How much is the Lauki Platinum 10GB plan?",
     "tools_any": [], "must": [], "must_any": []},  # price guardrail is the real test
    {"q": "Premium plan ki price kya hai?",
     "tools_any": [], "must": ["449"], "must_any": []},
]


def tools_called(messages) -> list:
    names = []
    for m in messages:
        if isinstance(m, AIMessage):
            names.extend(tc["name"] for tc in (m.tool_calls or []))
    return names


def run_case(case: dict, allowed: set) -> dict:
    start = time.perf_counter()
    try:
        result = lauki_agent.invoke({"messages": [("user", case["q"])]})
    except Exception as exc:  # keep going if one question fails (e.g. rate limit)
        return {"question": case["q"], "error": str(exc), "passed": False,
                "latency_s": round(time.perf_counter() - start, 2)}
    latency = time.perf_counter() - start

    msgs = result["messages"]
    answer = str(msgs[-1].content)
    called = tools_called(msgs)

    tool_ok = (not case["tools_any"]) or any(t in called for t in case["tools_any"])
    facts_ok = all(s.lower() in answer.lower() for s in case["must"]) and (
        not case["must_any"] or any(s.lower() in answer.lower() for s in case["must_any"]))
    bad_prices = find_unverified_prices(answer, allowed)
    price_ok = not bad_prices

    return {
        "question": case["q"], "answer": answer, "tools_called": called,
        "tool_ok": tool_ok, "facts_ok": facts_ok, "price_ok": price_ok,
        "unverified_prices": bad_prices, "latency_s": round(latency, 2),
        "passed": tool_ok and facts_ok and price_ok,
    }


def main() -> None:
    model = getattr(settings, "nebius_model", None) or getattr(settings, "groq_model", "unknown")
    allowed = allowed_prices(MOCK_PLANS_DB, MOCK_CUSTOMER_DB)
    print(f"Model: {model}\nRunning {len(CASES)} questions...\n")

    results = []
    for i, case in enumerate(CASES, 1):
        r = run_case(case, allowed)
        results.append(r)
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"[{mark}] {i}. {r['question']}  ({r['latency_s']}s)")
        if "error" in r:
            print(f"       error: {r['error']}")
        elif not r["passed"]:
            print(f"       tools={r['tools_called']} tool_ok={r['tool_ok']} "
                  f"facts_ok={r['facts_ok']} price_ok={r['price_ok']} "
                  f"bad_prices={r['unverified_prices']}")
            print(f"       answer: {r['answer'][:160]}")

    ok = [r for r in results if "error" not in r]
    lat = sorted(r["latency_s"] for r in ok)
    summary = {
        "model": model,
        "questions": len(results),
        "passed": sum(r["passed"] for r in results),
        "price_safe": sum(r.get("price_ok", False) for r in ok),
        "errors": len(results) - len(ok),
        "latency_avg_s": round(statistics.mean(lat), 2) if lat else None,
        "latency_median_s": round(statistics.median(lat), 2) if lat else None,
        "latency_max_s": lat[-1] if lat else None,
    }
    print("\n=== SUMMARY ===")
    for k, v in summary.items():
        print(f"{k}: {v}")

    with open("eval_results.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2, ensure_ascii=False)
    print("\nSaved eval_results.json")


if __name__ == "__main__":
    main()
