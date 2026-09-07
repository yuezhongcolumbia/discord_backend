from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from app.api.exception_handlers import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.cassandra import cassandra_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await run_in_threadpool(cassandra_client.connect)

    try:
        yield
    finally:
        await run_in_threadpool(cassandra_client.close)

app = FastAPI(
    title=settings.app_name,
    lifespan = lifespan,
)

register_exception_handlers(app)

app.include_router(
    api_router,
    prefix="/api/v1",
)


@app.get("/")
async def root():
    return {"message": "Discord API"}