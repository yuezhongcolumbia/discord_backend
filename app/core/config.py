from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Discord API"
    database_url: str
    sql_echo: bool = False

    cassandra_contact_points: str = "127.0.0.1"
    cassandra_port: int = 9042
    cassandra_keyspace: str = "discord_messages"

    ollama_message_semantic_model_name: str = "qwen3:1.7b"
    message_semantic_prompt_version: str = "sentiment-v1"
    langfuse_enabled: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "https://us.cloud.langfuse.com"

    # ---kafka setting---
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_message_accepted_topic: str = "discord.message.accepted.v1"

    # Maximum time librdkafka may spend delivering a produced message.
    kafka_delivery_timeout_ms: int = 5000

    # Maximum time the application waits for the delivery callback.
    kafka_publish_wait_timeout_seconds: float = 6.0

    # Dedicated consumer group for Cassandra message persistence.
    kafka_message_persistence_group_id: str = (
    "discord-message-persistence-consumer-v1"
    )

    # Offset reset policy used only when this consumer group has no committed offset.
    kafka_consumer_auto_offset_reset: Literal["earliest", "latest"] = "earliest"

    # Maximum time a consumer poll waits for records before returning.
    kafka_consumer_poll_timeout_seconds: float = 1.0

    # Initial delay before retrying a failed Cassandra persistence attempt.
    kafka_consumer_retry_initial_backoff_seconds: float = 2.0

    # Upper bound for exponential retry delays.
    kafka_consumer_retry_max_backoff_seconds: float = 30.0

    # Maximum Cassandra persistence attempts before the consumer exits.
    kafka_consumer_retry_max_attempts: int = 7

    kafka_message_persisted_topic: str = (
        "discord.message.persisted.v1"
    )

    kafka_message_semantic_group_id: str = (
        "discord-message-semantic-v1"
    )
    kafka_message_semantic_batch_size: int = 50

    kafka_message_semantic_flush_interval_seconds: float = 60.0

    # ---conversation-assistance setting---
    conversational_assistance_context_message_limit: int = 30
    conversational_assistance_playbook_limit: int = 3
    # Maximum time the API waits for Cassandra to catch up to the
    # client-provided context cursor before returning 503.
    conversational_assistance_context_wait_timeout_seconds: float = (
        1.0
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()