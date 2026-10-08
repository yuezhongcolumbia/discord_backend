from elasticsearch import AsyncElasticsearch

from app.core.config import settings


def create_elasticsearch_client() -> AsyncElasticsearch:
    return AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        request_timeout=(
            settings.elasticsearch_request_timeout_seconds
        ),
    )