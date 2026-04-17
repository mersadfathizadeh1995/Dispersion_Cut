"""Axis settings panel -- limits, scale, grid, ticks, labels."""
from __future__ import annotations

from ..qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox
QLineEdit = QtWidgets.QLineEdit

from ..models import AxisConfig


class AxisPanel(QWidget):
    """Controls for axis limits, scale, grid, ticks, and labels."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # -- Labels group --
        labels_group = QGroupBox("Labels")
        labels_form = QFormLayout(labels_group)

        self._xlabel = QLineEdit("Frequency (Hz)")
        self._xlabel.textChanged.connect(lambda: self.changed.emit())
        labels_form.addRow("X label:", self._xlabel)

        self._ylabel = QLineEdit("Phase Velocity (m/s)")
        self._ylabel.textChanged.connect(lambda: self.changed.emit())
        labels_form.addRow("Y label:", self._ylabel)

        self._title = QLineEdit()
        self._title.setPlaceholderText("(auto from plot type)")
        self._title.textChanged.connect(lambda: self.changed.emit())
        labels_form.addRow("Title:", self._title)

        layout.addWidget(labels_group)

        # -- Limits group --
        limits_group = QGroupBox("Axis Limits")
        limits_form = QFormLayout(limits_group)

        self._auto_x = QCheckBox("Auto X")
        self._auto_x.setChecked(True)
        self._auto_x.toggled.connect(self._on_auto_x_toggled)
        limits_form.addRow(self._auto_x)

        self._x_min = self._limit_spin()
        limits_form.addRow("X min:", self._x_min)
        self._x_max = self._limit_spin(100.0)
        limits_form.addRow("X max:", self._x_max)

        self._auto_y = QCheckBox("Auto Y")
        self._auto_y.setChecked(True)
        self._auto_y.toggled.connect(self._on_auto_y_toggled)
        limits_form.addRow(self._auto_y)

        self._y_min = self._limit_spin()
        limits_form.addRow("Y min:", self._y_min)
        self._y_max = self._limit_spin(1000.0)
        limits_form.addRow("Y max:", self._y_max)

        self._x_min.setEnabled(False)
        self._x_max.setEnabled(False)
        self._y_min.setEnabled(False)
        self._y_max.setEnabled(False)

        layout.addWidget(limits_group)

        # -- Scale group --
        scale_group = QGroupBox("Scale")
        scale_form = QFormLayout(scale_group)

        self._x_scale = QComboBox()
        self._x_scale.addItems(["log", "linear"])
        self._x_scale.setCurrentText("log")
        self._x_scale.currentTextChanged.connect(lambda: self.changed.emit())
        scale_form.addRow("X scale:", self._x_scale)

        self._y_scale = QComboBox()
        self._y_scale.addItems(["linear", "log"])
        self._y_scale.setCurrentText("linear")
        self._y_scale.currentTextChanged.connect(lambda: self.changed.emit())
        scale_form.addRow("Y scale:", self._y_scale)

        layout.addWidget(scale_group)

        # -- Grid group --
        grid_group = QGroupBox("Grid")
        grid_form = QFormLayout(grid_group)

        self._show_grid = QCheckBox("Show grid")
        self._show_grid.setChecked(True)
        self._show_grid.toggled.connect(self.changed)
        grid_form.addRow(self._show_grid)

        self._grid_alpha = QDoubleSpinBox()
        self._grid_alpha.setRange(0.0, 1.0)
        self._grid_alpha.setSingleStep(0.05)
        self._grid_alpha.setDecimals(2)
        self._grid_alpha.setValue(0.3)
        self._grid_alpha.valueChanged.connect(self.changed)
        grid_form.addRow("Opacity:", self._grid_alpha)

        layout.addWidget(grid_group)

        # -- Ticks group --
        ticks_group = QGroupBox("Ticks")
        ticks_form = QFormLayout(ticks_group)

        self._tick_dir = QComboBox()
        self._tick_dir.addItems(["out", "in", "inout"])
        self._tick_dir.setCurrentText("out")
        self._tick_dir.currentTextChanged.connect(lambda: self.changed.emit())
        ticks_form.addRow("Direction:", self._tick_dir)

        self._minor_ticks = QCheckBox("Show minor ticks")
        self._minor_ticks.toggled.connect(self.changed)
        ticks_form.addRow(self._minor_ticks)

        layout.addWidget(ticks_group)
        layout.addStretch()

    def _limit_spin(self, default: float = 0.0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-1e6, 1e6)
        spin.setSingleStep(10.0)
        spin.setDecimals(2)
        spin.setValue(default)
        spin.valueChanged.connect(self.changed)
        return spin

    def _on_auto_x_toggled(self, checked: bool) -> None:
        self._x_min.setEnabled(not checked)
        self._x_max.setEnabled(not checked)
        self.changed.emit()

    def _on_auto_y_toggled(self, checked: bool) -> None:
        self._y_min.setEnabled(not checked)
        self._y_max.setEnabled(not checked)
        self.changed.emit()

    def write_to(self, cfg: AxisConfig) -> None:
        cfg.xlabel = self._xlabel.text()
        cfg.ylabel = self._ylabel.text()
        cfg.title = self._title.text()
        cfg.auto_x = self._auto_x.isChecked()
        cfg.auto_y = self._auto_y.isChecked()
        if not cfg.auto_x:
            cfg.x_min = self._x_min.value()
            cfg.x_max = self._x_max.value()
        else:
            cfg.x_min = None
            cfg.x_max = None
        if not cfg.auto_y:
            cfg.y_min = self._y_min.value()
            cfg.y_max = self._y_max.value()
        else:
            cfg.y_min = None
            cfg.y_max = None
        cfg.x_scale = self._x_scale.currentText()
        cfg.y_scale = self._y_scale.currentText()
        cfg.grid.show = self._show_grid.isChecked()
        cfg.grid.alpha = self._grid_alpha.value()
        cfg.ticks.direction = self._tick_dir.currentText()
        cfg.ticks.show_minor = self._minor_ticks.isChecked()

    def read_from(self, cfg: AxisConfig) -> None:
        widgets = [self._xlabel, self._ylabel, self._title,
                   self._auto_x, self._auto_y,
                   self._x_min, self._x_max, self._y_min, self._y_max,
                   self._x_scale, self._y_scale,
                   self._show_grid, self._grid_alpha,
                   self._tick_dir, self._minor_ticks]
        for w in widgets:
            w.blockSignals(True)
        self._xlabel.setText(cfg.xlabel)
        self._ylabel.setText(cfg.ylabel)
        self._title.setText(cfg.title)
        self._auto_x.setChecked(cfg.auto_x)
        self._auto_y.setChecked(cfg.auto_y)
        if cfg.x_min is not None:
            self._x_min.setValue(cfg.x_min)
        if cfg.x_max is not None:
            self._x_max.setValue(cfg.x_max)
        if cfg.y_min is not None:
            self._y_min.setValue(cfg.y_min)
        if cfg.y_max is not None:
            self._y_max.setValue(cfg.y_max)
        self._x_min.setEnabled(not cfg.auto_x)
        self._x_max.setEnabled(not cfg.auto_x)
        self._y_min.setEnabled(not cfg.auto_y)
        self._y_max.setEnabled(not cfg.auto_y)
        self._x_scale.setCurrentText(cfg.x_scale)
        self._y_scale.setCurrentText(cfg.y_scale)
        self._show_grid.setChecked(cfg.grid.show)
        self._grid_alpha.setValue(cfg.grid.alpha)
        self._tick_dir.setCurrentText(cfg.ticks.direction)
        self._minor_ticks.setChecked(cfg.ticks.show_minor)
        for w in widgets:
            w.blockSignals(False)
