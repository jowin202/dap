import os
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Response, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt as bc
from jose import jwt

from models.user import User
from models.refresh_token import RefreshToken
from utils.db import get_db

router = APIRouter(prefix="/api/auth")
bearer = HTTPBearer()

ADMIN_TOKEN        = os.environ["ADMIN_TOKEN"]
JWT_SECRET         = os.environ["JWT_SECRET"]
JWT_EXPIRE         = int(os.environ.get("JWT_EXPIRE_HOURS", 8))
REFRESH_EXPIRE_DAYS = int(os.environ.get("REFRESH_EXPIRE_DAYS", 30))


@router.post("/create_user", status_code=201)
async def create_user(
    body: dict,
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    if creds.credentials != ADMIN_TOKEN:
        raise HTTPException(401, "Ungültiger Admin-Token")
    result = await db.execute(select(User).where(User.username == body["username"]))
    if result.scalar_one_or_none():
        raise HTTPException(409, "Username bereits vergeben")
    user = User(username=body["username"], password_hash=bc.hashpw(body["password"].encode(), bc.gensalt()).decode())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": str(user.id), "username": user.username}


@router.post("/login")
async def login(body: dict, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.username == body["username"], User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or not bc.checkpw(body["password"].encode(), user.password_hash.encode()):
        raise HTTPException(401, "Falsche Credentials")

    exp   = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE)
    token = jwt.encode({"sub": str(user.id), "exp": exp}, JWT_SECRET, algorithm="HS256")

    if body.get("remember_me"):
        raw        = secrets.token_urlsafe(64)
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRE_DAYS)
        rt = RefreshToken(user_id=user.id, token_hash=bc.hashpw(raw.encode(), bc.gensalt()).decode(), expires_at=expires_at)
        db.add(rt)
        await db.commit()
        response.set_cookie(
            key="refresh_token",
            value=raw,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=REFRESH_EXPIRE_DAYS * 86400,
        )

    return {"access_token": token, "token_type": "bearer"}


@router.post("/refresh")
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str = Cookie(default=None),
):
    if not refresh_token:
        raise HTTPException(401, "Kein Refresh-Token")
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.revoked_at.is_(None))
    )
    rt = next(
        (r for r in result.scalars() if bc.checkpw(refresh_token.encode(), r.token_hash.encode())), None
    )
    if not rt or not rt.is_valid:
        raise HTTPException(401, "Ungültiger oder abgelaufener Refresh-Token")

    exp   = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE)
    token = jwt.encode({"sub": str(rt.user_id), "exp": exp}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout")
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str = Cookie(default=None),
):
    if refresh_token:
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.revoked_at.is_(None))
        )
        rt = next(
            (r for r in result.scalars() if bc.checkpw(refresh_token.encode(), r.token_hash.encode())), None
        )
        if rt:
            rt.revoked_at = datetime.now(timezone.utc)
            await db.commit()
    response.delete_cookie("refresh_token")
    return {}


def require_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        return jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Ungültiger oder abgelaufener Token")
