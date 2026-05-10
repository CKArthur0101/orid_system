# 測試／實驗用登入帳號對照

登入帳號存在資料表 `user.email`（欄位名仍為 `email`，可為學號）。顯示名稱為 `user.display_name`。

## 種子腳本預設（`seed_test_accounts.py`）

| 角色 | 登入帳號（user.email） | 顯示名稱（display_name） | 預設密碼 |
|------|------------------------|--------------------------|----------|
| 學生 | `114524021` | 林宜萱 | `OridTest2026!` |
| 教師 | `orid.teacher@example.com` | 示範教師 | `OridTest2026!` |

執行：`uv run python commands/seed_test_accounts.py --with-class`

參數可覆寫：`--student-login`、`--student-display-name`、`--teacher-login`、`--teacher-display-name`、`--password`。

## Migration 會嘗試更新的既有帳號（`i0a1b2c3d4e5`）

若 DB 內曾存在下列帳號，upgrade 時會一併改名（無則略過）：

| 條件（舊 email） | 新登入帳號 | display_name |
|------------------|------------|--------------|
| `arthur.chiu0101@gmail.com` 或 `arthur.chiu0101@%` | `114524020` | 邱振凱 |
| `orid.student@example.com` | `114524021` | 林宜萱 |

若你的 Arthur 使用其他 email，請在 DBeaver 手動 `UPDATE "user" SET email = '114524020', display_name = '邱振凱' WHERE ...`。

## 前端環境變數 `ORID_FORCE_NEW_ALLOWLIST`

BFF [`/api/users/me`](nextjs-frontend/app/api/users/me/route.ts) 會把允許清單與**登入帳號**比對（小寫）。請改為學號，例如：

```env
ORID_FORCE_NEW_ALLOWLIST=114524020,114524021
```

（勿再使用 `arthur...@...` 除非該帳仍未遷移。）

## 忘記密碼

學號帳號通常無信箱，**忘記密碼／重設信**可能無法使用。實驗帳號請以種子腳本重設密碼或由管理員更新 `hashed_password`。
