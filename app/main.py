from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from app.api.exception_handlers import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.cassandra import cassandra_client
from app.db.elasticsearch import create_elasticsearch_client
from app.db.redis import create_redis_client
from app.messaging.kafka import create_kafka_producer
from app.messaging.kafka_message_accepted_publisher import (
    KafkaMessageAcceptedPublisher,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await run_in_threadpool(cassandra_client.connect)

    try:
        kafka_producer = create_kafka_producer()

        try:
            elasticsearch_client = create_elasticsearch_client()

            try:
                redis_client = create_redis_client()

                try:
                    app.state.elasticsearch_client = (
                        elasticsearch_client
                    )
                    app.state.redis_client = redis_client

                    app.state.message_publisher = (
                        KafkaMessageAcceptedPublisher(
                            producer=kafka_producer,
                            topic=settings.kafka_message_accepted_topic,
                            publish_wait_timeout_seconds=(
                                settings.kafka_publish_wait_timeout_seconds
                            ),
                        )
                    )

                    yield
                finally:
                    await redis_client.aclose()
            finally:
                await elasticsearch_client.close()
        finally:
            await run_in_threadpool(
                kafka_producer.flush,
                10,
            )
    finally:
        await run_in_threadpool(cassandra_client.close)


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

register_exception_handlers(app)

app.include_router(
    api_router,
    prefix="/api/v1",
)


@app.get("/")
async def root():
    return {"message": "Discord API"}