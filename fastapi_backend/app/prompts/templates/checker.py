from __future__ import annotations


ORID_CHECKER_STAGE_RULES = """
目前 ORID 階段：{stage}
- O：只問故事中的角色、事件、順序、轉折，不問感受、道理、行動
- R：問感受＋原因，而且原因要連回故事事件
- I：問道理／提醒＋理由，而且理由要連回故事
- D：問下次可做的小行動，而且要具體、貼近日常
""".strip()

BOOK_GROUNDING_RULES = """
判斷原則（很重要）：
- 學生只能引用 BOOK_CONTEXT 裡真實出現的人物、事件、關係、物品與動作；其餘一律 grounded=false。
- O 段：最嚴格。若寫了書裡沒有的具體事件（誰做了什麼），或書裡沒有的具體物品／食物（例：書裡是柿子卻寫地瓜），grounded=false。
- R/I 段：感受與想法可以來自學生，但若把「書裡沒有發生」的情節當成事實（含「因為……」的錯誤理由），grounded=false。
- D 段：若學生只寫自己的行動計畫、沒有捏造新事件，可 grounded=true。
- 學生用簡稱（爺爺、奶奶）若明顯指書中角色，不算書外；但若搭配書裡沒有的動作或物品（例：打奶奶、吃地瓜、吃奶奶），仍 grounded=false。
- 若句子很短，但已出現**書裡沒有的具體名詞**（食物、物品、動作組合），仍 grounded=false；只有「太短且全是感想、沒有具體書外名詞」時，才 grounded=true，reason 寫「資訊不足但未見明顯衝突」。
- unsupported_span 請填學生原句中最有問題的短短一段（例：爺爺吃地瓜、吃地瓜），不要整句抄很長。
""".strip()
