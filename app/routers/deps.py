"""
Shared FastAPI dependencies for authentication and team scoping.

CurrentUser is extracted from the JWT Bearer token and injected into endpoints.
Non-admin users are restricted to their own team's data (RBAC).
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from jose import JWTError, jwt

from app.config import settings


class CurrentUser:
    """Lightweight user context from JWT — no DB hit required."""

    __slots__ = ("user_id", "email", "role", "team_name")

    def __init__(self, user_id: int, email: str, role: str, team_name: str):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.team_name = team_name

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _decode_token(token: str) -> CurrentUser:
    """Decode and validate a JWT token, return CurrentUser."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return CurrentUser(
        user_id=int(payload["sub"]),
        email=payload["email"],
        role=payload["role"],
        team_name=payload.get("team", ""),
    )


async def get_current_user(request: Request) -> CurrentUser:
    """Extract user from Authorization: Bearer <token>. Raises 401 if missing/invalid."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization token")
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        return _decode_token(token)
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_optional_user(request: Request) -> CurrentUser | None:
    """Extract user if Bearer token is present, return None otherwise."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        return _decode_token(token)
    except (JWTError, KeyError, ValueError):
        return None
