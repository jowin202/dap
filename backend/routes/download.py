import os
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, PlainTextResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.url import base_url
from utils.db import get_db
from models.upload import Upload

router = APIRouter()

_template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
jinja = Environment(loader=FileSystemLoader(os.path.abspath(_template_dir)))

FILES_DIR = os.environ.get("FILES_DIR", "/data/files")

BLOCK_SIZE = 8 * 1024 * 1024  # 8 MB


async def get_valid_upload(token: str, db: AsyncSession) -> Upload:
    result = await db.execute(
        select(Upload).where(
            Upload.token == token,
            Upload.deleted_at.is_(None),
        )
    )
    upload = result.scalar_one_or_none()
    if not upload:
        raise HTTPException(404, "Nicht gefunden")
    if not upload.is_valid:
        raise HTTPException(410, "Abgelaufen")
    return upload


@router.get("/download/{token}")
async def download_file(token: str, db: AsyncSession = Depends(get_db)):
    upload = await get_valid_upload(token, db)
    path   = f"{FILES_DIR}/{upload.token}.enc"

    if not os.path.exists(path):
        raise HTTPException(404, "Datei nicht gefunden")

    def iterfile():
        with open(path, "rb") as f:
            while chunk := f.read(BLOCK_SIZE):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type="application/octet-stream",
        headers={
            "Content-Length": str(upload.size_bytes),
            "Content-Disposition": f'attachment; filename="{upload.filename}"',
        },
    )


@router.get("/api/info/{token}")
async def file_info(token: str, db: AsyncSession = Depends(get_db)):
    upload = await get_valid_upload(token, db)
    return {
        "filename":   upload.filename,
        "size_bytes": upload.size_bytes,
        "expires_at": upload.expires_at.isoformat() if upload.expires_at else None,
    }


@router.get("/psdec/{token}/")
async def powershell_script(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    await get_valid_upload(token, db)
    url  = f"{base_url(request)}/download/{token}"
    tmpl = jinja.get_template("decrypt.ps1.j2")
    return PlainTextResponse(tmpl.render(download_url=url), media_type="text/plain")


@router.get("/shdec/{token}/")
async def shell_script(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    await get_valid_upload(token, db)
    url  = f"{base_url(request)}/download/{token}"
    tmpl = jinja.get_template("decrypt.sh.j2")
    return PlainTextResponse(tmpl.render(download_url=url), media_type="text/plain")
