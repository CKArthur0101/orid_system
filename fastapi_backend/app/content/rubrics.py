from __future__ import annotations

from copy import deepcopy
from typing import Any


def _item(
    criterion_id: str,
    name: str,
    focus: str,
    levels: list[str],
    prompts: list[str] | None = None,
) -> dict[str, Any]:
    labels = ("1 起步", "2 接近", "3 達標", "4 精進")
    item: dict[str, Any] = {
        "id": criterion_id,
        "name": name,
        "focus": focus,
        "levels": [
            {"label": label, "desc": desc}
            for label, desc in zip(labels, levels, strict=True)
        ],
    }
    if prompts:
        item["student_prompts"] = prompts
    return item


UNIFIED_ORID_RUBRIC: dict[str, Any] = {
    "schema": "writing_rubric_v1",
    "version": 5,
    "purpose": "primary_orid_feedback_and_stage_completion",
    "score_range": "1-4",
    "ok_rule": "level_3_or_4_true_level_1_or_2_false",
    "student_bands": {"1": "開始寫", "2": "差一點", "3": "不錯", "4": "很好"},
    "by_stage": {
        "O": [
            _item(
                "O1",
                "客觀觀察",
                "依文本寫出重要人物、事件與故事發展",
                [
                    "沒有寫到故事內容、明顯偏題，或只有個人看法。",
                    "寫到部分正確的人物或事件，但內容不完整，人物關係或事件順序不清楚。",
                    "正確寫出重要人物與事件，能看出故事的大致發展。",
                    "能依序整理多個重要事件，並清楚呈現人物、事件或情節的變化。",
                ],
            )
        ],
        "R": [
            _item(
                "R1",
                "感受反應",
                "表達自己的感受，並以故事內容說明原因",
                [
                    "沒有表達自己的感受，或感受與故事無關。",
                    "有寫出感受，但原因模糊，或只有重述故事事件。",
                    "清楚寫出自己的感受，並用故事中的事件或畫面說明原因。",
                    "能深入解釋感受、察覺感受的變化，或理解角色為何引起這種感受。",
                ],
            )
        ],
        "I": [
            _item(
                "I1",
                "詮釋體會",
                "說出對故事的理解或啟發，並以故事內容支持",
                [
                    "只有重述故事、空泛口號，或內容偏題。",
                    "有提出道理或想法，但較籠統，缺少故事依據。",
                    "清楚寫出學到的道理或對故事的理解，並以故事內容支持。",
                    "能進一步說明行為與結果的關係，並連結自己的生活經驗或觀點。",
                ],
            )
        ],
        "D": [
            _item(
                "D1",
                "行動決定",
                "提出具體可行且呼應故事體會的個人行動",
                [
                    "只有願望或口號，沒有寫出自己的實際行動。",
                    "有行動方向，但仍不清楚要做什麼，或與故事體會的連結較弱。",
                    "寫出一個自己能做到、具體可行，而且呼應故事體會的行動。",
                    "能進一步說明適用情境、做法或第一步，也能考慮可能遇到的困難與調整方式。",
                ],
            )
        ],
    },
}


_SA_LEVELS = [
    "未表達自己的感受或想法。",
    "能說出感受或想法，但原因不清楚。",
    "能說明自己的感受、想法及其原因。",
    "能察覺感受的變化，並理解感受、想法與行為之間的關係。",
]
_SM_LEVELS = [
    "沒有提出調整方法或可實行策略。",
    "有改善意願，但做法較模糊。",
    "能提出一個可行的自我調整或持續行動方法。",
    "能預想困難，並提出提醒、調整或持續實行的方法。",
]
_SOA_LEVELS = [
    "只從自己的角度看事情，未注意他人。",
    "知道別人可能有感受或需要，但描述較籠統。",
    "能根據故事或情境理解他人的感受與需要。",
    "能理解不同角色的立場、原因與情境差異。",
]
_RS_LEVELS = [
    "沒有提出互動方法，或提出的方法可能造成衝突。",
    "只寫出幫忙、合作或溝通等概括方向。",
    "能提出具體的傾聽、表達、合作或求助方法。",
    "能兼顧自己與他人，並提出尊重、協調或處理衝突的方法。",
]
_RD_LEVELS = [
    "沒有提出選擇，或提出的行動明顯不合適。",
    "知道應該怎麼做，但沒有說明具體做法或可能影響。",
    "能提出安全、尊重他人且可行的選擇。",
    "能思考行動後果、比較不同選擇，並說明必要時如何調整。",
]


UNIFIED_SEL_RUBRIC: dict[str, Any] = {
    "schema": "sel_rubric_v1",
    "version": 3,
    "purpose": "auxiliary_guidance_and_observational_evidence",
    "framework": "CASEL_five_competencies",
    "student_language_policy": (
        "Do not mention SEL dimension names to students; convert them into one "
        "concrete, age-appropriate question that still serves the current ORID gap."
    ),
    "by_stage": {
        "O": [],
        "R": [
            _item(
                "SEL_SA",
                "自我覺察",
                "辨認自己的感受、想法與原因",
                _SA_LEVELS,
                [
                    "故事中的哪一個地方讓你有這種感覺？",
                    "你的感覺有沒有前後變化？為什麼？",
                ],
            ),
            _item(
                "SEL_SOA",
                "社會覺察",
                "理解角色或他人的感受、需要與立場",
                _SOA_LEVELS,
                [
                    "故事中的角色當時可能有什麼感受或需要？",
                    "不同角色看這件事時，可能有什麼不一樣？",
                ],
            ),
        ],
        "I": [
            _item(
                "SEL_SOA",
                "社會覺察",
                "理解角色或他人的感受、需要與立場",
                _SOA_LEVELS,
                [
                    "角色的做法對別人造成了什麼影響？",
                    "換成另一個角色來看，這件事可能有什麼不同？",
                ],
            ),
            _item(
                "SEL_RS",
                "人際技巧",
                "以合適的方法表達、傾聽、合作或求助",
                _RS_LEVELS,
                [
                    "遇到類似情況時，你可以怎麼說，讓對方理解你？",
                    "如果需要合作或求助，你會怎麼開口？",
                ],
            ),
        ],
        "D": [
            _item(
                "SEL_RD",
                "負責任的決定",
                "作出安全、尊重他人且可行的選擇",
                _RD_LEVELS,
                [
                    "這個行動可能會對你或別人帶來什麼影響？",
                    "如果原來的方法不適合，你還可以怎麼調整？",
                ],
            ),
            _item(
                "SEL_SM",
                "自我管理",
                "提出可行的自我調整或持續行動方法",
                _SM_LEVELS,
                [
                    "遇到困難時，你可以先用什麼方法提醒或調整自己？",
                    "你要怎麼讓自己持續做到這個行動？",
                ],
            ),
            _item(
                "SEL_RS",
                "人際技巧",
                "以合適的方法表達、傾聽、合作或求助",
                _RS_LEVELS,
                [
                    "這個行動需要和誰互動？你會怎麼說或怎麼做？",
                    "你要怎麼兼顧自己和對方的感受？",
                ],
            ),
        ],
    },
}


# Each week receives its own object to prevent accidental cross-week mutation,
# while descriptors and thresholds remain identical across all three books.
WEEK1_ORID_RUBRIC: dict[str, Any] = deepcopy(UNIFIED_ORID_RUBRIC)
WEEK3_ORID_RUBRIC: dict[str, Any] = deepcopy(UNIFIED_ORID_RUBRIC)
WEEK5_ORID_RUBRIC: dict[str, Any] = deepcopy(UNIFIED_ORID_RUBRIC)

WEEK1_SEL_RUBRIC: dict[str, Any] = deepcopy(UNIFIED_SEL_RUBRIC)
WEEK3_SEL_RUBRIC: dict[str, Any] = deepcopy(UNIFIED_SEL_RUBRIC)
WEEK5_SEL_RUBRIC: dict[str, Any] = deepcopy(UNIFIED_SEL_RUBRIC)
