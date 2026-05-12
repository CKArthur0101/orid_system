from __future__ import annotations

from typing import Any, Optional, Tuple
import re

from app.prompts.templates.writing_feedback import (
    BOOK_FACT_RULES,
    FEW_SHOT_BLOCK,
    SHARED_CORE,
    STAGE_BLOCKS,
)


def _format_writing_rubric_for_prompt(book_pack: Optional[dict[str, Any]], stage: str) -> str:
    """
    Optional book_pack key: writing_rubric (schema writing_rubric_v1 recommended).
    Supports two formats for `levels`:
      - Old: list of strings ["1 起步", "2 接近", ...]
      - New: list of dicts  [{"label": "1 起步", "desc": "..."}, ...]
    """
    if not isinstance(book_pack, dict):
        return ""
    raw = book_pack.get("writing_rubric")
    if not isinstance(raw, dict):
        return ""
    by_stage = raw.get("by_stage")
    if not isinstance(by_stage, dict):
        return ""
    items = by_stage.get(stage) or by_stage.get((stage or "O").strip().upper())
    if not isinstance(items, list) or not items:
        return ""

    lines: list[str] = [
        "【評量標準（ok=true ← 層級3達標或4精進；ok=false ← 層級1或2）】",
    ]
    for it in items[:4]:
        if not isinstance(it, dict):
            continue
        rid = str(it.get("id") or "").strip()
        name = str(it.get("name") or "").strip()
        levels = it.get("levels")
        if not name:
            continue
        lv_parts: list[str] = []
        if isinstance(levels, list):
            for lv in levels[:4]:
                label = str(lv.get("label") if isinstance(lv, dict) else lv).strip()
                if label:
                    lv_parts.append(label)
        rid_tag = f"[{rid}]" if rid else ""
        lv_str = "／".join(lv_parts) if lv_parts else ""
        lines.append(f"- {rid_tag}{name}" + (f"：{lv_str}" if lv_str else ""))

    lines.append("rubric_focus=向度id，rubric_level_estimate=最接近層級標籤")
    return "\n".join(lines)


def _excerpts_for_prompt(
    book_pack: Optional[dict[str, Any]],
    max_items: int = 5,
    max_chars: int = 900,
    student_text: str = "",
) -> str:
    ex = (book_pack or {}).get("story_excerpts") or []
    if not isinstance(ex, list):
        return "（未提供摘錄）"

    parsed: list[tuple[Optional[int], str]] = []
    for x in ex:
        if isinstance(x, dict):
            page = x.get("page")
            text = str(x.get("text") or "").strip()
            if text and "（無文字）" not in text:
                parsed.append((page, text))
        else:
            s = str(x).strip()
            if s:
                parsed.append((None, s))

    if not parsed:
        return "（未提供摘錄）"

    if student_text and len(parsed) > max_items:
        student_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}", student_text))

        def _score(entry: tuple) -> int:
            _, t = entry
            t_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}", t))
            return len(student_tokens & t_tokens)

        sorted_parsed = sorted(enumerate(parsed), key=lambda iv: _score(iv[1]), reverse=True)
        top_indices = {i for i, _ in sorted_parsed[:max_items]}
        top_indices.update(range(min(2, len(parsed))))
        selected = [parsed[i] for i in sorted(top_indices)][:max_items]
    else:
        selected = parsed[:max_items]

    lines: list[str] = []
    for page, text in selected:
        s = f"[P{page}] {text}" if page is not None else text
        lines.append(s)

    blob = "\n".join(f"・{l}" for l in lines)
    if len(blob) > max_chars:
        return blob[: max_chars - 1] + "…"
    return blob


def _characters_for_prompt(book_pack: Optional[dict[str, Any]]) -> str:
    chars = (book_pack or {}).get("characters") or []
    if not isinstance(chars, list) or not chars:
        return "（未提供角色清單）"
    lines: list[str] = []
    for c in chars:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "").strip()
        role = str(c.get("role") or "").strip()
        if name:
            lines.append(f"「{name}」：{role}" if role else f"「{name}」")
    return "、".join(lines) if lines else "（未提供角色清單）"


def build_genai_feedback_prompts(
    *,
    stage: str,
    text: str,
    book_pack: Optional[dict[str, Any]],
) -> Tuple[str, str]:
    """
    兩層：共用核心 + 依 O/R/I/D 分流。
    輸出純 JSON：praise, missing(≤1), suggestions(≤1), example, improved(多為 null)
    """
    stage = stage if stage in {"O", "R", "I", "D"} else "O"
    book_title = (book_pack or {}).get("book_title", "本週繪本")
    guide = ((book_pack or {}).get("writing_guide", {}) or {}).get(stage, "")
    key_events = (book_pack or {}).get("key_events", [])
    key_events_str = "\n".join(f"・{x}" for x in key_events) if key_events else "（未提供摘要）"
    excerpts_block = _excerpts_for_prompt(book_pack, student_text=text)
    characters_block = _characters_for_prompt(book_pack)
    stage_block = STAGE_BLOCKS.get(stage, STAGE_BLOCKS["O"])
    rubric_block = _format_writing_rubric_for_prompt(book_pack, stage)

    book_fact_section = "" if stage == "D" else f"""
{BOOK_FACT_RULES}

【教材不符時的回饋要求】
學生寫了書中沒有或對不上的事 → ok 為 false；missing 要**點名是哪個詞或哪件事**看起來不在書裡，並用「書裡說的是『……』」這樣的說法引一句最接近的書中內容讓學生對照；**禁止**用「對照摘要句」「對照摘錄句」等術語。suggestions 引導學生對照那句書中內容改寫，仍**不要幫寫整段**。
""".strip()

    system_prompt = f"""
你是國小五、六年級的 ORID 寫作回饋老師。下面分兩層：先**共用規則**，再**本段專屬規則**。請只輸出 JSON，不要廢話。

====================
一、共用核心規則
====================
{SHARED_CORE}

{book_fact_section}

【教材僅能由此來，不可編造情節】
書名：{book_title}
{"角色清單（學生寫的角色名必須對照這裡）：" + characters_block if stage != "D" else "書名已知；D 段不做角色名查核。"}
{"故事摘要：" + chr(10) + key_events_str if stage != "D" else "（D 段：故事摘要僅供背景參考，不要要求學生對齊書本情節。）"}
{"故事摘錄（可以直接引用句子來引導學生）：" + chr(10) + excerpts_block if stage != "D" else ""}
教師本段說明：{guide or "（未提供）"}
{rubric_block if rubric_block else "（本週未提供 writing_rubric；仍依本段專屬規則回饋。）"}

【語氣與長度感】
整體不要太長，但要讓學生看完就知道下一步怎麼補，讀起來像老師在旁邊一步一步帶寫。
用字要適合國小五、六年級：短句、口語、容易懂。不要用「深化、完整度、精準、論述、脈絡、可執行」這類太大人的詞。
尤其 suggestions 與 example 不能只丟一句很空的提醒，要能真的幫學生往下寫。

====================
二、本段專屬：{stage}
====================
{stage_block}

====================
三、JSON 欄位與品質
====================
- praise：**必須**看得出你有讀學生原文，盡量點到裡面的人/事/詞（若完全空白再用鼓勵下筆，禁止空泛罐頭讚美）。
- missing：不多於 1 條，對準本段一個主問題。
- suggestions：不多於 1 條，可以 1–2 句；第一句先說「要補什麼」，第二句再說「可以怎麼補」，最好帶有「你可以先……」「再……」這種一步一步的口氣，避免只有抽象提醒。
- example：給 1–2 句與學生原文貼近的續寫小例子，幫學生看懂可以怎麼寫；語氣要像老師示範起頭，不要整篇代寫，但也不要只丟一句空的句型。
- improved：通常 null。

【輸出格式】只輸出純 JSON，不要 markdown，不要 ```。
{{
  "ok": boolean,
  "praise": string,
  "missing": string[],
  "suggestions": string[],
  "example": string,
  "improved": null,
  "rubric_focus": string or null,
  "rubric_level_estimate": string or null
}}
- rubric_focus：本輪回饋主要對準的評量向度（有提供 writing_rubric 時填 id 或名稱；沒有則可 null）。
- rubric_level_estimate：依該向度估計學生草稿接近哪一層（用向度裡的層級用語；沒把握可 null）。

{FEW_SHOT_BLOCK}
""".strip()

    user_prompt = f"""
學生「{stage}」段原文如下（你回饋時稱讚要對準這些字，不要重複罐頭句）：

---
{text}
---

請輸出 JSON。missing 與 suggestions 陣列各至多只放 1 個字串。請用國小五、六年級看得懂的口吻。example 請給可直接接著寫的具體小例子。improved 多數情況為 null。
""".strip()

    return system_prompt, user_prompt
