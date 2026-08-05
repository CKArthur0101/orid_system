# AI–ORID 反思寫作系統：研究設計脈絡

> 文件角色：**研究設計單一真相（研究問題、組別、資料來源）**  
> 建立日期：2026-08  
> 實作細節以程式碼為準；本文件規範「研究要測什麼、資料怎麼對應」。  
> 相關實作規格見：[`ORID_CHATBOT_DESIGN.md`](ORID_CHATBOT_DESIGN.md)、[`../fastapi_backend/docs/RASF_SCORING_SPEC.md`](../fastapi_backend/docs/RASF_SCORING_SPEC.md)、[`../fastapi_backend/docs/SYNTHESIS_INTEGRATED_WRITING_SPEC.md`](../fastapi_backend/docs/SYNTHESIS_INTEGRATED_WRITING_SPEC.md)、[`orid_ai_feedback_rubric.md`](orid_ai_feedback_rubric.md)。

---

## 一、系統研究背景

本系統為 **AI–ORID 反思寫作系統**，研究對象為**國小五年級**學生。學生閱讀指定故事後，在同一平台上進行寫作任務。

核心教學架構為 **ORID**：

| 階段 | 英文 | 意義（學生語） |
|------|------|----------------|
| O | Objective | 觀察：故事裡發生什麼 |
| R | Reflective | 感受：我覺得怎樣、為什麼 |
| I | Interpretive | 體會：我學到／想到什麼 |
| D | Decisional | 行動：以後我會怎麼做 |

**AI 不是單純聊天機器人**，而是實驗組「研究處理（treatment）」的一部分：依學生寫作內容、ORID 階段、SEL 面向與 feedback rubric 提供**引導式**個人化回饋，目的在支持反思寫作表現、SEL 表現，以及修改／再思考行為。

---

## 二、六週流程（正式實驗目標）

共 **六週、三本書**；每本書兩週。

| 週次 | 任務類型 | 說明 |
|------|----------|------|
| 第 1、3、5 週 | ORID 分段寫作 | 分別完成 O、R、I、D 四格 |
| 第 2、4、6 週 | 整合反思寫作 | 依**上一週** O/R/I/D，整理成一篇完整反思短文 |

對應程式概念（前端）：

- `nextjs-frontend/lib/orid/week-flow.ts`：`isOddWeek` / `isEvenWeek` / `priorOddWeek`
- 後端研究摘要：`task_type` = `orid_stage`（奇數週）／`synthesis`（偶數週）

### 目前實作狀態（限制）

- 正式實驗目標為六週三書；**後兩本書尚未定稿**。
- 目前週次解鎖、書包內容、控制組提示參數化**以現有可測範圍為主**；完整三書就緒後再擴充（見文末「已知限制」）。
- 實作入口：`nextjs-frontend/app/dashboard/books/week/[week]/page.tsx`

---

## 三、實驗組與控制組設計

### 3.1 共同點

- 同一平台、同樣文本、同樣任務流程（奇數 ORID／偶數整合）。
- 同樣徽章機制（作為參與與階段性完成指標，**不是**主要學習成效依變項）。

### 3.2 主要差異

| | 實驗組 experimental | 控制組 control |
|--|---------------------|----------------|
| 引導 | AI **個人化**引導式 feedback | **固定**提示句與文本提問 |
| Chatbot | 有（寫作教練／整合回饋） | **無**個人化 AI chatbot |
| 系統自動分 | 可產生（過程／dashboard／探索用） | **不**產生個人化 AI 系統分 |

### 3.3 條件值在系統中的命名

| 層級 | 常見值 | 說明 |
|------|--------|------|
| `User.orid_condition` | `experimental` / `control` | 研究分組 |
| Session `condition` | `genai` / `control` | 寫作 session 內部分流（實驗組常對應 `genai`） |
| Research summary | 快照使用者條件 | 匯出／教師後台用 |

正規化邏輯：`fastapi_backend/app/services/orid_condition.py`  
分流主路徑：`fastapi_backend/app/routes/orid.py`、`week/[week]/page.tsx`

### 3.4 AI feedback 在研究中的角色

- 對準 **RQ1**（ORID 反思寫作表現）、**RQ2**（SEL 表現）、**RQ3**（投入與修正行為）。
- 必須是引導式（問題、提示、方向），**不可**整篇代寫。
- 詳細規則見 [`orid_ai_feedback_rubric.md`](orid_ai_feedback_rubric.md)。

### 3.5 控制組固定提示在研究中的角色

- 作為**對照處理**：提供同等任務結構下的非個人化鷹架（句型／文本提問）。
- 前端：`nextjs-frontend/lib/orid/control-guide-pages.ts`、`WritingPromptHelper.tsx`。
- 控制組若觸發後端規則式回覆，仍**不是**個人化 LLM feedback；正式組間比較**不以**控制組系統分為依變項。

---

## 四、研究問題（RQ）

**RQ1**  
相較於固定提示句與文本提問引導，AI 個人化回饋是否能提升國小高年級學生在 ORID 架構下的反思寫作表現？

**RQ2**  
相較於固定提示句與文本提問引導，AI 個人化回饋是否能提升學生在反思寫作中的 SEL 表現？

**RQ3**  
不同引導方式是否會影響學生的寫作投入與修正行為？

**RQ4**  
學生對 AI–ORID 反思寫作系統的科技接受度如何？

---

## 五、各 RQ 對應資料來源

### 5.1 正式分析原則（已確認）

| 項目 | 決策 |
|------|------|
| RQ1／RQ2 正式依變項 | 以**人工 rubric 評分**為主（兩組作品用同一套人評規準） |
| 系統 AI 自動分數 | **過程參考**、dashboard 顯示、**探索性**資料；**不是**唯一正式依變項 |
| 控制組系統分 | **不需要**個人化 AI 系統分；避免組間測量不等價 |
| 徽章 | 兩組都有；參與／階段完成指標，**非**主要學習成效 |
| RQ4 | **Google 表單或紙本問卷**；不做進系統 |

### 5.2 RQ1 — ORID 反思寫作表現

| 來源 | 用途 |
|------|------|
| 人工 ORID／整合寫作 rubric | **正式**組間比較 |
| 系統 `orid_score`／階段 `feedback.ok`／層級估計 | 探索、歷程、教師儀表 |
| 奇數週寫作 JSON（`stages.O/R/I/D`）與偶數週 `synthesis_draft` | 人評材料 |

人評向度細節見 [`orid_ai_feedback_rubric.md`](orid_ai_feedback_rubric.md)。

### 5.3 RQ2 — SEL 表現

| 來源 | 用途 |
|------|------|
| 人工 SEL／反思中 SEL 面向評分 | **正式**組間比較 |
| 系統 `sel_score` 與各 `SEL_*` 層級 | 探索用（僅實驗組路徑較完整） |

研究用語與系統 CASEL ID 對照（已確認）：

| 研究用語 | 系統 ID | 備註 |
|----------|---------|------|
| 情緒覺察 | `SEL_SA` | 自我覺察 |
| 同理理解 | `SEL_SOA` | 社會覺察 |
| 關係理解 | `SEL_RS` | 人際技巧 |
| 負責任行動 | `SEL_RD` | 負責任的決定 |
| 生活連結 | （不新增 SEL ID） | 置於 **I 段體會／反思深度** |
| （系統另有）自我管理 | `SEL_SM` | 系統計分仍存在；研究論述以四向＋生活連結為主，必要時於人評表註明是否評 SM |

定義檔：`fastapi_backend/app/content/rubrics.py`（`WEEK1_SEL_RUBRIC`）。

### 5.4 RQ3 — 寫作投入與修正行為

系統研究摘要（`OridWeeklyResearchSummary`／`orid_research_summary.py`）優先觀察：

| 欄位 | 意義 |
|------|------|
| `word_count` | 寫作投入（字數／字元規則以實作為準） |
| `save_count` | 草稿儲存歷程 |
| `revision_count` | 內容修正行為 |
| `guide_use_count` | 引導資源使用（實驗組：AI 回饋次數等；控制組：固定提示瀏覽等） |
| `badge_count` | 階段性完成／參與 |
| `is_submitted` | 任務完成率 |

AI feedback 設計應鼓勵學生回到自己的文字修改，以促進上述歷程指標（見 feedback rubric 文件）。

### 5.5 RQ4 — 科技接受度

- **不在系統內實作**問卷模組。
- 使用課堂 **Google 表單或紙本**；分析時與 `user_id`／班級／條件對齊即可。

### 5.6 匯出欄位資料字典（Phase 5）

教師「研究分析」CSV（`/research-export`）與課堂監控 CSV 中的系統分欄位：

| 欄位（研究匯出） | 意義 | 正式分析角色 |
|------------------|------|----------------|
| `word_count` / `save_count` / `revision_count` / `guide_use_count` | RQ3 歷程 | 可用 |
| `badge_count` / `earned_badges` | 參與／階段完成（奇數週 start/30/60/90；**不含** `badge_synthesis_start`） | 非 RQ1／RQ2 主 DV |
| `ai_system_*_score_exploratory` | 系統 AI 自動分 | **探索用 only**；正式 RQ1／RQ2 用人評 |
| `condition` / `week` / `task_type` / `is_submitted` | 分組與完成 | 可用 |

人評分數目前在系統外（紙本／表單／獨立表）；匯出後與 `student_email`／週次對齊即可。

---

## 六、奇數週與偶數週任務（研究層）

### 6.1 奇數週（1、3、5）— ORID 分段

- 學生依序完成 O→R→I→D。
- 實驗組：按「取得回饋」→ `source=feedback_button` → 結構化評量＋引導敘事。
- 控制組：固定提示翻頁（`getControlGuidePages`），無個人化 AI 批改。

### 6.2 偶數週（2、4、6）— 整合反思短文

- **不是**重寫四格，而是把上週四段**收成一篇**。
- 實驗組：`source=synthesis_feedback`，`stage=ALL`。
- 控制組：`getSynthesisGuidePages` 固定提示。
- 偶數週 AI 應檢查完整性、連貫性、反思深度、**SEL 表現（引導用）**、行動具體性；**正式分數仍以人評為主**，目前不急著做偶數週正式自動計分。

---

## 七、徽章在研究中的定位

| 徽章 ID | 名稱（概念） | 軌道 |
|---------|--------------|------|
| `badge_start` | 下筆 | 奇數週 ORID |
| `badge_30` / `badge_60` / `badge_90` | 松果銅／銀／金 | 階段進度（非總分門檻） |
| `badge_synthesis_start` | 整合下筆章 | 偶數週整合 |

- 兩組皆可獲得對應軌道徽章。
- **不作為** RQ1／RQ2 主要成效指標。
- 已知：兩組「階段通過」判定實作可能不同（實驗組偏 `feedback.ok`；控制組偏有內容）。若差異過大再另議是否統一（非本文件變更範圍）。

實作：`fastapi_backend/app/services/orid_badges.py`、`nextjs-frontend/lib/orid/badgeRules.ts`。

---

## 八、主要程式入口索引

| 主題 | 路徑 |
|------|------|
| 週寫作主頁 | `nextjs-frontend/app/dashboard/books/week/[week]/page.tsx` |
| 週流程 | `nextjs-frontend/lib/orid/week-flow.ts` |
| 控制組提示 | `nextjs-frontend/lib/orid/control-guide-pages.ts` |
| Coach chat API | `fastapi_backend/app/routes/orid.py` → `writing_coach_chat` |
| ORID／SEL rubric 定義 | `fastapi_backend/app/content/rubrics.py` |
| 系統計分 | `fastapi_backend/app/services/orid_rubric_scoring.py` |
| 研究摘要 | `fastapi_backend/app/services/orid_research_summary.py` |
| 條件分流 | `fastapi_backend/app/services/orid_condition.py` |
| AI feedback 研究規準 | [`orid_ai_feedback_rubric.md`](orid_ai_feedback_rubric.md) |

---

## 九、已知限制與後續（研究／工程）

1. **三書未齊**：書包、週解鎖等擴充，等後兩本確定後再處理。控制組提示已支援 `bookId`／週次參數化；**book1** 有角色提問，**book2／book3** 暫用通用句（無書一角色名）。  
2. **系統分 ≠ 正式 DV**：儀表板分數不可單獨宣稱回答 RQ1／RQ2。  
3. **偶數週自動計分**：文件已要求 SEL **引導**面向；正式自動計分非優先。  
4. **舊文件落差**：部分歷史設計文可能描述已廢棄之 `/orid/chat` 或與現行「人評為主」策略不同——以**本文件＋現行程式**為準（見下方衝突說明）。  
5. **條件閘門（Phase 4）**：控制組 session 呼叫 `writing-coach/chat`、`writings/feedback`、`writings/assist` 回 **403**；前端隱藏「取得回饋／取得整合回饋」；session 條件由 `User.orid_condition` 決定（僅 force_new 帳號可覆寫）。  
6. **分數／徽章對齊（Phase 5）**：控制組 `/progress` 不回系統分；寫入寫作 JSON 時剝除 `score`；徽章事件週次改用學術週（1–6）；教師儀表與 CSV 標明系統分為探索用；研究匯出徽章依該列週次篩選，且省略 `badge_synthesis_start`。

### 與既有 docs 的關係（衝突說明）

| 既有文件 | 關係 |
|----------|------|
| `RASF_SCORING_SPEC.md` | 描述系統 RASF **自動計分／單點引導**機制；仍有效作**實作規格**，但**正式論文依變項**改以人評為主（本文件優先）。 |
| `SYNTHESIS_INTEGRATED_WRITING_SPEC.md` | 曾以四階 A–D、另一套 4 條 rubric（證據／扣題／結構／語言）描述；現行產品主路徑多為單一整合稿＋完整／連貫／深度／行動。研究用整合 rubric 以 [`orid_ai_feedback_rubric.md`](orid_ai_feedback_rubric.md) 為準；該 spec 保留作工程／可選階段參考。 |
| `ORID_CHATBOT_DESIGN.md` | 偏早期聊天／換階設計；正式任務主路徑已是 `writing-coach/chat`。研究角色以本文件為準。 |

---

## 十、版本紀錄

| 日期 | 說明 |
|------|------|
| 2026-08 | Phase 1 初版：RQ、組別、資料來源、人評為主決策、SEL 映射 |
| 2026-08 | Phase 4：條件閘門與控制組提示 bookId 參數化（book2/3 通用 fallback） |
| 2026-08 | Phase 5：系統分＝探索用標示、控制組分數剝除、徽章週次修正、匯出資料字典 |
