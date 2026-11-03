import socket

import pytest
from pika import ConnectionParameters
from pika.exceptions import AMQPConnectionError

from .threadsafe import ThreadsafeConnection


def test_failed_connection_stops_ioloop_thread():
    # Find a local port with nothing listening on it.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    # The autouse check_thread_cleanup fixture fails if the ioloop thread leaks.
    with pytest.raises(AMQPConnectionError):
        ThreadsafeConnection(
            ConnectionParameters(host="127.0.0.1", port=port, connection_attempts=1)
        )
