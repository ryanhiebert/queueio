from collections.abc import Generator
from contextlib import AbstractContextManager
from contextlib import contextmanager

from pika import URLParameters

from queueio.backend import Backend

from .broker import PikaBroker
from .journal import PikaJournal
from .threadsafe import ThreadsafeConnection


class PikaBackend(Backend):
    def __init__(self, connection: ThreadsafeConnection):
        self.__connection = connection

    @classmethod
    @contextmanager
    def connect(cls, uri: str, /) -> Generator[PikaBackend]:
        connection = ThreadsafeConnection(URLParameters(uri))
        try:
            yield cls(connection)
        finally:
            connection.close()

    def broker(self) -> AbstractContextManager[PikaBroker]:
        return PikaBroker.connect(self.__connection)

    def journal(self) -> AbstractContextManager[PikaJournal]:
        return PikaJournal.connect(self.__connection)
