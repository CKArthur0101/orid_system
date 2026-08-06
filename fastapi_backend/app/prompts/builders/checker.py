from __future__ import annotations

from typing import Any, Optional, Tuple
import json

from app.prompts.shared_parts.book_context import build_book_context_block
from app.prompts.templates.checker import BOOK_GROUNDING_RULES, ORID_CHECKER_STAGE_RULES

Stage = str  # "O" | "R" | "I" | "D"


def build_orid_checker_prompts(
    *,
    student_text: str,
    book_pack: Optional[dict[str, Any]],
    stage: Stage,
    message_history: Optional[list[str]] = None,
    max_history: int = 6,
) -> Tuple[str, str]:
    """
    Checker responsibilities:
    1) Detect unsafe language.
    2) Detect off-topic.
    3) Produce ONE narrow, stage-appropriate, book-anchored next question.
    """
    stage = (stage or "O").strip().upper()
    if stage not in {"O", "R", "I", "D"}:
        stage = "O"

    book_context = build_book_context_block(book_pack, max_events=6, max_chars=1200)

    history = message_history or []
    history = [str(x).strip() for x in history if str(x).strip()]
    history = history[-max_history:]

    sys = f"""
你是「兒童閱讀對話的安全與引導檢查器（ORID Checker）」。
你只能根據 BOOK_CONTEXT 判斷與提問，不可編造故事細節或書外資訊。

你的工作有三件：
(1) 偵測學生訊息是否含不友善用語（辱罵、人身攻擊、歧視、威脅、性暗示等）。
(2) 偵測是否離題。
(3) 產生一個「下一小步」的問題（suggested_question）。

{ORID_CHECKER_STAGE_RULES.format(stage=stage)}

判斷離題的重要原則：
- 只要學生有提到書中角色、事件、畫面、主題，或對這些內容做簡單評論，都不算離題。
- 例如「他很小氣」「這樣不公平」「他後來有改變」都不算離題。
- 像「我今天中午吃排骨便當」「我昨天去打球」這種明顯和故事無關的生活句子，才算 off_topic=true。
- 不要因為學生只說一小句就當成離題；先看它有沒有碰到故事線索。

suggested_question 的重要原則：
- 要問「下一小步」，不是退回大題。
- 若學生已經說到一個事件，不要又問「故事發生了什麼」。
- 若學生已經說到感受，不要又問「你有什麼感覺」；要問原因或是哪個畫面。
- 若學生已經說到道理，不要又問「提醒我們什麼」；要問理由或故事根據。
- 若學生已經說到行動，不要又問「你會怎麼做」；要問第一步、對誰、什麼時候做。
- 若學生明顯離題，不要重複他的生活瑣事細節；用「故事裡哪一幕／誰做了什麼」把他拉回來，不要直接提供書中完整事件答案。
- suggested_question 只能有一個問號（？）。

輸出必須是純 JSON，不要任何多餘文字、不要 code block。
JSON schema（欄位不可少）：
{{
  "unsafe_language": boolean,
  "unsafe_reason": string,
  "off_topic": boolean,
  "reason": string,
  "suggested_question": string
}}

若 unsafe_language=true：
- unsafe_reason 用很短一句話，例如：語氣不友善 / 包含人身攻擊
- reason 填相同意思
- suggested_question 仍要給，但要溫和把學生拉回書與本階段方向，不可重複學生的髒話

若 off_topic=true：
- reason 用「離題」或「先回到故事」
- suggested_question 要用本階段方向拉回，不可責備；不要直接提供書中完整事件答案。

若既不 unsafe 也不 off-topic：
- off_topic=false，reason 用「OK」或「貼近本階段」
- suggested_question 要是本階段下一個更窄的問題，不可跳階，也不可回到整體大題

BOOK_CONTEXT：
{book_context}
""".strip()

    user = f"""
學生訊息：
{student_text}

近期對話（只用來判斷是否離題與下一小步，不可編造書外資訊）：
{json.dumps(history, ensure_ascii=False)}
""".strip()

    return sys, user


def build_book_grounding_checker_prompts(
    *,
    student_text: str,
    book_pack: Optional[dict[str, Any]],
    stage: Stage,
) -> Tuple[str, str]:
    """
    LLM grounding checker:
    Decide whether the student's claim is supported by BOOK_CONTEXT facts.
    """
    stage = (stage or "O").strip().upper()
    if stage not in {"O", "R", "I", "D"}:
        stage = "O"
    book_context = build_book_context_block(book_pack, max_events=8, max_chars=1500)
    sys = f"""
你是「教材事實核對器」。
你的任務：判斷學生這句話是否可由 BOOK_CONTEXT 支持。
只允許根據 BOOK_CONTEXT 判斷，不可編造或腦補。

{BOOK_GROUNDING_RULES}

輸出必須是純 JSON，不要多餘文字：
{{
  "grounded": boolean,
  "reason": string,
  "unsupported_span": string
}}

欄位規範：
- reason：20 字內，簡短說明（例：教材可支持 / 疑似新增書外事件）
- unsupported_span：若 grounded=false，填學生原句中的關鍵片段；否則填空字串。

目前階段：{stage}
BOOK_CONTEXT：
{book_context}
""".strip()
    user = f"學生句子：\n{student_text}"
    return sys, user
