"""
Global settings panel — sheet-level controls.

Tab 2 of the right panel: grid layout, figure dimensions, margins,
canvas quality, legend defaults, background.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
    Horizontal, PolicyExpanding,
)
from .collapsible import CollapsibleSection

if TYPE_CHECKING:
    from ...core.models import SheetState


class GlobalSettingsPanel(QtWidgets.QWidget):
    """
    Global settings for the current sheet.

    Signals
    -------
    grid_changed(int, int)
    layout_changed(str, object)
    legend_changed(str, object)
    """

    grid_changed = Signal(int, int)
    layout_changed = Signal(str, object)
    legend_changed = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ── Grid Layout ──────────────────────────────────────────────
        grid_sec = CollapsibleSection("Grid Layout", expanded=True)
        gl = grid_sec.form
        gl.setSpacing(4)

        self._spin_rows = QtWidgets.QSpinBox()
        self._spin_rows.setRange(1, 6)
        self._spin_rows.setValue(1)
        self._spin_rows.valueChanged.connect(self._on_grid_spin)
        gl.addRow("Rows:", self._spin_rows)

        self._spin_cols = QtWidgets.QSpinBox()
        self._spin_cols.setRange(1, 6)
        self._spin_cols.setValue(1)
        self._spin_cols.valueChanged.connect(self._on_grid_spin)
        gl.addRow("Columns:", self._spin_cols)

        layout.addWidget(grid_sec)

        # ── Figure Dimensions ────────────────────────────────────────
        dim_sec = CollapsibleSection("Figure Dimensions", expanded=True)
        dl = dim_sec.form
        dl.setSpacing(4)

        self._spin_fig_w = QtWidgets.QDoubleSpinBox()
        self._spin_fig_w.setRange(4.0, 30.0)
        self._spin_fig_w.setSingleStep(0.5)
        self._spin_fig_w.setDecimals(1)
        self._spin_fig_w.setValue(10.0)
        self._spin_fig_w.setSuffix(" in")
        self._spin_fig_w.valueChanged.connect(
            lambda v: self._emit_layout("figure_width", v))
        dl.addRow("Width:", self._spin_fig_w)

        self._spin_fig_h = QtWidgets.QDoubleSpinBox()
        self._spin_fig_h.setRange(3.0, 24.0)
        self._spin_fig_h.setSingleStep(0.5)
        self._spin_fig_h.setDecimals(1)
        self._spin_fig_h.setValue(7.0)
        self._spin_fig_h.setSuffix(" in")
        self._spin_fig_h.valueChanged.connect(
            lambda v: self._emit_layout("figure_height", v))
        dl.addRow("Height:", self._spin_fig_h)

        layout.addWidget(dim_sec)

        # ── Margins (numeric spinboxes, NOT sliders) ─────────────────
        margin_sec = CollapsibleSection("Margins", expanded=True)
        ml = margin_sec.form
        ml.setSpacing(4)

        self._spin_hspace = QtWidgets.QDoubleSpinBox()
        self._spin_hspace.setRange(0.0, 1.0)
        self._spin_hspace.setSingleStep(0.05)
        self._spin_hspace.setDecimals(2)
        self._spin_hspace.setValue(0.30)
        self._spin_hspace.setToolTip("Vertical gap between subplot rows")
        self._spin_hspace.valueChanged.connect(
            lambda v: self._emit_layout("hspace", v))
        ml.addRow("Row gap:", self._spin_hspace)

        self._spin_wspace = QtWidgets.QDoubleSpinBox()
        self._spin_wspace.setRange(0.0, 1.0)
        self._spin_wspace.setSingleStep(0.05)
        self._spin_wspace.setDecimals(2)
        self._spin_wspace.setValue(0.30)
        self._spin_wspace.setToolTip("Horizontal gap between subplot columns")
        self._spin_wspace.valueChanged.connect(
            lambda v: self._emit_layout("wspace", v))
        ml.addRow("Col gap:", self._spin_wspace)

        layout.addWidget(margin_sec)

        # ── Render Quality ───────────────────────────────────────────
        quality_sec = CollapsibleSection("Canvas Quality", expanded=False)
        ql = quality_sec.form
        ql.setSpacing(4)

        self._combo_quality = QtWidgets.QComboBox()
        self._combo_quality.addItems([
            "Low (72 DPI)",
            "Medium (100 DPI)",
            "High (150 DPI)",
            "Very High (300 DPI)",
            "Ultra (600 DPI)",
        ])
        self._combo_quality.setCurrentIndex(4)
        self._combo_quality.currentIndexChanged.connect(self._on_quality)
        ql.addRow("Quality:", self._combo_quality)

        layout.addWidget(quality_sec)

        # ── Typography (global base size × scales) ───────────────────
        typo_sec = CollapsibleSection("Typography", expanded=True)
        tf = typo_sec.form
        tf.setSpacing(4)

        self._spin_base_font = QtWidgets.QSpinBox()
        self._spin_base_font.setRange(6, 32)
        self._spin_base_font.setValue(10)
        self._spin_base_font.setToolTip("Scales title, axis, tick, and legend fonts together")
        self._spin_base_font.valueChanged.connect(
            lambda v: self._emit_layout("base_size", int(v))
        )
        tf.addRow("Base font size:", self._spin_base_font)

        from .fonts import CURATED_FONTS
        self._font_combo = QtWidgets.QComboBox()
        self._font_combo.addItems(CURATED_FONTS)
        self._font_combo.setMaxVisibleItems(12)
        self._font_combo.currentTextChanged.connect(self._on_font_family)
        tf.addRow("Font family:", self._font_combo)

        self._chk_bold = QtWidgets.QCheckBox("Bold")
        self._chk_bold.setToolTip(
            "Apply bold weight to title, axis labels, ticks, and legend"
        )
        self._chk_bold.toggled.connect(self._on_font_bold)
        tf.addRow("", self._chk_bold)

        self._spin_freq_dec = QtWidgets.QSpinBox()
        self._spin_freq_dec.setRange(0, 6)
        self._spin_freq_dec.setValue(1)
        self._spin_freq_dec.setToolTip(
            "Number of decimals shown for frequency labels (e.g. f = 9.2 Hz)"
        )
        self._spin_freq_dec.valueChanged.connect(
            lambda v: self._emit_layout("freq_decimals", int(v)))
        tf.addRow("Frequency decimals:", self._spin_freq_dec)

        self._spin_lambda_dec = QtWidgets.QSpinBox()
        self._spin_lambda_dec.setRange(0, 6)
        self._spin_lambda_dec.setValue(1)
        self._spin_lambda_dec.setToolTip(
            "Number of decimals shown for wavelength labels (e.g. λ = 43.0 m)"
        )
        self._spin_lambda_dec.valueChanged.connect(
            lambda v: self._emit_layout("lambda_decimals", int(v)))
        tf.addRow("Wavelength decimals:", self._spin_lambda_dec)

        expert = CollapsibleSection("Font scale factors (advanced)", expanded=False)
        ef = expert.form
        self._spin_title_sc = QtWidgets.QDoubleSpinBox()
        self._spin_title_sc.setRange(0.5, 3.0)
        self._spin_title_sc.setSingleStep(0.05)
        self._spin_title_sc.setDecimals(2)
        self._spin_title_sc.setValue(1.2)
        self._spin_title_sc.valueChanged.connect(
            lambda v: self._emit_layout("title_scale", float(v))
        )
        ef.addRow("Title ×:", self._spin_title_sc)

        self._spin_axis_sc = QtWidgets.QDoubleSpinBox()
        self._spin_axis_sc.setRange(0.5, 3.0)
        self._spin_axis_sc.setSingleStep(0.05)
        self._spin_axis_sc.setDecimals(2)
        self._spin_axis_sc.setValue(1.0)
        self._spin_axis_sc.valueChanged.connect(
            lambda v: self._emit_layout("axis_label_scale", float(v))
        )
        ef.addRow("Axis label ×:", self._spin_axis_sc)

        self._spin_tick_sc = QtWidgets.QDoubleSpinBox()
        self._spin_tick_sc.setRange(0.5, 3.0)
        self._spin_tick_sc.setSingleStep(0.05)
        self._spin_tick_sc.setDecimals(2)
        self._spin_tick_sc.setValue(0.9)
        self._spin_tick_sc.valueChanged.connect(
            lambda v: self._emit_layout("tick_label_scale", float(v))
        )
        ef.addRow("Tick label ×:", self._spin_tick_sc)

        self._spin_leg_sc = QtWidgets.QDoubleSpinBox()
        self._spin_leg_sc.setRange(0.5, 3.0)
        self._spin_leg_sc.setSingleStep(0.05)
        self._spin_leg_sc.setDecimals(2)
        self._spin_leg_sc.setValue(0.9)
        self._spin_leg_sc.valueChanged.connect(
            lambda v: self._emit_layout("legend_scale", float(v))
        )
        ef.addRow("Legend ×:", self._spin_leg_sc)

        typo_layout = QtWidgets.QVBoxLayout()
        typo_layout.addWidget(typo_sec)
        typo_layout.addWidget(expert)
        typo_wrap = QtWidgets.QWidget()
        typo_wrap.setLayout(typo_layout)
        layout.addWidget(typo_wrap)

        # ── Legend ────────────────────────────────────────────────────
        legend_sec = CollapsibleSection("Legend", expanded=False)
        ll = legend_sec.form
        ll.setSpacing(4)

        self._chk_legend = QtWidgets.QCheckBox("Show legend")
        self._chk_legend.setChecked(True)
        self._chk_legend.toggled.connect(
            lambda v: self._emit_legend("visible", v))
        ll.addRow(self._chk_legend)

        self._combo_legend_pos = QtWidgets.QComboBox()
        self._combo_legend_pos.addItems([
            "best", "upper right", "upper left",
            "lower left", "lower right", "center left",
            "center right", "lower center", "upper center", "center",
        ])
        self._combo_legend_pos.currentTextChanged.connect(
            lambda v: self._emit_legend("position", v))
        ll.addRow("Position:", self._combo_legend_pos)

        self._spin_legend_font = QtWidgets.QSpinBox()
        self._spin_legend_font.setRange(6, 20)
        self._spin_legend_font.setValue(9)
        self._spin_legend_font.valueChanged.connect(
            lambda v: self._emit_legend("font_size", v))
        ll.addRow("Font size:", self._spin_legend_font)

        self._chk_legend_frame = QtWidgets.QCheckBox("Frame")
        self._chk_legend_frame.setChecked(True)
        self._chk_legend_frame.toggled.connect(
            lambda v: self._emit_legend("frame_on", v))
        ll.addRow(self._chk_legend_frame)

        layout.addWidget(legend_sec)

        layout.addStretch(1)

    # ── Public API ────────────────────────────────────────────────────

    def populate(self, sheet: "SheetState"):
        """Sync controls from a SheetState."""
        self._updating = True

        self._spin_rows.setValue(sheet.grid_rows)
        self._spin_cols.setValue(sheet.grid_cols)
        self._spin_fig_w.setValue(sheet.figure_width)
        self._spin_fig_h.setValue(sheet.figure_height)
        self._spin_hspace.setValue(sheet.hspace)
        self._spin_wspace.setValue(sheet.wspace)

        # Canvas quality
        dpi = getattr(sheet, "canvas_dpi", 600)
        if dpi <= 72:
            self._combo_quality.setCurrentIndex(0)
        elif dpi <= 100:
            self._combo_quality.setCurrentIndex(1)
        elif dpi <= 150:
            self._combo_quality.setCurrentIndex(2)
        elif dpi <= 300:
            self._combo_quality.setCurrentIndex(3)
        else:
            self._combo_quality.setCurrentIndex(4)

        typo = sheet.typography
        for w in (
            self._spin_base_font, self._spin_title_sc, self._spin_axis_sc,
            self._spin_tick_sc, self._spin_leg_sc,
        ):
            w.blockSignals(True)
        self._spin_base_font.setValue(int(typo.base_size))
        self._spin_title_sc.setValue(float(typo.title_scale))
        self._spin_axis_sc.setValue(float(typo.axis_label_scale))
        self._spin_tick_sc.setValue(float(typo.tick_label_scale))
        self._spin_leg_sc.setValue(float(typo.legend_scale))
        for w in (
            self._spin_base_font, self._spin_title_sc, self._spin_axis_sc,
            self._spin_tick_sc, self._spin_leg_sc,
        ):
            w.blockSignals(False)
        self._font_combo.blockSignals(True)
        from .fonts import populate_font_combo
        populate_font_combo(self._font_combo, typo.font_family)
        self._font_combo.blockSignals(False)

        self._chk_bold.blockSignals(True)
        self._chk_bold.setChecked(
            str(getattr(typo, "font_weight", "normal")).lower() == "bold"
        )
        self._chk_bold.blockSignals(False)

        for w in (self._spin_freq_dec, self._spin_lambda_dec):
            w.blockSignals(True)
        self._spin_freq_dec.setValue(int(getattr(typo, "freq_decimals", 1)))
        self._spin_lambda_dec.setValue(int(getattr(typo, "lambda_decimals", 1)))
        for w in (self._spin_freq_dec, self._spin_lambda_dec):
            w.blockSignals(False)

        # Legend
        leg = sheet.legend
        self._chk_legend.setChecked(leg.visible)
        idx = self._combo_legend_pos.findText(leg.position)
        if idx >= 0:
            self._combo_legend_pos.setCurrentIndex(idx)
        self._spin_legend_font.setValue(leg.font_size)
        self._chk_legend_frame.setChecked(leg.frame_on)

        self._updating = False

    # ── Internal ──────────────────────────────────────────────────────

    def _on_grid_spin(self):
        if not self._updating:
            self.grid_changed.emit(
                self._spin_rows.value(), self._spin_cols.value())

    def _on_quality(self, idx):
        if self._updating:
            return
        dpi_map = {0: 72, 1: 100, 2: 150, 3: 300, 4: 600}
        self._emit_layout("canvas_dpi", dpi_map.get(idx, 600))

    def _emit_layout(self, attr: str, value):
        if not self._updating:
            self.layout_changed.emit(attr, value)

    def _emit_legend(self, attr: str, value):
        if not self._updating:
            self.legend_changed.emit(attr, value)

    def _on_font_family(self, family: str):
        if self._updating:
            return
        self._emit_layout("font_family", str(family))

    def _on_font_bold(self, checked: bool):
        if self._updating:
            return
        self._emit_layout("font_weight", "bold" if checked else "normal")
