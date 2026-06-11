# CLAUDE.md — Session Handoff Note

> This is a working note to hand off an exploration session (started on Claude Code
> on the web) to a local Claude Code instance. It records what was explored, what
> was decided, what was built, and what's next. Read this first, then continue.

## Goal of the session

Tour the `awesome-llm-apps` repo's examples, focusing on **generative UI agents**
and **voice AI agents**, then adapt one voice example to run **fully locally**
(no API keys, offline). The user runs **LM Studio** locally for LLMs.

## What was explored (in order)

1. Repo overview — categories: `starter_ai_agents`, `advanced_ai_agents`,
   `rag_tutorials`, `mcp_ai_agents`, `generative_ui_agents`, `voice_ai_agents`,
   `awesome_agent_skills`, `advanced_llm_apps`, `ai_agent_framework_crash_course`.
   - Established: `awesome_agent_skills` is NOT a prerequisite for the others
     (it's SKILL.md packages, independent of the runnable app templates).
2. `generative_ui_agents/generative-ui-starter-project` — shared agent state
   (CopilotKit `useCoAgent`), chat-driven kanban; LangGraph backend.
3. `generative_ui_agents/ai-deep-research-agent` — tool-rendered cards via
   `useDefaultTool`; Deep Agents + Tavily; thread-isolated `research()` tool to
   stop subagent callbacks leaking to the frontend.
4. `generative_ui_agents/ai-financial-coach-agent` — Google ADK multi-agent
   router; mixes `useCoAgent` (cards from shared state via `output_key`) with
   `useCopilotAction` (status pills); Pydantic `output_schema`.
5. `voice_ai_agents/` — all four examples surveyed with API/cost analysis:
   - `ai_audio_tour_agent` (OpenAI only, paid)
   - `customer_support_voice_agent` (OpenAI paid + Firecrawl/Qdrant free tiers)
   - `insurance_claim_live_agent_team` (Google Gemini Live API; free tier exists;
     hybrid graph = LlmAgents + deterministic rules in `policies.py`)
   - `voice_rag_openaisdk` (OpenAI paid + Qdrant free + FastEmbed local)

## Key decisions

- User is most interested in the **customer-support / voice-RAG** topics and wants
  **local models**. Verdict: embeddings (FastEmbed) and vector DB (Qdrant) can be
  fully local for free; LLM swappable to a local OpenAI-compatible endpoint;
  **TTS is the only real porting work** (OpenAI TTS has no local drop-in).
- **Keep LM Studio, do NOT switch to Ollama** — LM Studio already exposes an
  OpenAI-compatible server at `http://localhost:1234/v1`, which is all this app
  needs. (Ollama only worth it for headless/server use.)

## Artifacts created on this branch (`claude/loving-clarke-iw3d6n`)

| File | Purpose |
| --- | --- |
| `generative_ui_agents/ai-deep-research-agent/RUNBOOK.md` | End-to-end run guide (keys, network policy, troubleshooting) |
| `generative_ui_agents/ai-deep-research-agent/quickstart.sh` | Idempotent setup + network preflight (detects OpenAI/Tavily blocks) |
| `voice_ai_agents/voice_rag_openaisdk/rag_voice_local.py` | **Fully-local Voice RAG** (LM Studio + FastEmbed + local Qdrant + Kokoro TTS) |
| `voice_ai_agents/voice_rag_openaisdk/requirements-local.txt` | Deps for the local variant |

## Local Voice RAG — design decisions (`rag_voice_local.py`)

- LLM: `OpenAIChatCompletionsModel` + `AsyncOpenAI(base_url=...)` → LM Studio `:1234`
  (Ollama `:11434` via sidebar). `set_tracing_disabled(True)` is required so the
  agents SDK doesn't call OpenAI tracing in the background.
- Vector DB: `QdrantClient(path="./qdrant_local")` — embedded local mode, no Docker.
- Embeddings: FastEmbed (unchanged from original — already local).
- TTS: Kokoro (`KPipeline`, 24 kHz WAV). Dropped the original's second "TTS
  instructions agent" — it only fed OpenAI's steerable-TTS `instructions` param,
  which local engines don't support. Piper noted as a lighter alternative.
- Removed `LocalAudioPlayer` (plays on server, wrong for a web app); use `st.audio`.

## Environment constraints discovered (web session)

- Web env type was `cloud_default`; its network policy **blocks `api.openai.com`
  and `api.tavily.com`** (`403 host_not_allowed`), so end-to-end runs of the
  cloud examples were not possible here. npm/pypi/github/Anthropic API are allowed.
  Policy changes require a NEW session to take effect.
- System had Node 22, npm, pnpm, Python 3.11 (+ system 3.12), uv. Deep-research
  needs Python 3.12 (`uv venv --python 3.12`).
- **No API keys were ever provided**, and a secrets audit confirmed **none were
  committed/pushed**. Local `.env` files are gitignored.

## How to run the local Voice RAG (on the user's machine)

```bash
# 1) LM Studio: load a model, then Developer → Local Server → Start (port 1234)
# 2) Kokoro system dep:
apt-get install espeak-ng        # mac: brew install espeak-ng
# 3) Install + run:
cd voice_ai_agents/voice_rag_openaisdk
pip install -r requirements-local.txt
streamlit run rag_voice_local.py
```

## Suggested next steps / open TODOs

- [ ] Actually run `rag_voice_local.py` locally against LM Studio and verify the
      full path (PDF upload → retrieval → local LLM answer → Kokoro audio).
- [ ] Optionally add a Piper-based `synthesize_speech` variant for weak machines.
- [ ] If the customer-support topic is wanted too, apply the same local recipe to
      `customer_support_voice_agent` (same shape: OpenAI LLM+TTS, FastEmbed,
      Qdrant; plus it crawls docs via Firecrawl — could swap to a local crawler).
- [ ] (Earlier idea) Run the cloud `ai-deep-research-agent` end-to-end — needs a
      permissive network policy + real OpenAI/Tavily keys.
```
