from contextlib import contextmanager

from .gather import gather as gather
from .invocation import priority as priority
from .pause import pause as pause
from .queueio import QueueIO as RealQueueIO
from .registry import routine as routine


@contextmanager
def activate():
    with RealQueueIO().activate():
        yield
