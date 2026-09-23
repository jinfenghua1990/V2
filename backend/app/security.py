from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException


@dataclass(frozen=True)
class Principal:
    actor_type: str
    actor_id: str
    role: str


def allow_local_access() -> Principal:
    """Only used by isolated test applications, never by the production app."""

    return Principal(actor_type="test", actor_id="local-test", role="admin")


def _role_set(name: str, default: str) -> set[str]:
    raw = os.getenv(name, default)
    return {value.strip() for value in raw.split(",") if value.strip()}


def _authenticate(authorization: Optional[str]) -> Principal:
    expected = os.getenv("V2_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="V2_API_KEY 未配置")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="需要 Bearer API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    presented = authorization.removeprefix("Bearer ").strip()
    if not presented or not secrets.compare_digest(presented, expected):
        raise HTTPException(status_code=403, detail="API Key 无效")

    role = os.getenv("V2_API_ROLE", "admin").strip() or "admin"
    if role not in _role_set("V2_API_READ_ROLES", "admin,operator,viewer"):
        raise HTTPException(status_code=403, detail="当前角色没有访问权限")
    actor_id = os.getenv("V2_API_ACTOR_ID", "api-client").strip() or "api-client"
    return Principal(actor_type="api", actor_id=actor_id, role=role)


def require_api_access(
    authorization: Optional[str] = Header(default=None),
) -> Principal:
    return _authenticate(authorization)


def require_write_access(
    authorization: Optional[str] = Header(default=None),
) -> Principal:
    principal = _authenticate(authorization)
    if principal.role not in _role_set("V2_API_WRITE_ROLES", "admin,operator"):
        raise HTTPException(status_code=403, detail="当前角色没有写入权限")
    return principal
