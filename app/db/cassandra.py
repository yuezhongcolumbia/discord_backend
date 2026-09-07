from cassandra.cluster import Cluster
from cassandra.cluster import Session as CassandraSession

from app.core.config import settings


class CassandraClient:
    def __init__(self) -> None:
        self._cluster: Cluster | None = None
        self._session: CassandraSession | None = None

    def connect(self) -> None:
        self._cluster = Cluster(
            contact_points=settings.cassandra_contact_points.split(","),
            port=settings.cassandra_port,
        )
        self._session = self._cluster.connect(
            settings.cassandra_keyspace,
        )

    def get_session(self) -> CassandraSession:
        if self._session is None:
            raise RuntimeError("Cassandra client is not connected")

        return self._session

    def close(self) -> None:
        if self._session is not None:
            self._session.shutdown()
            self._session = None

        if self._cluster is not None:
            self._cluster.shutdown()
            self._cluster = None


cassandra_client = CassandraClient()