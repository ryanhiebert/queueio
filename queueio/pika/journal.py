from collections.abc import Generator
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from typing import cast

from queueio.journal import Journal

from .threadsafe import ThreadsafeConnection


class PikaJournal(Journal):
    @classmethod
    @contextmanager
    def connect(cls, connection: ThreadsafeConnection) -> Generator[PikaJournal]:
        journal = cls(connection)
        try:
            yield journal
        finally:
            journal.shutdown()

    def __init__(self, connection: ThreadsafeConnection):
        self.__subscribe_channel = connection.channel()
        self.__publish_channel = connection.channel()

        declare_result = self.__subscribe_channel.queue_declare("", exclusive=True)
        self.__subscribe_queue = cast(str, declare_result.method.queue)

        self.__shutdown_lock = Lock()
        self.__shutdown = False
        self.__subscribe_channel.queue_bind(
            self.__subscribe_queue,
            "amq.topic",
            routing_key="#",
        )

        result = self.__subscribe_channel.consume(self.__subscribe_queue, auto_ack=True)
        self.__subscribe_consumer_tag = cast(str, result.method.consumer_tag)

    def subscribe(self) -> Iterator[bytes]:
        for _, _, body in self.__subscribe_channel.messages():
            yield body

    def publish(self, message: bytes):
        self.__publish_channel.publish(
            exchange="amq.topic",
            routing_key="",
            body=message,
        )

    def shutdown(self):
        with self.__shutdown_lock:
            if self.__shutdown:
                return
            self.__shutdown = True

            self.__subscribe_channel.cancel(self.__subscribe_consumer_tag)
            self.__subscribe_channel.close()
            self.__publish_channel.close()
