# Deep Research Agent — Runbook(端到端跑通指南)

這份是為了「在新的 Claude Code on the web session(或本機)從零跑通」而準備的。
照順序做即可。

> ✅ **已實測通過的免費配置**(2026-06):Groq `openai/gpt-oss-120b` + Tavily 免費 key。
> 完整鏈路驗證過:`write_todos`(規劃)→ `research` 工具 → Tavily 真實搜尋 → 帶引用的報告。
> 最快路徑:`bash quickstart.sh` → 兩個 `.env` 填下方「選項 B」→ 啟動兩個 server。

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

需要兩把:一把搜尋(Tavily)、一把 LLM(OpenAI 或免費替代)。

| 服務 | 網址 | 費用 |
|------|------|------|
| **Tavily**(網路搜尋,必需) | https://app.tavily.com | **免費**:每月 1000 次、免綁卡 |
| **OpenAI**(LLM,選項 A) | https://platform.openai.com/api-keys | **付費**:需先儲值(最低約 $5),用多少扣多少 |
| **Groq**(LLM,選項 B — 推薦免費) | https://console.groq.com | **完全免費、免綁卡**,OpenAI 相容 |

### LLM 怎麼選?

- **要完全免費** → 用 **Groq**(見下方 §3 的設定)。本專案 `agent.py` / `tools.py` 已支援
  透過 `OPENAI_BASE_URL` 指向任何 OpenAI 相容端點,換供應商**只改 `.env`、不用動程式**。
- ⚠️ **Groq 模型挑選很重要**:這個 deep agent 重度依賴 tool calling。實測
  `llama-3.3-70b-versatile` 會產出**壞掉的 tool call 格式**(`tool_use_failed`),
  請改用 **`openai/gpt-oss-120b`**(實測穩定)。其他可考慮 `qwen/qwen3-32b`。
- 其他免費且連得到的相容供應商:OpenRouter(`https://openrouter.ai/api/v1`)、
  Together;設定方式同 Groq,只是 `OPENAI_BASE_URL` / `OPENAI_MODEL` 換掉。

> 💡 **驗證 key 是否有效**(別只看 HTTP code,要看 body):
> ```bash
> # Tavily(回 results 就是有效;回 401 / "Unauthorized" 就是無效)
> curl -s -X POST https://api.tavily.com/search \
>   -H "Authorization: Bearer $TAVILY_API_KEY" \
>   -H "Content-Type: application/json" \
>   -d '{"query":"test","max_results":1}' | head -c 200
> # Groq(回模型清單就有效)
> curl -s https://api.groq.com/openai/v1/models \
>   -H "Authorization: Bearer $OPENAI_API_KEY" -o /dev/null -w "%{http_code}\n"
> ```

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

然後編輯**兩個** `.env`,把佔位值換成真的。二選一:

**選項 A — OpenAI(付費):**
```bash
OPENAI_API_KEY=sk-你的真實key
OPENAI_MODEL=gpt-4o            # 改成你帳號可用的真實模型(repo 預設 gpt-5.2 是佔位名)
# OPENAI_BASE_URL 留空 = 用官方 OpenAI
TAVILY_API_KEY=tvly-你的真實key
```

**選項 B — Groq(免費,推薦):**
```bash
OPENAI_API_KEY=gsk_你的Groq金鑰
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=openai/gpt-oss-120b   # 不要用 llama-3.3-70b,tool calling 會壞
TAVILY_API_KEY=tvly-你的真實key
```

> ⚠️ `.env` 已被 `.gitignore` 排除,不會被 commit,放心填。
> 兩個 `.env`(專案資料夾 + `agent/`)內容要一致。

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
| `tool_use_failed` / `<function=...>` 格式錯誤 | LLM 產出壞掉的 tool call。換更會 tool calling 的模型:Groq 用 `openai/gpt-oss-120b`(別用 `llama-3.3-70b-versatile`) |
| research 回 `Unauthorized: missing or invalid API key`、`0 sources` | **Tavily key 無效**(不是程式問題)。用 §1 的 curl 指令驗 key;無效就到 console 重新產生 |
| LLM 不走 `research` 工具、直接憑記憶回答 | 問題不夠「需要查」。提示詞明確要求「research/查最新/附來源」可逼它用工具 |
| 用 Groq 時所有 LLM 呼叫都打到官方 OpenAI 失敗 | 確認 `OPENAI_BASE_URL=https://api.groq.com/openai/v1` 兩個 `.env` 都有設 |
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
