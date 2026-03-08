"""WARNING: This module is a work in progress.

The PsycopgJournal implementation has not been extensively reviewed. It passes
the base test suite but may contain bugs or design flaws. You shouldn't use this yet.
"""

from collections.abc import Iterator
from contextlib import suppress
from threading import Lock

import psycopg

from queueio.journal import Journal


class PsycopgJournal(Journal):
    @classmethod
    def from_uri(cls, uri: str, /):
        return cls(uri)

    def __init__(self, uri: str):
        self.__publish_conn = psycopg.connect(uri, autocommit=True)
        self.__subscribe_conn = psycopg.connect(uri, autocommit=True)
        self.__publish_lock = Lock()
        self.__shutdown_lock = Lock()
        self.__shutdown = False

        # Ensure schema exists
        self.__publish_conn.execute("""
            CREATE TABLE IF NOT EXISTS queueio_journal (
                id BIGSERIAL PRIMARY KEY,
                body BYTEA NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        # LISTEN before SELECT to avoid race condition:
        # any NOTIFY after LISTEN will be buffered, and the subsequent
        # SELECT establishes our starting position.
        self.__subscribe_conn.execute("LISTEN queueio_journal")
        row = self.__subscribe_conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM queueio_journal"
        ).fetchone()
        assert row is not None
        self.__last_id: int = row[0]

    def publish(self, message: bytes):
        with self.__publish_lock, self.__publish_conn.transaction():
            self.__publish_conn.execute(
                t"INSERT INTO queueio_journal (body) VALUES ({message})"
            )
            self.__publish_conn.execute("NOTIFY queueio_journal")

    def subscribe(self) -> Iterator[bytes]:
        try:
            while not self.__shutdown:
                rows = self.__subscribe_conn.execute(
                    t"""
                    SELECT id, body FROM queueio_journal
                    WHERE id > {self.__last_id}
                    ORDER BY id
                    """
                ).fetchall()

                for row in rows:
                    self.__last_id = row[0]
                    yield row[1]

                if not rows and not self.__shutdown:
                    # Wait for a notification to wake us up
                    for _ in self.__subscribe_conn.notifies(timeout=1.0):
                        break  # Got one, go back to query loop
        finally:
            with suppress(Exception):
                self.__subscribe_conn.execute("UNLISTEN queueio_journal")
            with suppress(Exception):
                self.__subscribe_conn.close()

    def shutdown(self):
        with self.__shutdown_lock:
            if self.__shutdown:
                return
            self.__shutdown = True

            # Wake up the subscriber by sending a notification
            with suppress(Exception):
                self.__publish_conn.execute("NOTIFY queueio_journal")

            with suppress(Exception):
                self.__publish_conn.close()
