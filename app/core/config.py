from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Discord API"
    database_url: str
    sql_echo: bool = False

    cassandra_contact_points: str = "127.0.0.1"
    cassandra_port: int = 9042
    cassandra_keyspace: str = "discord_messages"

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_message_accepted_topic: str = "discord.message.accepted.v1"

    # Maximum time librdkafka may spend delivering a produced message.
    kafka_delivery_timeout_ms: int = 5000

    # Maximum time the application waits for the delivery callback.
    kafka_publish_wait_timeout_seconds: float = 6.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()