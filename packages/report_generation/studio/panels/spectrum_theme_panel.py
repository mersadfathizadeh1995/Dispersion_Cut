"""Shared spectrum theme panel for all plot types.

Controls colormap, render mode, alpha, colorbar, and contour levels
in one place rather than duplicating across per-plot-type widgets.
"""
from __future__ import annotations

from ..qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QSpinBox = QtWidgets.QSpinBox

from ..models import SpectrumConfig


class SpectrumThemePanel(QWidget):
    """Shared panel for spectrum display settings (colormap, alpha, colorbar, etc.)."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # -- Colormap --
        cmap_group = QGroupBox("Colormap")
        cmap_form = QFormLayout(cmap_group)

        self._colormap = QComboBox()
        self._colormap.addItems([
            "viridis", "plasma", "inferno", "magma", "cividis",
            "jet", "hot", "coolwarm", "RdYlBu", "Spectral",
            "turbo", "twilight", "ocean", "terrain",
        ])
        self._colormap.setCurrentText("viridis")
        self._colormap.currentTextChanged.connect(lambda: self.changed.emit())
        cmap_form.addRow("Colormap:", self._colormap)

        self._render_mode = QComboBox()
        self._render_mode.addItems(["imshow", "contour"])
        self._render_mode.setCurrentText("imshow")
        self._render_mode.currentTextChanged.connect(lambda: self.changed.emit())
        cmap_form.addRow("Render mode:", self._render_mode)

        layout.addWidget(cmap_group)

        # -- Display --
        display_group = QGroupBox("Display")
        display_form = QFormLayout(display_group)

        self._alpha = QDoubleSpinBox()
        self._alpha.setRange(0.0, 1.0)
        self._alpha.setSingleStep(0.05)
        self._alpha.setDecimals(2)
        self._alpha.setValue(0.8)
        self._alpha.valueChanged.connect(self.changed)
        display_form.addRow("Alpha:", self._alpha)

        self._levels = QSpinBox()
        self._levels.setRange(5, 100)
        self._levels.setValue(30)
        self._levels.setToolTip("Number of contour levels (for contour mode)")
        self._levels.valueChanged.connect(self.changed)
        display_form.addRow("Contour levels:", self._levels)

        layout.addWidget(display_group)

        # -- Colorbar --
        cbar_group = QGroupBox("Colorbar")
        cbar_form = QFormLayout(cbar_group)

        self._show_colorbar = QCheckBox("Show colorbar")
        self._show_colorbar.setChecked(True)
        self._show_colorbar.toggled.connect(self.changed)
        cbar_form.addRow(self._show_colorbar)

        self._colorbar_orient = QComboBox()
        self._colorbar_orient.addItems(["vertical", "horizontal"])
        self._colorbar_orient.setCurrentText("vertical")
        self._colorbar_orient.currentTextChanged.connect(lambda: self.changed.emit())
        cbar_form.addRow("Orientation:", self._colorbar_orient)

        layout.addWidget(cbar_group)
        layout.addStretch()

    def write_to(self, spec: SpectrumConfig) -> None:
        spec.colormap = self._colormap.currentText()
        spec.render_mode = self._render_mode.currentText()
        spec.alpha = self._alpha.value()
        spec.levels = self._levels.value()
        spec.show_colorbar = self._show_colorbar.isChecked()
        spec.colorbar_orientation = self._colorbar_orient.currentText()

    def read_from(self, spec: SpectrumConfig) -> None:
        widgets = (self._colormap, self._render_mode, self._alpha,
                   self._levels, self._show_colorbar, self._colorbar_orient)
        for w in widgets:
            w.blockSignals(True)
        self._colormap.setCurrentText(spec.colormap)
        self._render_mode.setCurrentText(spec.render_mode)
        self._alpha.setValue(spec.alpha)
        self._levels.setValue(spec.levels)
        self._show_colorbar.setChecked(spec.show_colorbar)
        self._colorbar_orient.setCurrentText(spec.colorbar_orientation)
        for w in widgets:
            w.blockSignals(False)
