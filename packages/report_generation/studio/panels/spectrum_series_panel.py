"""Per-series spectrum background settings panel.

Displayed when a 'Spectrum Background' sub-layer is selected
in the data tree.  Controls are written to / read from a
SpectrumLayer on the parent DataSeries.
"""
from __future__ import annotations

from ..qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QCheckBox = QtWidgets.QCheckBox
QComboBox = QtWidgets.QComboBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QSpinBox = QtWidgets.QSpinBox
QLabel = QtWidgets.QLabel

from ..figure_model import SpectrumLayer

_COLORMAPS = [
    "viridis", "plasma", "inferno", "magma", "cividis",
    "jet", "hot", "coolwarm", "RdYlBu", "Spectral",
    "turbo", "twilight", "ocean", "terrain",
]
_RENDER_MODES = ["imshow", "contour"]


class SpectrumSeriesPanel(QWidget):
    """Settings panel for a single spectrum sub-layer."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_uid: str = ""
        self._build_ui()

    @property
    def current_uid(self) -> str:
        return self._current_uid

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Spectrum Background")
        header.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(header)

        # Colormap group
        cmap_group = QGroupBox("Colormap")
        cmap_form = QFormLayout(cmap_group)

        self._colormap = QComboBox()
        self._colormap.addItems(_COLORMAPS)
        self._colormap.currentIndexChanged.connect(self.changed)
        cmap_form.addRow("Colormap:", self._colormap)

        self._render_mode = QComboBox()
        self._render_mode.addItems(_RENDER_MODES)
        self._render_mode.currentIndexChanged.connect(self.changed)
        cmap_form.addRow("Render mode:", self._render_mode)

        layout.addWidget(cmap_group)

        # Display group
        disp_group = QGroupBox("Display")
        disp_form = QFormLayout(disp_group)

        self._alpha = QDoubleSpinBox()
        self._alpha.setRange(0.0, 1.0)
        self._alpha.setSingleStep(0.05)
        self._alpha.setDecimals(2)
        self._alpha.setValue(0.8)
        self._alpha.valueChanged.connect(self.changed)
        disp_form.addRow("Opacity:", self._alpha)

        self._levels = QSpinBox()
        self._levels.setRange(5, 100)
        self._levels.setValue(30)
        self._levels.valueChanged.connect(self.changed)
        disp_form.addRow("Contour levels:", self._levels)

        layout.addWidget(disp_group)

        # Colorbar group
        cbar_group = QGroupBox("Colorbar")
        cbar_form = QFormLayout(cbar_group)

        self._show_colorbar = QCheckBox("Show colorbar")
        self._show_colorbar.toggled.connect(self.changed)
        cbar_form.addRow(self._show_colorbar)

        self._colorbar_orient = QComboBox()
        self._colorbar_orient.addItems(["vertical", "horizontal"])
        self._colorbar_orient.currentIndexChanged.connect(self.changed)
        cbar_form.addRow("Orientation:", self._colorbar_orient)

        layout.addWidget(cbar_group)
        layout.addStretch()

    # ── Read / Write ──────────────────────────────────────────────

    def load_from(self, uid: str, spec: SpectrumLayer) -> None:
        self._current_uid = uid
        self.blockSignals(True)
        idx = self._colormap.findText(spec.colormap)
        if idx >= 0:
            self._colormap.setCurrentIndex(idx)
        idx = self._render_mode.findText(spec.render_mode)
        if idx >= 0:
            self._render_mode.setCurrentIndex(idx)
        self._alpha.setValue(spec.alpha)
        self._levels.setValue(spec.levels)
        self._show_colorbar.setChecked(spec.show_colorbar)
        idx = self._colorbar_orient.findText(spec.colorbar_orientation)
        if idx >= 0:
            self._colorbar_orient.setCurrentIndex(idx)
        self.blockSignals(False)

    def write_to(self, spec: SpectrumLayer) -> None:
        spec.colormap = self._colormap.currentText()
        spec.render_mode = self._render_mode.currentText()
        spec.alpha = self._alpha.value()
        spec.levels = self._levels.value()
        spec.show_colorbar = self._show_colorbar.isChecked()
        spec.colorbar_orientation = self._colorbar_orient.currentText()
