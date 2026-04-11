"""Subplot properties panel -- per-subplot axis, grid, scale, spectrum background.

Shown in the right panel when a subplot is selected in the DataTree.
"""
from __future__ import annotations

from ..qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QLineEdit = QtWidgets.QLineEdit
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QSpinBox = QtWidgets.QSpinBox
QCheckBox = QtWidgets.QCheckBox
QComboBox = QtWidgets.QComboBox

from ..figure_model import SubplotModel


class SubplotPropsPanel(QWidget):
    """Per-subplot properties: axis limits, scale, labels, grid, spectrum background."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_key = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # -- Title --
        title_group = QGroupBox("Subplot")
        title_form = QFormLayout(title_group)

        self._title = QLineEdit()
        self._title.setPlaceholderText("Subplot title")
        self._title.editingFinished.connect(self.changed)
        title_form.addRow("Title:", self._title)

        layout.addWidget(title_group)

        # -- Axis Scale --
        scale_group = QGroupBox("Axis Scale")
        scale_form = QFormLayout(scale_group)

        self._x_scale = QComboBox()
        self._x_scale.addItems(["log", "linear"])
        self._x_scale.currentTextChanged.connect(lambda: self.changed.emit())
        scale_form.addRow("X scale:", self._x_scale)

        self._y_scale = QComboBox()
        self._y_scale.addItems(["linear", "log"])
        self._y_scale.currentTextChanged.connect(lambda: self.changed.emit())
        scale_form.addRow("Y scale:", self._y_scale)

        layout.addWidget(scale_group)

        # -- Axis Labels --
        label_group = QGroupBox("Labels")
        label_form = QFormLayout(label_group)

        self._x_label = QLineEdit("Frequency (Hz)")
        self._x_label.editingFinished.connect(self.changed)
        label_form.addRow("X label:", self._x_label)

        self._y_label = QLineEdit("Phase Velocity (m/s)")
        self._y_label.editingFinished.connect(self.changed)
        label_form.addRow("Y label:", self._y_label)

        layout.addWidget(label_group)

        # -- Axis Limits --
        limits_group = QGroupBox("Axis Limits")
        limits_form = QFormLayout(limits_group)

        self._auto_x = QCheckBox("Auto X")
        self._auto_x.setChecked(True)
        self._auto_x.toggled.connect(self._on_auto_x_toggled)
        limits_form.addRow(self._auto_x)

        self._x_min = QDoubleSpinBox()
        self._x_min.setRange(-1e9, 1e9)
        self._x_min.setDecimals(4)
        self._x_min.setEnabled(False)
        self._x_min.valueChanged.connect(self.changed)
        limits_form.addRow("X min:", self._x_min)

        self._x_max = QDoubleSpinBox()
        self._x_max.setRange(-1e9, 1e9)
        self._x_max.setDecimals(4)
        self._x_max.setValue(100.0)
        self._x_max.setEnabled(False)
        self._x_max.valueChanged.connect(self.changed)
        limits_form.addRow("X max:", self._x_max)

        self._auto_y = QCheckBox("Auto Y")
        self._auto_y.setChecked(True)
        self._auto_y.toggled.connect(self._on_auto_y_toggled)
        limits_form.addRow(self._auto_y)

        self._y_min = QDoubleSpinBox()
        self._y_min.setRange(-1e9, 1e9)
        self._y_min.setDecimals(4)
        self._y_min.setEnabled(False)
        self._y_min.valueChanged.connect(self.changed)
        limits_form.addRow("Y min:", self._y_min)

        self._y_max = QDoubleSpinBox()
        self._y_max.setRange(-1e9, 1e9)
        self._y_max.setDecimals(4)
        self._y_max.setValue(1000.0)
        self._y_max.setEnabled(False)
        self._y_max.valueChanged.connect(self.changed)
        limits_form.addRow("Y max:", self._y_max)

        layout.addWidget(limits_group)

        # -- Grid --
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
        grid_form.addRow("Alpha:", self._grid_alpha)

        self._grid_style = QComboBox()
        self._grid_style.addItems(["--", "-", "-.", ":"])
        self._grid_style.currentTextChanged.connect(lambda: self.changed.emit())
        grid_form.addRow("Style:", self._grid_style)

        layout.addWidget(grid_group)

        # -- Spectrum Background --
        spec_group = QGroupBox("Spectrum Background")
        spec_form = QFormLayout(spec_group)

        self._show_spectrum = QCheckBox("Show spectrum")
        self._show_spectrum.setChecked(False)
        self._show_spectrum.toggled.connect(self.changed)
        spec_form.addRow(self._show_spectrum)

        self._spectrum_offset = QSpinBox()
        self._spectrum_offset.setRange(0, 999)
        self._spectrum_offset.setToolTip("Offset index for spectrum data")
        self._spectrum_offset.valueChanged.connect(self.changed)
        spec_form.addRow("Offset index:", self._spectrum_offset)

        layout.addWidget(spec_group)

        # -- Legend --
        legend_group = QGroupBox("Legend")
        legend_form = QFormLayout(legend_group)

        self._show_legend = QCheckBox("Show legend")
        self._show_legend.setChecked(True)
        self._show_legend.toggled.connect(self.changed)
        legend_form.addRow(self._show_legend)

        self._legend_loc = QComboBox()
        self._legend_loc.addItems([
            "best", "upper right", "upper left", "lower left",
            "lower right", "right", "center left", "center right",
            "lower center", "upper center", "center",
        ])
        self._legend_loc.currentTextChanged.connect(lambda: self.changed.emit())
        legend_form.addRow("Location:", self._legend_loc)

        self._legend_ncol = QSpinBox()
        self._legend_ncol.setRange(1, 10)
        self._legend_ncol.setValue(1)
        self._legend_ncol.valueChanged.connect(self.changed)
        legend_form.addRow("Columns:", self._legend_ncol)

        layout.addWidget(legend_group)
        layout.addStretch()

    def load_from(self, sp: SubplotModel) -> None:
        self._current_key = sp.key
        self._block_all(True)

        self._title.setText(sp.title)
        self._x_scale.setCurrentText(sp.x_scale)
        self._y_scale.setCurrentText(sp.y_scale)
        self._x_label.setText(sp.x_label)
        self._y_label.setText(sp.y_label)
        self._auto_x.setChecked(sp.auto_x)
        self._x_min.setEnabled(not sp.auto_x)
        self._x_max.setEnabled(not sp.auto_x)
        if sp.x_min is not None:
            self._x_min.setValue(sp.x_min)
        if sp.x_max is not None:
            self._x_max.setValue(sp.x_max)
        self._auto_y.setChecked(sp.auto_y)
        self._y_min.setEnabled(not sp.auto_y)
        self._y_max.setEnabled(not sp.auto_y)
        if sp.y_min is not None:
            self._y_min.setValue(sp.y_min)
        if sp.y_max is not None:
            self._y_max.setValue(sp.y_max)
        self._show_grid.setChecked(sp.show_grid)
        self._grid_alpha.setValue(sp.grid_alpha)
        self._grid_style.setCurrentText(sp.grid_linestyle)
        self._show_spectrum.setChecked(sp.show_spectrum)
        if sp.spectrum_offset_index is not None:
            self._spectrum_offset.setValue(sp.spectrum_offset_index)
        self._show_legend.setChecked(sp.show_legend)
        self._legend_loc.setCurrentText(sp.legend_location)
        self._legend_ncol.setValue(sp.legend_ncol)

        self._block_all(False)

    def write_to(self, sp: SubplotModel) -> None:
        sp.title = self._title.text()
        sp.x_scale = self._x_scale.currentText()
        sp.y_scale = self._y_scale.currentText()
        sp.x_label = self._x_label.text()
        sp.y_label = self._y_label.text()
        sp.auto_x = self._auto_x.isChecked()
        if not sp.auto_x:
            sp.x_min = self._x_min.value()
            sp.x_max = self._x_max.value()
        else:
            sp.x_min = None
            sp.x_max = None
        sp.auto_y = self._auto_y.isChecked()
        if not sp.auto_y:
            sp.y_min = self._y_min.value()
            sp.y_max = self._y_max.value()
        else:
            sp.y_min = None
            sp.y_max = None
        sp.show_grid = self._show_grid.isChecked()
        sp.grid_alpha = self._grid_alpha.value()
        sp.grid_linestyle = self._grid_style.currentText()
        sp.show_spectrum = self._show_spectrum.isChecked()
        sp.spectrum_offset_index = self._spectrum_offset.value() if sp.show_spectrum else None
        sp.show_legend = self._show_legend.isChecked()
        sp.legend_location = self._legend_loc.currentText()
        sp.legend_ncol = self._legend_ncol.value()

    @property
    def current_key(self) -> str:
        return self._current_key

    def _on_auto_x_toggled(self, checked: bool) -> None:
        self._x_min.setEnabled(not checked)
        self._x_max.setEnabled(not checked)
        self.changed.emit()

    def _on_auto_y_toggled(self, checked: bool) -> None:
        self._y_min.setEnabled(not checked)
        self._y_max.setEnabled(not checked)
        self.changed.emit()

    def _block_all(self, block: bool) -> None:
        for w in (self._title, self._x_scale, self._y_scale,
                  self._x_label, self._y_label,
                  self._auto_x, self._auto_y,
                  self._x_min, self._x_max, self._y_min, self._y_max,
                  self._show_grid, self._grid_alpha, self._grid_style,
                  self._show_spectrum, self._spectrum_offset,
                  self._show_legend, self._legend_loc, self._legend_ncol):
            w.blockSignals(block)
