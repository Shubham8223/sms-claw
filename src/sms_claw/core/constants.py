"""Application-wide constants."""
from __future__ import annotations

# Memory
WORKING_MEMORY_TTL_SECONDS: int = 1800        # 30 min
WORKING_MEMORY_MAX_MESSAGES: int = 20
SHORT_TERM_RETENTION_DAYS: int = 30
SHORT_TERM_MAX_SUMMARIES: int = 5

# SMS
SMS_MAX_REPLY_CHARS: int = 300                # trim agent reply to this
SMS_HARD_MAX_CHARS: int = 1600                # provider hard limit

# Rate limiting
RATE_LIMIT_WINDOW_SECONDS: int = 3600         # 1 hour bucket

# OTP
OTP_DIGITS: int = 6

# Agent
MAX_TOOL_ITERATIONS: int = 10

# Embedding
EMBEDDING_MODEL: str = "text-embedding-3-small"
EMBEDDING_DIMENSIONS: int = 1536
