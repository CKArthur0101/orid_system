from __future__ import annotations

from typing import Any


WEEK1_ORID_RUBRIC: dict[str, Any] = {
    "schema": "writing_rubric_v1",
    "version": 4,
    "purpose": "primary_orid_feedback_and_research_scoring",
    "score_range": "1-4",
    "scoring_formula": "triangular_cumulative_v1",
    "scoring_note": (
        "level n → n*(n+1)/2 pts (1→1, 2→3, 3→6, 4→10); "
        "ORID max 40, SEL max 50, total max 90"
    ),
    "total_score": (
        "ORID(O1+R1+I1+D1) max 40 + "
        "SEL(SEL_SA+SEL_SM+SEL_SOA+SEL_RS+SEL_RD) max 50 = 90"
    ),
    "ok_rule": "level_3_or_4_true_level_1_or_2_false",
    "student_bands": {
        "1": "開始寫",
        "2": "差一點",
        "3": "不錯",
        "4": "很好",
    },
    "by_stage": {
        "O": [
            {
                "id": "O1",
                "name": "客觀事實",
                "focus": "依文本寫人物、事件與大致順序",
                "levels": [
                    {"label": "1 起步", "desc": "只有感想，或與故事事實對不上。"},
                    {"label": "2 接近", "desc": "有人物／事件，但只寫開頭＋一小段，缺中間發展或結尾轉折，整體仍偏短。"},
                    {"label": "3 達標", "desc": "人物正確；開頭衝突、中間發展、結尾轉折都至少各寫到一點，大致清楚、無明顯事實錯誤。"},
                    {"label": "4 精進", "desc": "能串起開頭→中間→轉折的多件事件，並呈現故事變化或重要細節。"},
                ],
            }
        ],
        "R": [
            {
                "id": "R1",
                "name": "感受反應",
                "focus": "表達感受並說明原因（連回故事）",
                "levels": [
                    {"label": "1 起步", "desc": "只有空洞感受（如很好、開心），沒有原因。"},
                    {"label": "2 接近", "desc": "有感受與簡短原因，但偏短；或幾乎沒寫到書裡具體那一幕。"},
                    {"label": "3 達標", "desc": "有明確感受、清楚原因，並點出書裡具體一幕（誰做了什麼），篇幅不只一句口號。"},
                    {"label": "4 精進", "desc": "感受具體；能連結角色、事件或自身經驗與感受的關係。"},
                ],
            }
        ],
        "I": [
            {
                "id": "I1",
                "name": "詮釋意義",
                "focus": "說出道理／啟發並用故事支持",
                "levels": [
                    {"label": "1 起步", "desc": "只有空泛道理（如要善良、要做好事）。"},
                    {"label": "2 接近", "desc": "有想法，但偏短；或只說「要大方／不要小氣」，沒有清楚連回故事情節。"},
                    {"label": "3 達標", "desc": "能說出從故事學到的道理，並用書裡一件具體事件支持；不是一句口號就結束。"},
                    {"label": "4 精進", "desc": "啟發有深度；能連結角色行為、故事結果或生活經驗。"},
                ],
            }
        ],
        "D": [
            {
                "id": "D1",
                "name": "行動決定",
                "focus": "提出生活中可執行的具體行動",
                "levels": [
                    {"label": "1 起步", "desc": "只有空願望（如我要變好、我要努力）。"},
                    {"label": "2 接近", "desc": "有行動方向，但不夠具體（如只說「去幫忙」），不清楚何時、對誰或怎麼做。"},
                    {"label": "3 達標", "desc": "能提出生活中可做到的具體行動，含情境／對象／第一步，不是一句空話。"},
                    {"label": "4 精進", "desc": "能說明情境、對象、做法，並連回故事帶給自己的啟發。"},
                ],
            }
        ],
    },
}


WEEK1_SEL_RUBRIC: dict[str, Any] = {
    "schema": "sel_rubric_v1",
    "version": 2,
    "purpose": "auxiliary_guidance_and_research_scoring",
    "framework": "CASEL_five_competencies",
    "scoring_formula": "triangular_cumulative_v1",
    "scoring_note": (
        "Same formula as ORID: level n → n*(n+1)/2 pts; "
        "SEL max 50 (SEL_SA+SEL_SM+SEL_SOA+SEL_RS+SEL_RD). "
        "Does not decide feedback_ok."
    ),
    "student_language_policy": (
        "Do not mention SEL dimension names to students; "
        "convert them into concrete questions. "
        "Prefer student bands: 差一點／不錯／很好."
    ),
    "by_stage": {
        "O": [],
        "R": [
            {
                "id": "SEL_SA",
                "name": "自我覺察",
                "focus": "辨認並表達自己的感受與想法",
                "student_prompts": [
                    "故事中哪一個地方讓你有這種感覺？",
                    "你的感覺可以再說得更清楚一點嗎？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "幾乎沒有表達感受或想法，或只使用很籠統的詞語。"},
                    {"label": "2 接近", "desc": "能寫出一種感受或想法，但較少說明為什麼。"},
                    {"label": "3 達標", "desc": "能清楚說出自己的感受或想法，並說明與故事事件的關係。"},
                    {"label": "4 精進", "desc": "能更細緻描述感受或想法，並理解自己為何有這種反應或變化。"},
                ],
            },
            {
                "id": "SEL_SOA",
                "name": "社會覺察",
                "focus": "理解角色或他人的感受、想法與立場",
                "student_prompts": [
                    "你覺得阿松爺爺當時可能在想什麼？",
                    "如果你是故事裡的人，你可能會有什麼感覺？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "只從自己的角度描述，較少注意角色或他人的感受。"},
                    {"label": "2 接近", "desc": "有提到角色或他人的感受，但說明較簡單。"},
                    {"label": "3 達標", "desc": "能理解角色可能的感受或想法，並能連結故事事件說明原因。"},
                    {"label": "4 精進", "desc": "能比較不同角色的立場，或說明角色行為背後可能的原因。"},
                ],
            },
            {
                "id": "SEL_SM",
                "name": "自我管理",
                "focus": "衝動或不舒服時，能想到可做到的調節方式",
                "student_prompts": [
                    "如果你很想把東西留給自己，你可以先做什麼讓自己停一下？",
                    "生氣或著急的時候，你可以先用哪個小方法再決定怎麼做？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "完全沒有「先停一下／換做法」的想法。"},
                    {"label": "2 接近", "desc": "有模糊想法（例如我會忍住），但不知道具體怎麼做。"},
                    {"label": "3 達標", "desc": "能提出一個具體、做得到的小策略（例如先深呼吸、先問清楚）。"},
                    {"label": "4 精進", "desc": "策略具體，能說明何時用、對自己或情況有什麼幫助。"},
                ],
            },
        ],
        "I": [
            {
                "id": "SEL_SOA",
                "name": "社會覺察",
                "focus": "理解角色或他人的感受、想法與立場",
                "student_prompts": [
                    "阿松爺爺為什麼會有這樣的改變？",
                    "哎唷奶奶的做法讓故事有什麼不一樣？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "只從自己的角度描述，較少注意角色或他人的感受。"},
                    {"label": "2 接近", "desc": "有提到角色或他人的感受，但說明較簡單。"},
                    {"label": "3 達標", "desc": "能理解角色可能的感受或想法，並能連結故事事件說明原因。"},
                    {"label": "4 精進", "desc": "能比較不同角色的立場，或說明角色行為背後可能的原因。"},
                ],
            },
            {
                "id": "SEL_RS",
                "name": "人際技巧",
                "focus": "與他人互動時合適的說法或做法",
                "student_prompts": [
                    "如果要跟同學分享，你會怎麼說才比較不傷人？",
                    "你想邀請別人一起做什麼？會怎麼開口？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "沒有提到與他人如何互動。"},
                    {"label": "2 接近", "desc": "有提到別人，但做法或說法不清楚。"},
                    {"label": "3 達標", "desc": "能提出一個對他人清楚、友善、做得到的互動做法。"},
                    {"label": "4 精進", "desc": "能考慮對方感受，並說明怎麼說或怎麼做才較不傷人、較能合作。"},
                ],
            },
        ],
        "D": [
            {
                "id": "SEL_RD",
                "name": "負責任的決定",
                "focus": "合適、可行、對自己或他人有幫助的決定或行動",
                "student_prompts": [
                    "如果你遇到類似情況，你可以在什麼時候、對誰、怎麼做？",
                    "這個決定會對你或別人有什麼幫助？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "只寫出想改變，但沒有具體決定或做法。"},
                    {"label": "2 接近", "desc": "有提出行動方向，但行動較模糊或不容易執行。"},
                    {"label": "3 達標", "desc": "能提出一個具體、可做到的決定或行動。"},
                    {"label": "4 精進", "desc": "能說明情境、對象、做法，並考慮行動可能帶來的影響。"},
                ],
            },
            {
                "id": "SEL_SM",
                "name": "自我管理",
                "focus": "衝動或不舒服時，能想到可做到的調節方式",
                "student_prompts": [
                    "下次很想馬上做決定時，你可以先做哪個小步驟？",
                    "你要怎麼提醒自己先想清楚再行動？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "完全沒有「先停一下／換做法」的想法。"},
                    {"label": "2 接近", "desc": "有模糊想法（例如我會忍住），但不知道具體怎麼做。"},
                    {"label": "3 達標", "desc": "能提出一個具體、做得到的小策略（例如先深呼吸、先問清楚）。"},
                    {"label": "4 精進", "desc": "策略具體，能說明何時用、對自己或情況有什麼幫助。"},
                ],
            },
            {
                "id": "SEL_RS",
                "name": "人際技巧",
                "focus": "與他人互動時合適的說法或做法",
                "student_prompts": [
                    "你會怎麼跟對方說，才能把界線說清楚又不傷人？",
                    "你想和誰一起做？你會怎麼邀請他？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "沒有提到與他人如何互動。"},
                    {"label": "2 接近", "desc": "有提到別人，但做法或說法不清楚。"},
                    {"label": "3 達標", "desc": "能提出一個對他人清楚、友善、做得到的互動做法。"},
                    {"label": "4 精進", "desc": "能考慮對方感受，並說明怎麼說或怎麼做才較不傷人、較能合作。"},
                ],
            },
        ],
    },
}

# ── Week 3 (《朱家故事》) ────────────────────────────────────────────────────

WEEK3_ORID_RUBRIC: dict[str, Any] = {
    "schema": "writing_rubric_v1",
    "version": 1,
    "purpose": "primary_orid_feedback_and_research_scoring",
    "score_range": "1-4",
    "scoring_formula": "triangular_cumulative_v1",
    "scoring_note": (
        "level n → n*(n+1)/2 pts (1→1, 2→3, 3→6, 4→10); "
        "ORID max 40, SEL max 50, total max 90"
    ),
    "total_score": (
        "ORID(O1+R1+I1+D1) max 40 + "
        "SEL(SEL_SA+SEL_SOA+SEL_RS+SEL_RD) max 50 = 90"
    ),
    "ok_rule": "level_3_or_4_true_level_1_or_2_false",
    "student_bands": {
        "1": "開始寫",
        "2": "差一點",
        "3": "不錯",
        "4": "很好",
    },
    "by_stage": {
        "O": [
            {
                "id": "O1",
                "name": "事實描述",
                "focus": "依故事寫人物、事件與大致順序",
                "levels": [
                    {"label": "1 起步", "desc": "只寫感想，或只說「很感人」，沒有說出故事裡發生的事，或內容與故事事實對不上。"},
                    {"label": "2 接近", "desc": "有寫出部分事件，但角色、事情或前後順序不夠清楚，例如只寫朱太太離開卻沒說前因。"},
                    {"label": "3 達標", "desc": "能寫出主要角色和重要事件，讓人知道故事大致發生了什麼，無明顯事實錯誤。"},
                    {"label": "4 精進", "desc": "能依順序清楚寫出多個重要事件，例如朱太太平常一人做所有家事、留下紙條離開、家裡變得像豬圈、大家後來一起分擔家事。"},
                ],
            }
        ],
        "R": [
            {
                "id": "R1",
                "name": "感受與原因",
                "focus": "表達感受並說明原因（連回故事）",
                "levels": [
                    {"label": "1 起步", "desc": "只寫簡單感覺，或感覺和故事內容沒有明顯關係。"},
                    {"label": "2 接近", "desc": "有寫出感覺，但原因說得不夠清楚，或只簡單一兩個字。"},
                    {"label": "3 達標", "desc": "能寫出自己的感覺，並說明這個感覺和故事中的哪件事有關。"},
                    {"label": "4 精進", "desc": "能寫出較細膩的感受和原因，例如看到朱太太每天做很多事卻被催促，會替她覺得辛苦或委屈；看到大家後來一起做家事，會覺得比較溫暖。"},
                ],
            }
        ],
        "I": [
            {
                "id": "I1",
                "name": "道理與連結",
                "focus": "說出道理／啟發並用故事支持",
                "levels": [
                    {"label": "1 起步", "desc": "只重複故事內容，沒有說出自己的理解或想法。"},
                    {"label": "2 接近", "desc": "有寫出一點想法，但比較籠統，和故事事件連結不夠明確。"},
                    {"label": "3 達標", "desc": "能說出故事帶來的提醒，並能連結到家人、責任或互相尊重。"},
                    {"label": "4 精進", "desc": "能根據故事提出較深入的理解，例如朱先生和孩子們後來才發現家事不是一個人的責任，也能連結到自己生活中需要體諒家人、分擔事情的經驗。"},
                ],
            }
        ],
        "D": [
            {
                "id": "D1",
                "name": "具體行動",
                "focus": "提出生活中可執行的具體行動",
                "levels": [
                    {"label": "1 起步", "desc": "只寫很籠統的想法，或沒有寫出自己可以做什麼。"},
                    {"label": "2 接近", "desc": "有寫出想做的事，但行動不夠具體，或不太看得出什麼時候可以做到。"},
                    {"label": "3 達標", "desc": "能寫出一個自己可以做到的具體行動，並和故事主題有關。"},
                    {"label": "4 精進", "desc": "能寫出清楚又可實行的行動，例如吃完飯後主動收碗、幫忙擦桌子、整理自己的床，或看到家人忙碌時主動問需要幫忙什麼。"},
                ],
            }
        ],
    },
}


WEEK3_SEL_RUBRIC: dict[str, Any] = {
    "schema": "sel_rubric_v1",
    "version": 1,
    "purpose": "auxiliary_guidance_and_research_scoring",
    "framework": "CASEL_five_competencies",
    "scoring_formula": "triangular_cumulative_v1",
    "scoring_note": (
        "Same formula as ORID: level n → n*(n+1)/2 pts; "
        "SEL max 50 (SEL_SA+SEL_SOA+SEL_RS+SEL_RD). "
        "Does not decide feedback_ok."
    ),
    "student_language_policy": (
        "Do not mention SEL dimension names to students; "
        "convert them into concrete questions. "
        "Prefer student bands: 差一點／不錯／很好."
    ),
    "by_stage": {
        "O": [],
        "R": [
            {
                "id": "SEL_SA",
                "name": "自我覺察",
                "focus": "辨認並表達自己的感受與想法",
                "student_prompts": [
                    "故事中哪一個地方讓你有這種感覺？",
                    "你的感覺可以再說得更清楚一點嗎？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "幾乎沒有表達感受或想法，或只使用很籠統的詞語。"},
                    {"label": "2 接近", "desc": "能寫出一種感受或想法，但較少說明為什麼。"},
                    {"label": "3 達標", "desc": "能清楚說出自己的感受或想法，並說明與故事事件的關係。"},
                    {"label": "4 精進", "desc": "能更細緻描述感受或想法，並理解自己為何有這種反應或變化。"},
                ],
            },
            {
                "id": "SEL_SOA",
                "name": "社會覺察",
                "focus": "理解角色或他人的感受、想法與立場",
                "student_prompts": [
                    "你覺得朱太太當時可能在想什麼？",
                    "如果你是朱太太，你可能會有什麼感覺？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "只從自己的角度描述，較少注意角色或他人的感受。"},
                    {"label": "2 接近", "desc": "有提到角色或他人的感受，但說明較簡單。"},
                    {"label": "3 達標", "desc": "能理解角色可能的感受或想法，並能連結故事事件說明原因。"},
                    {"label": "4 精進", "desc": "能比較不同角色的立場，或說明角色行為背後可能的原因。"},
                ],
            },
        ],
        "I": [
            {
                "id": "SEL_SOA",
                "name": "社會覺察",
                "focus": "理解角色或他人的感受、想法與立場",
                "student_prompts": [
                    "朱先生和孩子們後來為什麼願意幫忙做家事？",
                    "朱太太最後選擇留下來，你覺得她心裡可能有什麼想法？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "只從自己的角度描述，較少注意角色或他人的感受。"},
                    {"label": "2 接近", "desc": "有提到角色或他人的感受，但說明較簡單。"},
                    {"label": "3 達標", "desc": "能理解角色可能的感受或想法，並能連結故事事件說明原因。"},
                    {"label": "4 精進", "desc": "能比較不同角色的立場，或說明角色行為背後可能的原因。"},
                ],
            },
            {
                "id": "SEL_RS",
                "name": "人際技巧",
                "focus": "與他人互動時合適的說法或做法",
                "student_prompts": [
                    "如果要請家人幫忙，你會怎麼說才比較合適？",
                    "你想怎麼讓家人知道你感謝他們的付出？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "沒有提到與他人如何互動。"},
                    {"label": "2 接近", "desc": "有提到別人，但做法或說法不清楚。"},
                    {"label": "3 達標", "desc": "能提出一個對他人清楚、友善、做得到的互動做法。"},
                    {"label": "4 精進", "desc": "能考慮對方感受，並說明怎麼說或怎麼做才較不傷人、較能合作。"},
                ],
            },
        ],
        "D": [
            {
                "id": "SEL_RD",
                "name": "負責任的決定",
                "focus": "合適、可行、對自己或他人有幫助的決定或行動",
                "student_prompts": [
                    "如果你遇到類似情況，你可以在什麼時候、對誰、怎麼做？",
                    "這個行動會對你或家人有什麼幫助？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "只寫出想改變，但沒有具體決定或做法。"},
                    {"label": "2 接近", "desc": "有提出行動方向，但行動較模糊或不容易執行。"},
                    {"label": "3 達標", "desc": "能提出一個具體、可做到的決定或行動。"},
                    {"label": "4 精進", "desc": "能說明情境、對象、做法，並考慮行動可能帶來的影響。"},
                ],
            },
            {
                "id": "SEL_RS",
                "name": "人際技巧",
                "focus": "與他人互動時合適的說法或做法",
                "student_prompts": [
                    "你會怎麼跟家人說，才能讓大家都願意一起分擔？",
                    "你想和誰一起做？你會怎麼邀請他？",
                ],
                "levels": [
                    {"label": "1 起步", "desc": "沒有提到與他人如何互動。"},
                    {"label": "2 接近", "desc": "有提到別人，但做法或說法不清楚。"},
                    {"label": "3 達標", "desc": "能提出一個對他人清楚、友善、做得到的互動做法。"},
                    {"label": "4 精進", "desc": "能考慮對方感受，並說明怎麼說或怎麼做才較不傷人、較能合作。"},
                ],
            },
        ],
    },
}
