import os
import glob
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.upload import Upload
from models.refresh_token import RefreshToken
from utils.db import AsyncSessionLocal

FILES_DIR = os.environ.get("FILES_DIR", "/data/files")


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
        path = f"{FILES_DIR}/{upload.token}.enc"
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


async def _cleanup_refresh_tokens(db: AsyncSession):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.expires_at <= now)
    )
    for rt in result.scalars():
        await db.delete(rt)
    await db.commit()


async def _cleanup_orphans(db: AsyncSession):
    tokens_on_disk = {
        os.path.basename(p).replace(".enc", "")
        for p in glob.glob(f"{FILES_DIR}/*.enc")
    }
    result = await db.execute(select(Upload.token))
    tokens_in_db = {str(row[0]) for row in result.all()}

    for orphan in tokens_on_disk - tokens_in_db:
        try:
            os.remove(f"{FILES_DIR}/{orphan}.enc")
        except FileNotFoundError:
            pass
