"""
Randomized ORID grounding fuzz tester.

Purpose:
- Generate diverse student inputs (grounded + fabricated + mixed + off-topic)
- Call /orid/writing-coach/chat using your real auth + session flow
- Report block/allow behavior and error cases quickly

Usage (from fastapi_backend):
  uv run python commands/run_orid_checker_fuzz.py --email orid.student@example.com --password OridTest2026!

Optional:
  --base-url http://localhost:8000
  --week 1
  --condition genai
  --per-category 12
  --seed 42
  --output-json fuzz_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
from dataclasses import asdict, dataclass
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()


@dataclass
class FuzzCase:
    category: str
    stage: str
    text: str
    expect_block: Optional[bool] = None


@dataclass
class FuzzResult:
    category: str
    stage: str
    text: str
    expect_block: Optional[bool]
    status_code: int
    blocked: Optional[bool]
    ok: bool
    ai_reply: str
    feedback_missing: list[str]
    feedback_suggestions: list[str]
    error: str = ""


def _split_clauses(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    parts = re.split(r"[。！？；，\n]+", raw)
    out = [p.strip() for p in parts if len(p.strip()) >= 4]
    return out


def _characters_from_book_pack(book_pack: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in (book_pack.get("characters") or [])[:20]:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                out.append(name)
        else:
            s = str(item or "").strip()
            if s:
                out.append(s)
    # fallback to avoid empty generation
    if not out:
        out = ["阿松爺爺", "哎唷奶奶", "小朋友"]
    return out


def _event_clauses_from_book_pack(book_pack: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for ev in (book_pack.get("key_events") or [])[:30]:
        out.extend(_split_clauses(ev))
    for ex in (book_pack.get("story_excerpts") or [])[:20]:
        out.extend(_split_clauses(ex))
    # de-dup keep order
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        uniq.append(x)
    if not uniq:
        uniq = ["阿松爺爺把柿子藏起來", "大家一起吃柿子", "最後一起撒種子"]
    return uniq


def _stage_for_category(rng: random.Random, category: str) -> str:
    if category in {"grounded_event", "fabricated_event", "mixed_true_false"}:
        return rng.choice(["O", "O", "R", "I", "D"])
    return rng.choice(["O", "R", "I", "D"])


def _build_cases(
    *,
    rng: random.Random,
    book_pack: dict[str, Any],
    per_category: int,
) -> list[FuzzCase]:
    chars = _characters_from_book_pack(book_pack)
    events = _event_clauses_from_book_pack(book_pack)

    fake_actions = [
        "去打籃球",
        "坐火箭去外太空",
        "突然過世",
        "跑去當總統",
        "跟外星人說話",
        "在夜店唱歌",
        "開飛船出國",
        "被機器人帶走",
    ]
    daily_topics = [
        "我今天午餐吃雞排便當",
        "昨天我去KTV唱歌",
        "我等一下要去打電動",
        "我剛剛在滑手機",
        "明天要考數學我好緊張",
        "我今天晚上要看球賽",
    ]

    cases: list[FuzzCase] = []
    categories = [
        "grounded_event",
        "fabricated_event",
        "mixed_true_false",
        "offtopic_daily",
        "short_ambiguous",
    ]
    for cat in categories:
        for _ in range(per_category):
            stage = _stage_for_category(rng, cat)
            if cat == "grounded_event":
                e = rng.choice(events)
                if stage == "R":
                    text = f"我覺得很有感覺，因為{e}"
                elif stage == "I":
                    text = f"這件事讓我明白要分享，因為{e}"
                elif stage == "D":
                    text = f"下次遇到類似情況，我會先想想{e}再做決定"
                else:
                    text = e
                cases.append(FuzzCase(cat, stage, text, expect_block=False))
                continue

            if cat == "fabricated_event":
                c = rng.choice(chars)
                a = rng.choice(fake_actions)
                if stage == "R":
                    text = f"我覺得很難過，因為{c}{a}"
                elif stage == "I":
                    text = f"我學到一件事，因為{c}{a}"
                elif stage == "D":
                    text = f"下次如果{c}{a}，我會先冷靜"
                else:
                    text = f"{c}{a}"
                cases.append(FuzzCase(cat, stage, text, expect_block=True))
                continue

            if cat == "mixed_true_false":
                true_part = rng.choice(events)
                c = rng.choice(chars)
                a = rng.choice(fake_actions)
                text = f"{true_part}，後來{c}{a}"
                cases.append(FuzzCase(cat, stage, text, expect_block=True))
                continue

            if cat == "offtopic_daily":
                text = rng.choice(daily_topics)
                cases.append(FuzzCase(cat, stage, text, expect_block=True))
                continue

            # short_ambiguous: weak signal; mark as unlabeled to inspect behavior drift
            text = rng.choice(["爺爺", "不知道", "嗯", "很難過", "我覺得", "分享"])
            cases.append(FuzzCase(cat, stage, text, expect_block=None))

    rng.shuffle(cases)
    return cases


def _is_blocked_feedback(resp: dict[str, Any]) -> bool:
    ai_reply = str(resp.get("ai_reply") or "")
    miss = [str(x) for x in (resp.get("feedback_missing") or [])]
    sug = [str(x) for x in (resp.get("feedback_suggestions") or [])]
    joined = "\n".join([ai_reply, *miss, *sug])
    return "對齊教材" in joined or "不像書裡發生" in joined


async def _login_get_token(client: httpx.AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"login failed: {resp.status_code} {resp.text}")
    obj = resp.json()
    token = str(obj.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("login succeeded but no access_token found")
    return token


async def _ensure_session(
    client: httpx.AsyncClient,
    *,
    token: str,
    week: int,
    condition: str,
) -> dict[str, Any]:
    resp = await client.post(
        "/orid/sessions/ensure",
        params={"week": week, "condition": condition, "force_new": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"ensure session failed: {resp.status_code} {resp.text}")
    return resp.json()


async def _read_book_pack(
    client: httpx.AsyncClient,
    *,
    token: str,
    reading_id: str,
) -> dict[str, Any]:
    resp = await client.get(
        f"/orid/readings/{reading_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"get reading failed: {resp.status_code} {resp.text}")
    reading = resp.json()
    content = str(reading.get("content") or "").strip()
    try:
        obj = json.loads(content)
    except Exception as e:
        raise RuntimeError(f"reading.content is not valid json: {e}") from e
    if not isinstance(obj, dict) or obj.get("schema") != "book_pack_v1":
        raise RuntimeError("reading.content is not a book_pack_v1 object")
    return obj


async def _run_one(
    client: httpx.AsyncClient,
    *,
    token: str,
    session_id: str,
    week: int,
    case: FuzzCase,
) -> FuzzResult:
    payload = {
        "session_id": session_id,
        "student_text": case.text,
        "stage": case.stage,
        "draft": "d1",
        "source": "feedback_button",
        "week": week,
        "save_feedback": False,
    }
    resp = await client.post(
        "/orid/writing-coach/chat",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        return FuzzResult(
            category=case.category,
            stage=case.stage,
            text=case.text,
            expect_block=case.expect_block,
            status_code=resp.status_code,
            blocked=None,
            ok=False,
            ai_reply="",
            feedback_missing=[],
            feedback_suggestions=[],
            error=resp.text[:500],
        )
    data = resp.json()
    blocked = _is_blocked_feedback(data)
    ok = (case.expect_block is None) or (blocked == case.expect_block)
    return FuzzResult(
        category=case.category,
        stage=case.stage,
        text=case.text,
        expect_block=case.expect_block,
        status_code=200,
        blocked=blocked,
        ok=ok,
        ai_reply=str(data.get("ai_reply") or ""),
        feedback_missing=[str(x) for x in (data.get("feedback_missing") or [])],
        feedback_suggestions=[str(x) for x in (data.get("feedback_suggestions") or [])],
    )


def _print_report(results: list[FuzzResult]) -> None:
    labeled = [r for r in results if r.expect_block is not None and r.status_code == 200]
    errors = [r for r in results if r.status_code != 200]
    unlabeled = [r for r in results if r.expect_block is None and r.status_code == 200]

    print("\n=== ORID Checker Fuzz Report ===")
    print(f"total cases      : {len(results)}")
    print(f"labeled evaluated: {len(labeled)}")
    print(f"unlabeled        : {len(unlabeled)}")
    print(f"http errors      : {len(errors)}")

    if labeled:
        passed = sum(1 for r in labeled if r.ok)
        print(f"overall pass rate: {passed}/{len(labeled)} = {passed / len(labeled):.1%}")

    by_cat: dict[str, list[FuzzResult]] = {}
    for r in labeled:
        by_cat.setdefault(r.category, []).append(r)
    for cat in sorted(by_cat):
        arr = by_cat[cat]
        passed = sum(1 for r in arr if r.ok)
        block_rate = sum(1 for r in arr if r.blocked) / len(arr) if arr else 0
        print(f"- {cat:20s} pass={passed:>3}/{len(arr):<3} block_rate={block_rate:.1%}")

    mismatches = [r for r in labeled if not r.ok][:12]
    if mismatches:
        print("\n--- sample mismatches ---")
        for i, r in enumerate(mismatches, 1):
            print(f"[{i}] category={r.category} stage={r.stage} expect_block={r.expect_block} got_block={r.blocked}")
            print(f"    text: {r.text}")
            print(f"    missing: {r.feedback_missing[:1]}")
            print(f"    ai: {r.ai_reply[:120].replace(chr(10), ' ')}")

    if errors:
        print("\n--- sample http errors ---")
        for i, r in enumerate(errors[:8], 1):
            print(f"[{i}] status={r.status_code} category={r.category} stage={r.stage}")
            print(f"    text: {r.text}")
            print(f"    error: {r.error[:180]}")


async def main() -> None:
    p = argparse.ArgumentParser(description="Randomized ORID grounding fuzz runner.")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--email", required=True, help="Test account email")
    p.add_argument("--password", required=True, help="Test account password")
    p.add_argument("--week", type=int, default=1)
    p.add_argument(
        "--condition",
        default="genai",
        choices=["genai", "control", "template"],
        help="Session condition for this fuzz run",
    )
    p.add_argument("--per-category", type=int, default=10, help="Cases per category")
    p.add_argument("--seed", type=int, default=20260428)
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--output-json", default="", help="Optional path to save full result JSON")
    args = p.parse_args()

    rng = random.Random(args.seed)
    timeout = httpx.Timeout(args.timeout, connect=args.timeout)
    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), timeout=timeout) as client:
        token = await _login_get_token(client, args.email, args.password)
        sess = await _ensure_session(
            client,
            token=token,
            week=args.week,
            condition=args.condition,
        )
        session_id = str(sess.get("id") or "")
        reading_id = str(sess.get("reading_id") or "")
        if not session_id or not reading_id:
            raise RuntimeError("session ensure response missing id/reading_id")

        pack = await _read_book_pack(client, token=token, reading_id=reading_id)
        print(f"book_title={pack.get('book_title')} | events={len(pack.get('key_events') or [])}")

        cases = _build_cases(rng=rng, book_pack=pack, per_category=args.per_category)
        results: list[FuzzResult] = []
        for c in cases:
            r = await _run_one(
                client,
                token=token,
                session_id=session_id,
                week=args.week,
                case=c,
            )
            results.append(r)

    _print_report(results)

    if args.output_json:
        payload = {
            "summary": {
                "total": len(results),
                "labeled": sum(1 for x in results if x.expect_block is not None and x.status_code == 200),
                "http_errors": sum(1 for x in results if x.status_code != 200),
            },
            "results": [asdict(r) for r in results],
        }
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\njson report saved: {args.output_json}")


if __name__ == "__main__":
    asyncio.run(main())
