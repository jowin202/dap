import uuid
import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Depends

from utils.url import base_url
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


@router.post("/upload")
async def upload_file(
    request: Request,
    db=Depends(get_db),
    user=Depends(require_user),
):
    token      = uuid.uuid4()
    filename   = request.headers.get("x-filename", "file.bin")
    expires_in = request.headers.get("x-expires-in", "24h")
    delta      = EXPIRY_MAP.get(expires_in, timedelta(hours=24))
    expires_at = datetime.now(timezone.utc) + delta if delta is not None else None

    os.makedirs(FILES_DIR, exist_ok=True)
    path = f"{FILES_DIR}/{token}.enc"
    size = 0
    with open(path, "wb") as f:
        async for chunk in request.stream():
            f.write(chunk)
            size += len(chunk)

    upload = Upload(
        token=token,
        filename=filename,
        size_bytes=size,
        expires_at=expires_at,
    )
    db.add(upload)
    await db.commit()

    base = base_url(request)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "")).split(":")[0]
    is_local = host in ("localhost", "127.0.0.1", "::1")
    curl_flags = "-sfkL" if is_local else "-sfL"
    irm_flags  = " -SkipCertificateCheck" if is_local else ""
    return {
        "token":        str(token),
        "expires_at":   expires_at.isoformat() if expires_at else None,
        "download_url": f"{base}/download/{token}",
        "ps_cmd":       f'powershell -Command "irm{irm_flags} {base}/psdec/{token}/ | iex"',
        "sh_cmd":       f"curl {curl_flags} {base}/shdec/{token}/ | sh",
    }
