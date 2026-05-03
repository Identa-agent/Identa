# packages/identa-sdk/identa/sdk/registry.py
import contextvars
from dataclasses import dataclass
from typing import Any, Callable, Type, TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from identa.sdk.adapters.base import BaseAdapter
    from identa.core.ports.storage import StoragePort
    from identa.core.ports.exporter import ExporterPort

class UnsupportedFrameworkError(TypeError):
    """Raised when no adapter matches the supplied agent object."""

@dataclass
class AdapterEntry:
    matcher: Callable[[Any], bool]
    adapter_cls: Type['BaseAdapter']
    name: str

class AgentRegistry:
    _entries: list[AdapterEntry] = []

    @classmethod
    def register(cls, matcher: Callable[[Any], bool], adapter_cls: Type['BaseAdapter'], name: str) -> None:
        cls._entries.append(AdapterEntry(matcher, adapter_cls, name))

    @classmethod
    def detect(cls, agent: Any) -> 'BaseAdapter':
        for entry in cls._entries:
            try:
                if entry.matcher(agent):
                    return entry.adapter_cls()
            except Exception:
                continue
        supported = ", ".join(e.name for e in cls._entries) or "<none>"
        raise UnsupportedFrameworkError(
            f"No Identa adapter matches {type(agent).__module__}.{type(agent).__qualname__}. "
            f"Supported frameworks: {supported}."
        )

class Registry:
    """
    Composition Root / DI Container for Identa SDK.
    Manages the lifecycle of core ports and adapters.
    """
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._handlers: Dict[Type, Any] = {}

    def register_service(self, interface: Type, implementation: Any):
        self._services[interface] = implementation

    def get_service(self, interface: Type) -> Any:
        if interface not in self._services:
            raise ValueError(f"Service {interface} not registered in Registry")
        return self._services[interface]

    def register_handler(self, command_type: Type, handler_instance: Any):
        self._handlers[command_type] = handler_instance

    def get_handler(self, command_type: Type) -> Any:
        if command_type not in self._handlers:
            raise ValueError(f"No handler registered for command type {command_type}")
        return self._handlers[command_type]

# ContextVar for thread-safe/async-safe global state
_registry_var: contextvars.ContextVar[Optional[Registry]] = contextvars.ContextVar(
    'identa_registry', default=None
)

def get_registry() -> Registry:
    registry = _registry_var.get()
    if registry is None:
        registry = Registry()
        _registry_var.set(registry)
    return registry
