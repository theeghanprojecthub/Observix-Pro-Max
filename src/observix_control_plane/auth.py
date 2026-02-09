from __future__ import annotations

from fastapi import Header, HTTPException, status


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    # injected by api.py closure
    raise RuntimeError("wire require_admin via dependency factory")


def require_agent(x_agent_token: str | None = Header(default=None)) -> str:
    if not x_agent_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing agent token"
        )
    return x_agent_token
