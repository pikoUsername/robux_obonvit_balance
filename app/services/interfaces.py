import abc
from typing import Union, Type, Callable, Dict, Any, Optional, List


class IListener(abc.ABC):
    @abc.abstractmethod
    def setup(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def __call__(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def close(self, *args, **kwargs):
        pass


ListenerType = IListener


class Notifier(abc.ABC):
    @abc.abstractmethod
    def run(self):
        pass


class BasicDBConnector(abc.ABC):
    @abc.abstractmethod
    async def execute(self, sql, *args, **kwargs) -> None:
        pass

    @abc.abstractmethod
    async def fetch(self, sql, *args, **kwargs) -> Dict[str, Any] | None:
        pass

    @abc.abstractmethod
    async def fetchmany(self, sql, *args, **kwargs) -> List[Dict[str, Any]]:
        pass

    @abc.abstractmethod
    async def close(self):
        pass


class BasicConsumer(abc.ABC):
    @abc.abstractmethod
    def connect(self):
        pass

    @abc.abstractmethod
    def run(self):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

