"""
Subplot settings panel — rich per-subplot configuration.

Shown in the Context tab when a subplot is selected (via tree or canvas click).
Sections: Title & Labels, X Axis, Y Axis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
    Horizontal, PolicyExpanding,
)
from .collapsible import CollapsibleSection

if TYPE_CHECKING:
    from ...core.models import SubplotState


class SubplotSettingsPanel(QtWidgets.QWidget):
    """
    Rich subplot settings with collapsible sections.

    Signals
    -------
    setting_changed(str, str, object)
        (subplot_key, attribute_name, new_value)
    """

    setting_changed = Signal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._subplot_key = ""
        self._batch_keys: list = []
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Selection info label
        self._lbl_selection = QtWidgets.QLabel("")
        self._lbl_selection.setStyleSheet(
            "font-weight: bold; color: #3399FF; padding: 2px 4px;")
        self._lbl_selection.setVisible(False)
        layout.addWidget(self._lbl_selection)

        # ── Title & Labels ────────────────────────────────────────────
        title_sec = CollapsibleSection("Title && Labels", expanded=True)
        tl = title_sec.form
        tl.setSpacing(4)

        self._edit_name = QtWidgets.QLineEdit()
        self._edit_name.setPlaceholderText("Subplot name")
        self._edit_name.editingFinished.connect(
            lambda: self._emit("name", self._edit_name.text()))
        tl.addRow("Name:", self._edit_name)

        self._combo_font = QtWidgets.QFontComboBox()
        self._combo_font.currentFontChanged.connect(
            lambda f: self._emit("font_family", f.family()))
        tl.addRow("Font:", self._combo_font)

        self._spin_title_size = QtWidgets.QSpinBox()
        self._spin_title_size.setRange(0, 36)
        self._spin_title_size.setSpecialValueText("Global")
        self._spin_title_size.valueChanged.connect(
            lambda v: self._emit("title_font_size", v))
        tl.addRow("Title size:", self._spin_title_size)

        self._spin_label_size = QtWidgets.QSpinBox()
        self._spin_label_size.setRange(0, 30)
        self._spin_label_size.setSpecialValueText("Global")
        self._spin_label_size.valueChanged.connect(
            lambda v: self._emit("axis_label_font_size", v))
        tl.addRow("Label size:", self._spin_label_size)

        self._spin_tick_size = QtWidgets.QSpinBox()
        self._spin_tick_size.setRange(0, 24)
        self._spin_tick_size.setSpecialValueText("Global")
        self._spin_tick_size.valueChanged.connect(
            lambda v: self._emit("tick_label_font_size", v))
        tl.addRow("Tick size:", self._spin_tick_size)

        layout.addWidget(title_sec)

        # ── X Axis ────────────────────────────────────────────────────
        x_sec = CollapsibleSection("X Axis", expanded=True)
        xl = x_sec.form
        xl.setSpacing(4)

        self._combo_domain = QtWidgets.QComboBox()
        self._combo_domain.addItems(["frequency", "wavelength"])
        self._combo_domain.currentTextChanged.connect(
            lambda v: self._emit("x_domain", v))
        xl.addRow("Domain:", self._combo_domain)

        self._combo_xscale = QtWidgets.QComboBox()
        self._combo_xscale.addItems(["linear", "log"])
        self._combo_xscale.currentTextChanged.connect(
            lambda v: self._emit("x_scale", v))
        xl.addRow("Scale:", self._combo_xscale)

        self._combo_xtick = QtWidgets.QComboBox()
        self._combo_xtick.addItems(["plain", "sci", "eng"])
        self._combo_xtick.currentTextChanged.connect(
            lambda v: self._emit("x_tick_format", v))
        xl.addRow("Tick format:", self._combo_xtick)

        # Auto + manual range
        self._chk_auto_x = QtWidgets.QCheckBox("Auto")
        self._chk_auto_x.setChecked(True)
        self._chk_auto_x.toggled.connect(self._on_auto_x)
        x_range = QtWidgets.QHBoxLayout()
        self._spin_xmin = QtWidgets.QDoubleSpinBox()
        self._spin_xmin.setRange(0, 99999)
        self._spin_xmin.setDecimals(2)
        self._spin_xmin.setEnabled(False)
        self._spin_xmax = QtWidgets.QDoubleSpinBox()
        self._spin_xmax.setRange(0, 99999)
        self._spin_xmax.setDecimals(2)
        self._spin_xmax.setEnabled(False)
        x_range.addWidget(self._spin_xmin)
        x_range.addWidget(QtWidgets.QLabel("–"))
        x_range.addWidget(self._spin_xmax)
        x_range.addWidget(self._chk_auto_x)
        xl.addRow("Range:", x_range)

        self._btn_apply_x = QtWidgets.QPushButton("Apply")
        self._btn_apply_x.setEnabled(False)
        self._btn_apply_x.clicked.connect(self._apply_x)
        xl.addRow("", self._btn_apply_x)

        self._edit_xlabel = QtWidgets.QLineEdit()
        self._edit_xlabel.setPlaceholderText("Default label")
        self._edit_xlabel.editingFinished.connect(
            lambda: self._emit("x_label", self._edit_xlabel.text()))
        xl.addRow("Label:", self._edit_xlabel)

        layout.addWidget(x_sec)

        # ── Y Axis ────────────────────────────────────────────────────
        y_sec = CollapsibleSection("Y Axis", expanded=True)
        yl = y_sec.form
        yl.setSpacing(4)

        self._combo_yscale = QtWidgets.QComboBox()
        self._combo_yscale.addItems(["linear", "log"])
        self._combo_yscale.currentTextChanged.connect(
            lambda v: self._emit("y_scale", v))
        yl.addRow("Scale:", self._combo_yscale)

        self._combo_ytick = QtWidgets.QComboBox()
        self._combo_ytick.addItems(["plain", "sci", "eng"])
        self._combo_ytick.currentTextChanged.connect(
            lambda v: self._emit("y_tick_format", v))
        yl.addRow("Tick format:", self._combo_ytick)

        self._chk_auto_y = QtWidgets.QCheckBox("Auto")
        self._chk_auto_y.setChecked(True)
        self._chk_auto_y.toggled.connect(self._on_auto_y)
        y_range = QtWidgets.QHBoxLayout()
        self._spin_ymin = QtWidgets.QDoubleSpinBox()
        self._spin_ymin.setRange(0, 99999)
        self._spin_ymin.setDecimals(2)
        self._spin_ymin.setEnabled(False)
        self._spin_ymax = QtWidgets.QDoubleSpinBox()
        self._spin_ymax.setRange(0, 99999)
        self._spin_ymax.setDecimals(2)
        self._spin_ymax.setEnabled(False)
        y_range.addWidget(self._spin_ymin)
        y_range.addWidget(QtWidgets.QLabel("–"))
        y_range.addWidget(self._spin_ymax)
        y_range.addWidget(self._chk_auto_y)
        yl.addRow("Range:", y_range)

        self._btn_apply_y = QtWidgets.QPushButton("Apply")
        self._btn_apply_y.setEnabled(False)
        self._btn_apply_y.clicked.connect(self._apply_y)
        yl.addRow("", self._btn_apply_y)

        self._edit_ylabel = QtWidgets.QLineEdit()
        self._edit_ylabel.setPlaceholderText("Default label")
        self._edit_ylabel.editingFinished.connect(
            lambda: self._emit("y_label", self._edit_ylabel.text()))
        yl.addRow("Label:", self._edit_ylabel)

        layout.addWidget(y_sec)

        layout.addStretch(1)

    # ── Public API ────────────────────────────────────────────────────

    def show_subplot(self, sp: "SubplotState"):
        """Populate from a SubplotState."""
        self._updating = True
        self._subplot_key = sp.key
        self._batch_keys = []
        self._lbl_selection.setVisible(False)

        self._edit_name.setText(sp.name)

        # Font
        if sp.font_family:
            self._combo_font.setCurrentFont(QtGui.QFont(sp.font_family))
        self._spin_title_size.setValue(sp.title_font_size)
        self._spin_label_size.setValue(sp.axis_label_font_size)
        self._spin_tick_size.setValue(sp.tick_label_font_size)

        # X axis
        idx = self._combo_domain.findText(sp.x_domain)
        if idx >= 0:
            self._combo_domain.setCurrentIndex(idx)
        idx = self._combo_xscale.findText(sp.x_scale)
        if idx >= 0:
            self._combo_xscale.setCurrentIndex(idx)
        idx = self._combo_xtick.findText(sp.x_tick_format)
        if idx >= 0:
            self._combo_xtick.setCurrentIndex(idx)
        self._chk_auto_x.setChecked(sp.auto_x)
        if sp.x_range:
            self._spin_xmin.setValue(sp.x_range[0])
            self._spin_xmax.setValue(sp.x_range[1])
        self._edit_xlabel.setText(sp.x_label)

        # Y axis
        idx = self._combo_yscale.findText(sp.y_scale)
        if idx >= 0:
            self._combo_yscale.setCurrentIndex(idx)
        idx = self._combo_ytick.findText(sp.y_tick_format)
        if idx >= 0:
            self._combo_ytick.setCurrentIndex(idx)
        self._chk_auto_y.setChecked(sp.auto_y)
        if sp.y_range:
            self._spin_ymin.setValue(sp.y_range[0])
            self._spin_ymax.setValue(sp.y_range[1])
        self._edit_ylabel.setText(sp.y_label)

        self._updating = False

    def show_subplots_batch(self, keys: list, subplots: list):
        """Batch editing for multiple subplots — common settings apply to all."""
        self._updating = True
        self._batch_keys = list(keys)
        self._subplot_key = keys[0] if keys else ""

        self._lbl_selection.setText(f"{len(keys)} subplots selected")
        self._lbl_selection.setVisible(True)

        # Show first subplot's values as a reference
        if subplots:
            sp = subplots[0]
            self._edit_name.setText("")
            self._edit_name.setPlaceholderText("(multiple)")
            if sp.font_family:
                self._combo_font.setCurrentFont(QtGui.QFont(sp.font_family))
            self._spin_title_size.setValue(sp.title_font_size)
            self._spin_label_size.setValue(sp.axis_label_font_size)
            self._spin_tick_size.setValue(sp.tick_label_font_size)

            idx = self._combo_domain.findText(sp.x_domain)
            if idx >= 0:
                self._combo_domain.setCurrentIndex(idx)
            idx = self._combo_xscale.findText(sp.x_scale)
            if idx >= 0:
                self._combo_xscale.setCurrentIndex(idx)
            idx = self._combo_yscale.findText(sp.y_scale)
            if idx >= 0:
                self._combo_yscale.setCurrentIndex(idx)

        self._updating = False

    def clear(self):
        """Reset to empty state."""
        self._subplot_key = ""

    # ── Internal ──────────────────────────────────────────────────────

    def _emit(self, attr: str, value):
        if self._updating:
            return
        if self._batch_keys and len(self._batch_keys) > 1:
            for key in self._batch_keys:
                self.setting_changed.emit(key, attr, value)
        elif self._subplot_key:
            self.setting_changed.emit(self._subplot_key, attr, value)

    def _on_auto_x(self, checked):
        self._spin_xmin.setEnabled(not checked)
        self._spin_xmax.setEnabled(not checked)
        self._btn_apply_x.setEnabled(not checked)
        if not self._updating:
            self._emit("auto_x", checked)

    def _on_auto_y(self, checked):
        self._spin_ymin.setEnabled(not checked)
        self._spin_ymax.setEnabled(not checked)
        self._btn_apply_y.setEnabled(not checked)
        if not self._updating:
            self._emit("auto_y", checked)

    def _apply_x(self):
        xmin, xmax = self._spin_xmin.value(), self._spin_xmax.value()
        if xmax > xmin:
            self._emit("x_range", (xmin, xmax))

    def _apply_y(self):
        ymin, ymax = self._spin_ymin.value(), self._spin_ymax.value()
        if ymax > ymin:
            self._emit("y_range", (ymin, ymax))
