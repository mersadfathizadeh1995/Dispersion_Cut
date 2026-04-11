"""Data series style panel -- per-series color, line, marker, alpha controls.

Shown in the right panel when a data series is selected in the DataTree.
"""
from __future__ import annotations

from ..qt_compat import QtWidgets, QtGui, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QLineEdit = QtWidgets.QLineEdit
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QSpinBox = QtWidgets.QSpinBox
QCheckBox = QtWidgets.QCheckBox
QComboBox = QtWidgets.QComboBox
QPushButton = QtWidgets.QPushButton
QColorDialog = QtWidgets.QColorDialog

from ..figure_model import DataSeries

_LINE_STYLES = ["solid", "dashed", "dashdot", "dotted"]
_MARKER_STYLES = ["o", "s", "^", "v", "D", "x", "+", "*", ".", "None"]


class DataStylePanel(QWidget):
    """Per-data-series style controls: color, line, marker, alpha, legend label."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_uid = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # -- Color --
        color_group = QGroupBox("Color")
        color_form = QFormLayout(color_group)

        color_row = QtWidgets.QHBoxLayout()
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(28, 28)
        self._color_btn.setToolTip("Click to pick a color")
        self._color_btn.clicked.connect(self._pick_color)
        color_row.addWidget(self._color_btn)
        self._color_edit = QLineEdit()
        self._color_edit.setPlaceholderText("#RRGGBB or empty for auto")
        self._color_edit.setMaximumWidth(120)
        self._color_edit.editingFinished.connect(self._on_color_text_changed)
        color_row.addWidget(self._color_edit)
        color_row.addStretch()
        color_form.addRow("Color:", color_row)

        self._alpha = QDoubleSpinBox()
        self._alpha.setRange(0.0, 1.0)
        self._alpha.setSingleStep(0.05)
        self._alpha.setDecimals(2)
        self._alpha.setValue(1.0)
        self._alpha.valueChanged.connect(self.changed)
        color_form.addRow("Alpha:", self._alpha)

        layout.addWidget(color_group)

        # -- Line --
        line_group = QGroupBox("Line")
        line_form = QFormLayout(line_group)

        self._show_line = QCheckBox("Connect markers with line")
        self._show_line.setChecked(True)
        self._show_line.toggled.connect(self.changed)
        line_form.addRow(self._show_line)

        self._line_width = QDoubleSpinBox()
        self._line_width.setRange(0.1, 10.0)
        self._line_width.setSingleStep(0.5)
        self._line_width.setDecimals(1)
        self._line_width.setValue(1.5)
        self._line_width.valueChanged.connect(self.changed)
        line_form.addRow("Width:", self._line_width)

        self._line_style = QComboBox()
        self._line_style.addItems(_LINE_STYLES)
        self._line_style.currentTextChanged.connect(lambda: self.changed.emit())
        line_form.addRow("Style:", self._line_style)

        layout.addWidget(line_group)

        # -- Marker --
        marker_group = QGroupBox("Marker")
        marker_form = QFormLayout(marker_group)

        self._marker_style = QComboBox()
        self._marker_style.addItems(_MARKER_STYLES)
        self._marker_style.currentTextChanged.connect(lambda: self.changed.emit())
        marker_form.addRow("Style:", self._marker_style)

        self._marker_size = QDoubleSpinBox()
        self._marker_size.setRange(0.5, 20.0)
        self._marker_size.setSingleStep(0.5)
        self._marker_size.setDecimals(1)
        self._marker_size.setValue(4.0)
        self._marker_size.valueChanged.connect(self.changed)
        marker_form.addRow("Size:", self._marker_size)

        layout.addWidget(marker_group)

        # -- Legend --
        legend_group = QGroupBox("Legend")
        legend_form = QFormLayout(legend_group)

        self._legend_label = QLineEdit()
        self._legend_label.setPlaceholderText("Auto (use series label)")
        self._legend_label.editingFinished.connect(self.changed)
        legend_form.addRow("Label:", self._legend_label)

        self._visible = QCheckBox("Visible")
        self._visible.setChecked(True)
        self._visible.toggled.connect(self.changed)
        legend_form.addRow(self._visible)

        layout.addWidget(legend_group)
        layout.addStretch()

    def load_from(self, ds: DataSeries) -> None:
        """Populate controls from a DataSeries."""
        self._current_uid = ds.uid
        self._block_all(True)

        self._color_edit.setText(ds.color or "")
        self._update_color_btn(ds.color or "")
        self._alpha.setValue(ds.alpha)
        self._show_line.setChecked(ds.show_line)
        self._line_width.setValue(ds.line_width if ds.line_width is not None else 1.5)
        self._line_style.setCurrentText(ds.line_style)
        marker = ds.marker_style if ds.marker_style is not None else "o"
        if marker not in _MARKER_STYLES:
            marker = "o"
        self._marker_style.setCurrentText(marker)
        self._marker_size.setValue(ds.marker_size if ds.marker_size is not None else 4.0)
        self._legend_label.setText(ds.legend_label or "")
        self._visible.setChecked(ds.visible)

        self._block_all(False)

    def write_to(self, ds: DataSeries) -> None:
        """Write control values into a DataSeries."""
        color_text = self._color_edit.text().strip()
        ds.color = color_text if color_text else None
        ds.alpha = self._alpha.value()
        ds.show_line = self._show_line.isChecked()
        ds.line_width = self._line_width.value()
        ds.line_style = self._line_style.currentText()
        marker = self._marker_style.currentText()
        ds.marker_style = marker if marker != "None" else None
        ds.marker_size = self._marker_size.value()
        label = self._legend_label.text().strip()
        ds.legend_label = label if label else None
        ds.visible = self._visible.isChecked()

    @property
    def current_uid(self) -> str:
        return self._current_uid

    def _pick_color(self) -> None:
        current = QtGui.QColor(self._color_edit.text() or "#000000")
        color = QColorDialog.getColor(current, self, "Pick Series Color")
        if color.isValid():
            hex_color = color.name()
            self._color_edit.setText(hex_color)
            self._update_color_btn(hex_color)
            self.changed.emit()

    def _on_color_text_changed(self) -> None:
        self._update_color_btn(self._color_edit.text())
        self.changed.emit()

    def _update_color_btn(self, color_str: str) -> None:
        if color_str:
            self._color_btn.setStyleSheet(
                f"background-color: {color_str}; border: 1px solid #888;"
            )
        else:
            self._color_btn.setStyleSheet("border: 1px solid #888;")

    def _block_all(self, block: bool) -> None:
        for w in (self._color_edit, self._alpha, self._show_line,
                  self._line_width, self._line_style, self._marker_style,
                  self._marker_size, self._legend_label, self._visible):
            w.blockSignals(block)
