import os
import glob
import time
from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.upload import Upload
from models.refresh_token import RefreshToken
from utils.db import AsyncSessionLocal

FILES_DIR = os.environ.get("FILES_DIR", "/data/files")

# Dateien ohne DB-Eintrag erst löschen, wenn sie so lange nicht mehr verändert wurden.
# Ein laufender Upload schreibt laufend (mtime aktuell) und steht erst am Ende in der DB.
ORPHAN_MIN_AGE_SECONDS = 60 * 60


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


async def cleanup_expired():
    async with AsyncSessionLocal() as db:
        await _cleanup_expired(db)
        await _cleanup_refresh_tokens(db)
        await _cleanup_orphans(db)


async def _cleanup_expired(db: AsyncSession):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Upload).where(
            Upload.expires_at <= now,
            Upload.deleted_at.is_(None),
        )
    )
    expired = result.scalars().all()

    for upload in expired:
        upload.deleted_at = now
    await db.commit()

    for upload in expired:
        _remove(f"{FILES_DIR}/{upload.token}.enc")


async def _cleanup_refresh_tokens(db: AsyncSession):
    now = datetime.now(timezone.utc)
    await db.execute(
        delete(RefreshToken).where(
            (RefreshToken.expires_at <= now) | RefreshToken.revoked_at.is_not(None)
        )
    )
    await db.commit()


async def _cleanup_orphans(db: AsyncSession):
    cutoff = time.time() - ORPHAN_MIN_AGE_SECONDS
    tokens_on_disk = {
        os.path.basename(p).removesuffix(".enc")
        for p in glob.glob(f"{FILES_DIR}/*.enc")
        if os.path.getmtime(p) < cutoff
    }
    if not tokens_on_disk:
        return
    result = await db.execute(select(Upload.token).where(Upload.deleted_at.is_(None)))
    tokens_in_db = {str(row[0]) for row in result.all()}

    for orphan in tokens_on_disk - tokens_in_db:
        _remove(f"{FILES_DIR}/{orphan}.enc")
