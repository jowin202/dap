import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(download.router)

# Compiled Angular frontend, copied into this directory at image build time.
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.join(os.path.dirname(__file__), "static"))


@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
async def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404)
    candidate = os.path.join(STATIC_DIR, full_path)
    if full_path and os.path.isfile(candidate):
        return FileResponse(candidate)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
