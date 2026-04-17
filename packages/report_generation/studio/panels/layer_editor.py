"""Layer Editor panel -- detailed per-layer style, visibility, and point control.

Shown in the left panel after the user commits a plot type to a sheet.
Provides a tree with expandable per-point toggles and a properties section
for color, line width, marker, alpha, and legend label overrides.
"""
from __future__ import annotations

from typing import List, Optional
import numpy as np

from ..qt_compat import (
    QtWidgets, Signal,
    Vertical, Checked, Unchecked, UserRole, ItemIsUserCheckable,
)

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QSplitter = QtWidgets.QSplitter
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QLineEdit = QtWidgets.QLineEdit
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox

from ..models import StudioLayerState


class LayerEditor(QWidget):
    """Per-layer and per-point style editor for a committed sheet figure.

    Signals
    -------
    layer_config_changed
        Emitted when any layer property or point mask changes.
    back_requested
        Emitted when the user wants to return to the plot selector.
    """

    layer_config_changed = Signal()
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # -- Header --
        header_row = QHBoxLayout()
        self._back_btn = QPushButton("<< Back to Plot Selection")
        self._back_btn.clicked.connect(self.back_requested.emit)
        header_row.addWidget(self._back_btn)
        header_row.addStretch()
        layout.addLayout(header_row)

        self._plot_type_label = QLabel("")
        self._plot_type_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        layout.addWidget(self._plot_type_label)

        # -- Splitter: tree on top, properties on bottom --
        splitter = QSplitter(Vertical)

        # Layer tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Layer / Point", "Freq", "Vel"])
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(16)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.currentItemChanged.connect(self._on_selection_changed)
        splitter.addWidget(self._tree)

        # Properties panel
        props_widget = QWidget()
        props_layout = QVBoxLayout(props_widget)
        props_layout.setContentsMargins(4, 4, 4, 4)

        props_group = QGroupBox("Layer Properties")
        props_form = QFormLayout(props_group)

        self._color_edit = QLineEdit()
        self._color_edit.setPlaceholderText("auto")
        self._color_edit.textChanged.connect(self._on_prop_changed)
        props_form.addRow("Color:", self._color_edit)

        self._line_width = QDoubleSpinBox()
        self._line_width.setRange(0.1, 10.0)
        self._line_width.setSingleStep(0.5)
        self._line_width.setValue(1.5)
        self._line_width.valueChanged.connect(self._on_prop_changed)
        props_form.addRow("Line width:", self._line_width)

        self._line_style = QComboBox()
        self._line_style.addItems(["solid", "dashed", "dotted", "dashdot"])
        self._line_style.currentTextChanged.connect(self._on_prop_changed)
        props_form.addRow("Line style:", self._line_style)

        self._marker_style = QComboBox()
        self._marker_style.addItems(["o", "s", "^", "v", "D", "x", "+", ".", "none"])
        self._marker_style.currentTextChanged.connect(self._on_prop_changed)
        props_form.addRow("Marker:", self._marker_style)

        self._marker_size = QDoubleSpinBox()
        self._marker_size.setRange(0.5, 20.0)
        self._marker_size.setSingleStep(0.5)
        self._marker_size.setValue(4.0)
        self._marker_size.valueChanged.connect(self._on_prop_changed)
        props_form.addRow("Marker size:", self._marker_size)

        self._alpha = QDoubleSpinBox()
        self._alpha.setRange(0.0, 1.0)
        self._alpha.setSingleStep(0.05)
        self._alpha.setDecimals(2)
        self._alpha.setValue(1.0)
        self._alpha.valueChanged.connect(self._on_prop_changed)
        props_form.addRow("Alpha:", self._alpha)

        self._legend_label = QLineEdit()
        self._legend_label.setPlaceholderText("(use default)")
        self._legend_label.textChanged.connect(self._on_prop_changed)
        props_form.addRow("Legend label:", self._legend_label)

        props_layout.addWidget(props_group)
        splitter.addWidget(props_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, stretch=1)

        self._layer_states: List[StudioLayerState] = []
        self._freq_arrays: List[np.ndarray] = []
        self._vel_arrays: List[np.ndarray] = []
        self._current_layer_idx: int = -1
        self._updating = False

    def set_plot_type(self, plot_type: str) -> None:
        self._plot_type_label.setText(f"Plot: {plot_type}")

    def populate(
        self,
        layer_states: List[StudioLayerState],
        freq_arrays: List[np.ndarray],
        vel_arrays: List[np.ndarray],
    ) -> None:
        """Fill the tree from layer states and data arrays."""
        self._layer_states = layer_states
        self._freq_arrays = freq_arrays
        self._vel_arrays = vel_arrays
        self._current_layer_idx = -1
        self._rebuild_tree()

    def get_layer_states(self) -> List[StudioLayerState]:
        return self._layer_states

    def _rebuild_tree(self) -> None:
        self._updating = True
        self._tree.clear()

        for ls in self._layer_states:
            i = ls.index
            top = QTreeWidgetItem(self._tree, [ls.label, "", ""])
            top.setFlags(top.flags() | ItemIsUserCheckable)
            top.setCheckState(0, Checked if ls.visible else Unchecked)
            top.setData(0, UserRole, ("layer", i))

            if i < len(self._freq_arrays):
                freqs = self._freq_arrays[i]
                vels = self._vel_arrays[i]
                mask = ls.point_mask
                for j in range(len(freqs)):
                    f_str = f"{freqs[j]:.2f}" if not np.isnan(freqs[j]) else "NaN"
                    v_str = f"{vels[j]:.1f}" if not np.isnan(vels[j]) else "NaN"
                    child = QTreeWidgetItem(top, [f"Point {j}", f_str, v_str])
                    child.setFlags(child.flags() | ItemIsUserCheckable)
                    is_on = True if mask is None else (mask[j] if j < len(mask) else True)
                    child.setCheckState(0, Checked if is_on else Unchecked)
                    child.setData(0, UserRole, ("point", i, j))

        self._tree.expandAll()
        self._updating = False

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating or column != 0:
            return
        data = item.data(0, UserRole)
        if data is None:
            return

        if data[0] == "layer":
            idx = data[1]
            for ls in self._layer_states:
                if ls.index == idx:
                    ls.visible = item.checkState(0) == Checked
                    break
            self.layer_config_changed.emit()

        elif data[0] == "point":
            layer_idx, point_idx = data[1], data[2]
            for ls in self._layer_states:
                if ls.index == layer_idx:
                    if ls.point_mask is None:
                        n = len(self._freq_arrays[layer_idx]) if layer_idx < len(self._freq_arrays) else 0
                        ls.point_mask = [True] * n
                    if point_idx < len(ls.point_mask):
                        ls.point_mask[point_idx] = item.checkState(0) == Checked
                    break
            self.layer_config_changed.emit()

    def _on_selection_changed(self, current: QTreeWidgetItem | None,
                              _previous: QTreeWidgetItem | None) -> None:
        if current is None:
            return
        data = current.data(0, UserRole)
        if data is None:
            return
        if data[0] == "layer":
            self._load_layer_props(data[1])
        elif data[0] == "point":
            self._load_layer_props(data[1])

    def _load_layer_props(self, layer_idx: int) -> None:
        self._current_layer_idx = layer_idx
        ls = None
        for s in self._layer_states:
            if s.index == layer_idx:
                ls = s
                break
        if ls is None:
            return

        self._updating = True
        self._color_edit.setText(ls.color or "")
        self._line_width.setValue(ls.line_width if ls.line_width is not None else 1.5)
        self._line_style.setCurrentText(ls.line_style)
        self._marker_style.setCurrentText(ls.marker_style or "o")
        self._marker_size.setValue(ls.marker_size if ls.marker_size is not None else 4.0)
        self._alpha.setValue(ls.alpha)
        self._legend_label.setText(ls.legend_label or "")
        self._updating = False

    def _on_prop_changed(self) -> None:
        if self._updating or self._current_layer_idx < 0:
            return
        ls = None
        for s in self._layer_states:
            if s.index == self._current_layer_idx:
                ls = s
                break
        if ls is None:
            return

        color_text = self._color_edit.text().strip()
        ls.color = color_text if color_text else None
        ls.line_width = self._line_width.value()
        ls.line_style = self._line_style.currentText()
        ms_text = self._marker_style.currentText()
        ls.marker_style = ms_text if ms_text != "none" else None
        ls.marker_size = self._marker_size.value()
        ls.alpha = self._alpha.value()
        legend_text = self._legend_label.text().strip()
        ls.legend_label = legend_text if legend_text else None

        self.layer_config_changed.emit()
