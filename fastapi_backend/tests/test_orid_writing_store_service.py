from app.services.orid_writing_store import ensure_orid_writing_obj, upsert_feedback_into_stage


def _empty(week: int):
    return {
        "schema": "orid_writing_v1",
        "week": week,
        "stages": {
            "O": {"d1": "", "d2": ""},
            "R": {"d1": "", "d2": ""},
            "I": {"d1": "", "d2": ""},
            "D": {"d1": "", "d2": ""},
        },
    }


def test_ensure_orid_writing_obj_fallback_to_empty():
    obj = ensure_orid_writing_obj(raw_content="{broken", week=1, empty_factory=_empty)
    assert obj["schema"] == "orid_writing_v1"
    assert obj["week"] == 1


def test_upsert_feedback_syncs_current_draft_text():
    obj = _empty(1)
    out = upsert_feedback_into_stage(
        obj=obj,
        stage="R",
        draft="d1",
        text="最新草稿內容",
        ok=False,
        missing=["缺少原因"],
        suggestions=["補上因為"],
        example=None,
        improved=None,
        empty_factory=_empty,
    )
    assert out["stages"]["R"]["d1"] == "最新草稿內容"
    assert out["stages"]["R"]["feedback"]["d1"]["missing"] == ["缺少原因"]

