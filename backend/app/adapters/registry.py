from collections.abc import Iterable

from ..config import Settings
from .bseu import BseuMonitoringAdapter
from .contract import MonitoringAdapter


class MonitoringAdapterRegistryError(LookupError):
    """Base error for deterministic monitoring-adapter resolution."""


class DuplicateMonitoringAdapterKeyError(MonitoringAdapterRegistryError):
    def __init__(self, key: str):
        super().__init__(f"Monitoring adapter key is registered more than once: {key}")
        self.key = key


class UnknownMonitoringAdapterError(MonitoringAdapterRegistryError):
    def __init__(self, key: str):
        super().__init__(f"Unknown monitoring adapter key: {key}")
        self.key = key


class MonitoringAdapterRegistry:
    def __init__(self, adapters: Iterable[MonitoringAdapter]):
        registered: dict[str, MonitoringAdapter] = {}
        for adapter in adapters:
            if adapter.key in registered:
                raise DuplicateMonitoringAdapterKeyError(adapter.key)
            registered[adapter.key] = adapter
        self._adapters = registered

    def get(self, key: str) -> MonitoringAdapter:
        try:
            return self._adapters[key]
        except KeyError as exc:
            raise UnknownMonitoringAdapterError(key) from exc

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


def build_bseu_monitoring_registry(settings: Settings) -> MonitoringAdapterRegistry:
    return MonitoringAdapterRegistry((BseuMonitoringAdapter(settings),))
