from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
