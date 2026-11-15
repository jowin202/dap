import os
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote

from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from utils.url import base_url, download_commands
from utils.db import get_db
from models.upload import Upload
from routes.auth import require_user

router = APIRouter()

EXPIRY_MAP = {
    "24h":   timedelta(hours=24),
    "7d":    timedelta(days=7),
    "30d":   timedelta(days=30),
    "never": None,
}

FILES_DIR = os.environ.get("FILES_DIR", "/data/files")


@router.post("/api/upload")
async def upload_file(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_user),
):
    token      = uuid.uuid4()
    filename   = os.path.basename(unquote(request.headers.get("x-filename", ""))) or "file.bin"
    expires_in = request.headers.get("x-expires-in", "24h")
    delta      = EXPIRY_MAP.get(expires_in, timedelta(hours=24))
    expires_at = datetime.now(timezone.utc) + delta if delta is not None else None

    os.makedirs(FILES_DIR, exist_ok=True)
    path = f"{FILES_DIR}/{token}.enc"
    size = 0
    try:
        with open(path, "wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
                size += len(chunk)
    except BaseException:
        # Abgebrochener Upload: keine halbe Datei liegen lassen
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        raise

    db.add(Upload(token=token, filename=filename, size_bytes=size, expires_at=expires_at))
    await db.commit()

    return {
        "token":        str(token),
        "expires_at":   expires_at.isoformat() if expires_at else None,
        "download_url": f"{base_url(request)}/download/{token}",
        **download_commands(request, str(token)),
    }
