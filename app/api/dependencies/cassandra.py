from functools import lru_cache

from cassandra.cluster import Session as CassandraSession

from app.db.cassandra import cassandra_client
from app.repositories.message_repository import MessageRepository


def get_cassandra_session() -> CassandraSession:
    return cassandra_client.get_session()


@lru_cache
def get_message_repository() -> MessageRepository:
    return MessageRepository(get_cassandra_session())