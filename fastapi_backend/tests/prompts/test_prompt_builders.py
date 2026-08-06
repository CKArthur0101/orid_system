from app.prompts.builders.checker import build_book_grounding_checker_prompts
from app.prompts.builders.coach_chat import (
    build_feedback_narration_prompt,
    build_synthesis_coach_system_prompt,
    build_writing_coach_system_prompt,
)
from app.prompts.builders.writing_assist import build_writing_d1_prompts, build_writing_d2_prompts
from app.prompts.builders.writing_feedback import build_genai_feedback_prompts
from app.content.rubrics import WEEK1_ORID_RUBRIC, WEEK1_SEL_RUBRIC
from app.prompts.policy.control_feedback import format_control_feedback_reply
from app.prompts.policy.feedback_focus import apply_o_key_event_gaps, normalize_feedback_focus, o_draft_meets_pass_bar
from app.prompts.policy.turn_destination import (
    CONTROL_O_META_MISSING,
    GENAI_META_MISSING_FALLBACK,
    personalized_control_praise_line,
    strip_orid_stage_tag,
)
from app.prompts.shared_parts.book_context import build_book_context_block
from app.prompts.versions import PROMPT_VERSIONS
from app.utils import strip_markdown_for_student_chat


def _book_pack() -> dict:
    return {
        "book_title": "阿松爺爺的柿子樹",
        "grade": "國小高年級",
        "key_events": [
            "阿松爺爺把柿子藏到屋後倉庫",
            "最後大家一起把柿子拿出來吃，並撒下種子。",
        ],
        "characters": [{"name": "阿松爺爺", "role": "故事角色"}],
        "writing_guide": {
            "O": "先把故事事件說清楚。",
            "D": "寫出下次你會怎麼做。",
        },
        "writing_rubric": {
            "schema": "writing_rubric_v1",
            "by_stage": {
                "O": [
                    {
                        "id": "O1",
                        "name": "事實描述",
                        "levels": [
                            {"label": "1 起步", "desc": "只有感想，沒有寫出故事人物或事件。"},
                            {"label": "2 接近", "desc": "有提到人物或事件，但內容零散。"},
                            {"label": "3 達標", "desc": "能正確寫出人物與至少一件重要事件。"},
                            {"label": "4 精進", "desc": "能寫出兩件以上有前後關聯的事件。"},
                        ],
                    }
                ],
                "R": [
                    {
                        "id": "R1",
                        "name": "感受與原因",
                        "levels": [
                            {"label": "1 起步", "desc": "沒有感受詞，也沒有原因。"},
                            {"label": "2 接近", "desc": "有感受，但原因不清楚。"},
                            {"label": "3 達標", "desc": "能寫出感受並連回故事原因。"},
                            {"label": "4 精進", "desc": "能把感受、原因與故事畫面說清楚。"},
                        ],
                    }
                ],
            },
        },
    }


def test_build_book_context_block_contract():
    block = build_book_context_block(_book_pack())
    assert "BOOK_CONTEXT" in block
    assert "阿松爺爺的柿子樹" in block
    assert "阿松爺爺" in block
    assert "重要事件" in block


def test_writing_assist_builders_include_stage_specific_contract():
    system_prompt, user_prompt = build_writing_d1_prompts(
        stage="O",
        book_pack=_book_pack(),
        chat_recent_hint="他一開始不分享柿子",
    )
    assert "ORID O 段 Draft 1" in system_prompt
    assert "阿松爺爺的柿子樹" in system_prompt
    assert "他一開始不分享柿子" in user_prompt

    d2_system, d2_user = build_writing_d2_prompts(
        stage="D",
        book_pack=_book_pack(),
        chat_recent_hint="我想學會分享",
        base_text="下次我會主動分給別人。",
    )
    assert "【TIPS】" in d2_system
    assert "下次我會主動分給別人。" in d2_user
    assert "Draft 2" in d2_user


def test_strip_orid_stage_tag_removes_section_prefix():
    assert strip_orid_stage_tag("[O 本段寫作] 好") == "好"
    assert strip_orid_stage_tag("[O 本段寫作] 不知道") == "不知道"


def test_personalized_control_praise_skips_fake_quote_for_one_word():
    p = personalized_control_praise_line("[O 本段寫作] 好", "客觀")
    assert p == ""
    q = personalized_control_praise_line("[O 本段寫作] 不知道", "客觀")
    assert q == ""


def test_control_feedback_short_o_with_anchor_uses_book_in_example():
    reply = format_control_feedback_reply(
        ok=False,
        missing=["內容還有點短，你可以試著多寫一點；也可以先看看下方「試試看這樣寫」的起頭，跟著接一句就好。"],
        suggestions=["你可以先寫出故事裡「誰做了什麼」一句，再補「後來……」接下去。"],
        stage="O",
        book_anchor="阿松爺爺把柿子藏到屋後倉庫",
        example=None,
        praise=personalized_control_praise_line("[O 本段寫作] 好", "客觀") or "",
        student_draft="[O 本段寫作] 好",
    )
    assert "阿松爺爺把柿子藏到屋後倉庫" in reply
    assert "誰做了什麼" in reply
    assert "故事中，＿＿＿做了＿＿＿" in reply


def test_genai_feedback_builder_changes_contract_by_stage():
    o_system, o_user = build_genai_feedback_prompts(
        stage="O",
        text="阿松爺爺把柿子藏起來。",
        book_pack=_book_pack(),
    )
    d_system, d_user = build_genai_feedback_prompts(
        stage="D",
        text="下次我會先分享一點零食。",
        book_pack=_book_pack(),
    )

    assert "角色清單（學生寫的角色名必須對照這裡）" in o_system
    assert "書名已知；D 段不做角色名查核。" in d_system
    assert "example：只給句型開頭、填空式提示或半句支架" in o_system
    assert "國小五、六年級" in o_system
    assert "40 分鐘" in o_system
    assert "一次只指出一個最重要的修改方向" in o_system
    assert "1 個問句" in o_system
    assert "2～4 個" not in o_system
    assert "學生「O」段原文如下" in o_user
    assert "不要" in o_user and ("書裡" in o_user or "故事裡" in o_user)
    assert "1 起步：只有感想，沒有寫出故事人物或事件。" in o_system
    assert "3 達標：能正確寫出人物與至少一件重要事件。" in o_system
    assert "學生「D」段原文如下" in d_user
    assert "對照上方「故事摘要」" not in d_user
    assert "student_anchor_quote" in o_system
    assert "draft_next_step" in o_system
    assert "RASF-Anchor" in o_system

    rag_system, _ = build_genai_feedback_prompts(
        stage="O",
        text="隔天用柿子蒂打陀螺",
        book_pack=_book_pack(),
        rag_context="「哎喲奶奶和小朋友用柿子蒂玩陀螺」",
    )
    assert "向量檢索" in rag_system
    assert "柿子蒂玩陀螺" in rag_system

    d_rag_system, _ = build_genai_feedback_prompts(
        stage="D",
        text="下次我會分享",
        book_pack=_book_pack(),
        rag_context="不應出現在 D 段",
    )
    assert "向量檢索" not in d_rag_system
    assert "不應出現在 D 段" not in d_rag_system

    ts_system, _ = build_genai_feedback_prompts(
        stage="O",
        text="好",
        book_pack=_book_pack(),
        input_bucket="too_short",
    )
    assert "輸入偏短" in ts_system

    mx_system, _ = build_genai_feedback_prompts(
        stage="O",
        text="I think 阿松爺爺 很自私",
        book_pack=_book_pack(),
        input_bucket="mixed_script",
    )
    assert "繁中文" in mx_system

    stuck_o, stuck_user = build_genai_feedback_prompts(
        stage="O",
        text="[O 本段寫作] 還不會寫。",
        book_pack=_book_pack(),
        input_bucket="normal",
    )
    stuck_o2, stuck_user2 = build_genai_feedback_prompts(
        stage="O",
        text="[O 本段寫作] 我不知道誰做了什麼",
        book_pack=_book_pack(),
        input_bucket="normal",
    )
    assert "本輪特別：O 段草稿極短或學生表達卡住" in stuck_user
    assert "本輪特別：O 段草稿極短或學生表達卡住" in stuck_user2
    assert "不要把完整答案寫好給學生複製" in stuck_o

    r_system, _ = build_genai_feedback_prompts(
        stage="R",
        text="我覺得很開心",
        book_pack=_book_pack(),
    )
    assert "1 個問句" in r_system
    assert "因為" in r_system


def test_week1_formal_orid_and_sel_rubrics_are_available():
    assert WEEK1_ORID_RUBRIC["schema"] == "writing_rubric_v1"
    assert WEEK1_ORID_RUBRIC["version"] == 4
    assert WEEK1_ORID_RUBRIC["by_stage"]["O"][0]["name"] == "客觀事實"
    assert WEEK1_ORID_RUBRIC["by_stage"]["O"][0]["levels"][2]["desc"] == (
        "人物正確；至少寫到開頭衝突，並再寫一段中間或結尾的重要情節，大致清楚、無明顯事實錯誤。"
    )
    assert WEEK1_ORID_RUBRIC["by_stage"]["D"][0]["levels"][3]["desc"] == (
        "能說明情境、對象、做法，並連回故事帶給自己的啟發。"
    )

    assert WEEK1_SEL_RUBRIC["schema"] == "sel_rubric_v1"
    assert WEEK1_SEL_RUBRIC["version"] == 2
    assert WEEK1_SEL_RUBRIC["by_stage"]["O"] == []
    assert [item["id"] for item in WEEK1_SEL_RUBRIC["by_stage"]["R"]] == [
        "SEL_SA",
        "SEL_SOA",
        "SEL_SM",
    ]
    assert [item["id"] for item in WEEK1_SEL_RUBRIC["by_stage"]["I"]] == [
        "SEL_SOA",
        "SEL_RS",
    ]
    assert [item["id"] for item in WEEK1_SEL_RUBRIC["by_stage"]["D"]] == [
        "SEL_RD",
        "SEL_SM",
        "SEL_RS",
    ]


def test_genai_feedback_prompt_uses_orid_as_primary_and_sel_as_auxiliary():
    pack = {
        **_book_pack(),
        "writing_rubric": WEEK1_ORID_RUBRIC,
        "sel_rubric": WEEK1_SEL_RUBRIC,
    }

    r_system, _ = build_genai_feedback_prompts(
        stage="R",
        text="我覺得很難過。",
        book_pack=pack,
    )
    assert "【ORID 主要評量標準" in r_system
    assert "ok 只依 ORID" in r_system
    assert "SEL 輔助引導" in r_system
    assert "故事中哪一個地方讓你有這種感覺" in r_system
    assert "你覺得阿松爺爺當時可能在想什麼" in r_system
    assert "不要在給學生的文字中直接使用「SEL」" in r_system
    assert "研究對準" in r_system
    assert "RQ1" in r_system and "RQ2" in r_system and "RQ3" in r_system
    assert "情緒覺察" in r_system

    i_system, _ = build_genai_feedback_prompts(
        stage="I",
        text="我學到要分享。",
        book_pack=pack,
    )
    assert "生活連結" in i_system
    assert "對準 RQ1" in i_system

    d_system, _ = build_genai_feedback_prompts(
        stage="D",
        text="我要更好。",
        book_pack=pack,
    )
    assert "負責任行動" in d_system

    o_system, _ = build_genai_feedback_prompts(
        stage="O",
        text="我覺得這個故事很溫暖。",
        book_pack=pack,
    )
    assert "不使用 SEL 輔助" in o_system
    assert "內部參考：情緒覺察" not in o_system
    assert "故事中哪一個地方讓你有這種感覺" not in o_system
    assert "對準 RQ1" in o_system


def test_normalize_feedback_focus_o_meta_stuck_prefers_spec_over_short_canned():
    m, s = normalize_feedback_focus(
        stage="O",
        missing=["內容還有點短，讀的人還看不出故事在演什麼"],
        suggestions=["我們先補一句「是誰做了什麼」，事情就會更清楚。"],
        student_text="我不知道誰做了什麼",
    )
    assert m[0] == GENAI_META_MISSING_FALLBACK
    assert "摘要" in s[0] or "摘錄" in s[0]


def test_normalize_feedback_focus_o_meta_stuck_keeps_book_anchored_model_output():
    m, s = normalize_feedback_focus(
        stage="O",
        missing=["你這句還在想故事裡誰先做什麼；我們先用書裡「阿松爺爺藏柿子」當第一句。"],
        suggestions=["你可以先寫故事裡阿松爺爺把柿子藏到倉庫，再接「後來……」。"],
        student_text="我不知道誰做了什麼",
    )
    assert "阿松爺爺" in m[0] + s[0]
    assert m[0] != GENAI_META_MISSING_FALLBACK


def test_coach_and_checker_builders_keep_expected_sections():
    coach_system = build_writing_coach_system_prompt(
        stage="R",
        book_context=build_book_context_block(_book_pack()),
        source="feedback_button",
        student_display_name="小華",
        student_login="student@school.edu",
        input_bucket="too_short",
        opening_hint="先多寫半句就好。",
        prev_ai_opener="我有看到你的訊息",
    )
    assert "ORID 寫作回饋同伴" in coach_system
    assert "只談目前段：R" in coach_system
    assert "小華" in coach_system
    assert "too_short" in coach_system
    assert "先多寫半句就好" in coach_system
    assert "本輪草稿中英混雜：可主動" not in coach_system

    coach_mixed = build_writing_coach_system_prompt(
        stage="O",
        book_context=build_book_context_block(_book_pack()),
        source="free_text",
        input_bucket="mixed_script",
    )
    assert "本輪草稿中英混雜：可主動" in coach_mixed

    narration_system, narration_user = build_feedback_narration_prompt(
        stage="I",
        feedback_json_summary='{"ok": true, "praise": "有提到故事事件"}',
        student_display_name="小華",
        student_login="x@y.z",
        student_draft_excerpt="我觉得故事很有趣。",
        input_bucket="mixed_script",
        opening_hint="先固定一種主要語言。",
        prev_ai_opener=None,
    )
    assert "每段最多 2 句" in narration_system
    assert "你已經做到：" in narration_system
    assert "再想一想：" in narration_system
    assert "可以這樣修改：" in narration_system
    assert "像老師坐在學生旁邊" in narration_system
    assert "書裡完全沒有的詞" in narration_system
    assert "RASF-Anchor" in narration_system
    assert "填空" in narration_system
    assert "故事覆蓋" in narration_system or "書裡情節" in narration_system or "去看／掃故事摘要" in narration_system
    assert "Markdown" in narration_system or "純文字" in narration_system
    assert "先肯定再引導" in narration_system
    assert "繁體中文為主" in narration_system
    assert "循序漸進" in narration_system
    assert "【I 段" in narration_system
    assert "生活連結" in narration_system
    assert "禁止「我們一步一步來」" in narration_system
    assert "2～4 個短任務" not in narration_system
    assert "可以這樣修改：" in narration_user
    assert "【輸入粗分類】mixed_script" in narration_user
    assert "我觉得故事很有趣" in narration_user
    assert "結構化回饋 JSON" in narration_user

    synthesis_system = build_synthesis_coach_system_prompt(
        book_context=build_book_context_block(_book_pack()),
        week1_orid_lines={"O": "他把柿子藏起來", "R": "", "I": "", "D": ""},
        student_display_name="小華",
        student_login=None,
        opening_hint="先檢查段落銜接。",
        prev_ai_opener="我有看到",
    )
    assert "第 1 週四段（唯讀參考）" in synthesis_system
    assert "O 客觀" in synthesis_system
    assert "小華" in synthesis_system
    assert "先檢查段落銜接" in synthesis_system
    assert "你已經做到：" in synthesis_system
    assert "再想一想：" in synthesis_system
    assert "可以這樣修改：" in synthesis_system
    assert "SEL 表現" in synthesis_system
    assert "生活連結" in synthesis_system
    assert "優先規則" in synthesis_system
    assert "完整 ≠ 連貫" in synthesis_system
    assert "硬串" in synthesis_system
    assert "串起來了" in synthesis_system
    assert "不做正式計分" in synthesis_system
    assert "回到整合寫作格子" in synthesis_system
    # 可選 meta 仍會插入中段；預設不傳時僅有 playbook 內建「三段標題」與週一區塊，無【學生自填閱讀心得】中段
    assert "【學生自填閱讀心得" not in synthesis_system
    assert "【當前寫作階段】" not in synthesis_system
    assert "草稿看起來像是把上週幾段" not in synthesis_system

    syn_layered = build_synthesis_coach_system_prompt(
        book_context=build_book_context_block(_book_pack()),
        week1_orid_lines={"O": "他把柿子藏起來", "R": "", "I": "", "D": ""},
        synthesis_phase="short_draft",
        feedback_round=1,
        reading_excerpt="我讀到分享很重要。",
    )
    assert "【學生自填閱讀心得／摘記節選（唯讀）】" in syn_layered
    assert "我讀到分享很重要" in syn_layered
    assert "【當前寫作階段】" in syn_layered
    assert "【本輪回饋層級" in syn_layered
    assert "完整性" in syn_layered and "連貫性" in syn_layered

    syn_r2 = build_synthesis_coach_system_prompt(
        book_context=build_book_context_block(_book_pack()),
        week1_orid_lines={"O": "他把柿子藏起來", "R": "", "I": "", "D": ""},
        synthesis_phase="short_draft",
        feedback_round=2,
    )
    assert "SEL表現" in syn_r2 or "SEL 表現" in syn_r2
    assert "反思深度" in syn_r2

    syn_r2_depth = build_synthesis_coach_system_prompt(
        book_context=build_book_context_block(_book_pack()),
        week1_orid_lines={"O": "他把柿子藏起來", "R": "", "I": "", "D": ""},
        feedback_round=2,
        student_text=(
            "讀完阿松爺爺的故事後，我最記得他一開始把甜柿子藏起來、不肯分享，"
            "這讓我覺得他很小氣也很孤單。"
            "後來看到大家因為分享變得開心，我才明白分享其實可以讓自己和別人都更好過。"
            "所以下次當球場上有人想加入我們，我會先說好啊，再約他一起練投籃。"
        ),
    )
    assert "【第二輪／銜接已大致足夠】" in syn_r2_depth
    assert "不要**去改短／拆句" in syn_r2_depth or "不要**要求改短／拆句" in syn_r2_depth
    assert "【本輪為第二輪】" in syn_r2_depth
    assert "不是把句子改短" in syn_r2_depth

    checker_system, checker_user = build_book_grounding_checker_prompts(
        student_text="阿松爺爺把柿子藏到屋後倉庫",
        book_pack=_book_pack(),
        stage="O",
    )
    assert "教材事實核對器" in checker_system
    assert "BOOK_CONTEXT" in checker_system
    assert "學生句子" in checker_user


def test_synthesis_pasted_stage_paragraphs_detection():
    """複製 O/R/I/D 按鈕直接貼上（未加銜接語）應被偵測到，觸發連貫性優先提示。"""
    from app.prompts.builders.coach_chat import looks_like_pasted_stage_paragraphs

    week1_lines = {
        "O": "阿松爺爺一開始都不分享柿子，總是自己吃掉一些柿子",
        "R": "因為看到阿松爺爺打抱不平，凶巴巴的把老爺爺趕跑",
        "I": "這件事讓我學到，獨自吃東西沒有和大家一起分享有趣",
        "D": "下次我遇到有好東西的時候，也想跟朋友分享",
    }
    pasted_draft = "\n".join(week1_lines.values())
    assert looks_like_pasted_stage_paragraphs(pasted_draft, week1_lines) is True

    # A freshly written synthesis paragraph (not verbatim copies) must not trigger it.
    written_draft = (
        "故事中阿松爺爺很自私，我覺得很生氣。後來大家決定要一起分享，"
        "我學到分享比獨占快樂。下次我也想試著分享。"
    )
    assert looks_like_pasted_stage_paragraphs(written_draft, week1_lines) is False

    # No Week-1 reference lines available (e.g. empty week1) — can't detect, default False.
    assert looks_like_pasted_stage_paragraphs(pasted_draft, None) is False
    assert looks_like_pasted_stage_paragraphs(pasted_draft, {}) is False

    synthesis_pasted_system = build_synthesis_coach_system_prompt(
        book_context=build_book_context_block(_book_pack()),
        week1_orid_lines=week1_lines,
        student_text=pasted_draft,
    )
    assert "草稿看起來像是把上週幾段" in synthesis_pasted_system
    assert "連貫性" in synthesis_pasted_system
    assert "不要**要求整篇重寫" in synthesis_pasted_system
    assert "先不要談 SEL" in synthesis_pasted_system

    synthesis_written_system = build_synthesis_coach_system_prompt(
        book_context=build_book_context_block(_book_pack()),
        week1_orid_lines=week1_lines,
        student_text=written_draft,
    )
    assert "草稿看起來像是把上週幾段" not in synthesis_written_system


def test_synthesis_hard_stitched_orid_forces_coherence_priority():
    """硬串偵測不綁定特定書本人名／情節，靠通用連貫線索判斷。"""
    from app.prompts.builders.coach_chat import find_abrupt_orid_boundaries, looks_like_hard_stitched_orid_synthesis

    hard_stitched = (
        "故事裡阿松爺爺的柿子很甜，卻都不分享給別人，只把蒂跟葉子給別人，"
        "後來葉子變成有趣的東西，爺爺就不給了把葉子藏起來，最後還把樹砍掉。"
        "我覺得爺爺這樣很小氣。"
        "這件事讓我學到分享不一定是壞事，因為後來分享反而有驚喜。"
        "下次我打籃球有人要報隊，我不會拒絕，會跟他一起打，學新技巧。"
    )
    assert looks_like_hard_stitched_orid_synthesis(hard_stitched) is True

    # Same hard-stitch pattern but a completely different book/story/action —
    # detector must generalise, not key off this one essay's nouns.
    other_book_hard_stitched = (
        "書裡的小熊一開始都自己躲在洞裡看書，不跟其他動物玩，也不借書給別人。"
        "我覺得小熊這樣很孤單，看起來也不快樂。"
        "這件事讓我學到，一個人看書雖然自由，但少了朋友會很無聊。"
        "以後班上分組的時候，我不會自己選好朋友就好，會多找還沒有組別的同學。"
    )
    assert looks_like_hard_stitched_orid_synthesis(other_book_hard_stitched) is True

    integrated = (
        "讀完阿松爺爺的故事後，我最記得他一開始把甜柿子藏起來、不肯分享，"
        "這讓我覺得他很小氣也很孤單。"
        "後來看到大家因為分享變得開心，我才明白分享其實可以讓自己和別人都更好過。"
        "所以下次當球場上有人想加入我們，我會先說好啊，再約他一起練投籃。"
    )
    assert looks_like_hard_stitched_orid_synthesis(integrated) is False

    # Weaker case: only one abrupt transition (R→I has a connector, I→D doesn't)
    # should not fire the full force-block — avoids over-triggering on essays
    # that are mostly fine with just one soft spot.
    mostly_ok_one_gap = (
        "故事裡的小熊一開始都自己躲在洞裡看書，不跟其他動物玩。"
        "我覺得小熊這樣很孤單，這讓我覺得他其實也想要朋友。"
        "我才明白，一個人看書雖然自由，但少了朋友會很無聊。"
        "以後班上分組的時候，我會多找還沒有組別的同學。"
    )
    boundaries = find_abrupt_orid_boundaries(mostly_ok_one_gap)
    assert len(boundaries) <= 1
    assert looks_like_hard_stitched_orid_synthesis(mostly_ok_one_gap) is False

    system = build_synthesis_coach_system_prompt(
        book_context=build_book_context_block(_book_pack()),
        week1_orid_lines={"O": "他把柿子藏起來", "R": "", "I": "", "D": ""},
        student_text=hard_stitched,
    )
    assert "【偵測】草稿雖然故事／感受／體會／行動大致都有" in system
    assert "完整 ≠ 連貫" in system
    assert "本輪先不要談 SEL" in system
    assert "串起來了" in system
    assert "行動精修" in system
    assert "不要**去改『行動』那一句本身的長短或拆句" in system
    # Points at the actual weak boundary rather than a fixed script.
    assert "銜接特別不足的地方大約在" in system

    integrated_system = build_synthesis_coach_system_prompt(
        book_context=build_book_context_block(_book_pack()),
        week1_orid_lines={"O": "他把柿子藏起來", "R": "", "I": "", "D": ""},
        student_text=integrated,
    )
    assert "【偵測】草稿雖然故事／感受／體會／行動大致都有" not in integrated_system
    assert "【偵測】草稿看起來像是把上週幾段" not in integrated_system


def test_normalize_feedback_focus_o_high_avoids_sequence_regression():
    long_o = (
        "一開始阿松爺爺把柿子都藏起來，然後只給哎唷奶奶柿子蒂，隔天，"
        "哎唷奶奶和小朋友用柿子蒂打陀螺，玩得很開心。"
    )
    missing, suggestions = normalize_feedback_focus(
        stage="O",
        missing=[""],
        suggestions=[""],
        student_text=long_o,
    )
    assert "先發生、後發生" not in missing[0]
    assert ("書裡" in missing[0]) or ("故事" in missing[0]) or ("細節" in missing[0]) or ("轉折" in missing[0]) or ("銜接" in missing[0]) or ("旁人" in missing[0]) or ("反應" in missing[0])
    assert len(suggestions) == 1


def test_normalize_feedback_focus_o_high_fallback_never_polish_only_pool():
    """Hash-picked fallback must not claim 'summary already covered' without real alignment."""
    long_o = (
        "一開始阿松爺爺把柿子都藏起來，然後只給哎唷奶奶柿子蒂，隔天，"
        "哎唷奶奶和小朋友用柿子蒂打陀螺，玩得很開心。"
    )
    _missing, suggestions = normalize_feedback_focus(
        stage="O",
        missing=[""],
        suggestions=[""],
        student_text=long_o,
    )
    assert "小升級" not in suggestions[0]


def test_strip_markdown_for_student_chat_removes_bold_markers():
    assert strip_markdown_for_student_chat("a**b**c") == "abc"
    assert "**" not in strip_markdown_for_student_chat("選一個**大事件**來寫")


def test_o_draft_meets_pass_bar():
    # Opening + mid + late → pass
    assert o_draft_meets_pass_bar(
        "阿松爺爺家的柿子很甜，可是他一直自己吃，不想分給別人。"
        "哎唷奶奶搬來後，他只給她柿子蒂。後來他把柿子藏進倉庫，最後還把樹砍掉，只剩樹樁。"
    )
    # Feeling only → fail
    assert not o_draft_meets_pass_bar("我覺得這個故事很溫暖。")
    # Only one beat → fail
    assert not o_draft_meets_pass_bar("阿松爺爺把柿子藏起來。")
    # Early+mid only (no climax) → fail; student still needs 砍樹／樹樁等
    assert not o_draft_meets_pass_bar(
        "故事裡我看到阿松爺爺不分享柿子，然後只給奶奶柿子蒂，後來他把柿子都採下來藏進倉庫。"
    )


def test_apply_o_key_event_gaps_skips_when_pass_bar_met():
    """Already level-3-worthy O drafts must not keep getting more plot homework."""
    pass_o = (
        "阿松爺爺家的柿子很甜，可是他一直自己吃，不想分給別人。"
        "哎唷奶奶搬來後，他只給她柿子蒂。後來他把柿子藏進倉庫，最後還把樹砍掉，只剩樹樁。"
    )
    key_events = [
        "阿松爺爺家的柿子很甜，但他一直想把柿子獨占起來，不想分給別人。",
        "阿松爺爺在大家面前吃柿子、炫耀柿子有多好，旁人只能羨慕地看著。",
        "阿松爺爺擔心大家來要柿子蒂，急忙把柿子樹上的柿子都採下來藏到屋後倉庫。",
        "阿松爺爺為了不讓大家再拿到，急忙砍樹，最後發現只剩樹樁。",
    ]
    m, s = apply_o_key_event_gaps(
        stage="O",
        strength="high",
        student_text=pass_o,
        key_events=key_events,
        missing=["你已經抓到重點事件了：下一步試著寫出故事裡還沒提到的一段"],
        suggestions=["先挑書裡一件你稿子上還沒寫到的事"],
    )
    assert m[0].startswith("你已經抓到重點事件了")
    assert "書裡還有這些情節" not in m[0]


def test_apply_o_key_event_gaps_replaces_generic_o_when_events_missing():
    # Thin O: character + only one beat → still below pass bar, gaps may fill in
    long_o = "一開始阿松爺爺把柿子都藏起來，玩得很開心。"
    key_events = [
        "阿松爺爺家的柿子很甜，但他一直想把柿子獨占起來，不想分給別人。",
        "阿松爺爺在大家面前吃柿子、炫耀柿子有多好，旁人只能羨慕地看著。",
        "阿松爺爺擔心大家來要柿子蒂，急忙把柿子樹上的柿子都採下來藏到屋後倉庫，結果小朋友來要時樹上已沒有柿子。",
        "阿松爺爺改拿出採柿子時掉下來的一片「柿子葉」給大家，哎唷奶奶和小朋友很開心並帶回去。",
        "阿松爺爺再改拿出打葉子時掉落的一根「樹枝」給大家；隔天哎唷奶奶和小朋友用樹枝烤麵包、吃得很開心，還說樹枝快不夠用。",
        "阿松爺爺為了不讓大家再拿到，急忙砍樹枝，最後發現自己竟把整棵柿子樹弄到只剩樹椿，後悔大哭。",
    ]
    m, s = apply_o_key_event_gaps(
        stage="O",
        strength="high",
        student_text=long_o,
        key_events=key_events,
        missing=["你已經抓到重點事件了：下一步試著寫出故事裡還沒提到的一段"],
        suggestions=["先挑書裡一件你稿子上還沒寫到的事，用三句話寫出誰、做了什麼、後來怎麼了"],
    )
    blob = m[0] + s[0]
    assert "倉庫" in blob or "柿子葉" in blob or "樹枝" in blob or "砍" in blob or "獨占" in blob or "柿子蒂" in blob
    assert "中間衝突" not in m[0]


def test_apply_o_key_event_gaps_skips_grounding_priority_missing():
    m, s = apply_o_key_event_gaps(
        stage="O",
        strength="high",
        student_text="一開始阿松爺爺把柿子都藏起來。",
        key_events=["阿松爺爺把柿子藏到屋後倉庫"],
        missing=["你寫的「外星人」看起來不在書裡；書裡說的是「阿松爺爺」。"],
        suggestions=["請改成書裡的人物與事件"],
    )
    assert "外星人" in m[0]


def test_control_feedback_o_meta_stuck_reply_uses_anchor_nudge_not_raw_missing():
    reply = format_control_feedback_reply(
        ok=False,
        missing=[CONTROL_O_META_MISSING],
        suggestions=["請你先把故事摘要裡一個誰做了什麼寫成一句。"],
        stage="O",
        book_anchor="阿松爺爺把柿子藏到屋後倉庫",
        example=None,
        student_draft="我不知道誰做了什麼",
    )
    assert "故事裡到底是誰做了什麼" in reply
    assert "阿松爺爺把柿子藏到屋後倉庫" in reply


def test_control_feedback_o_meta_stuck_prefers_book_anchor_over_echo_suggestion():
    reply = format_control_feedback_reply(
        ok=False,
        missing=["內容還有點短，讀的人還看不出故事在演什麼"],
        suggestions=["我們先補一句「是誰做了什麼」，事情就會更清楚。"],
        stage="O",
        book_anchor="阿松爺爺把柿子藏到屋後倉庫",
        example=None,
        student_draft="我不知道誰做了什麼",
    )
    assert "阿松爺爺把柿子藏到屋後倉庫" in reply
    assert "故事裡有「" in reply
    assert "我們先補一句「是誰做了什麼」" not in reply
    assert "故事裡到底是誰做了什麼" in reply


def test_control_feedback_reply_does_not_prefix_step_by_step():
    reply = format_control_feedback_reply(
        ok=False,
        missing=["事件順序還能再清楚一點"],
        suggestions=["把先發生什麼、後來怎樣補出來，讀的人就更容易懂。"],
        stage="O",
        book_anchor="阿松爺爺把柿子藏到屋後倉庫",
        example="故事裡先發生的是阿松爺爺把柿子藏起來，後來大家才知道他不想分給別人。",
        student_draft="阿松爺爺不分享柿子",
    )
    assert "我們一步一步來" not in reply
    assert "誰做了什麼" in reply
    assert "故事中，＿＿＿做了＿＿＿" in reply


def test_prompt_versions_cover_active_surfaces():
    assert {
        "writing_assist_d1",
        "writing_assist_d2",
        "genai_feedback",
        "feedback_narration",
        "writing_coach",
        "synthesis_coach",
        "book_grounding_checker",
        "orid_checker",
    }.issubset(PROMPT_VERSIONS.keys())
    assert PROMPT_VERSIONS["genai_feedback"] == "wf_v11"
    assert PROMPT_VERSIONS["feedback_narration"] == "fn_v11"
    assert PROMPT_VERSIONS["synthesis_coach"] == "sc_v12"
