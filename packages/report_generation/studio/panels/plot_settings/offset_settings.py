"""Settings widget for source-offset analysis plot types."""
from __future__ import annotations

from ...qt_compat import QtWidgets

QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QSpinBox = QtWidgets.QSpinBox
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox

from .base import BasePlotSettingsWidget
from ...models import ReportStudioSettings


class OffsetSettings(BasePlotSettingsWidget):
    """Settings for offset_curve_only, offset_with_spectrum, offset_spectrum_only, offset_grid."""

    def __init__(self, n_offsets: int = 0, parent=None):
        super().__init__(parent)
        self._n_offsets = n_offsets
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # -- Offset selection --
        offset_group = QGroupBox("Offset Selection")
        offset_form = QFormLayout(offset_group)

        self._offset_index = QSpinBox()
        self._offset_index.setRange(0, max(0, n_offsets - 1))
        self._offset_index.setValue(0)
        self._offset_index.valueChanged.connect(self.changed)
        offset_form.addRow("Offset index:", self._offset_index)

        layout.addWidget(offset_group)

        # -- Spectrum options --
        spec_group = QGroupBox("Spectrum Display")
        spec_form = QFormLayout(spec_group)

        self._include_spectrum = QCheckBox("Include spectrum")
        self._include_spectrum.toggled.connect(self.changed)
        spec_form.addRow(self._include_spectrum)

        self._render_mode = QComboBox()
        self._render_mode.addItems(["imshow", "contour"])
        self._render_mode.setCurrentText("imshow")
        self._render_mode.currentTextChanged.connect(lambda: self.changed.emit())
        spec_form.addRow("Render mode:", self._render_mode)

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
        return self._offset_index.value()

    @property
    def grid_rows(self) -> int | None:
        v = self._grid_rows.value()
        return v if v > 0 else None

    @property
    def grid_cols(self) -> int | None:
        v = self._grid_cols.value()
        return v if v > 0 else None

    def write_to(self, settings: ReportStudioSettings) -> None:
        settings.spectrum.render_mode = self._render_mode.currentText()
        settings.spectrum.colormap = self._colormap.currentText()
        settings.spectrum.alpha = self._spectrum_alpha.value()
        settings.curve_overlay.style = self._overlay_style.currentText()
        settings.curve_overlay.outline = self._peak_outline.isChecked()

    def read_from(self, settings: ReportStudioSettings) -> None:
        for w in (self._render_mode, self._colormap, self._spectrum_alpha,
                  self._overlay_style, self._peak_outline):
            w.blockSignals(True)
        self._render_mode.setCurrentText(settings.spectrum.render_mode)
        self._colormap.setCurrentText(settings.spectrum.colormap)
        self._spectrum_alpha.setValue(settings.spectrum.alpha)
        self._overlay_style.setCurrentText(settings.curve_overlay.style)
        self._peak_outline.setChecked(settings.curve_overlay.outline)
        for w in (self._render_mode, self._colormap, self._spectrum_alpha,
                  self._overlay_style, self._peak_outline):
            w.blockSignals(False)
