from collections.abc import Iterator
from threading import Lock
from typing import cast

from pika import URLParameters
from pika.connection import Parameters

from queueio.journal import Journal

from .threadsafe import ThreadsafeConnection


class PikaJournal(Journal):
    @classmethod
    def from_uri(cls, uri: str, /):
        """Create a journal instance from a URI."""
        return cls(URLParameters(uri))

    def __init__(self, connection_params: Parameters):
        self.__connection = ThreadsafeConnection(connection_params)
        self.__subscribe_channel = self.__connection.channel()
        self.__publish_channel = self.__connection.channel()

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
            self.__connection.close()
