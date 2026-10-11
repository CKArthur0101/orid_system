from __future__ import annotations

from typing import Any, Optional, Tuple
import re

from app.prompts.policy.student_input_bucket import bucket_tone_hint_zh
from app.prompts.text_loader import fill_prompt, read_prompt_file, read_prompt_pieces
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


def _prompt_piece(pieces: dict[str, str], key: str) -> str:
    return pieces.get(key) or pieces["O"]





def build_genai_feedback_prompts(
    *,
    stage: str,
    text: str,
    book_pack: Optional[dict[str, Any]],
    input_bucket: str = "normal",
    rag_context: str = "",
    recent_context: str = "",
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
    pieces = read_prompt_pieces("genai_feedback_pieces.txt")
    revision_target = _prompt_piece(pieces, f"revision_{stage}")
    example_scaffold = _prompt_piece(pieces, f"example_{stage}")
    bucket_hint = bucket_tone_hint_zh(input_bucket)
    formatted_rag = format_rag_context_for_prompt(rag_context) if stage != "D" else ""
    context_block = (recent_context or "").strip() or "（這是本階段第一輪回饋）"
    primary_id = f"{stage}1"
    material = (
        f"角色：{characters_block}\n故事事件：\n{key_events_str}\n故事摘錄：\n{excerpts_block}"
        if stage != "D"
        else f"故事主題：{themes_block}\nD 段行動主題範圍：{d_action_scope}"
    )
    filled = {
        "階段": stage,
        "本段規則": _prompt_piece(pieces, stage),
        "教材核對": pieces["grounding_d"] if stage == "D" else pieces["grounding_story"],
        "書名": book_title,
        "教材內容": material,
        "檢索補充": formatted_rag,
        "教師說明": guide or "（未提供）",
        "評量標準": rubric_block or "依本段規則判定 1～4 級。",
        "SEL引導": sel_guidance_block,
        "修改落點": revision_target,
        "例句型": example_scaffold,
        "主向度": primary_id,
        "D欄位規則": pieces["d_schema"] if stage == "D" else pieces["d_schema_null"],
        "輸入狀態": bucket_hint,
        "最近互動": context_block,
    }
    system_prompt = fill_prompt(read_prompt_file("genai_feedback_system.txt"), filled)
    user_prompt = fill_prompt(
        read_prompt_file("genai_feedback_user.txt"),
        {"階段": stage, "學生原文": text, "主向度": primary_id},
    )

    return system_prompt, user_prompt
