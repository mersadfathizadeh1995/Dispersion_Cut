"""
Aggregated curve settings panel — per-aggregate style controls.

Shown in the Context tab when an aggregated curve node is selected
in the data tree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
)
from .collapsible import CollapsibleSection

if TYPE_CHECKING:
    from ...core.models import AggregatedCurve


_LINE_STYLES = [
    ("-", "Solid"),
    ("--", "Dashed"),
    ("-.", "Dash-dot"),
    (":", "Dotted"),
    ("none", "None"),
]

_MARKER_STYLES = [
    ("o", "Circle"),
    ("s", "Square"),
    ("^", "Triangle"),
    ("D", "Diamond"),
    ("none", "None"),
]


class AggregatedSettingsPanel(QtWidgets.QWidget):
    """
    Per-aggregated-curve style settings.

    Signals
    -------
    aggregated_style_changed(str, str, object)
        (uid, attr, value)
    """

    aggregated_style_changed = Signal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._current_uid: str = ""
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ── Average Line section ─────────────────────────────────────
        sec_avg = CollapsibleSection("Average Line", expanded=True)
        fl = sec_avg.form
        fl.setSpacing(4)

        self._lbl_name = QtWidgets.QLabel("—")
        self._lbl_name.setWordWrap(True)
        fl.addRow("Name:", self._lbl_name)

        self._chk_avg_visible = QtWidgets.QCheckBox("Visible")
        self._chk_avg_visible.setChecked(True)
        self._chk_avg_visible.toggled.connect(
            lambda v: self._emit("avg_visible", v))
        fl.addRow("", self._chk_avg_visible)

        self._btn_avg_color = QtWidgets.QPushButton()
        self._btn_avg_color.setFixedSize(60, 24)
        self._btn_avg_color.clicked.connect(self._on_avg_color)
        fl.addRow("Color:", self._btn_avg_color)

        self._spin_avg_lw = QtWidgets.QDoubleSpinBox()
        self._spin_avg_lw.setRange(0.5, 10.0)
        self._spin_avg_lw.setSingleStep(0.5)
        self._spin_avg_lw.setValue(2.0)
        self._spin_avg_lw.valueChanged.connect(
            lambda v: self._emit("avg_line_width", v))
        fl.addRow("Line width:", self._spin_avg_lw)

        self._combo_avg_ls = QtWidgets.QComboBox()
        for code, label in _LINE_STYLES:
            self._combo_avg_ls.addItem(label, code)
        self._combo_avg_ls.currentIndexChanged.connect(
            lambda: self._emit("avg_line_style",
                               self._combo_avg_ls.currentData()))
        fl.addRow("Line style:", self._combo_avg_ls)

        self._combo_avg_mk = QtWidgets.QComboBox()
        for code, label in _MARKER_STYLES:
            self._combo_avg_mk.addItem(label, code)
        self._combo_avg_mk.currentIndexChanged.connect(
            lambda: self._emit("avg_marker_style",
                               self._combo_avg_mk.currentData()))
        fl.addRow("Marker:", self._combo_avg_mk)

        self._spin_avg_ms = QtWidgets.QDoubleSpinBox()
        self._spin_avg_ms.setRange(0.0, 20.0)
        self._spin_avg_ms.setSingleStep(0.5)
        self._spin_avg_ms.setValue(0.0)
        self._spin_avg_ms.valueChanged.connect(
            lambda v: self._emit("avg_marker_size", v))
        fl.addRow("Marker size:", self._spin_avg_ms)

        layout.addWidget(sec_avg)

        # ── Uncertainty section ──────────────────────────────────────
        sec_unc = CollapsibleSection("Uncertainty", expanded=True)
        ul = sec_unc.form
        ul.setSpacing(4)

        self._chk_unc_visible = QtWidgets.QCheckBox("Visible")
        self._chk_unc_visible.setChecked(True)
        self._chk_unc_visible.toggled.connect(
            lambda v: self._emit("uncertainty_visible", v))
        ul.addRow("", self._chk_unc_visible)

        self._combo_unc_mode = QtWidgets.QComboBox()
        self._combo_unc_mode.addItem("Band (fill_between)", "band")
        self._combo_unc_mode.addItem("Errorbars", "errorbar")
        self._combo_unc_mode.currentIndexChanged.connect(
            lambda: self._emit("uncertainty_mode",
                               self._combo_unc_mode.currentData()))
        ul.addRow("Mode:", self._combo_unc_mode)

        self._spin_unc_alpha = QtWidgets.QDoubleSpinBox()
        self._spin_unc_alpha.setRange(0.0, 1.0)
        self._spin_unc_alpha.setSingleStep(0.05)
        self._spin_unc_alpha.setValue(0.25)
        self._spin_unc_alpha.valueChanged.connect(
            lambda v: self._emit("uncertainty_alpha", v))
        ul.addRow("Alpha:", self._spin_unc_alpha)

        self._btn_unc_color = QtWidgets.QPushButton()
        self._btn_unc_color.setFixedSize(60, 24)
        self._btn_unc_color.clicked.connect(self._on_unc_color)
        ul.addRow("Color:", self._btn_unc_color)

        layout.addWidget(sec_unc)

        # ── Shadow Curves section ────────────────────────────────────
        sec_shadow = CollapsibleSection("Shadow Curves", expanded=False)
        sl = sec_shadow.form
        sl.setSpacing(4)

        self._chk_shadow_visible = QtWidgets.QCheckBox("Visible")
        self._chk_shadow_visible.setChecked(True)
        self._chk_shadow_visible.toggled.connect(
            lambda v: self._emit("shadow_visible", v))
        sl.addRow("", self._chk_shadow_visible)

        self._spin_shadow_alpha = QtWidgets.QDoubleSpinBox()
        self._spin_shadow_alpha.setRange(0.0, 1.0)
        self._spin_shadow_alpha.setSingleStep(0.05)
        self._spin_shadow_alpha.setValue(0.15)
        self._spin_shadow_alpha.valueChanged.connect(
            lambda v: self._emit("shadow_alpha", v))
        sl.addRow("Alpha:", self._spin_shadow_alpha)

        layout.addWidget(sec_shadow)

        # ── Binning section ──────────────────────────────────────────
        sec_bin = CollapsibleSection("Binning", expanded=False)
        bl = sec_bin.form
        bl.setSpacing(4)

        self._spin_bins = QtWidgets.QSpinBox()
        self._spin_bins.setRange(10, 200)
        self._spin_bins.setValue(50)
        self._spin_bins.valueChanged.connect(
            lambda v: self._emit("num_bins", v))
        bl.addRow("Num bins:", self._spin_bins)

        self._spin_bias = QtWidgets.QDoubleSpinBox()
        self._spin_bias.setRange(0.1, 2.0)
        self._spin_bias.setSingleStep(0.1)
        self._spin_bias.setValue(0.7)
        self._spin_bias.valueChanged.connect(
            lambda v: self._emit("log_bias", v))
        bl.addRow("Log bias:", self._spin_bias)

        layout.addWidget(sec_bin)
        layout.addStretch(1)

    # ── Public API ────────────────────────────────────────────────────

    def show_aggregated(self, agg: "AggregatedCurve"):
        """Populate controls from an AggregatedCurve model."""
        self._updating = True
        self._current_uid = agg.uid

        self._lbl_name.setText(agg.display_name)
        self._set_color_btn(self._btn_avg_color, agg.avg_color)
        self._chk_avg_visible.setChecked(agg.avg_visible)
        self._spin_avg_lw.setValue(agg.avg_line_width)
        self._select_combo(self._combo_avg_ls, agg.avg_line_style)
        self._select_combo(self._combo_avg_mk, agg.avg_marker_style)
        self._spin_avg_ms.setValue(agg.avg_marker_size)

        self._chk_unc_visible.setChecked(agg.uncertainty_visible)
        self._select_combo(self._combo_unc_mode, agg.uncertainty_mode)
        self._spin_unc_alpha.setValue(agg.uncertainty_alpha)
        unc_clr = agg.effective_uncertainty_color
        self._set_color_btn(self._btn_unc_color, unc_clr)

        self._chk_shadow_visible.setChecked(agg.shadow_visible)
        self._spin_shadow_alpha.setValue(agg.shadow_alpha)

        self._spin_bins.setValue(agg.num_bins)
        self._spin_bias.setValue(agg.log_bias)

        self._updating = False

    # ── Internals ─────────────────────────────────────────────────────

    def _emit(self, attr: str, value):
        if not self._updating and self._current_uid:
            self.aggregated_style_changed.emit(self._current_uid, attr, value)

    def _on_avg_color(self):
        color = QtWidgets.QColorDialog.getColor(parent=self)
        if color.isValid():
            self._set_color_btn(self._btn_avg_color, color.name())
            self._emit("avg_color", color.name())

    def _on_unc_color(self):
        color = QtWidgets.QColorDialog.getColor(parent=self)
        if color.isValid():
            self._set_color_btn(self._btn_unc_color, color.name())
            self._emit("uncertainty_color", color.name())

    @staticmethod
    def _set_color_btn(btn: QtWidgets.QPushButton, color_str: str):
        btn.setStyleSheet(
            f"background-color: {color_str}; border: 1px solid #888;")

    @staticmethod
    def _select_combo(combo: QtWidgets.QComboBox, value):
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
