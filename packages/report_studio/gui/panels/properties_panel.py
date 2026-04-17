"""
Properties panel — right dock for curve style + subplot settings.

Shows context-sensitive controls: when a curve is selected, show curve
style editors; when a subplot is selected, show subplot settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
    Horizontal, Vertical,
    PolicyMinimum, PolicyExpanding, PolicyPreferred,
)

if TYPE_CHECKING:
    from ...core.models import OffsetCurve, SubplotState


class PropertiesPanel(QtWidgets.QWidget):
    """
    Right dock panel — curve style + subplot axis settings.

    Signals
    -------
    style_changed(str, str, object)
        (uid, attribute_name, new_value) — e.g. ("abc123", "color", "#FF0000")
    subplot_setting_changed(str, str, object)
        (subplot_key, attribute_name, new_value)
    """

    style_changed = Signal(str, str, object)
    subplot_setting_changed = Signal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(220)
        self.setMaximumWidth(350)

        self._current_uid: str = ""
        self._current_subplot_key: str = ""
        self._batch_uids: list = []
        self._updating = False  # guard against feedback loops

        self._build_ui()

    # ── Build UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # ── Curve Style Group ─────────────────────────────────────────
        self._curve_group = QtWidgets.QGroupBox("Curve Style")
        cg_layout = QtWidgets.QFormLayout()
        cg_layout.setSpacing(4)

        # Name label
        self._lbl_name = QtWidgets.QLabel("—")
        self._lbl_name.setWordWrap(True)
        cg_layout.addRow("Name:", self._lbl_name)

        # Color picker
        self._btn_color = QtWidgets.QPushButton()
        self._btn_color.setFixedSize(60, 24)
        self._btn_color.setToolTip("Click to change color")
        self._btn_color.clicked.connect(self._on_color_clicked)
        cg_layout.addRow("Color:", self._btn_color)

        # Line width
        self._spin_line_width = QtWidgets.QDoubleSpinBox()
        self._spin_line_width.setRange(0.1, 10.0)
        self._spin_line_width.setSingleStep(0.5)
        self._spin_line_width.setValue(1.5)
        self._spin_line_width.valueChanged.connect(
            lambda v: self._emit_style("line_width", v)
        )
        cg_layout.addRow("Line width:", self._spin_line_width)

        # Marker size
        self._spin_marker = QtWidgets.QDoubleSpinBox()
        self._spin_marker.setRange(0.0, 20.0)
        self._spin_marker.setSingleStep(0.5)
        self._spin_marker.setValue(4.0)
        self._spin_marker.valueChanged.connect(
            lambda v: self._emit_style("marker_size", v)
        )
        cg_layout.addRow("Marker size:", self._spin_marker)

        # Points info
        self._lbl_points = QtWidgets.QLabel("—")
        cg_layout.addRow("Points:", self._lbl_points)

        self._curve_group.setLayout(cg_layout)
        layout.addWidget(self._curve_group)

        # ── Subplot Settings Group ────────────────────────────────────
        self._subplot_group = QtWidgets.QGroupBox("Subplot Settings")
        sg_layout = QtWidgets.QFormLayout()
        sg_layout.setSpacing(4)

        # Domain selector
        self._combo_domain = QtWidgets.QComboBox()
        self._combo_domain.addItems(["frequency", "wavelength"])
        self._combo_domain.currentTextChanged.connect(
            lambda v: self._emit_subplot("x_domain", v)
        )
        sg_layout.addRow("X domain:", self._combo_domain)

        # Auto X / manual X range
        self._chk_auto_x = QtWidgets.QCheckBox("Auto")
        self._chk_auto_x.setChecked(True)
        self._chk_auto_x.toggled.connect(self._on_auto_x_toggled)
        x_row = QtWidgets.QHBoxLayout()
        self._spin_xmin = QtWidgets.QDoubleSpinBox()
        self._spin_xmin.setRange(0, 99999)
        self._spin_xmin.setDecimals(1)
        self._spin_xmin.setEnabled(False)
        self._spin_xmax = QtWidgets.QDoubleSpinBox()
        self._spin_xmax.setRange(0, 99999)
        self._spin_xmax.setDecimals(1)
        self._spin_xmax.setEnabled(False)
        x_row.addWidget(self._spin_xmin)
        x_row.addWidget(QtWidgets.QLabel("–"))
        x_row.addWidget(self._spin_xmax)
        x_row.addWidget(self._chk_auto_x)
        sg_layout.addRow("X range:", x_row)

        # Apply button for manual range
        self._btn_apply_x = QtWidgets.QPushButton("Apply X")
        self._btn_apply_x.setEnabled(False)
        self._btn_apply_x.clicked.connect(self._on_apply_x)
        sg_layout.addRow("", self._btn_apply_x)

        # Auto Y / manual Y range
        self._chk_auto_y = QtWidgets.QCheckBox("Auto")
        self._chk_auto_y.setChecked(True)
        self._chk_auto_y.toggled.connect(self._on_auto_y_toggled)
        y_row = QtWidgets.QHBoxLayout()
        self._spin_ymin = QtWidgets.QDoubleSpinBox()
        self._spin_ymin.setRange(0, 99999)
        self._spin_ymin.setDecimals(1)
        self._spin_ymin.setEnabled(False)
        self._spin_ymax = QtWidgets.QDoubleSpinBox()
        self._spin_ymax.setRange(0, 99999)
        self._spin_ymax.setDecimals(1)
        self._spin_ymax.setEnabled(False)
        y_row.addWidget(self._spin_ymin)
        y_row.addWidget(QtWidgets.QLabel("–"))
        y_row.addWidget(self._spin_ymax)
        y_row.addWidget(self._chk_auto_y)
        sg_layout.addRow("Y range:", y_row)

        self._btn_apply_y = QtWidgets.QPushButton("Apply Y")
        self._btn_apply_y.setEnabled(False)
        self._btn_apply_y.clicked.connect(self._on_apply_y)
        sg_layout.addRow("", self._btn_apply_y)

        self._subplot_group.setLayout(sg_layout)
        layout.addWidget(self._subplot_group)

        layout.addStretch(1)

        # Initially hidden until selection
        self._curve_group.setVisible(False)

    # ── Public API ────────────────────────────────────────────────────

    def show_curve(self, curve: "OffsetCurve"):
        """Populate curve style editors from a selected curve."""
        self._updating = True
        self._current_uid = curve.uid
        self._batch_uids = []
        self._curve_group.setVisible(True)
        self._curve_group.setTitle("Curve Style")

        self._lbl_name.setText(curve.display_name)
        self._set_color_button(curve.color)
        self._spin_line_width.setValue(curve.line_width)
        self._spin_marker.setValue(curve.marker_size)

        n_vis = int(curve.point_mask.sum()) if curve.point_mask is not None else curve.n_points
        self._lbl_points.setText(f"{n_vis} / {curve.n_points}")

        self._updating = False

    def show_subplot(self, sp: "SubplotState"):
        """Populate subplot settings from a selected subplot."""
        self._updating = True
        self._current_subplot_key = sp.key

        idx = self._combo_domain.findText(sp.x_domain)
        if idx >= 0:
            self._combo_domain.setCurrentIndex(idx)

        self._chk_auto_x.setChecked(sp.auto_x)
        self._chk_auto_y.setChecked(sp.auto_y)

        if sp.x_range:
            self._spin_xmin.setValue(sp.x_range[0])
            self._spin_xmax.setValue(sp.x_range[1])
        if sp.y_range:
            self._spin_ymin.setValue(sp.y_range[0])
            self._spin_ymax.setValue(sp.y_range[1])

        self._updating = False

    def clear_curve(self):
        """Hide curve editors."""
        self._curve_group.setVisible(False)
        self._current_uid = ""
        self._batch_uids = []

    def show_curves_batch(self, uids: list, curves: list):
        """Show batch curve editors for multiple selected curves."""
        self._updating = True
        self._batch_uids = list(uids)
        self._current_uid = uids[0] if uids else ""
        self._curve_group.setVisible(True)
        self._curve_group.setTitle(f"Curve Style ({len(uids)} selected)")

        # Show first curve's values as placeholder
        if curves:
            c = curves[0]
            self._lbl_name.setText(f"{len(uids)} curves selected")
            self._set_color_button(c.color)
            self._spin_line_width.setValue(c.line_width)
            self._spin_marker.setValue(c.marker_size)
            total = sum(cc.n_points for cc in curves)
            self._lbl_points.setText(f"{total} total points")

        self._updating = False

    # ── Internal handlers ─────────────────────────────────────────────

    def _emit_style(self, attr: str, value):
        if self._updating:
            return
        if self._batch_uids and len(self._batch_uids) > 1:
            for uid in self._batch_uids:
                self.style_changed.emit(uid, attr, value)
        elif self._current_uid:
            self.style_changed.emit(self._current_uid, attr, value)

    def _emit_subplot(self, attr: str, value):
        if not self._updating and self._current_subplot_key:
            self.subplot_setting_changed.emit(
                self._current_subplot_key, attr, value
            )

    def _set_color_button(self, color: str):
        self._btn_color.setStyleSheet(
            f"background-color: {color}; border: 1px solid #888;"
        )
        self._btn_color.setProperty("color", color)

    def _on_color_clicked(self):
        current = self._btn_color.property("color") or "#2196F3"
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(current), self, "Curve Color"
        )
        if color.isValid():
            hex_color = color.name()
            self._set_color_button(hex_color)
            self._emit_style("color", hex_color)

    def _on_auto_x_toggled(self, checked):
        self._spin_xmin.setEnabled(not checked)
        self._spin_xmax.setEnabled(not checked)
        self._btn_apply_x.setEnabled(not checked)
        if not self._updating:
            self._emit_subplot("auto_x", checked)

    def _on_auto_y_toggled(self, checked):
        self._spin_ymin.setEnabled(not checked)
        self._spin_ymax.setEnabled(not checked)
        self._btn_apply_y.setEnabled(not checked)
        if not self._updating:
            self._emit_subplot("auto_y", checked)

    def _on_apply_x(self):
        xmin = self._spin_xmin.value()
        xmax = self._spin_xmax.value()
        if xmax > xmin:
            self._emit_subplot("x_range", (xmin, xmax))

    def _on_apply_y(self):
        ymin = self._spin_ymin.value()
        ymax = self._spin_ymax.value()
        if ymax > ymin:
            self._emit_subplot("y_range", (ymin, ymax))
