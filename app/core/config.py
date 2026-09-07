from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Discord API"
    database_url: str
    sql_echo: bool = False

    cassandra_contact_points: str = "127.0.0.1"
    cassandra_port: int = 9042
    cassandra_keyspace: str = "discord_messages"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()