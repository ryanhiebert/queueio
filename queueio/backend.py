from abc import ABC
from abc import abstractmethod
from contextlib import AbstractContextManager

from .broker import Broker
from .journal import Journal


class Backend(ABC):
    """A backend provides context-managed access to a broker and journal."""

    @abstractmethod
    def broker(self) -> AbstractContextManager[Broker]:
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def journal(self) -> AbstractContextManager[Journal]:
        raise NotImplementedError("Subclasses must implement this method.")
