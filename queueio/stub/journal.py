import threading
from collections.abc import Generator
from collections.abc import Iterator
from contextlib import contextmanager

from queueio.journal import Journal
from queueio.queue import Queue
from queueio.queue import ShutDown


class StubJournal(Journal):
    """An in-memory journal implementation for testing."""

    @classmethod
    @contextmanager
    def create(cls) -> Generator[StubJournal]:
        journal = cls()
        try:
            yield journal
        finally:
            journal.shutdown()

    def __init__(self):
        self.__queue = Queue[bytes]()
        self.__shutdown_lock = threading.Lock()
        self.__shutdown = False

    def subscribe(self) -> Iterator[bytes]:
        while True:
            try:
                yield self.__queue.get()
            except ShutDown:
                return

    def publish(self, message: bytes):
        self.__queue.put(message)

    def shutdown(self):
        with self.__shutdown_lock:
            if self.__shutdown:
                return
            self.__shutdown = True
            self.__queue.shutdown()
