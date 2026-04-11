"""Settings widget for canvas export plot types."""
from __future__ import annotations

from ...qt_compat import QtWidgets

QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox

from .base import BasePlotSettingsWidget
from ...models import ReportStudioSettings


class CanvasSettings(BasePlotSettingsWidget):
    """Settings for canvas_frequency, canvas_wavelength, canvas_dual."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        spec_group = QGroupBox("Spectrum Options")
        spec_form = QFormLayout(spec_group)

        self._include_spectrum = QCheckBox("Include visible spectra")
        self._include_spectrum.setChecked(True)
        self._include_spectrum.toggled.connect(self.changed)
        spec_form.addRow(self._include_spectrum)

        self._colormap = QComboBox()
        self._colormap.addItems([
            "viridis", "plasma", "inferno", "magma", "cividis",
            "jet", "hot", "coolwarm", "RdYlBu",
        ])
        self._colormap.setCurrentText("viridis")
        self._colormap.currentTextChanged.connect(lambda: self.changed.emit())
        spec_form.addRow("Colormap:", self._colormap)

        self._spectrum_alpha = QDoubleSpinBox()
        self._spectrum_alpha.setRange(0.0, 1.0)
        self._spectrum_alpha.setSingleStep(0.05)
        self._spectrum_alpha.setDecimals(2)
        self._spectrum_alpha.setValue(0.8)
        self._spectrum_alpha.valueChanged.connect(self.changed)
        spec_form.addRow("Alpha:", self._spectrum_alpha)

        self._show_colorbar = QCheckBox("Show colorbar")
        self._show_colorbar.setChecked(True)
        self._show_colorbar.toggled.connect(self.changed)
        spec_form.addRow(self._show_colorbar)

        self._colorbar_orient = QComboBox()
        self._colorbar_orient.addItems(["vertical", "horizontal", "none"])
        self._colorbar_orient.setCurrentText("vertical")
        self._colorbar_orient.currentTextChanged.connect(lambda: self.changed.emit())
        spec_form.addRow("Colorbar:", self._colorbar_orient)

        layout.addWidget(spec_group)
        layout.addStretch()

    def write_to(self, settings: ReportStudioSettings) -> None:
        settings.spectrum.colormap = self._colormap.currentText()
        settings.spectrum.alpha = self._spectrum_alpha.value()
        settings.spectrum.show_colorbar = self._show_colorbar.isChecked()
        settings.spectrum.colorbar_orientation = self._colorbar_orient.currentText()

    def read_from(self, settings: ReportStudioSettings) -> None:
        for w in (self._colormap, self._spectrum_alpha,
                  self._show_colorbar, self._colorbar_orient):
            w.blockSignals(True)
        self._colormap.setCurrentText(settings.spectrum.colormap)
        self._spectrum_alpha.setValue(settings.spectrum.alpha)
        self._show_colorbar.setChecked(settings.spectrum.show_colorbar)
        self._colorbar_orient.setCurrentText(settings.spectrum.colorbar_orientation)
        for w in (self._colormap, self._spectrum_alpha,
                  self._show_colorbar, self._colorbar_orient):
            w.blockSignals(False)
