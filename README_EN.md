# LARY (Life-Agent-RU-YEE)

An AI-powered life management agent framework with a pluggable architecture. Automate daily tasks like meal planning and grocery shopping through natural language conversations.

## Features

- **Multi-Agent Collaboration** — Meal planning agent and purchasing agent work together, from recipe generation to one-click cart filling
- **Pluggable Plugin System** — Agents, Memory, and Extensions are all plugins, supporting community development and hot-reload
- **SSE Real-time Streaming** — Tool call progress, thinking status, and operation logs are pushed to the frontend in real time
- **Android Device Automation** — Controls Android devices via uiautomator2 to automatically search and add products on the Hema (Freshippo) app
- **User Profiling** — Automatically collects household size, taste preferences, etc. for personalized recipe recommendations
- **SkillHub Marketplace** — Browse, install, and uninstall community plugins online

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, LiteLLM, Pydantic v2, SQLAlchemy (async) |
| Frontend | Vue 3 + TypeScript, Vite, Tailwind CSS |
| Infrastructure | Docker Compose, PostgreSQL 16, Redis 7, Nginx |
| Testing | pytest + pytest-asyncio (backend), Vitest (frontend) |
| Linting | Ruff (line-length=120, target py311) |

## Project Structure

```
main.py                     # FastAPI entrypoint
config.yaml                 # App config (plugins, LLM, logging)
core/
  orchestrator.py            # Orchestration engine (intent routing → agent execution)
  agent_comm.py              # Inter-agent communication (agent_call tool)
  intent_router.py           # LLM intent recognition
  plugin_registry.py         # Plugin discovery, loading, registration
  skillhub.py                # Skill marketplace (index/install/uninstall)
  database.py                # SQLAlchemy async engine
  interfaces/                # Abstract base classes
api/
  chat.py                    # POST /api/chat (SSE stream)
  skillhub.py                # SkillHub REST API
plugins/
  agents/
    meal_agent/              # Meal planning agent
    purchasing_agent/        # Purchasing agent (Hema automation)
  memory/
    short_term_memory/       # Chat history (Redis + PG)
    user_profile/            # User profile
    delivery_address/        # Delivery address
  extensions/
    device_gateway/          # Device gateway (WebSocket)
    automation_u2/           # uiautomator2 Android automation
web/src/
  views/                     # ChatView, SkillHubView, DevicesView
  components/chat/           # MessageBubble, ToolCallCard, ChatInput
  composables/useSSE.ts      # SSE streaming message handler
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16 + Redis 7 (can be started via Docker)

### 1. Clone the Repository

```bash
git clone https://github.com/user/LARY.git
cd LARY
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env and fill in at least one LLM API key
```

Supported LLM providers:
- **Volcengine** (default): `VOLCENGINE_API_KEY`
- **OpenAI**: `OPENAI_API_KEY`
- **Anthropic**: `ANTHROPIC_API_KEY`
- Falls back to Ollama local model when no key is configured

### 3. Start Infrastructure

```bash
docker compose up -d postgres redis
```

### 4. Install and Start Backend

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python main.py
```

Backend runs at `http://localhost:8000`

### 5. Install and Start Frontend

```bash
cd web
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`, API requests are proxied to the backend.

### Docker Deployment

```bash
cp .env.example .env
# Edit .env and fill in API keys
docker compose up --build -d
```

Visit `http://localhost`

#### Android Device Connection (Purchasing Feature)

The purchasing agent controls the Hema APP on an Android device via uiautomator2. Docker deployment connects via USB by default:

1. Connect Android device to the server via USB
2. Enable USB debugging on the device
3. `docker-compose.yml` is pre-configured with USB passthrough (`/dev/bus/usb`)

To connect via network, configure in `config.yaml`:

```yaml
plugins:
  automation_u2:
    device_addr: "192.168.1.100:5555"  # Android device IP
```

## Running Tests

### Backend Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short
```

### Frontend Tests

```bash
cd web
npx vitest run
```

### Lint Check

```bash
ruff check .
```

## Configuration

| File | Purpose |
|------|---------|
| `.env` | Environment variables (API keys, DB connections) — **not committed to git** |
| `config.yaml` | App configuration (enabled plugins, LLM models, parameters) |
| `.env.example` | Environment variable template |

## License

[MIT](LICENSE)
