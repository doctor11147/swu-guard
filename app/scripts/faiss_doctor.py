"""FAISS 与 MySQL 一致性诊断 / 修复工具。

设计动机
--------
``face_embeddings.id`` 与 FAISS 向量 id 必须一一对应。但实际部署中两边可能漂移：
- FAISS 是进程内单例，uvicorn 不重启时旧状态会写回磁盘
- MySQL ``DELETE`` 不能让 ``auto_increment`` 回退，导致清理后新写入 id ≥ 旧最大值+1
- MVP 时代写入的向量与 v0.2 的 MySQL 表之间天然存在脏数据

工具行为
--------
- 默认：扫描 FAISS 与 MySQL，打印差集（FAISS 孤儿 + MySQL 孤儿）
- ``--reset`` ：原子清空两侧
    1) ``DELETE FROM face_embeddings``
    2) ``ALTER TABLE face_embeddings AUTO_INCREMENT = 1``  （让下一次注册从 1 开始）
    3) 删除 FAISS 文件
- ``--prune`` ：仅从 FAISS 移除 MySQL 不存在的 id（保留有 MySQL 对应记录的向量）

使用
----
**注意**：执行 ``--reset`` / ``--prune`` 后必须重启 uvicorn，因为进程内存里仍有旧 FaissStore。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import faiss
from sqlalchemy import delete, select, text

from app.store.models import FaceEmbedding
from app.store.session import db_session

DEFAULT_FAISS = Path(__file__).resolve().parents[1] / "data" / "faces.faiss"


def _read_faiss_ids(faiss_path: Path) -> list[int]:
    if not faiss_path.exists():
        return []
    idx = faiss.read_index(str(faiss_path))
    if not hasattr(idx, "id_map"):
        return []
    return [int(i) for i in faiss.vector_to_array(idx.id_map)]


async def _read_mysql_ids() -> set[int]:
    async with db_session() as s:
        rows = await s.scalars(select(FaceEmbedding.id))
        return {int(i) for i in rows.all()}


async def diagnose(faiss_path: Path) -> tuple[set[int], set[int]]:
    """返回 (faiss_orphans, mysql_orphans)。"""
    faiss_ids_list = _read_faiss_ids(faiss_path)
    faiss_ids = set(faiss_ids_list)
    mysql_ids = await _read_mysql_ids()

    faiss_orphans = faiss_ids - mysql_ids        # FAISS 有但 MySQL 没有
    mysql_orphans = mysql_ids - faiss_ids        # MySQL 有但 FAISS 没有
    dups = len(faiss_ids_list) - len(faiss_ids)  # FAISS 内部重复

    print(f"FAISS file   : {faiss_path}")
    print(f"FAISS ntotal : {len(faiss_ids_list)} (unique={len(faiss_ids)}, duplicates={dups})")
    print(f"MySQL count  : {len(mysql_ids)}")
    print(f"FAISS 孤儿   : {len(faiss_orphans)}   {sorted(faiss_orphans)[:20]}{'...' if len(faiss_orphans) > 20 else ''}")
    print(f"MySQL 孤儿   : {len(mysql_orphans)}   {sorted(mysql_orphans)[:20]}{'...' if len(mysql_orphans) > 20 else ''}")
    return faiss_orphans, mysql_orphans


async def reset(faiss_path: Path) -> None:
    """两侧原子清空。⚠️ 需停 uvicorn 后执行。"""
    print("===== RESET =====")
    async with db_session() as s:
        await s.execute(delete(FaceEmbedding))
        # 重置 auto_increment，确保下次注册从 id=1 开始（与新空 FAISS 对齐）
        await s.execute(text("ALTER TABLE face_embeddings AUTO_INCREMENT = 1"))
        await s.commit()
        print("✅ MySQL face_embeddings 已清空 + AUTO_INCREMENT 重置为 1")

    if faiss_path.exists():
        bak = faiss_path.with_suffix(faiss_path.suffix + ".bak")
        faiss_path.replace(bak)
        print(f"✅ FAISS 文件已备份到 {bak} 并清空")
    else:
        print("ℹ️  FAISS 文件不存在，无需删除")

    print("\n⚠️  重启 uvicorn 让进程内 FaissStore 重新加载空索引。")


async def prune(faiss_path: Path) -> None:
    """仅从 FAISS 移除 MySQL 不存在的孤儿 id。需停 uvicorn 后执行。"""
    print("===== PRUNE =====")
    faiss_orphans, _ = await diagnose(faiss_path)
    if not faiss_orphans:
        print("✅ 无孤儿，无需修剪。")
        return
    if not faiss_path.exists():
        print("ℹ️  FAISS 文件不存在，无需修剪。")
        return

    idx = faiss.read_index(str(faiss_path))
    import numpy as np
    sel = faiss.IDSelectorBatch(np.asarray(sorted(faiss_orphans), dtype=np.int64))
    removed = int(idx.remove_ids(sel))
    faiss.write_index(idx, str(faiss_path))
    print(f"✅ FAISS 已移除 {removed} 个孤儿 id")
    print("\n⚠️  重启 uvicorn 让进程内 FaissStore 重新加载。")


async def _amain() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true", help="清空两侧（备份 FAISS）")
    p.add_argument("--prune", action="store_true", help="仅从 FAISS 移除 MySQL 不存在的 id")
    p.add_argument("--faiss", default=str(DEFAULT_FAISS))
    args = p.parse_args()
    faiss_path = Path(args.faiss)

    if args.reset and args.prune:
        print("--reset 与 --prune 互斥", file=sys.stderr)
        return 1

    if args.reset:
        await reset(faiss_path)
    elif args.prune:
        await prune(faiss_path)
    else:
        await diagnose(faiss_path)
    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
