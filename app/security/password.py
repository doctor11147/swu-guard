"""密码哈希 · bcrypt（passlib 包装）。

为何选 bcrypt：
- 自适应成本（rounds 可调），抗暴力破解
- 自带 salt
- passlib API 稳定，是 FastAPI 官方教程默认推荐
"""
from __future__ import annotations

from passlib.context import CryptContext

# rounds=12 在 M1 上约 ~100ms/次，是安全 vs 用户体验的常见折中
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain: str) -> str:
    """生成 bcrypt 哈希。返回形如 ``$2b$12$....`` 的字符串。"""
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """常量时间比对。错误的哈希格式也会安全返回 False。"""
    try:
        return _pwd_ctx.verify(plain, hashed)
    except (ValueError, TypeError):
        return False
