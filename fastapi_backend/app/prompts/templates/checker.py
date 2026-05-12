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
- O 段：最嚴格。若寫了書裡沒有的具體事件（誰做了什麼），grounded=false。
- R/I/D 段：若學生是感受、想法、行動，且沒有捏造新事件，可 grounded=true；
  但只要把「書裡沒有發生」的事件當成事實，就 grounded=false。
- 太短或資訊不足時，優先 grounded=true，reason 寫「資訊不足但未見明顯衝突」。
""".strip()
