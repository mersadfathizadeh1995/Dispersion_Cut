"""Base class for per-plot-type settings widgets."""
from __future__ import annotations

from ...qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget

from ....config import PlotConfig
from ...models import ReportStudioSettings


class BasePlotSettingsWidget(QWidget):
    """Abstract base for plot-type-specific settings panels.

    Subclasses must implement write_to() and read_from() to transfer
    their UI values to/from the studio settings.
    """

    changed = Signal()

    def write_to(self, settings: ReportStudioSettings) -> None:
        """Write widget values into the settings object."""
        raise NotImplementedError

    def read_from(self, settings: ReportStudioSettings) -> None:
        """Populate widgets from the settings object."""
        raise NotImplementedError
