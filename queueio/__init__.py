from contextlib import contextmanager

from .gather import gather as gather
from .pause import pause as pause
from .queueio import QueueIO as QueueIO
from .queueio import priority as priority
from .queuevar import QueueVar as QueueVar
from .registry import routine as routine


@contextmanager
def activate():
    with QueueIO.default() as queueio, queueio.activate():
        yield
