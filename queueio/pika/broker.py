from threading import Lock

from pika import URLParameters
from pika.connection import Parameters
from pika.spec import BasicProperties

from queueio.broker import Broker
from queueio.queuespec import QueueSpec

from .receiver import PikaReceiver
from .threadsafe import ThreadsafeConnection


class PikaBroker(Broker):
    """A broker enables producing and consuming messages on a queue."""

    @classmethod
    def from_uri(cls, uri: str, /):
        """Create a broker instance from a URI."""
        return cls(URLParameters(uri))

    def __init__(self, connection_params: Parameters):
        self.__connection = ThreadsafeConnection(connection_params)
        self.__channel = self.__connection.channel()
        self.__shutdown_lock = Lock()
        self.__shutdown = False
        self.__receivers = set[PikaReceiver]()

    def enqueue(self, body: bytes, /, *, queue: str, priority: int):
        self.__channel.publish(
            exchange="",
            routing_key=queue,
            body=body,
            properties=BasicProperties(priority=priority),
        )

    def create(self, *, queue: str):
        channel = self.__connection.channel()
        channel.queue_declare(
            queue=queue, durable=True, arguments={"x-max-priority": 9}
        )
        channel.close()

    def delete(self, *, queue: str):
        channel = self.__connection.channel()
        channel.delete(queue=queue)
        channel.close()

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
            self.__connection.close()

    def __del__(self):
        self.shutdown()
