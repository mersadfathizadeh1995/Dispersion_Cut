"""
Sheet panel — grid layout, legend, and typography controls.

Sits at the bottom of the right dock (below properties panel)
or as a collapsible section within it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...qt_compat import (
    QtWidgets, QtCore, Signal,
    Horizontal, PolicyMinimum, PolicyExpanding,
)

if TYPE_CHECKING:
    from ...core.models import SheetState


class SheetPanel(QtWidgets.QWidget):
    """
    Sheet-level controls: grid layout, legend, typography.

    Signals
    -------
    grid_changed(int, int)
        (rows, cols)
    col_ratios_changed(list)
    legend_changed(str, object)
        (attribute, value) — e.g. ("visible", True), ("position", "upper right")
    typography_changed(str, object)
        (attribute, value)
    """

    grid_changed = Signal(int, int)
    col_ratios_changed = Signal(list)
    layout_changed = Signal(str, object)  # (attr, value) for hspace/wspace/figure_width/height
    legend_changed = Signal(str, object)
    typography_changed = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # ── Grid Layout Group ─────────────────────────────────────────
        grid_group = QtWidgets.QGroupBox("Grid Layout")
        gl = QtWidgets.QFormLayout()
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

        grid_group.setLayout(gl)
        layout.addWidget(grid_group)

        # ── Layout / Margins Group ────────────────────────────────────
        layout_group = QtWidgets.QGroupBox("Layout")
        lo = QtWidgets.QFormLayout()
        lo.setSpacing(4)

        self._spin_fig_w = QtWidgets.QDoubleSpinBox()
        self._spin_fig_w.setRange(4.0, 30.0)
        self._spin_fig_w.setSingleStep(0.5)
        self._spin_fig_w.setDecimals(1)
        self._spin_fig_w.setValue(10.0)
        self._spin_fig_w.setSuffix(" in")
        self._spin_fig_w.valueChanged.connect(
            lambda v: self._emit_layout("figure_width", v))
        lo.addRow("Width:", self._spin_fig_w)

        self._spin_fig_h = QtWidgets.QDoubleSpinBox()
        self._spin_fig_h.setRange(3.0, 24.0)
        self._spin_fig_h.setSingleStep(0.5)
        self._spin_fig_h.setDecimals(1)
        self._spin_fig_h.setValue(7.0)
        self._spin_fig_h.setSuffix(" in")
        self._spin_fig_h.valueChanged.connect(
            lambda v: self._emit_layout("figure_height", v))
        lo.addRow("Height:", self._spin_fig_h)

        self._slider_hspace = QtWidgets.QSlider(Horizontal)
        self._slider_hspace.setRange(0, 100)
        self._slider_hspace.setValue(30)
        self._slider_hspace.setToolTip("Vertical spacing between rows")
        self._slider_hspace.valueChanged.connect(
            lambda v: self._emit_layout("hspace", v / 100.0))
        lo.addRow("Row gap:", self._slider_hspace)

        self._slider_wspace = QtWidgets.QSlider(Horizontal)
        self._slider_wspace.setRange(0, 100)
        self._slider_wspace.setValue(30)
        self._slider_wspace.setToolTip("Horizontal spacing between columns")
        self._slider_wspace.valueChanged.connect(
            lambda v: self._emit_layout("wspace", v / 100.0))
        lo.addRow("Col gap:", self._slider_wspace)

        layout_group.setLayout(lo)
        layout.addWidget(layout_group)

        # ── Legend Group ──────────────────────────────────────────────
        legend_group = QtWidgets.QGroupBox("Legend")
        ll = QtWidgets.QFormLayout()
        ll.setSpacing(4)

        self._chk_legend_visible = QtWidgets.QCheckBox("Show legend")
        self._chk_legend_visible.setChecked(True)
        self._chk_legend_visible.toggled.connect(
            lambda v: self._emit_legend("visible", v)
        )
        ll.addRow(self._chk_legend_visible)

        self._combo_legend_pos = QtWidgets.QComboBox()
        self._combo_legend_pos.addItems([
            "best", "upper right", "upper left",
            "lower left", "lower right", "center left",
            "center right", "lower center", "upper center",
            "center",
        ])
        self._combo_legend_pos.currentTextChanged.connect(
            lambda v: self._emit_legend("position", v)
        )
        ll.addRow("Position:", self._combo_legend_pos)

        self._spin_legend_font = QtWidgets.QSpinBox()
        self._spin_legend_font.setRange(6, 20)
        self._spin_legend_font.setValue(9)
        self._spin_legend_font.valueChanged.connect(
            lambda v: self._emit_legend("font_size", v)
        )
        ll.addRow("Font size:", self._spin_legend_font)

        self._chk_legend_frame = QtWidgets.QCheckBox("Frame")
        self._chk_legend_frame.setChecked(True)
        self._chk_legend_frame.toggled.connect(
            lambda v: self._emit_legend("frame_on", v)
        )
        ll.addRow(self._chk_legend_frame)

        legend_group.setLayout(ll)
        layout.addWidget(legend_group)

        # ── Typography Group ──────────────────────────────────────────
        typo_group = QtWidgets.QGroupBox("Typography")
        tl = QtWidgets.QFormLayout()
        tl.setSpacing(4)

        self._spin_title_size = QtWidgets.QSpinBox()
        self._spin_title_size.setRange(6, 24)
        self._spin_title_size.setValue(12)
        self._spin_title_size.valueChanged.connect(
            lambda v: self._emit_typo("title_size", v)
        )
        tl.addRow("Title size:", self._spin_title_size)

        self._spin_axis_label = QtWidgets.QSpinBox()
        self._spin_axis_label.setRange(6, 20)
        self._spin_axis_label.setValue(10)
        self._spin_axis_label.valueChanged.connect(
            lambda v: self._emit_typo("axis_label_size", v)
        )
        tl.addRow("Axis label:", self._spin_axis_label)

        self._spin_tick_label = QtWidgets.QSpinBox()
        self._spin_tick_label.setRange(6, 18)
        self._spin_tick_label.setValue(9)
        self._spin_tick_label.valueChanged.connect(
            lambda v: self._emit_typo("tick_label_size", v)
        )
        tl.addRow("Tick label:", self._spin_tick_label)

        typo_group.setLayout(tl)
        layout.addWidget(typo_group)

        layout.addStretch(1)

    # ── Public API ────────────────────────────────────────────────────

    def populate(self, sheet: "SheetState"):
        """Sync controls from a SheetState."""
        self._updating = True

        self._spin_rows.setValue(sheet.grid_rows)
        self._spin_cols.setValue(sheet.grid_cols)

        # Layout
        self._spin_fig_w.setValue(sheet.figure_width)
        self._spin_fig_h.setValue(sheet.figure_height)
        self._slider_hspace.setValue(int(sheet.hspace * 100))
        self._slider_wspace.setValue(int(sheet.wspace * 100))

        # Legend
        leg = sheet.legend
        self._chk_legend_visible.setChecked(leg.visible)
        idx = self._combo_legend_pos.findText(leg.position)
        if idx >= 0:
            self._combo_legend_pos.setCurrentIndex(idx)
        self._spin_legend_font.setValue(leg.font_size)
        self._chk_legend_frame.setChecked(leg.frame_on)

        # Typography
        typo = sheet.typography
        self._spin_title_size.setValue(typo.title_size)
        self._spin_axis_label.setValue(typo.axis_label_size)
        self._spin_tick_label.setValue(typo.tick_label_size)

        self._updating = False

    # ── Internal handlers ─────────────────────────────────────────────

    def _on_grid_spin(self):
        if not self._updating:
            self.grid_changed.emit(
                self._spin_rows.value(), self._spin_cols.value()
            )

    def _emit_legend(self, attr: str, value):
        if not self._updating:
            self.legend_changed.emit(attr, value)

    def _emit_typo(self, attr: str, value):
        if not self._updating:
            self.typography_changed.emit(attr, value)

    def _emit_layout(self, attr: str, value):
        if not self._updating:
            self.layout_changed.emit(attr, value)
