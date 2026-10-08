from functools import lru_cache
from typing import Literal

from pydantic import Field
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
    langfuse_enabled: bool = True
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

    kafka_message_search_index_group_id: str = (
        "discord-message-search-index-v1"
    )

    # ---conversation-assistance setting---
    ollama_conversational_assistance_model_name: str = "qwen3:4b"
    ollama_conversational_assistance_tool_model_name: str = "qwen3:1.7b"
    ollama_text_embedding_model_name: str = "nomic-embed-text"
    conversational_assistance_context_message_limit: int = 30
    conversational_assistance_playbook_limit: int = 3
    conversational_assistance_retrieval_top_k: int = 3
    # Maximum number of historical messages retained after RRF fusion.
    conversational_assistance_fusion_top_k: int = Field(
        default=3,
        ge=1,
    )
    # Controls how strongly RRF favors higher-ranked candidates.
    conversational_assistance_rrf_rank_constant: int = Field(
        default=60,
        ge=1,
    )
    # Maximum time the API waits for Cassandra to catch up to the
    # client-provided context cursor before returning 503.
    conversational_assistance_context_wait_timeout_seconds: float =  1.0

    # ---conversation summary settings---
    ollama_conversation_summary_model_name: str = "qwen3:4b"
    conversation_summary_window_size: int = 5
    kafka_conversation_summary_group_id: str = "discord-conversation-summary-v1"
    # Allow slower local LLM calls and small historical backfills.
    kafka_conversation_summary_max_poll_interval_ms: int = 1_800_000

    # ---Elasticsearch settings---
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_message_index_name: str = "discord-messages-v1"
    elasticsearch_request_timeout_seconds: float = 10.0
    kafka_message_keyword_index_group_id: str = "discord-message-keyword-index-v1"


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()