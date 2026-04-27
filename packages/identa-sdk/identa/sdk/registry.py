# packages/identa-sdk/identa/sdk/registry.py
from dataclasses import dataclass
from typing import Any, Callable, Type
from identa.sdk.adapters.base import BaseAdapter

class UnsupportedFrameworkError(TypeError):
    """Raised when no adapter matches the supplied agent object."""

@dataclass
class AdapterEntry:
    matcher: Callable[[Any], bool]
    adapter_cls: Type[BaseAdapter]
    name: str

class AgentRegistry:
    _entries: list[AdapterEntry] = []

    @classmethod
    def register(cls, matcher: Callable[[Any], bool], adapter_cls: Type[BaseAdapter], name: str) -> None:
        cls._entries.append(AdapterEntry(matcher, adapter_cls, name))

    @classmethod
    def detect(cls, agent: Any) -> BaseAdapter:
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
