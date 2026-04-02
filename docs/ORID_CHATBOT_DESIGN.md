# AI–ORID 聊天機制與設計規格

本文件與 Cursor 計畫「ORID 聊天機制說明與設計」同步，供版本庫內查閱與與教授／團隊討論。實作狀態以程式碼為準；細部待辦見文末。

---

## 關於瀏覽器錯誤

`Unchecked runtime.lastError: Could not establish connection. Receiving end does not exist.` 多半是 **Chrome 擴充功能**（密碼管理、翻譯、廣告阻擋等）與分頁通訊失敗，**與後端聊天邏輯無關**，可忽略或暫時用無痕／關擴充確認。

---

## 一、目前聊天機制（白話版）

整體是：**學生送一句 → 後端存進資料庫 → 依「安全／離題／階段」分支 → 多半再叫一次大模型 → 再依規則組出最後給學生看的兩句話（承接 + 一個問句）→ 可能推進 O→R→I→D**。

### 1. 資料與上下文

- 每次 `POST /orid/chat` 會先把**學生這句**存成 `OridMessage`（`fastapi_backend/app/routes/orid.py`），帶 `session_id`、`stage`。
- 送進主模型時，`build_stage_history`（`fastapi_backend/app/services/orid_stage.py`）**只保留「目前階段」**的最近幾則（`ORID_HISTORY_LIMIT`），避免 O/R/I/D 混在一起干擾。

### 2. 安全與檢查器

- **安全**：`check_safety`（`fastapi_backend/app/services/safety.py`）；若判定不當內容，走簡短兩句式回覆，不進主對話流程。
- **ORID Checker**：`run_orid_checker`（`orid.py`）；另一個 LLM 呼叫回 JSON（離題、`suggested_question` 等），用於 **fallback 問句** 與是否走 `generate_natural_pullback`。

### 3. 主對話 LLM

- `llm_generate_reply` + `build_orid_chat_system_prompt`（`fastapi_backend/app/prompts/orid_chat.py`）：注入 `book_pack`、階段規則、PASS 說明、最低輪數等。
- 模型第一行輸出控制標籤：`【PASS:…】【NEXT:…】【REASON:…】`；`parse_control_tags` 拆出 `pass_ok`；無標籤時可改走 `heuristic_pass`（`ORID_ALLOW_HEURISTIC_PASS`）。

### 4. 題庫

- `pick_prompt_from_bank`：`book_pack.orid_prompt_bank` 依階段與輪次 `idx % len(bank)` 輪替；Checker 建議或題庫常成為 `fallback_q`，接在第二句。

### 5. 最後回覆組裝

- 通過且未換階：`_compose_reply_from_model` 等。
- 未通過：`generate_natural_pullback` + `fallback_q`。
- 換階：`generate_stage_transition_reply` + 下一階題庫問句。

### 6. 階段進度

- `decide_stage_progress`：`pass_ok`、累積通過次數、`min_ai_turns_same_stage` 皆滿足才 O→R→I→D。

---

## 二、為什麼容易覺得「不像聊天、像固定句」

1. 結構固定（承接 + 單一問句）與禁語表，節奏仍可能模式化。
2. 題庫整句當第二句，重複感強。
3. 控制標籤 + 規則覆寫，像「批改」。
4. 多段 LLM 拼接、temperature 偏低時語氣單一。
5. 歷史僅本階段，跨階感受斷裂。

---

## 三、更自然對話（實作時可選）

| 方向 | 概要 |
|------|------|
| A | 題庫改「方向提示」，由模型改寫成接續上一句的問法 |
| B | PASS/NEXT 改後端或獨立小模型，主模型只說人話 |
| C | 略增 temperature、允許偶爾多一句或先承接再下輪問 |
| D | 本階段 history 加上一階段摘要 |
| E | GenAI 組用結構一致 + paraphrase seed 兼顧可重現 |

---

## 四、每階段五輪與 `pass_ok`（已選策略）

- **決策**：每階段須累積 **5 次 `pass_ok`** 才允許進下一階 → 對應環境變數 **`ORID_REQUIRED_PASS_* = 5`**。
- **防邏輯卡死**：`decide_stage_progress` 在學生送第 5 句且通過時，本階段通常已有 **4** 則 AI 訊息；故 **`ORID_MIN_AI_TURNS_*` 不宜大於 4**（建議 **5 / 4** 組合），或改程式讓兩者自動一致。
- **離題／不安全輪次**：建議**不**計入有效 pass（不增加 `stage_turn`）。
- **書本錨定**：`book_pack` 進 system + 離題／故事相關規則 + prompt 要求追問引用學生上一句與書中元素。
- **深度**：同階段可用深度 1→2→3（事實→因果→換位）；未滿門檻前不應在語意上催促跳階。

---

## 五、離題與不當發言（NaturalRedirect 設計）

- **目標**：無法數學零漏洞；以 **多層偵測 + 固定優先序（不安全 > 離題 > 正常）** + **行為計次** 因應。
- **NaturalRedirect 編排器**：統一短 LLM，兩句繁中；第二句**一個問號**且**錨定 book_pack**；禁「系統、ORID、檢測到」等；用 `message_id`/hash 做 paraphrase seed。
- **類別**：`unsafe` / `off_topic` / `low_effort` / `meta`（同一編排器、不同策略片段）。
- **Tier4（可選）**：`consecutive_offtopic` / `consecutive_unsafe`；升級語氣、可選教師儀表板「需關注」。

**實作預計檔案**：`fastapi_backend/app/routes/orid.py`、`fastapi_backend/app/prompts/`（如 `natural_redirect.py`）、可選 `OridSession` 欄位與 migration。

---

## 六、補遺：Phase 2／倫理與營運

1. **對抗**：Prompt injection 防護（固定 system、不把學生內容當指令）；API **限流**。
2. **韌性**：LLM 逾時／429 **降級回覆** + log。
3. **可重現**：記錄模型名、**prompt 版本**、temperature、與 `condition`。
4. **學習者**：「聽不懂」**鷹架分支**／豁免輪，避免與「5× pass」衝突。
5. **倫理**：IRB、保存期限、去識別化、**PII** 不複述、log 遮罩政策。
6. **教師**：異常升級、日後課中介入／重設（進階）。
7. **無障礙與課堂**：語音（若做）、斷線與跨裝置 session 定義文件化。
8. **公平與心理安全**：不偏見 prompt；敏感主題安撫與「找大人談」底線。
9. **後設**：對話 **匯出**（CSV/JSON）對齊週次／階段；**人工抽樣**校準 Checker。

---

## 待辦清單（設計／實作追蹤）

- 對齊自然度 vs 實驗可重現／階段嚴格度  
- **已選**：`ORID_REQUIRED_PASS_*=5`，校對 `ORID_MIN_AI_TURNS_*`（建議 4）  
- 題庫／PASS 標籤／temperature／上下文：擇 1～2 項 PoC  
- 修改 `orid_chat.py`、`orid.py` 組裝邏輯與可選 checker  
- 可選：session 深度層級 + 書本錨定強化  
- **NaturalRedirect** 統一離題／不安全／低投入／meta  
- 可選：session strike、教師儀表板標記  
- **Phase2**：注入防護、限流、LLM 降級、版本 log、鷹架分支、IRB／PII、匯出  

---

## 相關程式入口

- 聊天主流程：`fastapi_backend/app/routes/orid.py`（`chat`）  
- 系統提示：`fastapi_backend/app/prompts/orid_chat.py`  
- 階段邏輯：`fastapi_backend/app/services/orid_stage.py`  
- 安全：`fastapi_backend/app/services/safety.py`  
