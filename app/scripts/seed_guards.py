"""为北碚校区七门 seed 7 个门卫账户 + 关联到各自门。

幂等：账户已存在不重复创建，关联已存在不重复 insert。
必须通过 ``--password`` 显式提供初始密码。

用法：
    conda activate face
    python -m app.scripts.seed_guards --password "replace-me"
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.security.password import hash_password
from app.services import guards as guards_svc
from app.store.session import db_session

# (username, gate_code, display_name)
GUARDS = [
    ("guard_hanhong",   "gate_hanhong",   "含弘门 · 门卫"),
    ("guard_xuexing",   "gate_xuexing",   "学行门 · 门卫"),
    ("guard_tiansheng", "gate_tiansheng", "天生门 · 门卫"),
    ("guard_xuefu",     "gate_xuefu",     "学府门 · 门卫"),
    ("guard_xueyuan",   "gate_xueyuan",   "学苑门 · 门卫"),
    ("guard_wenxing",   "gate_wenxing",   "文星门 · 门卫"),
    ("guard_jiangjun",  "gate_jiangjun",  "将军门 · 门卫"),
]

async def _run(password: str) -> int:
    pwd_hash = hash_password(password)
    print(f"将创建/更新 {len(GUARDS)} 个门卫账户\n")
    async with db_session() as s:
        for username, gate_code, name in GUARDS:
            admin = await guards_svc.get_or_create_guard(
                s, username=username, password_hash=pwd_hash,
                name=name, email=None,
            )
            linked = await guards_svc.link_admin_to_gate_by_code(
                s, admin, gate_code,
            )
            mark = "+" if linked else "·"
            print(f"  {mark} {username:<18}  →  {gate_code:<16}  ({name})")
    print("\n✅ 完成。门卫账户用各自 username + 上述密码登录。")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--password", required=True)
    args = p.parse_args()
    try:
        return asyncio.run(_run(args.password))
    except Exception as e:
        print(f"❌ 失败: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
