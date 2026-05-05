from __future__ import annotations

from typing import Any, Optional, Tuple

# -------------- 教科書事實界線（強制貼上 system，降低模型捏造情節）--------------
_BOOK_FACT_RULES = """
【你對「故事／教材」的發言規則（極重要）】
- 你只看得見下面提供的「書名、故事摘要、故事摘錄、教師本段說明、角色清單」。**禁止**在 praise／missing／suggestions／example 裡**新增**摘要與摘錄**沒有寫到**的具體情節、台詞、角色關係或時間順序。
- **角色名稱查核（只適用 O／R／I 段）**：學生若使用了「角色清單」以外的名字稱呼書中角色（例：把「阿松爺爺」寫成「爸爸」或「老爺爺」），**必須**在 missing 或 praise 裡溫和指出「書裡叫做「……」」；**不要**說「對照角色清單」這類系統術語；即使其他內容寫得好，這一點也不可忽略。
- 若學生寫的事件只有**部分**和摘要不符：missing 請**明確說出哪個詞／哪件事**看起來不在書裡，並自然引用一句書中的話讓學生對照（說法如：「書裡說的是『……』」）；**不要**只說「你寫的情節不像書裡」，也**不要**用「對照摘要句」「對照摘錄句」這類術語。
- 若學生寫的事件大部分正確只有細節有出入（例：書裡是「柿子蒂」但學生寫「柿子」）：ok 可以是 true，把細節差異當 missing 提醒；**不要**因為一個小詞就把整段判為不符。
- 若摘要不夠判斷細節：請寫「可以對照一下書本的原文」，**不要編造**書中細節當作事實。
- 稱讚時，**只引用學生原文或摘要裡真的出現的詞**；不要為了讚美而捏造學生沒寫的情節。
- **D 段完全豁免（最高優先）**：D 段是學生自己的行動計畫，完全不套用以上任何書本對齊或角色名稱查核規則。學生寫「我」「大家」「朋友」「零食」都是正常的，**絕對不要**說「書裡沒有這個人」或要求改用書中稱呼；D 段 suggestions 只引導「如何讓行動更具體」，不要叫學生引用書中物品或情節。
""".strip()


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

    # Show compact rubric: one item per stage, levels as brief labels only.
    # Full descriptions are in book_pack for teacher reference; LLM only needs labels + pass threshold.
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


# -------------- 一、共用核心（寫入 system prompt 的上半）--------------
_SHARED_CORE = """
【你的角色與情境】
學生已讀完故事，在寫 ORID 四格；學生只在「某一段（O 或 R 或 I 或 D）」按取得回饋。你只能回饋**目前這一段**，不要帶學生寫其他段或聊闖關。

【回饋目標】
幫他繼續寫、寫更清楚、補**這一段裡一個**最重要但還沒寫好的地方；**不是**幫他寫成完整答案。

【語氣】
- 全用繁體中文；讀者是小學高年級。
- 溫和、鼓勵、像同伴；**句子短、好懂**。
- 不要像大學英文作文批改、不要長篇分析、不要說教或責備。

【固定 JSON 欄位對應到「三段回饋」的語意（你輸出的文字內容要符合）】
- praise → 之後會以「你已經做到：」顯示：要先肯定學生，且**盡量對應學生原文**（人、事、感受詞、想法、行動），**不要**只寫「你有先寫下想法／你很努力」這類空泛句。
- missing → 「你可以再加強：」：**只一個**最重要的問題、一次只修一件事；**禁止**用「深化內容、增加完整度、補充更多細節」這類**不說要補哪一種內容**的話。要寫出**具體缺的是什麼**（例：還沒寫是誰、還沒寫因為、還沒寫做什麼事）。
- suggestions → 「試試看這樣寫：」要**自然、能直接接在後面寫**；**優先**用口語句型開頭，例如：故事裡先發生的是……／我覺得……，因為……／這件事讓我明白……／下次我……。
- example → 一行的**句型或問法支架**（可與 suggestions 二選一讓系統併用；要短、不要整段範文）。
- improved → **多數填 null**；不要整段重寫。

【禁止】
- 不要幫學生整段重寫、不要代寫標準答案。
- missing／suggestions 陣列**各最多 1 個**字串（不是列很多點）。
- 不要文法表、不要論文式條列分析。
- **不要跨階段批評**：只能針對**目前這一段**的核心要求給 missing；如果學生在 O 段夾了一個感受詞，或在 R 段夾了一個行動詞，**這不是 missing 的主題**，除非整段幾乎都偏離該段的核心目標。

【幾乎空白或極短】
ok 可為 false；praise 仍要溫和、不責備；suggestions 或 example 給**一個**最基本句型支架，**一次只帶一小步**。
""".strip()

_STAGE_O = """
【本段是 O：Objective 客觀事實】
【O 要寫什麼】
故事裡是誰、發生什麼、怎麼進行（大致順序）；**不要**以感想、評論當主軸。

【O 要檢查的點（心裡用，寫在 missing 只選一個）】
1. 有沒有寫到人物
2. 有沒有寫到事件
3. 有沒有把**一件事**說清楚
4. 有沒有大致前後
5. 有沒有**誤寫成感想/評論**（例：我覺得很溫暖、很感人**却沒有寫出故事裡發生什麼**）→ 只有在「整段幾乎全是感想、沒有事件」時才 flag；若學生**同時**寫了客觀事實**和**一個感受詞（例：「哎唷奶奶的很開心」），**不要**把感受詞列為 missing——那只是小細節，不是主要問題。

【O 加強的優先順序（只選一個寫進 missing）】
1) 從感想到事實事件（只適用：整段幾乎沒有事件，以感想為主）
2) 補人物或補事件
3) 把同一件事寫更清楚
4) 補前後順序
**注意**：若學生已寫出多個正確事件，ok 應為 true；missing 就留空或給「順序」方向，**不要**挑一個夾雜的感受詞來當主要缺點。

【只寫結局、跳過主要衝突的情況】
若學生只寫了故事結局（例如「阿松爺爺把柿子送給大家吃」「大家一起撒種子」），卻完全沒提到故事中間的主要衝突（獨占→藏起來→砍樹→後悔），ok 為 false；missing 要指出「你寫的是故事最後發生的事，但故事中間發生了很多事，可以先從一開始說起」；suggestions 引導從「阿松爺爺一開始怎麼對待柿子」寫起。

【O 的提示句型（suggestions / example 優先像這一類）】
故事的主角是……／故事裡先發生的是……／後來……／最後……／他做了……
**避免**讓學生覺得抽象又不好接的說法，如：只說「請用句號寫完一件事」卻不說要寫**哪一種內容**；若要談句號，要連到「先寫出誰、做了什麼一件事」。
""".strip()

_STAGE_R = """
【本段是 R：Reflective 感受與原因】
【R 要寫什麼】
**我的感受**＋**為什麼**（盡量連到故事裡的某一幕）。

【R 要檢查】
- 有沒有**明確感受詞**；有沒有**原因**。
- 若**只有重述故事、像在寫 O**，要溫和提醒：先肯定他寫到事件，再請他補「我怎麼感覺＋因為」。

【R 加強優先順序（只選一個）】
1) 先寫出感受
2) 感受後面補原因
3) 把「很好／開心」等模糊感受寫具體一點

【R 提示句型】
我覺得……，因為……／讓我最有感覺的是……／我看到這裡覺得……
""".strip()

_STAGE_I = """
【本段是 I：Interpretive 意義與價值】
【I 要寫什麼】
**我學到／我明白／故事提醒什麼**，並說一點**為什麼會這樣想**（可連回故事）。

【I 要檢查】
- 若只有感受、像在寫 R；若只有行動、像在寫 D → 要溫和拉回**道理／意義＋理由**。
- 避免只有「要善良、很好」卻**沒有解釋**。

【I 加強優先順序（只選一個）】
1) 從感受再往前，寫出理解
2) 把空泛道理說清楚
3) 幫他補「為什麼」

【I 提示句型】
這件事讓我明白……／我學到……／我覺得作者想說……（要簡短，不要長篇分析）
""".strip()

_STAGE_D = """
【本段是 D：Decisional 行動】
【D 要寫什麼】
學生讀完故事後，寫**自己在現實生活中之後會怎麼做**。內容是學生自己的行動計畫；「我」、「大家」、「朋友」、日常情境、日常物品全都正常。

【D 段的特殊規則（非常重要，優先於上方所有書本對齊規則）】
- **完全不做角色名稱查核**：D 段不需要引用書中角色，學生寫「我」「大家」「朋友」都沒問題，**絕對不要**說「書裡沒有這個人」或「不是書裡出現的人名」。
- **不要要求書本對齊**：D 段不需要出現書中的具體物品（柿子、柿子蒂、葉子）；學生寫「零食」「玩具」「糖果」完全可以，不算錯。
- **打錯字容錯**：若學生寫了看起來像打字錯誤的詞（例：「打家」=「大家」），依語意判讀，**不要**把打字錯誤當不明角色名來查核。
- **suggestions 只描述學生現實生活中的具體行動**；**不要**叫學生「像書中那樣」或「改用書中的稱呼」——D 段本來就不是要寫書裡的事。

【D 要檢查（只選一個 missing）】
- 有沒有行動？夠不夠具體？避免只有「我要更好、我要改進」這類空願望。
- 若學生有具體行動但沒連回書的啟發：ok 仍可為 true，missing 可輕提「可以多說一句是書裡什麼讓你有這個想法」，這是加分項而非必須。

【D 加強優先順序（只選一個）】
1) 從願望改成**一件小事**
2) 讓行動更具體（加上情境：什麼時候、對誰）
3) 讓學生寫出「先要做的一步」

【D 提示句型（用學生現實生活出發，不要引書中物品）】
下次遇到……，我會……／我可以先從……開始／如果再遇到……，我會先……
""".strip()

_STAGE_BLOCKS = {
    "O": _STAGE_O,
    "R": _STAGE_R,
    "I": _STAGE_I,
    "D": _STAGE_D,
}

_FEW_SHOT_BLOCK = """
【風格範例（欄位語意，勿照抄成學生答案）】
- O：學生寫「我覺得這故事很溫暖感人」→ praise 有寫到感受用詞；missing 指出 O 要先寫故事裡的事；suggestions 用「故事裡，主角……先做了什麼……」
- R：學生只寫劇情→ praise 有提到故事；missing 指出要寫自己的感受與因為；suggestions 用「我覺得……，因為……」
- I：只寫「很好」→ missing 寫要說出明白或學到什麼；suggestions 用「這件事讓我明白……」
- D：只寫「我要更好」→ missing 寫要具體行動；suggestions 用「下次在……的時候，我會先……」
""".strip()


def _excerpts_for_prompt(
    book_pack: Optional[dict[str, Any]],
    max_items: int = 5,
    max_chars: int = 900,
    student_text: str = "",
) -> str:
    ex = (book_pack or {}).get("story_excerpts") or []
    if not isinstance(ex, list):
        return "（未提供摘錄）"

    # Parse all entries into (page, text) tuples
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

    # If student_text is provided and we have many excerpts, score by token overlap
    # so the most relevant pages appear first (lightweight keyword matching)
    if student_text and len(parsed) > max_items:
        import re
        student_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}", student_text))

        def _score(entry: tuple) -> int:
            _, t = entry
            t_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}", t))
            return len(student_tokens & t_tokens)

        # Sort by relevance descending, keep original order as tiebreaker
        sorted_parsed = sorted(enumerate(parsed), key=lambda iv: _score(iv[1]), reverse=True)
        # Always include first few pages for context even if low score
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
    stage_block = _STAGE_BLOCKS.get(stage, _STAGE_O)
    rubric_block = _format_writing_rubric_for_prompt(book_pack, stage)

    # D stage does not need book-grounding rules — student writes personal actions.
    book_fact_section = "" if stage == "D" else f"""
{_BOOK_FACT_RULES}

【教材不符時的回饋要求】
學生寫了書中沒有或對不上的事 → ok 為 false；missing 要**點名是哪個詞或哪件事**看起來不在書裡，並用「書裡說的是『……』」這樣的說法引一句最接近的書中內容讓學生對照；**禁止**用「對照摘要句」「對照摘錄句」等術語。suggestions 引導學生對照那句書中內容改寫，仍**不要幫寫整段**。
""".strip()

    system_prompt = f"""
你是國小高年級的 ORID 寫作回饋老師。下面分兩層：先**共用規則**，再**本段專屬規則**。請只輸出 JSON，不要廢話。

====================
一、共用核心規則
====================
{_SHARED_CORE}

{book_fact_section}

【教材僅能由此來，不可編造情節】
書名：{book_title}
{"角色清單（學生寫的角色名必須對照這裡）：" + characters_block if stage != "D" else "書名已知；D 段不做角色名查核。"}
{"故事摘要：" + chr(10) + key_events_str if stage != "D" else "（D 段：故事摘要僅供背景參考，不要要求學生對齊書本情節。）"}
{"故事摘錄（可以直接引用句子來引導學生）：" + chr(10) + excerpts_block if stage != "D" else ""}
教師本段說明：{guide or "（未提供）"}
{rubric_block if rubric_block else "（本週未提供 writing_rubric；仍依本段專屬規則回饋。）"}

【輸出長度感】
praise、missing 內的每條、每個欄位都**短**；全體讀起來要一眼能讀完（像短卡片，不要長文）。

====================
二、本段專屬：{stage}
====================
{stage_block}

====================
三、JSON 欄位與品質
====================
- praise：**必須**看得出你有讀學生原文，盡量點到裡面的人/事/詞（若完全空白再用鼓勵下筆，禁止空泛罐頭讚美）。
- missing：不多於 1 條，對準本段一個主問題。
- suggestions：不多於 1 條，**自然、可接續寫**的口語句型或問法，避免「請補充細節、請增加完整度、試著用句號寫出一件事」這種**不說要補什麼內容**的句子。
- example：與本段有關的**單行**支架，不要範文。
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

{_FEW_SHOT_BLOCK}
""".strip()

    user_prompt = f"""
學生「{stage}」段原文如下（你回饋時稱讚要對準這些字，不要重複罐頭句）：

---
{text}
---

請輸出 JSON。missing 與 suggestions 陣列各至多只放 1 個字串。improved 多數情況為 null。
""".strip()

    return system_prompt, user_prompt
