import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta

import bcrypt as bc
import jwt
from fastapi import APIRouter, HTTPException, Depends, Response, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.refresh_token import RefreshToken
from utils.db import get_db

router = APIRouter(prefix="/api/auth")
bearer = HTTPBearer()

ADMIN_TOKEN         = os.environ["ADMIN_TOKEN"]
JWT_SECRET          = os.environ["JWT_SECRET"]
JWT_EXPIRE          = int(os.environ.get("JWT_EXPIRE_HOURS", 8))
REFRESH_EXPIRE_DAYS = int(os.environ.get("REFRESH_EXPIRE_DAYS", 30))

# bcrypt verarbeitet maximal 72 Bytes; bcrypt>=5 wirft bei längeren Passwörtern einen Fehler.
_BCRYPT_MAX = 72

# Dummy-Hash, damit ein Login mit unbekanntem Usernamen gleich lange dauert wie mit bekanntem.
_DUMMY_HASH = bc.hashpw(b"dummy", bc.gensalt())


class CreateUserBody(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)


class LoginBody(BaseModel):
    username: str
    password: str
    remember_me: bool = False


def _pw(password: str) -> bytes:
    return password.encode()[:_BCRYPT_MAX]


def _hash_refresh(raw: str) -> str:
    # Refresh-Tokens sind 64 Byte Zufall – ein schneller SHA-256 reicht und erlaubt
    # eine direkte Index-Suche statt bcrypt-Vergleich gegen jeden Datensatz.
    return hashlib.sha256(raw.encode()).hexdigest()


def _access_token(user_id) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE)
    return jwt.encode({"sub": str(user_id), "exp": exp}, JWT_SECRET, algorithm="HS256")


async def _find_refresh_token(db: AsyncSession, raw: str) -> RefreshToken | None:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == _hash_refresh(raw),
            RefreshToken.revoked_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


@router.post("/create_user", status_code=201)
async def create_user(
    body: CreateUserBody,
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    if not secrets.compare_digest(creds.credentials, ADMIN_TOKEN):
        raise HTTPException(401, "Ungültiger Admin-Token")
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(409, "Username bereits vergeben")
    user = User(username=body.username, password_hash=bc.hashpw(_pw(body.password), bc.gensalt()).decode())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": str(user.id), "username": user.username}


@router.post("/login")
async def login(body: LoginBody, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.username == body.username, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    stored = user.password_hash.encode() if user else _DUMMY_HASH
    if not bc.checkpw(_pw(body.password), stored) or not user:
        raise HTTPException(401, "Falsche Credentials")

    if body.remember_me:
        raw        = secrets.token_urlsafe(64)
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRE_DAYS)
        db.add(RefreshToken(user_id=user.id, token_hash=_hash_refresh(raw), expires_at=expires_at))
        await db.commit()
        response.set_cookie(
            key="refresh_token",
            value=raw,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/api/auth",
            max_age=REFRESH_EXPIRE_DAYS * 86400,
        )

    return {"access_token": _access_token(user.id), "token_type": "bearer"}


@router.post("/refresh")
async def refresh(
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    if not refresh_token:
        raise HTTPException(401, "Kein Refresh-Token")
    rt = await _find_refresh_token(db, refresh_token)
    if not rt or not rt.is_valid:
        raise HTTPException(401, "Ungültiger oder abgelaufener Refresh-Token")
    user = await db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Benutzer deaktiviert")
    return {"access_token": _access_token(rt.user_id), "token_type": "bearer"}


@router.post("/logout")
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    if refresh_token:
        rt = await _find_refresh_token(db, refresh_token)
        if rt:
            rt.revoked_at = datetime.now(timezone.utc)
            await db.commit()
    response.delete_cookie("refresh_token", path="/api/auth")
    # Cookies aus älteren Versionen wurden ohne path gesetzt
    response.delete_cookie("refresh_token")
    return {}


def require_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        return jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Ungültiger oder abgelaufener Token")
