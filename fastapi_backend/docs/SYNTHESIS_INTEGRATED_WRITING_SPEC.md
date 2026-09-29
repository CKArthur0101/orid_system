# 整合寫作（Week 2 synthesis）短規格

本文件描述 `orid_writing_v1` 內整合寫作階段、回饋輪次、rubric 與「閱讀心得」資料來源，供前後端與 prompt 對齊。不修改 Cursor 內附之計畫檔。

## 四階寫作（A–D）

| 階段鍵值 | 意義 | 學生主要產出（JSON 欄位） | 建議完成條件 |
|----------|------|---------------------------|----------------|
| `select_evidence` | 帶材料進場 | `synthesis_evidence_notes`（可含從週一貼上的短句） | 至少一句具體材料或勾選／摘錄 |
| `align_prompt` | 題幹鷹架 | `synthesis_align_scaffold`（填空句型） | 三句鷹架皆有文字 |
| `short_draft` | 短初稿 | `synthesis_short_draft`（建議 ≤400 字） | 達最低字數（UI 提示） |
| `expand_revise` | 擴寫／修訂 | `synthesis_draft`（完整整合稿） | 段落可讀、可送交 |

階段順序固定為 A→B→C→D；前端以精靈步驟引導，狀態寫入同一筆 `writing.content` JSON。

## 兩輪回饋

- **第 1 輪**（`feedback_round=1`）：prompt 要求「只給一個最小下一步」，並只對應 1～2 條 rubric／一個回饋層級。
- **第 2 輪**（`feedback_round=2`）：可談較完整的銜接、例子或語言，仍避免代寫全文。

前端用 `synthesis_round1_completed`（boolean）記錄「已使用過第一輪整合回饋」；未設為 `true` 時 UI 可限制不可選第二輪（避免跳過）。資料存於 `writing` JSON，重新整理後仍在。

## Rubric 與四枚獎章

三本書共用 `synthesis_rubric_v1`，四個向度皆採 1 起步、2 接近、3 達標、4 精進：

1. **內容整合** `content_integration`：具體故事事件、感受或想法、體會與未來行動形成同一條主線。
2. **文章連貫** `coherence`：順序合理，前後句與各部分關係清楚，不是把 ORID 四段硬貼。
3. **反思深度** `reflection_depth`：能用故事事件說明感受、想法或學習原因，不只重述或喊口號。
4. **行動應用** `action_application`：提出自己能做到、具體可行且呼應體會的行動。

每項達第 3／4 級即取得同名獎章；四項分開判斷，不使用總分。文章短、錯字或標點不直接降級，除非影響語意；第 3 級後不再強迫追求第 4 級。

每輪只引導一個第 1／2 級向度，修改後以同一 rubric 重評。學生可沿用、修改或完全重寫上一週內容；只評目前整合稿。

SEL 沿用奇數週的 CASEL 五面向統一 rubric，只協助把該向度的問題問得更具體，不決定獎章。沒有足夠 SEL 證據時記為 `null`，不可判成能力低落。

## 閱讀心得資料來源

- **獨立欄位** `synthesis_reading_reflection`：學生在整合寫作區自行填寫的「閱讀心得／摘記」（可空）。
- 與第 1 週四格 ORID **分開**；後端另可透過 API 可選欄位 `reading_excerpt` 帶入節選（通常與該欄位同步），注入 prompt 區塊【學生自填閱讀心得／摘記節選】。

## API 契約（向後相容）

`POST /orid/writing-coach/chat`，`source: synthesis_feedback`，`stage: ALL`（不變）。

| 欄位 | 型別 | 預設 | 說明 |
|------|------|------|------|
| `synthesis_phase` | 可選字串 | `null` | `select_evidence` / `align_prompt` / `short_draft` / `expand_revise`；未傳或非法值視同 `null`（舊行為）。 |
| `feedback_round` | int | `1` | `1` 或 `2`。 |
| `reading_excerpt` | 可選字串 | `null` | 心得節選，後端截斷後注入 prompt。 |
| `synthesis_clarify` | bool | `false` | 為 `true` 時允許在回饋末加 **一句** 澄清問句。 |

`student_text` 仍為必填；各階段由前端組好要給教練看的文字（可含小標）。

## 狀態持久化

- **唯一來源**：伺服器上的週二 `OridWriting.content`（JSON `orid_writing_v1`）。
- 延伸欄位：`synthesis_reading_reflection`、`synthesis_evidence_notes`、`synthesis_align_scaffold`、`synthesis_short_draft`、`synthesis_draft`、`synthesis_active_phase`、`synthesis_round1_completed`。
- 本機 `localStorage` 草稿鍵仍沿用，還原時一併帶入上述欄位。

## Prompt 版本

`PROMPT_VERSIONS["synthesis_coach"]` 隨 playbook 行為變更遞增，便於實驗記錄與對照。
