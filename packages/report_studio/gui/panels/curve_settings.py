"""
Curve settings panel — per-curve style controls.

Shown in the Context tab when a curve is selected in the data tree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from ...qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
)
from .collapsible import CollapsibleSection

if TYPE_CHECKING:
    from ...core.models import OffsetCurve


_LINE_STYLES = [
    ("-", "Solid"),
    ("--", "Dashed"),
    ("-.", "Dash-dot"),
    (":", "Dotted"),
]

_MARKER_STYLES = [
    ("o", "Circle"),
    ("s", "Square"),
    ("^", "Triangle"),
    ("D", "Diamond"),
    ("none", "None"),
]


class CurveSettingsPanel(QtWidgets.QWidget):
    """
    Per-curve style settings (color, line width, line style, marker, etc.).

    Signals
    -------
    style_changed(str, str, object)
        (uid, attr, value) — emitted for single or batch selection.
    """

    style_changed = Signal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._current_uid: str = ""
        self._batch_uids: List[str] = []
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        sec = CollapsibleSection("Curve Style", expanded=True)
        fl = sec.form
        fl.setSpacing(4)

        # Name (read-only)
        self._lbl_name = QtWidgets.QLabel("—")
        self._lbl_name.setWordWrap(True)
        fl.addRow("Name:", self._lbl_name)

        # Color
        self._btn_color = QtWidgets.QPushButton()
        self._btn_color.setFixedSize(60, 24)
        self._btn_color.setToolTip("Click to change color")
        self._btn_color.clicked.connect(self._on_color_clicked)
        fl.addRow("Color:", self._btn_color)

        # Show line toggle
        self._chk_show_line = QtWidgets.QCheckBox("Show line")
        self._chk_show_line.setChecked(True)
        self._chk_show_line.toggled.connect(
            lambda v: self._emit_style("line_visible", v))
        fl.addRow("", self._chk_show_line)

        # Line width
        self._spin_lw = QtWidgets.QDoubleSpinBox()
        self._spin_lw.setRange(0.1, 10.0)
        self._spin_lw.setSingleStep(0.5)
        self._spin_lw.setValue(1.5)
        self._spin_lw.valueChanged.connect(
            lambda v: self._emit_style("line_width", v))
        fl.addRow("Line width:", self._spin_lw)

        # Line style
        self._combo_ls = QtWidgets.QComboBox()
        for code, label in _LINE_STYLES:
            self._combo_ls.addItem(label, code)
        self._combo_ls.currentIndexChanged.connect(self._on_line_style)
        fl.addRow("Line style:", self._combo_ls)

        # Show markers toggle
        self._chk_show_marker = QtWidgets.QCheckBox("Show markers")
        self._chk_show_marker.setChecked(True)
        self._chk_show_marker.toggled.connect(
            lambda v: self._emit_style("marker_visible", v))
        fl.addRow("", self._chk_show_marker)

        # Marker size
        self._spin_ms = QtWidgets.QDoubleSpinBox()
        self._spin_ms.setRange(0.0, 20.0)
        self._spin_ms.setSingleStep(0.5)
        self._spin_ms.setValue(4.0)
        self._spin_ms.valueChanged.connect(
            lambda v: self._emit_style("marker_size", v))
        fl.addRow("Marker size:", self._spin_ms)

        # Marker style
        self._combo_mk = QtWidgets.QComboBox()
        for code, label in _MARKER_STYLES:
            self._combo_mk.addItem(label, code)
        self._combo_mk.currentIndexChanged.connect(self._on_marker_style)
        fl.addRow("Marker:", self._combo_mk)

        # Points info
        self._lbl_points = QtWidgets.QLabel("—")
        fl.addRow("Points:", self._lbl_points)

        layout.addWidget(sec)

        # ── Peak Display section ──────────────────────────────────────
        peak_sec = CollapsibleSection("Peak Display", expanded=False)
        pl = peak_sec.form
        pl.setSpacing(4)

        # Peak color
        self._btn_peak_color = QtWidgets.QPushButton("Use curve color")
        self._btn_peak_color.setFixedSize(120, 24)
        self._btn_peak_color.clicked.connect(self._on_peak_color_clicked)
        pl.addRow("Peak color:", self._btn_peak_color)

        # Outline toggle
        self._chk_outline = QtWidgets.QCheckBox("Draw outline")
        self._chk_outline.setChecked(False)
        self._chk_outline.toggled.connect(
            lambda v: self._emit_style("peak_outline", v))
        pl.addRow("", self._chk_outline)

        # Outline color
        self._btn_outline_color = QtWidgets.QPushButton()
        self._btn_outline_color.setFixedSize(60, 24)
        self._btn_outline_color.setStyleSheet(
            "background-color: #000000; border: 1px solid #888;")
        self._btn_outline_color.clicked.connect(self._on_outline_color_clicked)
        pl.addRow("Outline color:", self._btn_outline_color)

        # Outline width
        self._spin_outline_w = QtWidgets.QDoubleSpinBox()
        self._spin_outline_w.setRange(0.5, 5.0)
        self._spin_outline_w.setSingleStep(0.5)
        self._spin_outline_w.setValue(1.0)
        self._spin_outline_w.valueChanged.connect(
            lambda v: self._emit_style("peak_outline_width", v))
        pl.addRow("Outline width:", self._spin_outline_w)

        layout.addWidget(peak_sec)
        layout.addStretch(1)

    # ── Public API ────────────────────────────────────────────────────

    def show_curve(self, curve: "OffsetCurve"):
        """Show single curve style."""
        self._updating = True
        self._current_uid = curve.uid
        self._batch_uids = []

        self._lbl_name.setText(curve.display_name)
        self._set_color_btn(curve.color)
        self._chk_show_line.setChecked(getattr(curve, "line_visible", True))
        self._spin_lw.setValue(curve.line_width)
        self._chk_show_marker.setChecked(getattr(curve, "marker_visible", True))
        self._spin_ms.setValue(curve.marker_size)

        # Line style
        ls = getattr(curve, "line_style", "-")
        for i in range(self._combo_ls.count()):
            if self._combo_ls.itemData(i) == ls:
                self._combo_ls.setCurrentIndex(i)
                break

        # Marker style
        mk = getattr(curve, "marker_style", "o")
        for i in range(self._combo_mk.count()):
            if self._combo_mk.itemData(i) == mk:
                self._combo_mk.setCurrentIndex(i)
                break

        n_vis = int(curve.point_mask.sum()) if curve.point_mask is not None else curve.n_points
        self._lbl_points.setText(f"{n_vis} / {curve.n_points}")

        # Peak display
        pc = getattr(curve, "peak_color", "")
        if pc:
            self._btn_peak_color.setText("")
            self._btn_peak_color.setStyleSheet(
                f"background-color: {pc}; border: 1px solid #888;")
        else:
            self._btn_peak_color.setText("Use curve color")
            self._btn_peak_color.setStyleSheet("")
        self._chk_outline.setChecked(getattr(curve, "peak_outline", False))
        oc = getattr(curve, "peak_outline_color", "#000000")
        self._btn_outline_color.setStyleSheet(
            f"background-color: {oc}; border: 1px solid #888;")
        self._btn_outline_color.setProperty("color", oc)
        self._spin_outline_w.setValue(
            getattr(curve, "peak_outline_width", 1.0))

        self._updating = False

    def show_curves_batch(self, uids: List[str], curves: List["OffsetCurve"]):
        """Show batch-editable values for multiple curves."""
        self._updating = True
        self._batch_uids = list(uids)
        self._current_uid = uids[0] if uids else ""

        self._lbl_name.setText(f"{len(uids)} curves selected")
        if curves:
            c = curves[0]
            self._set_color_btn(c.color)
            self._spin_lw.setValue(c.line_width)
            self._spin_ms.setValue(c.marker_size)
            total = sum(cc.n_points for cc in curves)
            self._lbl_points.setText(f"{total} total points")

        self._updating = False

    def clear(self):
        """Reset to empty state."""
        self._current_uid = ""
        self._batch_uids = []

    # ── Internal ──────────────────────────────────────────────────────

    def _emit_style(self, attr: str, value):
        if self._updating:
            return
        if self._batch_uids and len(self._batch_uids) > 1:
            for uid in self._batch_uids:
                self.style_changed.emit(uid, attr, value)
        elif self._current_uid:
            self.style_changed.emit(self._current_uid, attr, value)

    def _set_color_btn(self, color: str):
        self._btn_color.setStyleSheet(
            f"background-color: {color}; border: 1px solid #888;")
        self._btn_color.setProperty("color", color)

    def _on_color_clicked(self):
        current = self._btn_color.property("color") or "#2196F3"
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(current), self, "Curve Color")
        if color.isValid():
            hex_c = color.name()
            self._set_color_btn(hex_c)
            self._emit_style("color", hex_c)

    def _on_line_style(self, idx):
        code = self._combo_ls.itemData(idx)
        if code:
            self._emit_style("line_style", code)

    def _on_marker_style(self, idx):
        code = self._combo_mk.itemData(idx)
        if code:
            self._emit_style("marker_style", code)

    def _on_peak_color_clicked(self):
        current = self._btn_peak_color.property("color") or "#FFFFFF"
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(current), self, "Peak Color")
        if color.isValid():
            hex_c = color.name()
            self._btn_peak_color.setText("")
            self._btn_peak_color.setStyleSheet(
                f"background-color: {hex_c}; border: 1px solid #888;")
            self._btn_peak_color.setProperty("color", hex_c)
            self._emit_style("peak_color", hex_c)

    def _on_outline_color_clicked(self):
        current = self._btn_outline_color.property("color") or "#000000"
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(current), self, "Outline Color")
        if color.isValid():
            hex_c = color.name()
            self._btn_outline_color.setStyleSheet(
                f"background-color: {hex_c}; border: 1px solid #888;")
            self._btn_outline_color.setProperty("color", hex_c)
            self._emit_style("peak_outline_color", hex_c)
