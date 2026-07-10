from __future__ import annotations

from typing import Any, Optional, Tuple
import re

from app.prompts.policy.student_input_bucket import (
    BUCKET_EMPTY,
    BUCKET_TOO_SHORT,
    bucket_tone_hint_zh,
)
from app.prompts.templates.writing_feedback import (
    BOOK_FACT_RULES,
    FEW_SHOT_BLOCK,
    SHARED_CORE,
    STAGE_BLOCKS,
)
from app.services.rag import format_rag_context_for_prompt


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
        "【ORID 主要評量標準（ok=true ← 層級3達標或4精進；ok=false ← 層級1或2）】",
        "ok 只依 ORID 本段標準判斷；SEL 只能輔助提問，不能改變 ok。",
        "計分採累加制：達到第 n 階 = 1+2+…+n 分（第1階=1, 第2階=3, 第3階=6, 第4階=10）。",
    ]
    for it in items[:4]:
        if not isinstance(it, dict):
            continue
        rid = str(it.get("id") or "").strip()
        name = str(it.get("name") or "").strip()
        focus = str(it.get("focus") or "").strip()
        levels = it.get("levels")
        if not name:
            continue
        lv_parts: list[str] = []
        if isinstance(levels, list):
            for lv in levels[:4]:
                label = str(lv.get("label") if isinstance(lv, dict) else lv).strip()
                desc = str(lv.get("desc") if isinstance(lv, dict) else "").strip()
                if label:
                    lv_parts.append(f"{label}：{desc}" if desc else label)
        rid_tag = f"[{rid}]" if rid else ""
        lv_str = "\n  ".join(lv_parts) if lv_parts else ""
        head = f"- {rid_tag}{name}" + (f"（評量重點：{focus}）" if focus else "")
        lines.append(head + (f"：{lv_str}" if lv_str else ""))

    lines.append("rubric_focus=本段 ORID 主向度id（必填，不可 null）；rubric_level_estimate=依段填多向度物件（見 JSON 格式）")
    return "\n".join(lines)


def _format_sel_guidance_for_prompt(book_pack: Optional[dict[str, Any]], stage: str) -> str:
    if not isinstance(book_pack, dict):
        return ""
    raw = book_pack.get("sel_rubric")
    if not isinstance(raw, dict):
        return ""
    by_stage = raw.get("by_stage")
    if not isinstance(by_stage, dict):
        return ""

    stage = (stage or "O").strip().upper()
    items = by_stage.get(stage) or []
    if stage == "O" or not isinstance(items, list) or not items:
        return (
            "【SEL 輔助引導（本段）】\n"
            "O 段不使用 SEL 輔助；只看故事人物、事件與前後變化。"
        )

    lines: list[str] = [
        "【SEL 輔助引導（只給 AI 內部使用，不取代 ORID 判斷）】",
        "SEL 只能幫你選一個友善問題；ok 只依 ORID 本段 rubric 判斷。",
        "不要在給學生的文字中直接使用「SEL」或「情緒覺察」「同理與觀點理解」「價值反思」「負責任行動」等術語。",
        "請把 SEL 轉成國小五、六年級看得懂的具體問題；每次最多用一個方向。",
    ]
    for it in items[:3]:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        focus = str(it.get("focus") or "").strip()
        prompts = [str(x).strip() for x in (it.get("student_prompts") or []) if str(x).strip()]
        if not name and not prompts:
            continue
        lines.append(f"- 內部參考：{name}" + (f"（{focus}）" if focus else ""))
        for p in prompts[:2]:
            lines.append(f"  可轉成問題：{p}")
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


_O_STUCK_HINT_PHRASES: tuple[str, ...] = (
    "還不會",
    "不會寫",
    "不知道怎麼寫",
    "不懂怎麼寫",
    "不知道要寫",
    "寫不出",
    "不會下筆",
    "我不知道",
    "不知道誰",
    "不懂誰",
    "分不清誰",
    "誰做了什麼",  # 常見 meta：「我不知道誰做了什麼」
    "想不起來",
)


_STAGE_RUBRIC_LEVEL_KEYS: dict[str, str] = {
    "O": '"O1": "X 層級"',
    "R": '"R1": "X 層級", "SEL_EA": "X 層級", "SEL_PT": "X 層級"',
    "I": '"I1": "X 層級", "SEL_VR": "X 層級", "SEL_PT": "X 層級"',
    "D": '"D1": "X 層級", "SEL_RA": "X 層級"',
}


def _rasf_json_format_block(stage: str) -> str:
    """RASF-Anchor 規則：多向度估層級 + 原文錨點引導。"""
    keys = _STAGE_RUBRIC_LEVEL_KEYS.get(stage.upper(), '"O1": "X 層級"')
    return f"""【RASF-Anchor 輸出規則（評量對準 + 原文錨點，重要）】
- rubric_focus：必填本段 ORID 主向度 id（O1 / R1 / I1 / D1），不可 null。
- rubric_level_estimate：必須是**物件**，依本段填入所有對應向度的層級估計：
  本段格式：{{{ keys }}}
  層級用語：「1 起步」「2 接近」「3 達標」「4 精進」（有把握才填，不確定可填 null）
  SEL 向度只估層級，**不要**另寫 missing；missing 只對 ORID 主向度（一刀）。
- student_anchor_quote（必填，除非草稿空白）：從學生原文**原封不動**摘 4～20 個連續字（人名、事件、感受詞、行動詞），供後續引導錨定；禁止改寫或捏造。
- draft_next_step（必填，除非草稿空白）：用白話寫**在學生哪一句前/後加什麼**才能升到下一階（預設目標 3 達標）；禁止給整段新例文。
- missing / suggestions 引導規則（RASF 核心）：
  先估 ORID 主向度目前是第幾階，再只描述「從目前階 → min(下一階, 3 達標)」還差的一個缺口。
  missing **必須**引用 student_anchor_quote（或同句中的學生用詞），用「你已經有○○，再補△△會更完整」語意。
  suggestions：**一個問句**，引導學生在 anchor 那句前/後自己補一句；不要列多步驟。
  example：多數填 null；若必填，只能是**接在 anchor 上的半句填空**（保留＿＿＿），禁止「故事的主角是……」這類從零開始的通用例句。
  **禁止**在第一輪就要求學生直接跳到 4 精進（除非 ORID 主向度已是 3 達標，才可引導精進）。
  SEL 的缺口不得成為 missing 的主題；SEL 最多用來把 ORID 那一刀的問句問得更具體。""".strip()


def _o_needs_book_plot_anchor(*, text: str, input_bucket: str) -> bool:
    """O 段若幾乎沒內容或學生表達卡住，JSON 層要強制帶書裡具體情節，避免只剩『一步一步』空架。"""
    if input_bucket in (BUCKET_EMPTY, BUCKET_TOO_SHORT):
        return True
    t = (text or "").strip()
    if not t:
        return True
    if any(p in t for p in _O_STUCK_HINT_PHRASES) and len(t) < 72:
        return True
    return False


def build_genai_feedback_prompts(
    *,
    stage: str,
    text: str,
    book_pack: Optional[dict[str, Any]],
    input_bucket: str = "normal",
    rag_context: str = "",
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
    sel_guidance_block = _format_sel_guidance_for_prompt(book_pack, stage)
    rasf_block = _rasf_json_format_block(stage)
    bucket_hint = bucket_tone_hint_zh(input_bucket)
    rag_block = ""
    if stage != "D":
        formatted_rag = format_rag_context_for_prompt(rag_context)
        if formatted_rag:
            rag_block = formatted_rag + "\n"

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
{rag_block if stage != "D" else ""}
教師本段說明：{guide or "（未提供）"}
{rubric_block if rubric_block else "（本週未提供 writing_rubric；仍依本段專屬規則回饋。）"}
{sel_guidance_block}

【語氣與長度感】
學生常在一節課約 **40 分鐘**內寫完 ORID 四格，所以回饋要短、清楚、可立刻動筆。
用字要適合國小五、六年級：短句、口語、容易懂。不要用「深化、完整度、精準、論述、脈絡、可執行」這類太大人的詞。
一次只指出一個最重要的修改方向；suggestions 優先用 1 個問句引導學生自己補，example 只給填空式支架。

【本輪輸入語氣（仍只輸出 JSON）】
{bucket_hint}

====================
二、本段專屬：{stage}
====================
{stage_block}

====================
三、JSON 欄位與品質
====================
- praise：**必須**看得出你有讀學生原文，盡量點到裡面的人/事/詞（若完全空白再用鼓勵下筆，禁止空泛罐頭讚美）。
- missing：不多於 1 條，對準本段**一個**主問題（一刀）；依 RASF 規則只談「下一階 gap」。
- suggestions：不多於 1 條；用 **1 個問句**或「下一步只補……」引導學生自己改，不要列多步驟，也不要把答案寫完。
- example：只給句型開頭、填空式提示或半句支架（例如「我覺得＿＿＿，因為＿＿＿。」）；不要填入完整角色、情節與答案讓學生可直接複製。
- improved：通常 null。

{rasf_block}

【輸出格式】只輸出純 JSON，不要 markdown，不要 ```。
{{
  "ok": boolean,
  "praise": string,
  "missing": string[],
  "suggestions": string[],
  "example": string or null,
  "improved": null,
  "rubric_focus": string,
  "rubric_level_estimate": object,
  "student_anchor_quote": string,
  "draft_next_step": string
}}
- rubric_focus：本段 ORID 主向度 id（O1 / R1 / I1 / D1），必填。
- rubric_level_estimate：依段填入多向度層級物件（見 RASF 規則），以「X 層級」格式填入。
- student_anchor_quote / draft_next_step：見 RASF-Anchor 規則；草稿空白時可填 null。

{FEW_SHOT_BLOCK}
""".strip()

    o_summary_priority = ""
    if stage == "O":
        o_summary_priority = (
            "若學生草稿已寫到多個事件且出現時間銜接，missing 請**優先**補齊「書裡／故事裡」還**幾乎沒寫到**的一大段情節（只依上方教材可支持的事實，勿發明）；"
            "用口語直接說缺哪一段，**不要**在 missing／suggestions／example 裡寫「故事摘要」「對照摘要」「掃摘要」等詞。\n"
            "suggestions 請用問句提示學生回想 1 個尚未寫到的具體情節，不要在 example 直接替學生寫成完整句。\n"
            "不要只要求加轉折詞、套先後句型或微調用詞，除非教材重點真的都已出現。\n\n"
        )

    o_plot_anchor = ""
    if stage == "O" and _o_needs_book_plot_anchor(text=text, input_bucket=input_bucket):
        o_plot_anchor = """
【本輪特別：O 段草稿極短或學生表達卡住】
suggestions 與 example **不可**整段只做「一步一步／慢慢來／先再最後」等抽象流程。
suggestions 可用問句帶到書裡一幕；example 仍只能是填空或半句支架，不要把完整答案寫好給學生複製。
""".strip()

    user_prompt = f"""
學生「{stage}」段原文如下（你回饋時稱讚要對準這些字，不要重複罐頭句）：

---
{text}
---

{o_summary_priority}{o_plot_anchor + chr(10) + chr(10) if o_plot_anchor else ""}請輸出 JSON。missing 與 suggestions 各至多 1 個字串；必須填 student_anchor_quote 與 draft_next_step（除非草稿空白）；suggestions 用 1 個問句引導在 anchor 句前/後補寫；example 多數 null，若填只能接 anchor 的半句填空。improved 多數 null。
""".strip()

    return system_prompt, user_prompt