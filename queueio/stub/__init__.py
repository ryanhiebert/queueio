from collections.abc import Generator
from contextlib import AbstractContextManager
from contextlib import contextmanager

from queueio.backend import Backend

from .broker import StubBroker
from .journal import StubJournal


class StubBackend(Backend):
    @classmethod
    @contextmanager
    def connect(cls) -> Generator[StubBackend]:
        yield cls()

    def broker(self) -> AbstractContextManager[StubBroker]:
        return StubBroker.create()

    def journal(self) -> AbstractContextManager[StubJournal]:
        return StubJournal.create()
