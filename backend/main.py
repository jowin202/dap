import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from routes import upload, download, auth
from jobs.cleanup import cleanup_expired

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(cleanup_expired, "interval", minutes=15, id="cleanup")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan, title="Encrypted File Transfer")

app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(download.router)

@app.get("/api/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


# Compiled Angular frontend, copied into this directory at image build time.
STATIC_DIR = os.path.realpath(
    os.environ.get("STATIC_DIR", os.path.join(os.path.dirname(__file__), "static"))
)


@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
async def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404)
    candidate = os.path.realpath(os.path.join(STATIC_DIR, full_path))
    # Nur Dateien innerhalb von STATIC_DIR ausliefern (Schutz gegen "../"-Pfade)
    if full_path and candidate.startswith(STATIC_DIR + os.sep) and os.path.isfile(candidate):
        return FileResponse(candidate)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
