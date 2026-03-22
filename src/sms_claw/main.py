"""Application entrypoint — runs uvicorn."""

from __future__ import annotations

import uvicorn

from sms_claw.core.config import get_settings


def main() -> None:
    s = get_settings()
    uvicorn.run(
        "sms_claw.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=not s.is_production,
        log_level=s.log_level.lower(),
        workers=1 if not s.is_production else 4,
    )


if __name__ == "__main__":
    main()
