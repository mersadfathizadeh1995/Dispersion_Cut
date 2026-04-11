"""Figure settings panel -- size, DPI, margins, tight-layout."""
from __future__ import annotations

from ..qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QSpinBox = QtWidgets.QSpinBox
QCheckBox = QtWidgets.QCheckBox

from ..models import FigureConfig


class FigurePanel(QWidget):
    """Controls for figure dimensions, DPI, margins, and layout."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # -- Size group --
        size_group = QGroupBox("Figure Size")
        size_form = QFormLayout(size_group)

        self._width = QDoubleSpinBox()
        self._width.setRange(2.0, 30.0)
        self._width.setSingleStep(0.5)
        self._width.setSuffix(" in")
        self._width.setValue(8.0)
        size_form.addRow("Width:", self._width)

        self._height = QDoubleSpinBox()
        self._height.setRange(2.0, 30.0)
        self._height.setSingleStep(0.5)
        self._height.setSuffix(" in")
        self._height.setValue(6.0)
        size_form.addRow("Height:", self._height)

        self._dpi = QSpinBox()
        self._dpi.setRange(72, 1200)
        self._dpi.setSingleStep(50)
        self._dpi.setValue(300)
        size_form.addRow("DPI:", self._dpi)

        layout.addWidget(size_group)

        # -- Margins group --
        margin_group = QGroupBox("Margins (inches)")
        margin_form = QFormLayout(margin_group)

        self._margin_left = self._margin_spin(0.8)
        margin_form.addRow("Left:", self._margin_left)
        self._margin_right = self._margin_spin(0.3)
        margin_form.addRow("Right:", self._margin_right)
        self._margin_top = self._margin_spin(0.4)
        margin_form.addRow("Top:", self._margin_top)
        self._margin_bottom = self._margin_spin(0.6)
        margin_form.addRow("Bottom:", self._margin_bottom)

        layout.addWidget(margin_group)

        # -- Layout group --
        layout_group = QGroupBox("Layout")
        layout_form = QFormLayout(layout_group)

        self._tight_layout = QCheckBox("Tight layout")
        self._tight_layout.setChecked(True)
        layout_form.addRow(self._tight_layout)

        layout.addWidget(layout_group)
        layout.addStretch()

        for w in (self._width, self._height, self._margin_left,
                  self._margin_right, self._margin_top, self._margin_bottom):
            w.valueChanged.connect(self.changed)
        self._dpi.valueChanged.connect(self.changed)
        self._tight_layout.toggled.connect(self.changed)

    def _margin_spin(self, default: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 5.0)
        spin.setSingleStep(0.1)
        spin.setDecimals(2)
        spin.setSuffix(" in")
        spin.setValue(default)
        return spin

    def write_to(self, cfg: FigureConfig) -> None:
        cfg.width = self._width.value()
        cfg.height = self._height.value()
        cfg.dpi = self._dpi.value()
        cfg.margin_left = self._margin_left.value()
        cfg.margin_right = self._margin_right.value()
        cfg.margin_top = self._margin_top.value()
        cfg.margin_bottom = self._margin_bottom.value()
        cfg.tight_layout = self._tight_layout.isChecked()

    def read_from(self, cfg: FigureConfig) -> None:
        for w in (self._width, self._height, self._margin_left,
                  self._margin_right, self._margin_top, self._margin_bottom,
                  self._dpi, self._tight_layout):
            w.blockSignals(True)
        self._width.setValue(cfg.width)
        self._height.setValue(cfg.height)
        self._dpi.setValue(cfg.dpi)
        self._margin_left.setValue(cfg.margin_left)
        self._margin_right.setValue(cfg.margin_right)
        self._margin_top.setValue(cfg.margin_top)
        self._margin_bottom.setValue(cfg.margin_bottom)
        self._tight_layout.setChecked(cfg.tight_layout)
        for w in (self._width, self._height, self._margin_left,
                  self._margin_right, self._margin_top, self._margin_bottom,
                  self._dpi, self._tight_layout):
            w.blockSignals(False)
