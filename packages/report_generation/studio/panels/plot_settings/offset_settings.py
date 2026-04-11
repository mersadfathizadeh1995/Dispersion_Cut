"""Settings widget for source-offset analysis plot types."""
from __future__ import annotations

from ...qt_compat import QtWidgets

QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QSpinBox = QtWidgets.QSpinBox
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox

from .base import BasePlotSettingsWidget
from ...models import ReportStudioSettings


class OffsetSettings(BasePlotSettingsWidget):
    """Settings for offset_curve_only, offset_with_spectrum, offset_spectrum_only, offset_grid."""

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

        # -- Spectrum toggle (whether to include spectrum in this plot) --
        spec_group = QGroupBox("Spectrum in Plot")
        spec_form = QFormLayout(spec_group)

        self._include_spectrum = QCheckBox("Include spectrum background")
        self._include_spectrum.toggled.connect(self.changed)
        spec_form.addRow(self._include_spectrum)

        layout.addWidget(spec_group)

        # -- Curve overlay --
        overlay_group = QGroupBox("Curve Overlay")
        overlay_form = QFormLayout(overlay_group)

        self._overlay_style = QComboBox()
        self._overlay_style.addItems(["line", "markers", "line+markers"])
        self._overlay_style.setCurrentText("line")
        self._overlay_style.currentTextChanged.connect(lambda: self.changed.emit())
        overlay_form.addRow("Style:", self._overlay_style)

        self._peak_outline = QCheckBox("Show outline")
        self._peak_outline.setChecked(True)
        self._peak_outline.toggled.connect(self.changed)
        overlay_form.addRow(self._peak_outline)

        layout.addWidget(overlay_group)

        # -- Grid layout for offset_grid --
        grid_group = QGroupBox("Grid Layout (Offset Grid)")
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
        settings.curve_overlay.style = self._overlay_style.currentText()
        settings.curve_overlay.outline = self._peak_outline.isChecked()

    def read_from(self, settings: ReportStudioSettings) -> None:
        for w in (self._overlay_style, self._peak_outline):
            w.blockSignals(True)
        self._overlay_style.setCurrentText(settings.curve_overlay.style)
        self._peak_outline.setChecked(settings.curve_overlay.outline)
        for w in (self._overlay_style, self._peak_outline):
            w.blockSignals(False)
