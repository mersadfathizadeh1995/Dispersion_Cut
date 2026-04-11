"""Settings widget for canvas export plot types."""
from __future__ import annotations

from ...qt_compat import QtWidgets

QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QCheckBox = QtWidgets.QCheckBox

from .base import BasePlotSettingsWidget
from ...models import ReportStudioSettings


class CanvasSettings(BasePlotSettingsWidget):
    """Settings for canvas_frequency, canvas_wavelength, canvas_dual.

    Spectrum colormap/alpha/colorbar are now in the shared Spectrum tab.
    This widget only controls canvas-specific toggles.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        group = QGroupBox("Canvas Options")
        form = QFormLayout(group)

        self._include_spectrum = QCheckBox("Include visible spectra")
        self._include_spectrum.setChecked(True)
        self._include_spectrum.toggled.connect(self.changed)
        form.addRow(self._include_spectrum)

        layout.addWidget(group)
        layout.addStretch()

    def write_to(self, settings: ReportStudioSettings) -> None:
        pass

    def read_from(self, settings: ReportStudioSettings) -> None:
        pass
