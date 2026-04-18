"""
Authentication Router — login, register, current user.

Uses JWT tokens stored in the frontend (localStorage).
Passwords hashed with bcrypt via passlib.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.db_models import User, UserRole

router = APIRouter(prefix="/api/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Schemas ─────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""
    team_name: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    team_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _create_token(user_id: int, email: str, role: str, team_name: str = "") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "email": email, "role": role, "team": team_name, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email + password, receive a JWT."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not pwd_context.verify(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = _create_token(user.id, user.email, user.role.value, user.team_name)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account. First user gets admin role."""
    # Check duplicate
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # First user becomes admin
    count_result = await db.execute(select(User))
    is_first = count_result.first() is None

    user = User(
        email=body.email,
        full_name=body.full_name or body.email.split("@")[0],
        hashed_password=pwd_context.hash(body.password),
        team_name=body.team_name,
        role=UserRole.ADMIN if is_first else UserRole.VIEWER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = _create_token(user.id, user.email, user.role.value, user.team_name)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def get_current_user(
    token: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Validate JWT and return current user info. Token passed as query param."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    return user
