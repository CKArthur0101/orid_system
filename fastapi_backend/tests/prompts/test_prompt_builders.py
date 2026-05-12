from app.prompts.builders.checker import build_book_grounding_checker_prompts
from app.prompts.builders.coach_chat import (
    build_feedback_narration_prompt,
    build_synthesis_coach_system_prompt,
    build_writing_coach_system_prompt,
)
from app.prompts.builders.writing_assist import build_writing_d1_prompts, build_writing_d2_prompts
from app.prompts.builders.writing_feedback import build_genai_feedback_prompts
from app.prompts.shared_parts.book_context import build_book_context_block
from app.prompts.versions import PROMPT_VERSIONS


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
    assert "example：給 1–2 句與學生原文貼近的續寫小例子" in o_system
    assert "國小五、六年級" in o_system
    assert "一步一步帶寫" in o_system
    assert "學生「O」段原文如下" in o_user
    assert "學生「D」段原文如下" in d_user


def test_coach_and_checker_builders_keep_expected_sections():
    coach_system = build_writing_coach_system_prompt(
        stage="R",
        book_context=build_book_context_block(_book_pack()),
        source="feedback_button",
    )
    assert "ORID 寫作回饋同伴" in coach_system
    assert "只談目前段：R" in coach_system

    narration_system, narration_user = build_feedback_narration_prompt(
        stage="I",
        feedback_json_summary='{"ok": true, "praise": "有提到故事事件"}',
    )
    assert "你已經做到：" in narration_system
    assert "你可以再加強：" in narration_system
    assert "試試看這樣寫：" in narration_system
    assert "像老師坐在學生旁邊" in narration_system
    assert "一步一步" in narration_system
    assert "第二段**一定要保留這個重點**" in narration_system
    assert "若 JSON 裡有 example，請保留成「例如：……」" in narration_system
    assert "結構化回饋 JSON" in narration_user

    synthesis_system = build_synthesis_coach_system_prompt(
        book_context=build_book_context_block(_book_pack()),
        week1_orid_lines={"O": "他把柿子藏起來", "R": "", "I": "", "D": ""},
    )
    assert "第 1 週四段（唯讀參考）" in synthesis_system
    assert "O 客觀" in synthesis_system

    checker_system, checker_user = build_book_grounding_checker_prompts(
        student_text="阿松爺爺把柿子藏到屋後倉庫",
        book_pack=_book_pack(),
        stage="O",
    )
    assert "教材事實核對器" in checker_system
    assert "BOOK_CONTEXT" in checker_system
    assert "學生句子" in checker_user


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
