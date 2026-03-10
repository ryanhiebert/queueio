from collections.abc import Generator
from collections.abc import Iterable
from contextlib import contextmanager
from contextlib import suppress
from threading import Lock

from pika.spec import BasicProperties

from queueio.broker import Broker
from queueio.queuespec import QueueSpec

from .receiver import PikaReceiver
from .threadsafe import ThreadsafeConnection


class PikaBroker(Broker):
    """A broker enables producing and consuming messages on a queue."""

    @classmethod
    @contextmanager
    def connect(cls, connection: ThreadsafeConnection) -> Generator[PikaBroker]:
        broker = cls(connection)
        try:
            yield broker
        finally:
            broker.shutdown()

    def __init__(self, connection: ThreadsafeConnection):
        self.__connection = connection
        self.__channel = self.__connection.channel()
        self.__shutdown_lock = Lock()
        self.__shutdown = False
        self.__receivers = set[PikaReceiver]()

    def sync(self, queues: Iterable[str], *, recreate: bool = False):
        channel = self.__connection.channel()
        try:
            for queue in queues:
                if recreate:
                    with suppress(Exception):
                        channel.delete(queue=queue)
                channel.queue_declare(
                    queue=queue, durable=True, arguments={"x-max-priority": 9}
                )
        finally:
            channel.close()

    def enqueue(self, body: bytes, /, *, queue: str, priority: int):
        self.__channel.publish(
            exchange="",
            routing_key=queue,
            body=body,
            properties=BasicProperties(priority=priority),
        )

    def purge(self, *, queue: str):
        self.__channel.purge(queue=queue)

    def receive(self, queuespec: QueueSpec, /) -> PikaReceiver:
        receiver = PikaReceiver(self.__connection, queuespec)
        self.__receivers.add(receiver)
        return receiver

    def shutdown(self):
        """Signal the final shutdown of the broker."""
        with self.__shutdown_lock:
            if self.__shutdown:
                return
            self.__shutdown = True
            for receiver in self.__receivers:
                receiver.shutdown()
            self.__channel.close()
