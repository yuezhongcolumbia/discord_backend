from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from app.api.exception_handlers import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.cassandra import cassandra_client
from app.messaging.kafka import create_kafka_producer
from app.messaging.kafka_message_publisher import KafkaMessagePublisher


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await run_in_threadpool(cassandra_client.connect)
    try:
        kafka_producer = create_kafka_producer()

        message_publisher = KafkaMessagePublisher(
            producer=kafka_producer,
            topic=settings.kafka_message_accepted_topic,
            publish_wait_timeout_seconds=settings.kafka_publish_wait_timeout_seconds,
        )

        app.state.message_publisher = message_publisher

        try:
            yield
        finally:
            await run_in_threadpool(
                kafka_producer.flush,
                10,
            )
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