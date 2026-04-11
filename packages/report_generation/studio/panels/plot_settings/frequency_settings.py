"""Settings widget for frequency-domain plot types."""
from __future__ import annotations

from ...qt_compat import QtWidgets

QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QSpinBox = QtWidgets.QSpinBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox

from .base import BasePlotSettingsWidget
from ...models import ReportStudioSettings


class FrequencySettings(BasePlotSettingsWidget):
    """Settings for aggregated, per_offset, and uncertainty plots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        group = QGroupBox("Frequency Plot Options")
        form = QFormLayout(group)

        self._max_offsets = QSpinBox()
        self._max_offsets.setRange(1, 100)
        self._max_offsets.setValue(10)
        self._max_offsets.valueChanged.connect(self.changed)
        form.addRow("Max offsets:", self._max_offsets)

        self._uncertainty_alpha = QDoubleSpinBox()
        self._uncertainty_alpha.setRange(0.0, 1.0)
        self._uncertainty_alpha.setSingleStep(0.05)
        self._uncertainty_alpha.setDecimals(2)
        self._uncertainty_alpha.setValue(0.3)
        self._uncertainty_alpha.valueChanged.connect(self.changed)
        form.addRow("Uncertainty fill alpha:", self._uncertainty_alpha)

        nf_group = QGroupBox("Near-Field Marking")
        nf_form = QFormLayout(nf_group)

        self._mark_nf = QCheckBox("Mark near-field")
        self._mark_nf.setChecked(True)
        self._mark_nf.toggled.connect(self.changed)
        nf_form.addRow(self._mark_nf)

        self._nf_style = QComboBox()
        self._nf_style.addItems(["faded", "crossed", "none"])
        self._nf_style.setCurrentText("faded")
        self._nf_style.currentTextChanged.connect(lambda: self.changed.emit())
        nf_form.addRow("NF style:", self._nf_style)

        self._nacd_threshold = QDoubleSpinBox()
        self._nacd_threshold.setRange(0.1, 5.0)
        self._nacd_threshold.setSingleStep(0.1)
        self._nacd_threshold.setDecimals(1)
        self._nacd_threshold.setValue(1.0)
        self._nacd_threshold.valueChanged.connect(self.changed)
        nf_form.addRow("NACD threshold:", self._nacd_threshold)

        layout.addWidget(group)
        layout.addWidget(nf_group)
        layout.addStretch()

    def write_to(self, settings: ReportStudioSettings) -> None:
        settings.max_offsets = self._max_offsets.value()
        settings.uncertainty_alpha = self._uncertainty_alpha.value()
        settings.near_field.mark = self._mark_nf.isChecked()
        settings.near_field.style = self._nf_style.currentText()
        settings.near_field.nacd_threshold = self._nacd_threshold.value()

    def read_from(self, settings: ReportStudioSettings) -> None:
        for w in (self._max_offsets, self._uncertainty_alpha,
                  self._mark_nf, self._nf_style, self._nacd_threshold):
            w.blockSignals(True)
        self._max_offsets.setValue(settings.max_offsets)
        self._uncertainty_alpha.setValue(settings.uncertainty_alpha)
        self._mark_nf.setChecked(settings.near_field.mark)
        self._nf_style.setCurrentText(settings.near_field.style)
        self._nacd_threshold.setValue(settings.near_field.nacd_threshold)
        for w in (self._max_offsets, self._uncertainty_alpha,
                  self._mark_nf, self._nf_style, self._nacd_threshold):
            w.blockSignals(False)
