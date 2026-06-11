"""Expire approved visitor appointments whose validity window has ended.

Usage:
    conda activate face
    python -m app.scripts.expire_visitor_appointments

This script is safe to run repeatedly from cron/systemd timer. It only updates
appointments in status='approved' whose appointment date/slot is already past.
"""
from __future__ import annotations

import asyncio

from app.services.visitors import expire_stale_appointments
from app.store.session import db_session


async def _main() -> None:
    async with db_session() as db:
        count = await expire_stale_appointments(db)
    print(f"expired_visitor_appointments={count}")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
