from app.prompts.parsers.json_payloads import (
    extract_json_object,
    parse_book_grounding_checker_json,
    parse_orid_checker_json,
)
from app.prompts.parsers.writing_assist import parse_writing_assist_response


def test_parse_writing_assist_response_splits_tips():
    raw = "改寫後段落。\n【TIPS】\n1) 補一句原因\n2) 把順序寫清楚\n3) 刪掉重複"
    draft_text, tips = parse_writing_assist_response(raw)
    assert draft_text == "改寫後段落。"
    assert tips == ["補一句原因", "把順序寫清楚", "刪掉重複"]


def test_parse_writing_assist_response_without_split_returns_raw_text():
    draft_text, tips = parse_writing_assist_response("只有草稿內容")
    assert draft_text == "只有草稿內容"
    assert tips == []


def test_json_parsers_extract_embedded_object():
    raw = '前文說明 {"grounded": false, "reason": "疑似新增書外事件", "unsupported_span": "去打籃球"} 後文'
    obj = parse_book_grounding_checker_json(raw)
    assert obj["grounded"] is False
    assert obj["unsupported_span"] == "去打籃球"

    raw2 = '```json {"unsafe_language": false, "off_topic": false, "reason": "OK", "suggested_question": "接著發生了什麼？"} ```'
    obj2 = parse_orid_checker_json(raw2)
    assert obj2["off_topic"] is False
    assert "接著發生了什麼" in obj2["suggested_question"]


def test_extract_json_object_reuses_manual_contract():
    raw = 'noise {"ok": true, "missing": [], "suggestions": ["我覺得……，因為……"]} noise'
    obj = extract_json_object(raw)
    assert obj["ok"] is True
    assert obj["suggestions"] == ["我覺得……，因為……"]
