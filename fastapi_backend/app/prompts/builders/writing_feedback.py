from __future__ import annotations

from typing import Any, Optional, Tuple
import re

from app.prompts.policy.student_input_bucket import (
    BUCKET_EMPTY,
    BUCKET_TOO_SHORT,
    bucket_tone_hint_zh,
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
        "層級只用於形成性引導與階段達標，不換算成數字分數。",
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
            "O 段不使用 SEL 輔助；只看故事人物、事件與前後變化（對準 ORID／RQ1）。"
        )

    research_focus = {
        "R": "本段研究焦點：先把感受與原因寫清楚（情緒覺察）；必要時一個同理角度問句。",
        "I": "本段研究焦點：體會＋故事支持；生活連結用「自己經驗」問句（不新增 SEL 代號）；可輔同理／關係理解。",
        "D": "本段研究焦點：具體可行行動（負責任行動）；必要時用學生語問對誰／什麼時候／怎麼做（關係理解）。",
    }.get(stage, "")

    lines: list[str] = [
        "【SEL 輔助引導（只給 AI 內部使用，不取代 ORID 判斷｜對準 RQ2）】",
        "SEL 只能幫你把那一個友善問句問得更具體；ok 只依 ORID 本段 rubric 判斷。",
        "研究用語對照（勿對學生說出）：情緒覺察≈SEL_SA；同理理解≈SEL_SOA；關係理解≈SEL_RS；負責任行動≈SEL_RD；生活連結→I 段體會，非 SEL ID。",
        "不要在給學生的文字中直接使用「SEL」或「情緒覺察」「同理理解」「關係理解」「負責任行動」「自我覺察」「自我管理」「社會覺察」「人際技巧」「負責任的決定」等術語。",
        "請把 SEL 轉成國小五、六年級看得懂的具體問題；每次最多用一個方向，且仍服務本段 ORID 主缺口。",
    ]
    if research_focus:
        lines.append(research_focus)
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


def _themes_for_prompt(book_pack: Optional[dict[str, Any]]) -> str:
    themes = (book_pack or {}).get("core_theme") or []
    if isinstance(themes, str):
        themes = [themes]
    if not isinstance(themes, list):
        return "（未提供）"
    cleaned = [str(theme).strip() for theme in themes if str(theme).strip()]
    return "、".join(cleaned) if cleaned else "（未提供）"


def _d_action_scope_for_prompt(book_pack: Optional[dict[str, Any]]) -> str:
    scope = str((book_pack or {}).get("d_action_scope") or "").strip()
    return scope or "依本週 D1 rubric 與本書主題判斷，不額外增加條件。"


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
    "R": '"R1": "X 層級", "SEL_SA": "X 層級", "SEL_SOA": "X 層級", "SEL_SM": "X 層級"',
    "I": '"I1": "X 層級", "SEL_SOA": "X 層級", "SEL_RS": "X 層級"',
    "D": '"D1": "X 層級", "SEL_RD": "X 層級", "SEL_SM": "X 層級", "SEL_RS": "X 層級"',
}


_STAGE_REVISION_TARGETS: dict[str, str] = {
    "O": "請回到 O 觀察段，補上故事裡真的發生的一件事",
    "R": "請回到 R 感受段，補上感受的原因",
    "I": "請回到 I 體會段，補上學到的想法或自己的經驗",
    "D": "請回到 D 行動段，補上一個自己做得到的行動",
}


_STAGE_EXAMPLE_SCAFFOLDS: dict[str, str] = {
    "O": "故事裡，＿＿做了＿＿。／我印象最深的是＿＿。",
    "R": "我覺得＿＿，因為＿＿。",
    "I": "這讓我想到＿＿。",
    "D": "以後遇到＿＿時，我會＿＿。",
}


def _stage_revision_target(stage: str) -> str:
    return _STAGE_REVISION_TARGETS.get((stage or "O").strip().upper(), _STAGE_REVISION_TARGETS["O"])


def _stage_example_scaffold(stage: str) -> str:
    return _STAGE_EXAMPLE_SCAFFOLDS.get((stage or "O").strip().upper(), _STAGE_EXAMPLE_SCAFFOLDS["O"])


def _rasf_json_format_block(stage: str) -> str:
    """RASF-Anchor 規則：多向度估層級 + 原文錨點引導。"""
    keys = _STAGE_RUBRIC_LEVEL_KEYS.get(stage.upper(), '"O1": "X 層級"')
    revision_target = _stage_revision_target(stage)
    example_scaffold = _stage_example_scaffold(stage)
    i_life = ""
    if (stage or "").strip().upper() == "I":
        i_life = (
            "\n- I 段特別：若缺的是「生活連結」（把自己經驗連上故事），"
            "用 suggestions 一個問句引導即可；**不要**為此新增 SEL id；"
            "仍以 I1 是否有體會＋故事支持為 ok 主判斷。"
        )
    d_semantic = ""
    if (stage or "").strip().upper() == "D":
        d_semantic = (
            "\n- D 段必須填 d_action_assessment：has_self_action、action_is_concrete、"
            "theme_aligned 都依整句語意判斷，不可用關鍵字清單。evidence_quote 必須原封不動摘自學生原文。"
            "missing_dimension 只能填 no_action、not_concrete、off_theme 或 null。"
            "theme_aligned 是判斷行動是否符合上方本書主題；但是否影響 ok，仍以本週 D1 第 3 級是否要求主題連結為準。"
            "判斷 theme_aligned 時要看行動本身是否直接落在『D 段行動主題範圍』；"
            "不能只因任何行動都可被廣義解釋成努力、負責或進步就判 true。"
            "若等級 1/2，missing 與 suggestions 必須承接學生原本的想法，例如學生寫『多體諒家人』，"
            "問句也要出現『體諒家人』，不可換成沒有原文錨點的通用模板。"
        )
    return f"""【RASF-Anchor 輸出規則（評量對準 + 原文錨點，重要｜對準 RQ1–RQ3）】
- rubric_focus：必填本段 ORID 主向度 id（O1 / R1 / I1 / D1），不可 null。
- rubric_level_estimate：必須是**物件**，依本段填入所有對應向度的層級估計：
  本段格式：{{{ keys }}}
  層級用語：「1 起步」「2 接近」「3 達標」「4 精進」（有把握才填，不確定可填 null）
  SEL 向度只估層級，**不要**另寫 missing；missing 只對 ORID 主向度（一刀）。
- student_anchor_quote（必填，除非草稿空白）：從學生原文**原封不動**摘 4～20 個連續字（人名、事件、感受詞、行動詞），供後續引導錨定；禁止改寫或捏造。
- draft_next_step：**僅在 ok=false（等級 1 或 2）時填寫**；最多 1 句，必須使用本段修改落點：「{revision_target}」。不要放入書中完整事件，也不要替學生完成句子。**等級 3 或 4 時填 null。**
- missing / suggestions 引導規則（RASF 核心）：
  先估 ORID 主向度目前是第幾階。
  **等級 3（達標）或 4（精進）→ ok=true；missing=[]；suggestions=[]；example=null；draft_next_step=null。不得再要求補細節、精進或下一階。**
  等級 1 或 2 → ok=false；再只描述「從目前階 → 3 達標」還差的一個缺口。
  missing（等級 1/2 才填）**必須**引用 student_anchor_quote（或同句中的學生用詞），用「你已經有○○，再補△△會更完整」語意。
  suggestions（等級 1/2 才填）：**一個短問句或短指令**，必須明確指向「{revision_target}」；不要列多步驟，不要寫書中完整事件，不要寫完整答案。
  example（等級 1/2 且必要才填）：只能使用本段填空支架：「{example_scaffold}」。保留＿＿，不得放入具體人名、完整情節、完整原因或完整做法。
  學生會看到的 praise / missing / suggestions / example / draft_next_step 必須改成學生語；不得出現 rubric、level、criteria、score、RASF、層級、等級、達標、精進、評分、規準等評量語。
  學生可見三段每段最多 2 個短句；每次最多一個主要修改方向。
  SEL 的缺口不得成為 missing 的主題；SEL 最多用來把 ORID 那一刀的問句問得更具體。{i_life}{d_semantic}""".strip()


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
    """Build one concise rubric-first prompt for experimental-group feedback."""
    stage = stage if stage in {"O", "R", "I", "D"} else "O"
    book_title = (book_pack or {}).get("book_title", "本週繪本")
    guide = ((book_pack or {}).get("writing_guide", {}) or {}).get(stage, "")
    key_events = (book_pack or {}).get("key_events", [])
    key_events_str = "\n".join(f"・{x}" for x in key_events) if key_events else "（未提供摘要）"
    excerpts_block = _excerpts_for_prompt(book_pack, student_text=text)
    characters_block = _characters_for_prompt(book_pack)
    themes_block = _themes_for_prompt(book_pack)
    d_action_scope = _d_action_scope_for_prompt(book_pack)
    rubric_block = _format_writing_rubric_for_prompt(book_pack, stage)
    sel_guidance_block = _format_sel_guidance_for_prompt(book_pack, stage)
    revision_target = _stage_revision_target(stage)
    example_scaffold = _stage_example_scaffold(stage)
    bucket_hint = bucket_tone_hint_zh(input_bucket)
    formatted_rag = format_rag_context_for_prompt(rag_context) if stage != "D" else ""
    stage_rules = {
        "O": (
            "只評客觀觀察：重要人物，以及至少兩個彼此相關的正確事實；"
            "若只寫一個事件，必須同時包含事件的前後變化，讓人看得出故事發展，才可達第 3 級。"
            "單一孤立事實只算第 2 級。語意相同的改寫算正確，不要求逐字重述。"
        ),
        "R": (
            "只評感受反應：必須同時有明確感受，以及造成該感受的書中事件或畫面。"
            "只有感受或只有故事重述，最高第 2 級。"
        ),
        "I": (
            "只評詮釋體會：必須同時有學到的道理或理解，以及支持該想法的書中內容。"
            "只有口號式道理或只有故事重述，最高第 2 級。"
            "生活連結是第 4 級表現，不是第 3 級必填。"
        ),
        "D": (
            "只評行動決定：必須同時寫出適用的情況或對象，以及自己做得到、具體且呼應故事主題的行動。"
            "不要求固定句型；情境、對象、做法不是固定三項必填，但至少要有情況或對象，加上具體行動。"
            "只有『我要努力／分享／幫忙』等願望，最高第 2 級。"
            "必須依整句語意判斷，不可用關鍵字清單評分。"
        ),
    }
    primary_id = f"{stage}1"
    material = (
        f"角色：{characters_block}\n故事事件：\n{key_events_str}\n故事摘錄：\n{excerpts_block}"
        if stage != "D"
        else f"故事主題：{themes_block}\nD 段行動主題範圍：{d_action_scope}"
    )
    grounding_rule = (
        "核對教材時看語意，不做逐字比對。只有明顯新增或寫錯人物、物品、事件才判未達標；"
        "省略非必要細節、角色簡稱及同義改寫都可接受。"
        if stage != "D"
        else "D 段寫學生現實生活，不檢查是否出現書中人物、物品或情節。"
    )
    d_schema_rule = (
        "d_action_assessment 必填，依整句語意填 has_self_action、action_is_concrete、"
        "theme_aligned、evidence_quote、missing_dimension。"
        if stage == "D"
        else "d_action_assessment 填 null。"
    )

    system_prompt = f"""你是國小五、六年級 ORID 寫作評量員。只輸出符合 schema 的 JSON。

【唯一通過標準】
只依本段 ORID rubric 決定 ok：第 3／4 級為 true，第 1／2 級為 false。SEL 只供研究與提問，不得改變 ok。達到第 3 級後立即停止修改要求，missing=[]、suggestions=[]、example=null、draft_next_step=null。
四段都採「兩個核心成分」原則，不以字數判斷：O 是相關事實／前後變化，R 是感受＋故事原因，I 是理解＋故事支持，D 是情況或對象＋具體行動。只碰到主題詞、只有結論或只有一個孤立資訊，不可判為第 3 級。

【本段 {stage}】
{stage_rules[stage]}
{grounding_rule}

【教材】
書名：{book_title}
{material}
{formatted_rag}
教師說明：{guide or "（未提供）"}

【正式 rubric】
{rubric_block or "依本段規則判定 1～4 級。"}
{sel_guidance_block}

【回饋規則】
- praise 只肯定學生原文中正確的內容，使用適合小學生的短句。
- 未達標時只指出一個最重要缺口；suggestions 只給一個問題或短指令，修改落點是「{revision_target}」。
- 不代寫答案。example 只能是「{example_scaffold}」這類留白句型或 null。
- student_anchor_quote 原封不動摘錄學生原文 4～20 字；未達標時填 draft_next_step，達標時填 null。
- rubric_focus 固定為 {primary_id}；rubric_level_estimate 至少包含 {primary_id}，值使用「1 起步／2 接近／3 達標／4 精進」。
- {d_schema_rule}
- 學生可見文字不得出現 rubric、level、RASF、層級、評分等術語。

【輸入狀態】
{bucket_hint}
""".strip()

    user_prompt = f"""請評量以下學生「{stage}」段原文：

---
{text}
---

先依教材與正式 rubric 判級，再讓 ok 與 {primary_id} 層級完全一致。只輸出 JSON。""".strip()

    return system_prompt, user_prompt
