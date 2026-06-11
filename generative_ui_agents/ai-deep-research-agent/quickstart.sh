#!/usr/bin/env bash
# Quickstart for the Deep Research Agent.
# Runs tooling checks, a network preflight (OpenAI/Tavily), and installs deps.
# See RUNBOOK.md for the full guide.

set -euo pipefail
cd "$(dirname "$0")"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; }
err()  { printf "  \033[31m✗\033[0m %s\n" "$1"; }

bold "[1/4] Toolchain check"
command -v node >/dev/null && ok "node $(node -v)" || { err "node not found"; exit 1; }
command -v npm  >/dev/null && ok "npm $(npm -v)"   || { err "npm not found";  exit 1; }
command -v uv   >/dev/null && ok "uv $(uv --version)" || { err "uv not found (https://docs.astral.sh/uv/)"; exit 1; }

bold "[2/4] Network preflight (does this environment allow OpenAI + Tavily?)"
check_host() {
  local name="$1" url="$2"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")
  if [ "$code" = "403" ]; then
    err "$name BLOCKED (HTTP 403 host_not_allowed) — network policy is blocking this host"
    return 1
  elif [ "$code" = "000" ]; then
    warn "$name unreachable (timeout/DNS) — check connectivity"
    return 1
  else
    ok "$name reachable (HTTP $code)"
    return 0
  fi
}
NET_OK=1
check_host "OpenAI" "https://api.openai.com/v1/models" || NET_OK=0
check_host "Tavily" "https://api.tavily.com/"          || NET_OK=0
if [ "$NET_OK" -eq 0 ]; then
  warn "One or more APIs are blocked. Env type: ${CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE:-unknown}"
  warn "On web: switch to a permissive network policy and start a NEW session (see RUNBOOK.md §0)."
  warn "Continuing with install anyway so the frontend/agent can still boot…"
fi

bold "[3/4] Frontend deps (npm install)"
npm install
ok "node_modules ready"

bold "[4/4] Agent deps (Python 3.12 venv via uv)"
cd agent
uv venv --python 3.12
# shellcheck disable=SC1091
source .venv/bin/activate
uv pip install -e .
ok "agent venv ready"
cd ..

bold "Done. Next steps:"
echo "  1. Create .env files and fill REAL keys:"
echo "       cp .env.example .env && cp .env.example agent/.env"
echo "       # edit both: OPENAI_API_KEY, OPENAI_MODEL, TAVILY_API_KEY"
echo "  2. Start agent  (terminal 1):  cd agent && source .venv/bin/activate && python main.py"
echo "  3. Start UI     (terminal 2):  npm run dev"
echo "  4. Open http://localhost:3000"
