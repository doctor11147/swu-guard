"""Create or update a superadmin with an explicitly supplied password.

Usage:
    conda activate face
    python -m app.scripts.seed_admin --username admin --password "replace-me"
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.security.password import hash_password
from app.store.models import Admin
from app.store.session import db_session

async def _run(username: str, password: str) -> int:
    async with db_session() as s:
        admin = await s.scalar(select(Admin).where(Admin.username == username))
        if admin is None:
            admin = Admin(
                username=username,
                password_hash=hash_password(password),
                name="System Administrator",
                email=None,
                role="superadmin",
                is_active=True,
            )
            s.add(admin)
        else:
            admin.password_hash = hash_password(password)
        await s.commit()
        print(f"Created or updated superadmin {username!r}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--username", default="admin")
    p.add_argument("--password", required=True)
    args = p.parse_args()
    return asyncio.run(_run(args.username, args.password))


if __name__ == "__main__":
    raise SystemExit(main())
