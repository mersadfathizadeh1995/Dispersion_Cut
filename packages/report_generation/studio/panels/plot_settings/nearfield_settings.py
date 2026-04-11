"""Settings widget for near-field analysis plot types."""
from __future__ import annotations

from ...qt_compat import QtWidgets

QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QSpinBox = QtWidgets.QSpinBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox
QLineEdit = QtWidgets.QLineEdit

from .base import BasePlotSettingsWidget
from ...models import ReportStudioSettings


class NearFieldSettings(BasePlotSettingsWidget):
    """Settings for nacd_curve, nacd_grid, nacd_combined, nacd_comparison, nacd_summary."""

    def __init__(self, offset_labels: list | None = None, parent=None):
        super().__init__(parent)
        labels = offset_labels or []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # -- Offset selection (by name) --
        offset_group = QGroupBox("Offset Selection")
        offset_form = QFormLayout(offset_group)

        self._offset_combo = QComboBox()
        for i, label in enumerate(labels):
            self._offset_combo.addItem(label, i)
        if not labels:
            self._offset_combo.addItem("No offsets loaded", 0)
        self._offset_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        offset_form.addRow("Offset:", self._offset_combo)

        layout.addWidget(offset_group)

        # -- NACD settings --
        nacd_group = QGroupBox("NACD Settings")
        nacd_form = QFormLayout(nacd_group)

        self._nacd_threshold = QDoubleSpinBox()
        self._nacd_threshold.setRange(0.1, 5.0)
        self._nacd_threshold.setSingleStep(0.1)
        self._nacd_threshold.setDecimals(1)
        self._nacd_threshold.setValue(1.0)
        self._nacd_threshold.valueChanged.connect(self.changed)
        nacd_form.addRow("NACD threshold:", self._nacd_threshold)

        self._show_spectrum = QCheckBox("Show spectrum background")
        self._show_spectrum.toggled.connect(self.changed)
        nacd_form.addRow(self._show_spectrum)

        self._farfield_color = QLineEdit("blue")
        self._farfield_color.textChanged.connect(lambda: self.changed.emit())
        nacd_form.addRow("Far-field color:", self._farfield_color)

        self._nearfield_color = QLineEdit("red")
        self._nearfield_color.textChanged.connect(lambda: self.changed.emit())
        nacd_form.addRow("Near-field color:", self._nearfield_color)

        layout.addWidget(nacd_group)

        # -- Grid layout for nacd_grid --
        grid_group = QGroupBox("Grid Layout (NACD Grid)")
        grid_form = QFormLayout(grid_group)

        self._grid_rows = QSpinBox()
        self._grid_rows.setRange(0, 10)
        self._grid_rows.setSpecialValueText("Auto")
        self._grid_rows.valueChanged.connect(self.changed)
        grid_form.addRow("Rows:", self._grid_rows)

        self._grid_cols = QSpinBox()
        self._grid_cols.setRange(0, 10)
        self._grid_cols.setSpecialValueText("Auto")
        self._grid_cols.valueChanged.connect(self.changed)
        grid_form.addRow("Columns:", self._grid_cols)

        layout.addWidget(grid_group)
        layout.addStretch()

    @property
    def offset_index(self) -> int:
        data = self._offset_combo.currentData()
        return data if data is not None else 0

    @property
    def grid_rows(self) -> int | None:
        v = self._grid_rows.value()
        return v if v > 0 else None

    @property
    def grid_cols(self) -> int | None:
        v = self._grid_cols.value()
        return v if v > 0 else None

    def write_to(self, settings: ReportStudioSettings) -> None:
        settings.near_field.nacd_threshold = self._nacd_threshold.value()
        settings.near_field.show_spectrum = self._show_spectrum.isChecked()
        settings.near_field.farfield_color = self._farfield_color.text()
        settings.near_field.nearfield_color = self._nearfield_color.text()

    def read_from(self, settings: ReportStudioSettings) -> None:
        for w in (self._nacd_threshold, self._show_spectrum,
                  self._farfield_color, self._nearfield_color):
            w.blockSignals(True)
        self._nacd_threshold.setValue(settings.near_field.nacd_threshold)
        self._show_spectrum.setChecked(settings.near_field.show_spectrum)
        self._farfield_color.setText(settings.near_field.farfield_color)
        self._nearfield_color.setText(settings.near_field.nearfield_color)
        for w in (self._nacd_threshold, self._show_spectrum,
                  self._farfield_color, self._nearfield_color):
            w.blockSignals(False)
