# Deep Research Agent — Runbook(端到端跑通指南)

這份是為了「在新的 Claude Code on the web session(或本機)從零跑通」而準備的。
照順序做即可。

---

## 0. 前置:網路策略(在 web 跑才需要注意)

這個 app 的 agent 需要連到 **OpenAI** 和 **Tavily**,但 web 環境的**預設網路策略
(`cloud_default`)會擋掉這兩個網域**(回 `403 host_not_allowed`)。

> 如何確認目前環境:`echo $CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE`
> 看到 `cloud_default` 就代表是預設策略,OpenAI/Tavily 會被擋。

**要在 web 完整跑,先做這件事:**
1. 在建立環境時,把網路策略改成**允許所有對外連線**,或自訂白名單明確加入：
   - `api.openai.com`
   - `api.tavily.com`
2. **開一個新的 session**(策略在容器啟動時固定,改了要重開才生效)。
3. 跑 `bash quickstart.sh`,它會先做連通性預檢,告訴你策略有沒有生效。

文件:https://code.claude.com/docs/en/claude-code-on-the-web

（在**本機**跑沒有這個限制,直接跳到第 1 步。）

---

## 1. 取得 API Key

| 服務 | 網址 | 費用 |
|------|------|------|
| **Tavily**(網路搜尋) | https://app.tavily.com | **免費**:每月 1000 次、免綁卡 |
| **OpenAI**(LLM) | https://platform.openai.com/api-keys | **付費**:需先儲值(最低約 $5),用多少扣多少 |

---

## 2. 一鍵安裝 + 預檢

```bash
cd generative_ui_agents/ai-deep-research-agent
bash quickstart.sh
```

`quickstart.sh` 會:
- 檢查 node / uv / python3.12
- **預檢 OpenAI、Tavily 連通性**(若被網路策略擋住會直接告訴你)
- `npm install`(前端依賴)
- 用 uv 建立 Python 3.12 venv 並安裝 agent 依賴

---

## 3. 填入真實 Key

建立 `.env`(在 **repo 根目錄這個專案資料夾** 和 **`agent/`** 兩處都要):

```bash
cp .env.example .env
cp .env.example agent/.env
```

然後編輯**兩個** `.env`,把佔位值換成真的:

```bash
OPENAI_API_KEY=sk-你的真實key
OPENAI_MODEL=gpt-4o            # 改成你帳號可用的真實模型(repo 預設 gpt-5.2 是佔位名)
TAVILY_API_KEY=tvly-你的真實key
```

> ⚠️ `.env` 已被 `.gitignore` 排除,不會被 commit,放心填。

---

## 4. 啟動(需要兩個終端機 / 兩個背景行程)

**終端機 1 — Agent 後端(:8123):**
```bash
cd agent
source .venv/bin/activate
python main.py
```
看到 `Application startup complete` + `/health` 回 ok 就成功。

**終端機 2 — 前端 UI(:3000):**
```bash
npm run dev
```

開 http://localhost:3000,問它研究任何主題即可。

---

## 5. 疑難排解

| 症狀 | 原因 / 解法 |
|------|------|
| `403 host_not_allowed` 連 OpenAI/Tavily | 網路策略沒放行 → 改策略 + 開新 session(見第 0 節) |
| 前端說 "having trouble connecting to my tools" | agent 後端沒起來,或 :8123 沒通。確認終端機 1 有跑起來 |
| agent 啟動就報 `Missing OPENAI_API_KEY` | `agent/.env` 沒填或沒被讀到 |
| 呼叫時報模型不存在 / 401 | `OPENAI_MODEL` 改成你帳號可用的真實模型;確認 key 有效且已儲值 |
| Python 版本 < 3.12 | 用 `uv venv --python 3.12`(uv 會自動下載 3.12) |

---

## 架構快照

```
使用者問題 → CopilotChat(前端 :3000)
   → CopilotKit Runtime → AG-UI
   → Python FastAPI(:8123)→ Deep Agent
       ├── write_todos / write_file / read_file(內建)
       └── research(query)
             └── 內部 Deep Agent [thread 隔離]
                   └── internet_search(Tavily)
```
