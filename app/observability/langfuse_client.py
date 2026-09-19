from langfuse import Langfuse

from app.core.config import settings


def create_langfuse_client() -> Langfuse | None:
    if not settings.langfuse_enabled:
        return None

    if (
        settings.langfuse_public_key is None
        or settings.langfuse_secret_key is None
    ):
        raise RuntimeError(
            "Langfuse is enabled, but its API keys are missing."
        )

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
    )