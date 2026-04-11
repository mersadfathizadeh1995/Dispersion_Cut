"""Settings widget for wavelength-domain plot types."""
from __future__ import annotations

from ...qt_compat import QtWidgets

QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QSpinBox = QtWidgets.QSpinBox

from .base import BasePlotSettingsWidget
from ...models import ReportStudioSettings


class WavelengthSettings(BasePlotSettingsWidget):
    """Settings for aggregated_wavelength, per_offset_wavelength, dual_domain."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        group = QGroupBox("Wavelength Plot Options")
        form = QFormLayout(group)

        self._max_offsets = QSpinBox()
        self._max_offsets.setRange(1, 100)
        self._max_offsets.setValue(10)
        self._max_offsets.valueChanged.connect(self.changed)
        form.addRow("Max offsets:", self._max_offsets)

        layout.addWidget(group)
        layout.addStretch()

    def write_to(self, settings: ReportStudioSettings) -> None:
        settings.max_offsets = self._max_offsets.value()

    def read_from(self, settings: ReportStudioSettings) -> None:
        self._max_offsets.blockSignals(True)
        self._max_offsets.setValue(settings.max_offsets)
        self._max_offsets.blockSignals(False)
