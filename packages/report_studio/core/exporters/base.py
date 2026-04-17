"""
Base exporter — abstract class for modular data export.

Each figure type can register its own exporter; the export panel
discovers them via ``AbstractExporter.can_export(sheet)``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..models import SheetState


class AbstractExporter(ABC):
    """
    Base class for data exporters.

    Subclass and implement ``name``, ``can_export``, ``export``.
    Optionally override ``get_options_widget`` to return a Qt widget
    that appears in the export panel for configuration.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable exporter name."""
        ...

    @abstractmethod
    def can_export(self, sheet: "SheetState") -> bool:
        """Return True if this exporter can export data from *sheet*."""
        ...

    @abstractmethod
    def export(self, sheet: "SheetState", path: str,
               options: Dict[str, Any]) -> str:
        """
        Export data to *path* with *options*.

        Returns a summary message.
        """
        ...

    def get_options_widget(self):
        """Return a QWidget for configuration, or ``None``."""
        return None
