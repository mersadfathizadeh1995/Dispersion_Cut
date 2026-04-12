"""
Global settings panel — sheet-level controls.

Tab 2 of the right panel: grid layout, figure dimensions, margins,
canvas quality, legend defaults, background.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...qt_compat import (
    QtWidgets, QtCore, Signal,
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
        self._combo_quality.addItems(["Low (72 DPI)", "Medium (100 DPI)", "High (150 DPI)"])
        self._combo_quality.setCurrentIndex(0)
        self._combo_quality.currentIndexChanged.connect(self._on_quality)
        ql.addRow("Quality:", self._combo_quality)

        layout.addWidget(quality_sec)

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
        dpi = getattr(sheet, "canvas_dpi", 72)
        if dpi <= 72:
            self._combo_quality.setCurrentIndex(0)
        elif dpi <= 100:
            self._combo_quality.setCurrentIndex(1)
        else:
            self._combo_quality.setCurrentIndex(2)

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
        dpi_map = {0: 72, 1: 100, 2: 150}
        self._emit_layout("canvas_dpi", dpi_map.get(idx, 72))

    def _emit_layout(self, attr: str, value):
        if not self._updating:
            self.layout_changed.emit(attr, value)

    def _emit_legend(self, attr: str, value):
        if not self._updating:
            self.legend_changed.emit(attr, value)
