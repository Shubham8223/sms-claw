# sms_claw

An SMS-powered personal AI agent gateway built with **Python 3.12**, **LangGraph**, and **FastAPI**.

Send an SMS to your number. Get back AI answers, live web search, WhatsApp messages, emails, GitHub actions — from any phone, anywhere.

---

## Architecture

```
src/sms_claw/
│
├── core/                  Zero-dependency shared infrastructure
│   ├── config.py          Pydantic-settings — single source of truth
│   ├── logging.py         structlog + rich tracebacks (JSON in prod)
│   ├── exceptions.py      Typed domain exceptions (no HTTP imports)
│   └── constants.py       All magic numbers in one place
│
├── database/              Persistence layer
│   ├── base.py            Async SQLAlchemy engine + session factory
│   └── models.py          All ORM models (User, Session, MessageLog, LongTermMemory)
│
├── repositories/          Data access — the ONLY layer that touches the DB
│   ├── user_repo.py
│   ├── session_repo.py
│   ├── message_repo.py
│   └── memory_repo.py     CRUD + pgvector semantic search
│
├── security/
│   └── auth.py            OTP, allowlist, HMAC verify, rate limit
│                          Raises domain exceptions, never HTTP exceptions
│
├── memory/                Domain concepts wrapping repositories
│   ├── working.py         Redis session buffer (TTL 30 min)
│   ├── short_term.py      Postgres session summaries (30 days)
│   └── long_term.py       pgvector semantic memories (indefinite)
│
├── sms_providers/         Pluggable SMS adapters
│   ├── base.py            Abstract interface (send, parse_inbound, verify_webhook)
│   ├── twilio_provider.py
│   ├── africas_talking_provider.py
│   ├── vonage_provider.py
│   └── registry.py        @register decorator + lru_cache factory
│
├── tools/                 LangChain tools auto-registered on import
│   ├── registry.py        @register_tool decorator + get_all_tools()
│   ├── web_tool.py        web_search + web_browse
│   ├── whatsapp_tool.py
│   ├── email_tool.py
│   ├── github_tool.py     github_search + github_create_issue
│   ├── telegram_tool.py
│   └── memory_tool.py     Injected per-request (needs phone + ltm)
│
├── agent/                 LangGraph ReAct loop
│   ├── state.py           AgentState TypedDict
│   ├── prompts.py         System prompt templates
│   ├── llm_factory.py     build_llm(provider, model) — Anthropic/OpenAI/Google
│   └── graph.py           Nodes: load_context→call_llm⇄run_tools→format_reply→save_memory
│
├── services/              Business logic — no HTTP, no raw DB calls
│   ├── enrollment_service.py   OTP flow orchestration
│   ├── message_service.py      Full SMS turn: enroll→rate_limit→session→agent
│   ├── session_service.py      Session lifecycle
│   └── admin_service.py        Read-only queries for admin API
│
└── api/                   HTTP boundary — no business logic
    ├── dependencies.py    FastAPI DI: db session, Redis, SMS provider
    ├── app.py             Factory + exception handler (domain → HTTP codes)
    └── routers/
        ├── webhook.py     POST /webhook/{twilio,africas-talking,vonage,generic}
        └── admin.py       GET/DELETE /admin/*
```

### Layer rules

| Layer | Imports allowed from | Must NOT import |
|---|---|---|
| `api/` | `services/`, `core/`, FastAPI | `repositories/`, `database/`, `agent/` directly |
| `services/` | `repositories/`, `memory/`, `agent/`, `security/`, `core/` | FastAPI, HTTP libs |
| `repositories/` | `database/`, `core/` | `services/`, `api/`, `agent/` |
| `memory/` | `repositories/`, `core/` | `services/`, `api/` |
| `agent/` | `tools/`, `memory/`, `core/` | `api/`, `services/` |

---

## Quickstart

### 1. Prerequisites
- Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker

### 2. Install

```bash
git clone https://github.com/yourname/sms_claw
cd sms_claw
uv sync --all-groups
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env — minimum required:
# APP_SECRET_KEY, ALLOWED_PHONE_NUMBERS, one LLM key, one SMS provider
```

### 4. Start infrastructure

```bash
docker compose up -d
uv run alembic upgrade head
```

### 5. Run

```bash
uv run sms_claw          # hot-reload dev server on :8000
```

### 6. Test locally (no SMS account needed)

```bash
curl -X POST http://localhost:8000/webhook/generic \
  -H "Content-Type: application/json" \
  -d '{"from": "+91YOURPHONE", "body": "What is 2+2?"}'
```

### 7. Expose + wire to SMS provider

```bash
ngrok http 8000
# Twilio webhook → https://<ngrok>/webhook/twilio
# Africa's Talking → https://<ngrok>/webhook/africas-talking
# Vonage → https://<ngrok>/webhook/vonage
```

---

## Commands

```bash
# Run
uv run sms_claw

# Tests
uv run pytest
uv run pytest --cov

# Lint / format / type check
uv run ruff check src/
uv run ruff format src/
uv run mypy src/

# Migrations
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
uv run alembic downgrade -1

# Admin
curl http://localhost:8000/admin/health
curl http://localhost:8000/admin/channels
curl http://localhost:8000/admin/users
curl http://localhost:8000/admin/users/+919876543210/memory
```

---

## Adding a new SMS provider

1. Create `src/sms_claw/sms_providers/myprovider_provider.py` — implement `SMSProviderBase` (`send`, `parse_inbound`, `verify_webhook`)
2. Register in `src/sms_claw/sms_providers/registry.py` inside `_load_all()`
3. Add a webhook route in `src/sms_claw/api/routers/webhook.py`
4. Add config fields to `src/sms_claw/core/config.py` and `.env.example`
5. Set `DEFAULT_SMS_PROVIDER=myprovider` in `.env`

## Adding a new tool

1. Create `src/sms_claw/tools/mytool.py` with `@register_tool @tool async def my_tool(...)`
2. Import it in `src/sms_claw/tools/registry.py` inside `get_all_tools()`
3. Done — the agent picks it up automatically on next restart

## Adding a new LLM provider

1. Add an `if _provider == "myprovider":` branch in `src/sms_claw/agent/llm_factory.py`
2. Add the API key field to `src/sms_claw/core/config.py` and `.env.example`
3. Set `DEFAULT_LLM_PROVIDER=myprovider` in `.env`

---

## Security model

| Layer | Mechanism |
|---|---|
| Identity | Phone number + OTP enrollment (Redis) |
| Access control | `ALLOWED_PHONE_NUMBERS` allowlist |
| Webhook integrity | HMAC-SHA256 per provider, checked in production only |
| Rate limiting | Token bucket in Redis, per number per hour |
| Domain isolation | HTTP exceptions never leak into services/agent |
| Production mode | `APP_ENV=production` disables `/docs`, generic endpoint, enables strict middleware |

---

## Memory system

| Tier | Store | TTL | Content |
|---|---|---|---|
| Working | Redis | 30 min | Live conversation (last 20 messages) |
| Short-term | Postgres | 30 days | Session summaries, message logs |
| Long-term | Postgres + pgvector | Indefinite | Semantic memories, preferences, facts |

---

## Production deployment

```bash
docker build -t sms_claw .
docker run -p 8000:8000 --env-file .env sms_claw
```

Or push to Railway / Render / Fly.io — set env vars in the dashboard and set `APP_ENV=production`.
