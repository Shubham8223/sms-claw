# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev

# ── Runtime stage ───────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app
RUN addgroup --system app && adduser --system --group app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/src"

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/admin/health').raise_for_status()"

CMD ["uvicorn", "sms_claw.api.app:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "4"]
