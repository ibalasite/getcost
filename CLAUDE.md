# getcost — Project Spec

## 專案目標

為 Claude Code 建立一個 **token 費用追蹤 skill**，可安裝至任意專案目錄。  
自動在 session 結束時結算費用、定期顯示累積消費，並提供手動查詢指令。

---

## 架構設計

```
/Users/tobala/projects/getcost/     ← 這個 repo
├── CLAUDE.md                       ← 本文件（AI 指令與 spec）
├── README.md                       ← 使用者文件
├── setup                           ← install / update / uninstall 腳本
├── skill.md                        ← /getcost Claude Code skill 主體
└── bin/
    ├── getcost-settings-hook.py    ← 管理 Stop + PostToolUse hook 注冊
    ├── getcost-session-end.py      ← Stop hook：session 結算
    ├── getcost-checkpoint.py       ← PostToolUse hook：5 分鐘 checkpoint
    └── getcost-calc.py             ← 共用庫：token → 費用 + 幣別換算
```

安裝後，各專案目錄會產生：

```
{project-dir}/
└── .getcost/
    ├── sessions.json               ← 所有已封存 session 記錄 + 累積 total
    ├── checkpoint.json             ← 最後一次 checkpoint 時間戳記
    └── .gitignore                  ← 自動建立，忽略整個 .getcost/
```

資料存在各專案目錄下（不集中），不進 git。

---

## 資料來源

Claude Code 將每個 session 的完整對話存為 JSONL：

```
~/.claude/projects/{project-hash}/{session-id}.jsonl
```

`project-hash` 規則：把專案目錄路徑中的 `/` 換成 `-`，例如：  
`/Users/tobala/projects/getcost` → `-Users-tobala-projects-getcost`

每個 API 呼叫在 JSONL 中對應一個含 `usage` 物件的 message entry：

```json
{
  "message": {
    "model": "claude-sonnet-4-6",
    "usage": {
      "input_tokens": 3,
      "cache_creation_input_tokens": 46358,
      "cache_read_input_tokens": 23655,
      "output_tokens": 346
    }
  }
}
```

加總一個 session 內所有 `usage` 物件即得 session 總 token 量。  
**current session** = 最新的 JSONL 檔案（mtime 最新）。

---

## 定價表（內建，可在 `~/.getcost/config.json` 覆寫）

| Model | Input $/1M | Output $/1M | Cache Write $/1M | Cache Read $/1M |
|-------|-----------|-------------|-----------------|----------------|
| claude-opus-4-7 | 15.00 | 75.00 | 18.75 | 1.50 |
| claude-sonnet-4-6 | 3.00 | 15.00 | 3.75 | 0.30 |
| claude-haiku-4-5 | 0.80 | 4.00 | 1.00 | 0.08 |
| (unknown model) | 3.00 | 15.00 | 3.75 | 0.30 |

---

## 幣別偵測邏輯（`getcost-calc.py`）

依序檢查：

1. `~/.getcost/config.json` 中的 `preferred_currency` 欄位（使用者手動設定，最高優先）
2. 系統環境變數 `LC_MONETARY` → 解析地區代碼
3. 環境變數 `LANG` → 解析語言代碼
4. 都無法判斷 → 預設 **USD**

語系 → 幣別對照：

| 語系前綴 | 幣別 | 符號 |
|---------|------|------|
| `zh_TW` | TWD | NT$ |
| `zh_HK` | HKD | HK$ |
| `ja`    | JPY | ¥ |
| `ko`    | KRW | ₩ |
| `en`    | USD | $ |
| `de`, `fr`, `es`, `it`, `pt` | EUR | € |
| 其他 / 未知 | USD | $ |

輸出格式：**固定顯示 USD**，若偵測到本地幣別則**額外顯示**：  
`$0.42 USD / NT$13.44 TWD`

匯率來源：安裝時從 `https://open.er-api.com/v6/latest/USD`（免費，無需 API key）取得，  
存入 `~/.getcost/config.json`。每次 `/getcost` 指令呼叫時若 cache 超過 24 小時則更新。

---

## Hook 設計

### Hook 1：Stop Hook（session 結束結算）

**觸發**：Claude Code session 關閉  
**腳本**：`bin/getcost-session-end.py`  
**注冊位置**：`~/.claude/settings.json` 的 `Stop` 事件  

行為流程：
1. 找出當前 session 的 JSONL 檔（project-hash 目錄下 mtime 最新的 .jsonl）
2. 加總所有 `usage` 物件，計算 session token 量
3. 依 model 套用定價，計算 USD 費用
4. 換算本地幣別
5. Append session 記錄至 `{project-dir}/.getcost/sessions.json`
6. 更新 `sessions.json` 的 `project_total` 累積欄位
7. 清除 `checkpoint.json` 的 `current_session_accumulated`（歸零）
8. 輸出結算摘要至 terminal

輸出範例：
```
[getcost] Session 結束 ────────────────────
  本次：45,231 tokens → $0.42 USD / NT$13.44
  目錄累積（12 sessions）：1,823,450 tokens → $17.82 USD / NT$570.24
─────────────────────────────────────────────
```

### Hook 2：PostToolUse Checkpoint（5 分鐘間隔）

**觸發**：每次工具呼叫後（PostToolUse）  
**腳本**：`bin/getcost-checkpoint.py`  
**注冊位置**：`~/.claude/settings.json` 的 `PostToolUse` 事件  
**Interval**：5 分鐘（可在 `~/.getcost/config.json` 的 `checkpoint_interval_minutes` 覆寫）

行為流程：
1. 讀取 `{project-dir}/.getcost/checkpoint.json` 的 `last_reported_at`
2. 若距今 < interval → 靜默退出（exit 0，不輸出任何訊息）
3. 若距今 ≥ interval：
   - 讀取 current session JSONL，計算本 session 累積 token + 費用
   - 輸出 checkpoint 摘要
   - 更新 `last_reported_at` 為現在時間

輸出範例：
```
[getcost] ⏱ 5min checkpoint — 本 session 累積：12,450 tokens → $0.12 USD / NT$3.84
```

---

## `/getcost` Skill 指令

呼叫 `skill.md`，執行 `bin/getcost-calc.py --report` 並格式化輸出：

```
[getcost] /Users/tobala/projects/mycoolapp
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
本 session（進行中）
  input      3,201 tokens
  cache_write  12,500 tokens
  cache_read   45,000 tokens
  output         820 tokens
  費用：$0.21 USD / NT$6.72

目錄歷史總計（12 sessions）
  總 tokens：2,891,023
  總費用：$27.41 USD / NT$877.12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
匯率：1 USD = 32.05 TWD（cache：2026-05-03）
```

`/getcost all` → 展開每個 session 的明細列表。

---

## 資料模型（`sessions.json`）

```json
{
  "project_path": "/Users/tobala/projects/mycoolapp",
  "project_total": {
    "input_tokens": 1234567,
    "cache_write_tokens": 456789,
    "cache_read_tokens": 890123,
    "output_tokens": 234567,
    "cost_usd": 17.82
  },
  "sessions": [
    {
      "session_id": "6f2ab7e2-2470-4e86-ba95-a7c49721df0a",
      "date": "2026-05-03T00:35:00Z",
      "model": "claude-sonnet-4-6",
      "tokens": {
        "input": 3000,
        "cache_write": 46000,
        "cache_read": 23000,
        "output": 800
      },
      "cost_usd": 0.42
    }
  ]
}
```

`checkpoint.json`：
```json
{
  "last_reported_at": "2026-05-03T01:23:45Z"
}
```

---

## `setup` 腳本介面（仿 gendoc）

```
./setup             # 等同 install
./setup install     # clone/copy → 部署 skill → 注冊兩個 hooks
./setup update      # git pull + 重新部署（保留 .getcost/ 資料）
./setup uninstall   # 移除兩個 hooks + 移除已複製的 skill 檔
                    # .getcost/ 資料預設保留（使用者手動刪除）
```

install 流程：
1. 前置檢查：`git`, `python3`, `curl` 是否存在
2. Clone repo 至 `~/.claude/skills/getcost/`（若已存在則 upgrade）
3. Copy `skill.md` 至 `~/.claude/skills/getcost.md`（讓 Claude Code 識別）
4. 執行 `bin/getcost-settings-hook.py add-stop` → 注冊 Stop hook
5. 執行 `bin/getcost-settings-hook.py add-posttooluse` → 注冊 PostToolUse hook
6. 初始化 `~/.getcost/config.json`（若不存在）
7. 在當前專案目錄建立 `.getcost/` + `.getcost/.gitignore`（內容：`*`）

---

## 已知限制

| 限制 | 說明 |
|------|------|
| Checkpoint 依賴工具呼叫 | 純對話（無工具呼叫）時 PostToolUse 不觸發；但純對話 = 幾乎無 token 消耗，可接受 |
| 匯率非即時 | 24 小時 cache，非 tick-level 匯率 |
| 進行中 session 費用為近似值 | 精確值在 Stop hook 時才結算 |
| 跨 model session | 同一 session 若切換 model，每筆 usage 獨立計算（JSONL 每行含 model 欄位） |

---

## 實作順序

1. `bin/getcost-calc.py` — token 計算 + 幣別換算核心庫
2. `bin/getcost-session-end.py` — Stop hook 腳本
3. `bin/getcost-checkpoint.py` — PostToolUse hook 腳本
4. `bin/getcost-settings-hook.py` — hook 注冊管理
5. `skill.md` — `/getcost` 指令主體
6. `setup` — install/update/uninstall 腳本
7. 整合測試：模擬 JSONL 資料 → 驗證計算結果
