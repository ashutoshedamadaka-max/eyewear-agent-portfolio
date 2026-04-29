"""
Eval Harness v3 - testing personality + follow-up handling
-----------------------------------------------------------
Adds these new metrics to the v2 suite:

8. PERSONALITY CONSISTENCY (LLM judge) - does the reply sound like Specs,
   not a generic AI assistant? Penalizes banned phrases.
9. FOLLOW-UP HANDLING (LLM judge) - when user asks a follow-up question
   about prior recommendations, does the agent stay in context and answer
   substantively?

Also adds 3 new test cases that simulate multi-turn conversations where
the user asks follow-up questions AFTER a recommendation.

Why this matters for your portfolio:
You can now show "v2 vs v3" deltas: same agent core, but personality and
conversation flow upgraded. Eval scores quantify the improvement. This is
the most senior-PM signal in your case study - measurable iteration.
"""

import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from agent import EyewearAgent, load_catalog, get_client

API_KEY = os.environ.get("OPENAI_API_KEY", "")
JUDGE_MODEL = "gpt-4o-mini"
CATALOG_PATH = "lenskart_catalogue.json"


# ---------- Test Case Schema ----------
@dataclass
class TestCase:
    id: str
    description: str
    turns: list[str]
    expected_behavior: str  # "recommend", "clarify", or "followup"
    max_budget_inr: Optional[int] = None
    expected_category: Optional[str] = None
    expected_use_case: Optional[str] = None
    expected_brand: Optional[str] = None
    # v3 additions
    is_followup_test: bool = False
    expected_topic: Optional[str] = None  # for follow-up cases


# ---------- Test Suite ----------
TEST_CASES = [
    # --- v2 cases (still apply) ---
    TestCase(
        id="T01_clear_sunglasses_with_budget",
        description="Clear intent + budget -> recommend immediately.",
        turns=["I need sunglasses for outdoor sports under 2500 rupees"],
        expected_behavior="recommend",
        max_budget_inr=2500, expected_category="Sunglasses", expected_use_case="Sports",
    ),
    TestCase(
        id="T02_vague_query",
        description="Vague query -> ask clarifying question.",
        turns=["I want to buy glasses"],
        expected_behavior="clarify",
    ),
    TestCase(
        id="T03_office_wear",
        description="Office work -> recommend Eyeglasses for Office.",
        turns=["Looking for eyeglasses for office work, budget 2000 INR"],
        expected_behavior="recommend",
        max_budget_inr=2000, expected_category="Eyeglasses", expected_use_case="Office",
    ),
    TestCase(
        id="T04_brand_specific",
        description="Brand-specific request -> only that brand.",
        turns=["Show me John Jacobs eyeglasses for daily wear"],
        expected_behavior="recommend",
        expected_category="Eyeglasses", expected_use_case="Daily", expected_brand="John Jacobs",
    ),
    TestCase(
        id="T05_multi_turn_gathering",
        description="Multi-turn gathering then recommendation.",
        turns=[
            "I need new glasses",
            "For working on my computer, I get eye strain",
            "Around 1800 rupees max",
        ],
        expected_behavior="recommend",
        max_budget_inr=1800, expected_category="Eyeglasses", expected_use_case="Office",
    ),
    TestCase(
        id="T06_impossible_budget",
        description="Impossible budget -> honest no-match, not invention.",
        turns=["I want sunglasses under 500 rupees"],
        expected_behavior="recommend",
        max_budget_inr=500,
    ),
    TestCase(
        id="T07_fashion_sunglasses",
        description="Fashion focus -> Sunglasses for Fashion/Social.",
        turns=["I want trendy sunglasses for parties and events, around 3000 rupees"],
        expected_behavior="recommend",
        max_budget_inr=3000, expected_category="Sunglasses", expected_use_case="Fashion",
    ),
    TestCase(
        id="T08_driving_sunglasses",
        description="Driving use case.",
        turns=["Need sunglasses for daily driving, budget 2500"],
        expected_behavior="recommend",
        max_budget_inr=2500, expected_category="Sunglasses", expected_use_case="Driving",
    ),
    TestCase(
        id="T09_lens_specific",
        description="Specific lens preference.",
        turns=["I need eyeglasses with blue cut lenses for long screen hours, under 2000"],
        expected_behavior="recommend",
        max_budget_inr=2000, expected_category="Eyeglasses", expected_use_case="Office",
    ),
    TestCase(
        id="T10_premium_request",
        description="Premium / no budget cap.",
        turns=["Show me premium titanium eyeglasses, money no object"],
        expected_behavior="recommend",
        expected_category="Eyeglasses", expected_use_case="Premium",
    ),
    # --- NEW v3 cases: follow-up handling ---
    TestCase(
        id="T11_followup_color_question",
        description="After recommendation, user asks about colors -> must stay in context.",
        turns=[
            "I need sunglasses for driving, around 2000 rupees",
            "Does the first one come in tortoise?",
        ],
        expected_behavior="followup",
        is_followup_test=True,
        expected_topic="color availability",
    ),
    TestCase(
        id="T12_followup_comparison",
        description="User asks for comparison -> agent should give an opinion.",
        turns=[
            "I want eyeglasses for office work under 2500",
            "Which one would you actually pick between these two?",
        ],
        expected_behavior="followup",
        is_followup_test=True,
        expected_topic="comparison / opinion",
    ),
    TestCase(
        id="T13_followup_lens_upgrade",
        description="User asks about lens upgrade -> agent should explain trade-off.",
        turns=[
            "I need eyeglasses for screens, budget 2000",
            "Is the blue cut upgrade actually worth it?",
        ],
        expected_behavior="followup",
        is_followup_test=True,
        expected_topic="lens upgrade trade-off",
    ),
]


# ---------- Rule-Based Metrics (unchanged from v2) ----------
def check_catalog_adherence(reply: str, recommended_ids: list[str], catalog: list[dict]) -> dict:
    valid_ids = {p["product_id"] for p in catalog}
    invalid = [pid for pid in recommended_ids if pid not in valid_ids]
    return {"passed": len(invalid) == 0, "invalid_ids": invalid,
            "recommended_count": len(recommended_ids)}


def check_budget_adherence(recommended_ids: list[str], max_budget: Optional[int],
                           catalog: list[dict]) -> dict:
    if not max_budget:
        return {"passed": True, "skipped": True}
    by_id = {p["product_id"]: p for p in catalog}
    over = [pid for pid in recommended_ids if by_id.get(pid, {}).get("price", 0) > max_budget]
    return {"passed": len(over) == 0, "over_budget_ids": over, "max_budget": max_budget}


def check_category_adherence(recommended_ids: list[str], expected: Optional[str],
                             catalog: list[dict]) -> dict:
    if not expected:
        return {"passed": True, "skipped": True}
    by_id = {p["product_id"]: p for p in catalog}
    wrong = [pid for pid in recommended_ids if by_id.get(pid, {}).get("category") != expected]
    return {"passed": len(wrong) == 0, "wrong_category_ids": wrong, "expected": expected}


def check_brand_adherence(recommended_ids: list[str], expected: Optional[str],
                          catalog: list[dict]) -> dict:
    if not expected:
        return {"passed": True, "skipped": True}
    by_id = {p["product_id"]: p for p in catalog}
    wrong = [pid for pid in recommended_ids if by_id.get(pid, {}).get("brand") != expected]
    return {"passed": len(wrong) == 0, "wrong_brand_ids": wrong, "expected": expected}


def check_clarification_behavior(reply: str, expected: str) -> dict:
    has_q = "?" in reply
    if expected == "clarify":
        return {"passed": has_q, "expected": "clarify", "got_question": has_q}
    return {"passed": True, "expected": expected, "note": "any reply acceptable"}


# ---------- v3 NEW: Banned-Phrase Check (deterministic personality check) ----------
BANNED_PHRASES = [
    "i'd be happy to help",
    "i would be happy to help",
    "great question",
    "wonderful!",
    "based on your needs",
    "i understand you're looking",
    "i understand that you",
    "as an ai",
    "to better assist you",
]


def check_banned_phrases(reply: str) -> dict:
    """Deterministic check: does the reply contain corporate-AI phrases?"""
    reply_lower = reply.lower()
    found = [p for p in BANNED_PHRASES if p in reply_lower]
    return {"passed": len(found) == 0, "found_phrases": found}


# ---------- LLM-as-Judge Metrics ----------
JUDGE_USE_CASE_SYSTEM = """Score 1-5 on whether the recommendation fits the user's stated use case.
Return JSON: {"score": N, "reasoning": "one sentence"}
5=perfect, 4=good, 3=acceptable, 2=poor, 1=irrelevant"""

JUDGE_QUALITY_SYSTEM = """Score 1-5 on warmth, conciseness (under 200 words), and helpfulness.
Return JSON: {"score": N, "reasoning": "one sentence"}"""

# v3 NEW
JUDGE_PERSONALITY_SYSTEM = """You're evaluating whether an eyewear shopping agent has a distinct personality
or sounds like a generic AI assistant.

The agent's intended voice: "Specs" - quirky expert, witty, conversational, uses contractions,
has opinions, light dry humor when natural. Avoids: "I'd be happy to help", "Great question",
"based on your needs", excessive exclamation marks, listing every feature.

Score 1-5:
5 = Strong distinctive personality, clearly NOT a generic assistant. Has opinions, voice shines through.
4 = Mostly in character, minor slips into generic territory.
3 = Acceptable but neutral - functional but not memorable.
2 = Sounds mostly like a generic AI assistant.
1 = Pure corporate/AI assistant tone, no personality.

Return JSON: {"score": N, "reasoning": "one sentence pointing to specific phrases"}"""

# v3 NEW
JUDGE_FOLLOWUP_SYSTEM = """You're evaluating whether an agent properly handled a follow-up question.

A good follow-up response:
- Stays in context about the previously discussed products
- Answers the actual question substantively (not deflects to a new search)
- Gives an opinion when asked ("which would you pick?")
- Uses catalog data when answering about colors, lens options, etc.

Score 1-5:
5 = Answered the follow-up directly and substantively, in context.
4 = Answered well, minor issues.
3 = Partially answered, some context drift.
2 = Mostly missed the question or restarted the conversation.
1 = Completely failed to handle as a follow-up.

Return JSON: {"score": N, "reasoning": "one sentence"}"""


def llm_judge(system: str, user_msg: str) -> dict:
    if not API_KEY:
        return {"score": 0, "reasoning": "API key not set", "skipped": True}
    try:
        client = get_client()
        response = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user_msg}],
            response_format={"type": "json_object"}, temperature=0.1,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"score": 0, "reasoning": f"Judge error: {e}", "error": True}


# ---------- Run a Single Test Case ----------
def run_test_case(test: TestCase, catalog: list[dict]) -> dict:
    agent = EyewearAgent(CATALOG_PATH)
    final_result = None
    all_replies = []
    start_time = time.time()

    for turn in test.turns:
        final_result = agent.chat(turn)
        all_replies.append(final_result["reply"])

    latency = time.time() - start_time
    final_reply = final_result["reply"]
    recommended_ids = final_result.get("recommended_ids", [])

    metrics = {
        "test_id": test.id,
        "description": test.description,
        "user_turns": test.turns,
        "all_replies": all_replies,
        "turns_used": len(test.turns),
        "latency_sec": round(latency, 2),
        "final_reply": final_reply,
        "recommended_ids": recommended_ids,
        "path_taken": final_result.get("path", "unknown"),
        "catalog_adherence": check_catalog_adherence(final_reply, recommended_ids, catalog),
        "budget_adherence": check_budget_adherence(recommended_ids, test.max_budget_inr, catalog),
        "category_adherence": check_category_adherence(recommended_ids, test.expected_category, catalog),
        "brand_adherence": check_brand_adherence(recommended_ids, test.expected_brand, catalog),
        "clarification_behavior": check_clarification_behavior(final_reply, test.expected_behavior),
        "banned_phrases": check_banned_phrases(final_reply),
    }

    # Use-case fit (only if recommendations were made)
    if test.expected_use_case and recommended_ids:
        ji = f"User's stated use case: {test.expected_use_case}\n\nAgent's recommendation:\n{final_reply}"
        metrics["use_case_fit"] = llm_judge(JUDGE_USE_CASE_SYSTEM, ji)
    else:
        metrics["use_case_fit"] = {"skipped": True}

    # Conversation quality (always)
    ji = f"User's message: {test.turns[-1]}\nAssistant's reply: {final_reply}"
    metrics["conversation_quality"] = llm_judge(JUDGE_QUALITY_SYSTEM, ji)

    # v3 NEW: personality consistency (always)
    ji = f"Agent reply to evaluate:\n{final_reply}"
    metrics["personality_consistency"] = llm_judge(JUDGE_PERSONALITY_SYSTEM, ji)

    # v3 NEW: follow-up handling (only if it's a follow-up test)
    if test.is_followup_test:
        ji = (
            f"Conversation:\n"
            + "\n".join(
                f"{'User' if i % 2 == 0 else 'Agent'}: "
                f"{test.turns[i//2] if i % 2 == 0 else all_replies[i//2]}"
                for i in range(len(test.turns) + len(all_replies))
                if i // 2 < max(len(test.turns), len(all_replies))
            )
            + f"\n\nThe user's follow-up question was: {test.turns[-1]}\n"
            + f"The agent's final reply was:\n{final_reply}\n\n"
            + f"Topic the user was asking about: {test.expected_topic}"
        )
        metrics["followup_handling"] = llm_judge(JUDGE_FOLLOWUP_SYSTEM, ji)
    else:
        metrics["followup_handling"] = {"skipped": True}

    return metrics


# ---------- Aggregate Report ----------
def generate_report(results: list[dict]) -> str:
    total = len(results)
    if not total:
        return "# No results\n"

    def pass_rate(metric_key):
        count = sum(1 for r in results
                    if r.get(metric_key, {}).get("skipped")
                    or r.get(metric_key, {}).get("passed"))
        return count, count * 100 // total

    catalog_pass, catalog_pct = pass_rate("catalog_adherence")
    budget_pass, budget_pct = pass_rate("budget_adherence")
    category_pass, category_pct = pass_rate("category_adherence")
    brand_pass, brand_pct = pass_rate("brand_adherence")
    clarify_pass, clarify_pct = pass_rate("clarification_behavior")
    banned_pass, banned_pct = pass_rate("banned_phrases")

    use_case_scores = [r["use_case_fit"]["score"] for r in results
                       if not r["use_case_fit"].get("skipped") and r["use_case_fit"].get("score")]
    quality_scores = [r["conversation_quality"]["score"] for r in results
                      if not r["conversation_quality"].get("skipped")
                      and r["conversation_quality"].get("score")]
    personality_scores = [r["personality_consistency"]["score"] for r in results
                          if not r["personality_consistency"].get("skipped")
                          and r["personality_consistency"].get("score")]
    followup_scores = [r["followup_handling"]["score"] for r in results
                       if not r["followup_handling"].get("skipped")
                       and r["followup_handling"].get("score")]

    avg_latency = sum(r["latency_sec"] for r in results) / total

    def avg(lst, n):
        return f"{sum(lst)/len(lst):.2f}/5 (n={n})" if lst else "N/A"

    report = f"""# Eyewear Agent v3 - Eval Report

## Summary
- **Total test cases:** {total} (10 from v2 + 3 new follow-up tests)
- **Avg latency per test:** {avg_latency:.2f}s

## Metric Scores

| Metric | Score | Type |
|---|---|---|
| Catalog adherence (no hallucinated products) | {catalog_pass}/{total} ({catalog_pct}%) | Hard rule |
| Budget adherence | {budget_pass}/{total} ({budget_pct}%) | Hard rule |
| Category adherence | {category_pass}/{total} ({category_pct}%) | Hard rule |
| Brand adherence | {brand_pass}/{total} ({brand_pct}%) | Hard rule |
| No banned corporate phrases | {banned_pass}/{total} ({banned_pct}%) | Hard rule (NEW) |
| Correct clarify-vs-recommend | {clarify_pass}/{total} ({clarify_pct}%) | Heuristic |
| Use-case fit (LLM judge) | {avg(use_case_scores, len(use_case_scores))} | LLM judge |
| Conversation quality (LLM judge) | {avg(quality_scores, len(quality_scores))} | LLM judge |
| **Personality consistency (LLM judge)** | {avg(personality_scores, len(personality_scores))} | LLM judge (NEW) |
| **Follow-up handling (LLM judge)** | {avg(followup_scores, len(followup_scores))} | LLM judge (NEW) |

## Per-Case Results

"""
    for r in results:
        report += f"### {r['test_id']}: {r['description']}\n\n"
        report += f"**Path taken:** {r.get('path_taken', 'unknown')}\n\n"
        preview = r["final_reply"][:400] + "..." if len(r["final_reply"]) > 400 else r["final_reply"]
        report += f"**Reply:** {preview}\n\n"
        report += f"- Recommended IDs: `{r['recommended_ids']}`\n"

        for key, label in [
            ("catalog_adherence", "Catalog adherence"),
            ("budget_adherence", "Budget adherence"),
            ("category_adherence", "Category adherence"),
            ("brand_adherence", "Brand adherence"),
            ("banned_phrases", "No banned phrases"),
            ("clarification_behavior", "Clarification"),
        ]:
            m = r.get(key, {})
            if m.get("skipped"):
                report += f"- {label}: N/A\n"
            else:
                status = "PASS" if m.get("passed") else "FAIL"
                report += f"- {label}: {status}"
                if not m.get("passed"):
                    if "found_phrases" in m: report += f" (found: {m['found_phrases']})"
                    if "invalid_ids" in m: report += f" (invalid: {m['invalid_ids']})"
                    if "over_budget_ids" in m: report += f" (over: {m['over_budget_ids']})"
                    if "wrong_category_ids" in m: report += f" (wrong: {m['wrong_category_ids']})"
                    if "wrong_brand_ids" in m: report += f" (wrong: {m['wrong_brand_ids']})"
                report += "\n"

        for key, label in [
            ("use_case_fit", "Use-case fit"),
            ("conversation_quality", "Conversation quality"),
            ("personality_consistency", "Personality"),
            ("followup_handling", "Follow-up handling"),
        ]:
            m = r.get(key, {})
            if not m.get("skipped"):
                report += f"- {label}: {m.get('score', 'n/a')}/5 - {m.get('reasoning', '')}\n"

        report += f"- Latency: {r['latency_sec']}s\n\n---\n\n"

    return report


# ---------- Main ----------
def main():
    if not API_KEY:
        print("WARNING: OPENAI_API_KEY not set.\n")

    catalog = load_catalog(CATALOG_PATH)
    print(f"Loaded {len(catalog)} products from {CATALOG_PATH}")
    print(f"Running {len(TEST_CASES)} test cases (v3 with personality + follow-up)...\n")

    results = []
    for i, test in enumerate(TEST_CASES, 1):
        print(f"[{i}/{len(TEST_CASES)}] {test.id}")
        try:
            result = run_test_case(test, catalog)
            results.append(result)
            print(f"   path: {result['path_taken']}, "
                  f"recs: {result['recommended_ids']}, "
                  f"latency: {result['latency_sec']}s")
        except Exception as e:
            print(f"   ERROR: {e}")
            results.append({"test_id": test.id, "error": str(e)})

    with open("eval_results.json", "w") as f:
        json.dump(results, f, indent=2)

    valid = [r for r in results if "error" not in r]
    if valid:
        report = generate_report(valid)
        with open("eval_report.md", "w") as f:
            f.write(report)
        print("\nSaved eval_results.json and eval_report.md")


if __name__ == "__main__":
    main()
