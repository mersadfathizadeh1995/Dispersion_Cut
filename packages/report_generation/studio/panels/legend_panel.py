"""Legend settings panel -- position, placement, frame, columns, offset."""
from __future__ import annotations

from ..qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QSpinBox = QtWidgets.QSpinBox
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox

from ..models import LegendConfig

_LOCATIONS = [
    "best", "upper right", "upper left", "lower left", "lower right",
    "right", "center left", "center right", "lower center", "upper center",
    "center",
]

_PLACEMENTS = [
    ("Inside", "inside"),
    ("Outside right", "outside_right"),
    ("Outside top", "outside_top"),
    ("Outside bottom", "outside_bottom"),
]


class LegendPanel(QWidget):
    """Controls for legend visibility, position, style."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # -- Visibility --
        vis_group = QGroupBox("Visibility")
        vis_form = QFormLayout(vis_group)

        self._show = QCheckBox("Show legend")
        self._show.setChecked(True)
        self._show.toggled.connect(self.changed)
        vis_form.addRow(self._show)

        layout.addWidget(vis_group)

        # -- Position group --
        pos_group = QGroupBox("Position")
        pos_form = QFormLayout(pos_group)

        self._placement = QComboBox()
        for display, _value in _PLACEMENTS:
            self._placement.addItem(display, _value)
        self._placement.currentIndexChanged.connect(lambda: self.changed.emit())
        pos_form.addRow("Placement:", self._placement)

        self._location = QComboBox()
        self._location.addItems(_LOCATIONS)
        self._location.setCurrentText("best")
        self._location.currentTextChanged.connect(lambda: self.changed.emit())
        pos_form.addRow("Location:", self._location)

        self._ncol = QSpinBox()
        self._ncol.setRange(1, 10)
        self._ncol.setValue(1)
        self._ncol.valueChanged.connect(self.changed)
        pos_form.addRow("Columns:", self._ncol)

        self._offset_x = QDoubleSpinBox()
        self._offset_x.setRange(-2.0, 2.0)
        self._offset_x.setSingleStep(0.05)
        self._offset_x.setDecimals(2)
        self._offset_x.setValue(0.0)
        self._offset_x.valueChanged.connect(self.changed)
        pos_form.addRow("Offset X:", self._offset_x)

        self._offset_y = QDoubleSpinBox()
        self._offset_y.setRange(-2.0, 2.0)
        self._offset_y.setSingleStep(0.05)
        self._offset_y.setDecimals(2)
        self._offset_y.setValue(0.0)
        self._offset_y.valueChanged.connect(self.changed)
        pos_form.addRow("Offset Y:", self._offset_y)

        layout.addWidget(pos_group)

        # -- Style group --
        style_group = QGroupBox("Style")
        style_form = QFormLayout(style_group)

        self._frame_on = QCheckBox("Show frame")
        self._frame_on.toggled.connect(self.changed)
        style_form.addRow(self._frame_on)

        self._frame_alpha = QDoubleSpinBox()
        self._frame_alpha.setRange(0.0, 1.0)
        self._frame_alpha.setSingleStep(0.05)
        self._frame_alpha.setDecimals(2)
        self._frame_alpha.setValue(0.8)
        self._frame_alpha.valueChanged.connect(self.changed)
        style_form.addRow("Frame opacity:", self._frame_alpha)

        self._shadow = QCheckBox("Shadow")
        self._shadow.toggled.connect(self.changed)
        style_form.addRow(self._shadow)

        self._markerscale = QDoubleSpinBox()
        self._markerscale.setRange(0.1, 5.0)
        self._markerscale.setSingleStep(0.1)
        self._markerscale.setDecimals(1)
        self._markerscale.setValue(1.0)
        self._markerscale.valueChanged.connect(self.changed)
        style_form.addRow("Marker scale:", self._markerscale)

        layout.addWidget(style_group)
        layout.addStretch()

    def write_to(self, cfg: LegendConfig) -> None:
        cfg.show = self._show.isChecked()
        cfg.placement = self._placement.currentData()
        cfg.location = self._location.currentText()
        cfg.ncol = self._ncol.value()
        cfg.offset_x = self._offset_x.value()
        cfg.offset_y = self._offset_y.value()
        cfg.frame_on = self._frame_on.isChecked()
        cfg.frame_alpha = self._frame_alpha.value()
        cfg.shadow = self._shadow.isChecked()
        cfg.markerscale = self._markerscale.value()

    def read_from(self, cfg: LegendConfig) -> None:
        widgets = [self._show, self._placement, self._location,
                   self._ncol, self._offset_x, self._offset_y,
                   self._frame_on, self._frame_alpha, self._shadow,
                   self._markerscale]
        for w in widgets:
            w.blockSignals(True)
        self._show.setChecked(cfg.show)
        idx = self._placement.findData(cfg.placement)
        if idx >= 0:
            self._placement.setCurrentIndex(idx)
        self._location.setCurrentText(cfg.location)
        self._ncol.setValue(cfg.ncol)
        self._offset_x.setValue(cfg.offset_x)
        self._offset_y.setValue(cfg.offset_y)
        self._frame_on.setChecked(cfg.frame_on)
        self._frame_alpha.setValue(cfg.frame_alpha)
        self._shadow.setChecked(cfg.shadow)
        self._markerscale.setValue(cfg.markerscale)
        for w in widgets:
            w.blockSignals(False)
