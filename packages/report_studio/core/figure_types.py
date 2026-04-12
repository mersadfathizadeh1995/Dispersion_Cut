"""
Figure type registry — extensible plugin system for different plot types.

Each figure type (source offset, near-field, uncertainty, ...) registers
itself as a ``FigureTypePlugin`` so the UI can discover available types
and their data loaders / settings without hard-coding.
"""

from __future__ import annotations

from typing import (
    Any, Dict, List, Optional, Protocol, Sequence, runtime_checkable,
)


@runtime_checkable
class FigureTypePlugin(Protocol):
    """Protocol that every figure-type plugin must implement."""

    @property
    def type_id(self) -> str:
        """Unique machine-readable identifier (e.g. ``'source_offset'``)."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable label shown in the UI dropdown."""
        ...

    @property
    def accepted_subplot_types(self) -> Sequence[str]:
        """Subplot types this plugin can render into."""
        ...

    def load_data(self, **kwargs) -> Dict[str, Any]:
        """Load data from user-specified sources.

        Returns a dict with at least ``'curves'`` and ``'spectra'`` lists.
        Concrete keys depend on the plugin.
        """
        ...

    def settings_fields(self) -> List[Dict[str, Any]]:
        """Return a descriptor list for the plugin's configurable settings.

        Each dict: ``{'key': str, 'label': str, 'type': str, 'default': ...}``
        """
        ...


class FigureTypeRegistry:
    """Central registry that plugins register into at import time."""

    def __init__(self):
        self._plugins: Dict[str, FigureTypePlugin] = {}

    def register(self, plugin: FigureTypePlugin) -> None:
        self._plugins[plugin.type_id] = plugin

    def get(self, type_id: str) -> Optional[FigureTypePlugin]:
        return self._plugins.get(type_id)

    def all_types(self) -> List[FigureTypePlugin]:
        return list(self._plugins.values())

    def type_ids(self) -> List[str]:
        return list(self._plugins.keys())

    def display_names(self) -> Dict[str, str]:
        """Return ``{type_id: display_name}`` mapping."""
        return {p.type_id: p.display_name for p in self._plugins.values()}


# Global singleton — plugins register at import time
registry = FigureTypeRegistry()
