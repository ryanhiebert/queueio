from __future__ import annotations

from contextlib import contextmanager
from contextvars import Context
from contextvars import ContextVar
from contextvars import copy_context
from typing import Any

_registry: dict[ContextVar, QueueVar] = {}


class QueueVar[T]:
    def __init__(self, name: str, *, default: T):
        self.__default = default
        self.__var: ContextVar[T] = ContextVar(name, default=default)
        _registry[self.__var] = self

    @property
    def name(self) -> str:
        return self.__var.name

    def get(self) -> T:
        return self.__var.get()

    @contextmanager
    def __call__(self, value: T, /):
        token = self.__var.set(value)
        try:
            yield
        finally:
            self.__var.reset(token)


class QueueContext:
    def __init__(self, data: dict[str, Any]):
        self.__data = data

    def __getitem__[T](self, var: QueueVar[T]) -> T:
        return self.__data[var.name]

    def get[T, Default](self, var: QueueVar[T], default: Default = None) -> T | Default:
        return self.__data.get(var.name, default)

    def __contains__(self, var: object) -> bool:
        if not isinstance(var, QueueVar):
            return False
        return var.name in self.__data

    def load(self, ctx: Context) -> None:
        def initialize():
            for contextvar, queuevar in _registry.items():
                if queuevar.name in self.__data:
                    contextvar.set(self.__data[queuevar.name])

        ctx.run(initialize)

    def serialize(self) -> dict[str, Any]:
        return dict(self.__data)

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> QueueContext:
        return cls(data)

    @classmethod
    def capture(cls) -> QueueContext:
        data: dict[str, Any] = {}
        ctx = copy_context()
        for contextvar in ctx:
            if contextvar in _registry:
                data[_registry[contextvar].name] = ctx[contextvar]
        return cls(data)
