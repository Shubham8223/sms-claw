"""Long-term memory repository — CRUD + pgvector semantic search."""

from __future__ import annotations

import json
import uuid

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.core.config import get_settings
from sms_claw.core.constants import EMBEDDING_MODEL
from sms_claw.core.logging import get_logger
from sms_claw.database.models import LongTermMemory

log = get_logger(__name__)
_s = get_settings()


class MemoryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Embedding ──────────────────────────────────────────────────────────────

    async def _embed(self, text_: str) -> list[float] | None:
        """Generate a float embedding vector. Returns None on failure."""
        if not _s.openai_api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {_s.openai_api_key}"},
                    json={"input": text_, "model": EMBEDDING_MODEL},
                )
                resp.raise_for_status()
                return resp.json()["data"][0]["embedding"]
        except Exception as exc:
            log.warning("embed_failed", error=str(exc), exc_info=True)
            return None

    # ── Write ──────────────────────────────────────────────────────────────────

    async def create(
        self,
        user_id: uuid.UUID,
        content: str,
        category: str = "general",
    ) -> LongTermMemory:
        embedding = await self._embed(content)
        mem = LongTermMemory(
            user_id=user_id,
            content=content,
            category=category,
            embedding=embedding,
        )
        self._db.add(mem)
        await self._db.flush()
        log.info("memory_saved", user_id=str(user_id), category=category)
        return mem

    # ── Read ───────────────────────────────────────────────────────────────────

    async def search(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int = 5,
    ) -> list[str]:
        """Semantic search if embeddings available, else recency fallback."""
        query_embedding = await self._embed(query)

        if query_embedding:
            try:
                rows = await self._db.execute(
                    text("""
                        SELECT content FROM long_term_memories
                        WHERE user_id = :uid
                        ORDER BY embedding::vector <=> cast(:emb AS vector)
                        LIMIT :lim
                        """),
                    {
                        "uid": str(user_id),
                        "emb": json.dumps(query_embedding),
                        "lim": limit,
                    },
                )
                return [r[0] for r in rows.fetchall()]
            except Exception as exc:
                log.warning("vector_search_failed", error=str(exc), exc_info=True)

        # Recency fallback
        rows = await self._db.execute(
            select(LongTermMemory.content)
            .where(LongTermMemory.user_id == user_id)
            .order_by(LongTermMemory.created_at.desc())
            .limit(limit)
        )
        return [r[0] for r in rows.fetchall()]

    async def list_by_user(
        self, user_id: uuid.UUID, limit: int = 20
    ) -> list[LongTermMemory]:
        result = await self._db.execute(
            select(LongTermMemory)
            .where(LongTermMemory.user_id == user_id)
            .order_by(LongTermMemory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
