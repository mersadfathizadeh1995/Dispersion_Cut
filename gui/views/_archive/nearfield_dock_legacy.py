"""Near-Field Evaluation dock.

Three tabs:
  1. NACD-Only   – Geometry-based NF evaluation (no reference needed)
  2. Reference   – Reference-curve-based V_R evaluation
  3. Results     – Batch summary, per-point inspection, deletions, export

λ-lines are handled by the separate WavelengthLinesDock.
Mode detection / rolling are separate tools (future).
"""
from __future__ import annotations

from typing import Optional, Dict, List

import numpy as np
from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore

from dc_cut.core.processing.nearfield.criteria import (
    SOURCE_TYPE_LABELS,
    ERROR_LEVEL_LABELS,
)
from dc_cut.core.processing.nearfield.ranges import (
    EvaluationRange,
    compute_range_mask,
    reference_coverage_warnings,
)
from dc_cut.core.processing.nearfield.range_derivation import (
    DerivedLimitSet,
    derive_limits,
)
from dc_cut.gui.widgets.collapsible_section import CollapsibleSection
from dc_cut.gui.widgets.nf_eval_ranges import NFEvalRangesWidget
from dc_cut.gui.widgets.nf_limit_lines import (
    draw_nf_limit_lines,
    draw_nf_limits_from_set,
    clear_nf_limit_lines,
)
from dc_cut.gui.views.nf_limits_tab import NFLimitsTab, LimitsLineState

# ── Qt5 / Qt6 enum compat ──────────────────────────────────────────
try:
    _UserRole = QtCore.Qt.UserRole
except AttributeError:
    _UserRole = QtCore.Qt.ItemDataRole.UserRole

try:
    _Checked = QtCore.Qt.Checked
    _Unchecked = QtCore.Qt.Unchecked
except AttributeError:
    _Checked = QtCore.Qt.CheckState.Checked
    _Unchecked = QtCore.Qt.CheckState.Unchecked

try:
    _ItemIsUserCheckable = QtCore.Qt.ItemIsUserCheckable
    _ItemIsEnabled = QtCore.Qt.ItemIsEnabled
except AttributeError:
    _ItemIsUserCheckable = QtCore.Qt.ItemFlag.ItemIsUserCheckable
    _ItemIsEnabled = QtCore.Qt.ItemFlag.ItemIsEnabled

try:
    _ItemIsEditable = QtCore.Qt.ItemIsEditable
except AttributeError:
    _ItemIsEditable = QtCore.Qt.ItemFlag.ItemIsEditable

# Default severity → colour mapping
_DEFAULT_COLORS = {
    "clean": "#2196F3",          # blue (Mode 1) / green (Mode 2 override)
    "contaminated": "#F44336",   # red
    "marginal": "#FF9800",       # orange
    "unknown": "#9E9E9E",        # grey
}

_MODE1_COLORS = {
    "clean": "#2196F3",          # blue
    "contaminated": "#F44336",   # red
}

_MODE2_COLORS = {
    "clean": "#4CAF50",          # green
    "contaminated": "#F44336",   # red
    "marginal": "#FF9800",       # orange
    "unknown": "#9E9E9E",        # grey
}


def _m2_user_lambda_max(eval_range: EvaluationRange) -> Optional[float]:
    """Effective ``user_lambda_max`` for V_R validity in Reference mode.

    Mirrors ``_resolve_user_lambda_max`` in :mod:`gui.controller.nf_inspector`:
    a non-empty range with no explicit \u03bb_max returns ``inf`` so the
    reference's own \u03bb-cap doesn't blank points the user asked about.
    """
    if eval_range is None or eval_range.is_empty():
        return None
    if eval_range.lambda_max is not None and eval_range.lambda_max > 0:
        return float(eval_range.lambda_max)
    return float(np.inf)


class NearFieldEvalDock(QtWidgets.QDockWidget):
    """Near-Field Evaluation dock – NACD-Only | Reference | Results."""

    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("NF Evaluation", parent)
        self.setObjectName("NearFieldEvalDock")
        self.c = controller
        self.eval = controller.nf_evaluator

        try:
            self.setFeatures(
                QtWidgets.QDockWidget.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFloatable
            )
        except AttributeError:
            self.setFeatures(
                QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )

        host = QtWidgets.QWidget(self)
        self.setWidget(host)
        root = QtWidgets.QVBoxLayout(host)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(2)

        self._tabs = QtWidgets.QTabWidget()
        root.addWidget(self._tabs)

        self._scatter_window = None
        self._last_report = None
        self._last_batch = None
        self._last_mode = None         # 'nacd' or 'reference'
        self._overlay_offsets = []     # list of offset indices currently overlaid

        # NF limit-line artists (cleared on cancel)
        self._nf_limit_artists: list = []

        # User-configurable severity colors
        self._mode1_colors = dict(_MODE1_COLORS)
        self._mode2_colors = dict(_MODE2_COLORS)

        self._build_nacd_tab()
        self._build_reference_tab()
        self._build_limits_tab()
        self._build_results_tab()

        # After all tabs exist, wire the evaluation-range prefs.
        self._load_dock_prefs()

    # ================================================================
    #  Tab 1: NACD-Only Mode
    # ================================================================
    def _build_nacd_tab(self) -> None:
        page = QtWidgets.QWidget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Array Geometry (collapsible) ──
        geom_sec = CollapsibleSection("Array Geometry", initially_expanded=True)
        geom_form = QtWidgets.QFormLayout()

        self._m1_n_recv = QtWidgets.QSpinBox()
        self._m1_n_recv.setRange(2, 200)
        self._m1_n_recv.setValue(24)
        geom_form.addRow("# Receivers:", self._m1_n_recv)

        self._m1_dx = QtWidgets.QDoubleSpinBox()
        self._m1_dx.setRange(0.1, 50.0)
        self._m1_dx.setDecimals(2)
        self._m1_dx.setValue(2.0)
        geom_form.addRow("Spacing (dx, m):", self._m1_dx)

        self._m1_first_pos = QtWidgets.QDoubleSpinBox()
        self._m1_first_pos.setRange(-500.0, 500.0)
        self._m1_first_pos.setDecimals(1)
        self._m1_first_pos.setValue(0.0)
        geom_form.addRow("First receiver (m):", self._m1_first_pos)

        geom_sec.add_layout(geom_form)
        layout.addWidget(geom_sec)

        # ── NACD Criteria (collapsible) ──
        crit_sec = CollapsibleSection("NACD Criteria", initially_expanded=True)
        crit_form = QtWidgets.QFormLayout()

        self._m1_source_type = QtWidgets.QComboBox()
        for key, label in SOURCE_TYPE_LABELS.items():
            self._m1_source_type.addItem(label, key)
        self._m1_source_type.currentIndexChanged.connect(self._m1_on_criteria_changed)
        crit_form.addRow("Source type:", self._m1_source_type)

        self._m1_error_level = QtWidgets.QComboBox()
        for key, label in ERROR_LEVEL_LABELS.items():
            self._m1_error_level.addItem(label, key)
        self._m1_error_level.currentIndexChanged.connect(self._m1_on_criteria_changed)
        crit_form.addRow("Error level:", self._m1_error_level)

        self._m1_nacd_thr = QtWidgets.QDoubleSpinBox()
        self._m1_nacd_thr.setRange(0.1, 5.0)
        self._m1_nacd_thr.setDecimals(2)
        self._m1_nacd_thr.setSingleStep(0.1)
        self._m1_nacd_thr.setValue(float(getattr(self.c, 'nacd_thresh', 1.0)))
        crit_form.addRow("NACD threshold:", self._m1_nacd_thr)

        crit_sec.add_layout(crit_form)
        layout.addWidget(crit_sec)

        # ── Colors (collapsible) ──
        color_sec = CollapsibleSection("Colors", initially_expanded=False)
        color_form = QtWidgets.QFormLayout()

        self._m1_clean_color_btn = self._make_color_button(
            self._mode1_colors["clean"], "clean", 1
        )
        color_form.addRow("Clean:", self._m1_clean_color_btn)

        self._m1_contam_color_btn = self._make_color_button(
            self._mode1_colors["contaminated"], "contaminated", 1
        )
        color_form.addRow("Contaminated:", self._m1_contam_color_btn)

        color_sec.add_layout(color_form)
        layout.addWidget(color_sec)

        # ── Evaluation Ranges (collapsible) ──
        lim_sec = CollapsibleSection(
            "Evaluation Ranges (f bands + λ bounds)", initially_expanded=True
        )
        self._m1_ranges = NFEvalRangesWidget()
        lim_sec.add_widget(self._m1_ranges)
        layout.addWidget(lim_sec)

        # ── Offset Selection  ──
        offset_sec = CollapsibleSection("Offset Selection", initially_expanded=True)
        self._m1_offset_layout = QtWidgets.QVBoxLayout()
        btn_row = QtWidgets.QHBoxLayout()
        sel_all = QtWidgets.QPushButton("Select All")
        sel_all.clicked.connect(lambda: self._set_all_offset_checks(self._m1_offset_checks, True))
        sel_none = QtWidgets.QPushButton("Select None")
        sel_none.clicked.connect(lambda: self._set_all_offset_checks(self._m1_offset_checks, False))
        btn_row.addWidget(sel_all)
        btn_row.addWidget(sel_none)
        self._m1_offset_layout.addLayout(btn_row)
        self._m1_offset_checks: List[QtWidgets.QCheckBox] = []
        offset_sec.add_layout(self._m1_offset_layout)
        layout.addWidget(offset_sec)

        # ── Run Button ──
        run_btn = QtWidgets.QPushButton("▶  Run NACD Evaluation")
        run_btn.setStyleSheet(
            "font-weight: bold; padding: 10px; font-size: 13px;"
            "background-color: #1565C0; color: white; border-radius: 4px;"
        )
        run_btn.clicked.connect(self._m1_run)
        layout.addWidget(run_btn)

        self._m1_status = QtWidgets.QLabel("")
        self._m1_status.setWordWrap(True)
        layout.addWidget(self._m1_status)

        layout.addStretch()
        self._tabs.addTab(scroll, "NACD-Only")

        # Pre-fill from prefs
        self._m1_load_prefs()

    # ================================================================
    #  Tab 2: Reference-Based Mode
    # ================================================================
    def _build_reference_tab(self) -> None:
        page = QtWidgets.QWidget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Reference Curve (collapsible) ──
        ref_sec = CollapsibleSection("Reference Curve", initially_expanded=True)
        ref_form = QtWidgets.QFormLayout()

        self._m2_ref_combo = QtWidgets.QComboBox()
        self._m2_ref_combo.addItems([
            "Longest offset (largest x̄)",
            "Median across offsets (NF-aware)",
            "Specific offset…",
            "Load file…",
        ])
        # Previous selection so "Load file…" can revert on cancel.
        self._m2_prev_ref_idx = 0
        self._m2_ref_combo.currentIndexChanged.connect(self._m2_on_ref_changed)
        ref_form.addRow("Source:", self._m2_ref_combo)

        self._m2_custom_offset = QtWidgets.QComboBox()
        self._m2_custom_offset.setVisible(False)
        self._m2_custom_offset.currentIndexChanged.connect(
            self._m2_on_custom_offset_changed
        )
        ref_form.addRow("Offset:", self._m2_custom_offset)

        self._m2_ref_status = QtWidgets.QLabel("No reference set")
        self._m2_ref_status.setWordWrap(True)
        ref_form.addRow(self._m2_ref_status)

        ref_sec.add_layout(ref_form)
        layout.addWidget(ref_sec)

        # ── Evaluation Ranges (collapsible) ──
        m2_range_sec = CollapsibleSection(
            "Evaluation Ranges (f bands + λ bounds)", initially_expanded=True
        )
        self._m2_ranges = NFEvalRangesWidget()
        m2_range_sec.add_widget(self._m2_ranges)
        layout.addWidget(m2_range_sec)

        # ── Severity Criteria (collapsible) ──
        sev_sec = CollapsibleSection("Severity Criteria", initially_expanded=True)
        sev_form = QtWidgets.QFormLayout()

        self._m2_source_type = QtWidgets.QComboBox()
        for key, label in SOURCE_TYPE_LABELS.items():
            self._m2_source_type.addItem(label, key)
        self._m2_source_type.currentIndexChanged.connect(self._m2_on_criteria_changed)
        sev_form.addRow("Source type:", self._m2_source_type)

        self._m2_error_level = QtWidgets.QComboBox()
        for key, label in ERROR_LEVEL_LABELS.items():
            self._m2_error_level.addItem(label, key)
        self._m2_error_level.currentIndexChanged.connect(self._m2_on_criteria_changed)
        sev_form.addRow("Error level:", self._m2_error_level)

        self._m2_nacd_thr = QtWidgets.QDoubleSpinBox()
        self._m2_nacd_thr.setRange(0.1, 5.0)
        self._m2_nacd_thr.setDecimals(2)
        self._m2_nacd_thr.setSingleStep(0.1)
        self._m2_nacd_thr.setValue(float(getattr(self.c, 'nacd_thresh', 1.0)))
        sev_form.addRow("NACD threshold:", self._m2_nacd_thr)

        self._m2_vr_onset = QtWidgets.QDoubleSpinBox()
        self._m2_vr_onset.setRange(0.5, 1.0)
        self._m2_vr_onset.setDecimals(2)
        self._m2_vr_onset.setSingleStep(0.05)
        self._m2_vr_onset.setValue(0.90)
        sev_form.addRow("V_R onset threshold:", self._m2_vr_onset)

        self._m2_clean_thr = QtWidgets.QDoubleSpinBox()
        self._m2_clean_thr.setRange(0.5, 1.0)
        self._m2_clean_thr.setDecimals(2)
        self._m2_clean_thr.setSingleStep(0.01)
        self._m2_clean_thr.setValue(0.95)
        sev_form.addRow("Clean threshold:", self._m2_clean_thr)

        self._m2_marginal_thr = QtWidgets.QDoubleSpinBox()
        self._m2_marginal_thr.setRange(0.3, 1.0)
        self._m2_marginal_thr.setDecimals(2)
        self._m2_marginal_thr.setSingleStep(0.01)
        self._m2_marginal_thr.setValue(0.85)
        sev_form.addRow("Marginal threshold:", self._m2_marginal_thr)

        sev_sec.add_layout(sev_form)
        layout.addWidget(sev_sec)

        # ── Colors (collapsible) ──
        color_sec = CollapsibleSection("Colors", initially_expanded=False)
        color_form = QtWidgets.QFormLayout()

        self._m2_clean_color_btn = self._make_color_button(
            self._mode2_colors["clean"], "clean", 2
        )
        color_form.addRow("Clean:", self._m2_clean_color_btn)

        self._m2_marginal_color_btn = self._make_color_button(
            self._mode2_colors["marginal"], "marginal", 2
        )
        color_form.addRow("Marginal:", self._m2_marginal_color_btn)

        self._m2_contam_color_btn = self._make_color_button(
            self._mode2_colors["contaminated"], "contaminated", 2
        )
        color_form.addRow("Contaminated:", self._m2_contam_color_btn)

        self._m2_unknown_color_btn = self._make_color_button(
            self._mode2_colors["unknown"], "unknown", 2
        )
        color_form.addRow("Unknown:", self._m2_unknown_color_btn)

        color_sec.add_layout(color_form)
        layout.addWidget(color_sec)

        # ── Offset Selection ──
        offset_sec = CollapsibleSection("Offset Selection", initially_expanded=True)
        self._m2_offset_layout = QtWidgets.QVBoxLayout()
        btn_row = QtWidgets.QHBoxLayout()
        sel_all = QtWidgets.QPushButton("Select All")
        sel_all.clicked.connect(lambda: self._set_all_offset_checks(self._m2_offset_checks, True))
        sel_none = QtWidgets.QPushButton("Select None")
        sel_none.clicked.connect(lambda: self._set_all_offset_checks(self._m2_offset_checks, False))
        btn_row.addWidget(sel_all)
        btn_row.addWidget(sel_none)
        self._m2_offset_layout.addLayout(btn_row)
        self._m2_offset_checks: List[QtWidgets.QCheckBox] = []
        offset_sec.add_layout(self._m2_offset_layout)
        layout.addWidget(offset_sec)

        # ── Run Button ──
        run_btn = QtWidgets.QPushButton("▶  Run Reference Evaluation")
        run_btn.setStyleSheet(
            "font-weight: bold; padding: 10px; font-size: 13px;"
            "background-color: #1976D2; color: white; border-radius: 4px;"
        )
        run_btn.clicked.connect(self._m2_run)
        layout.addWidget(run_btn)

        self._m2_status = QtWidgets.QLabel("")
        self._m2_status.setWordWrap(True)
        layout.addWidget(self._m2_status)

        layout.addStretch()
        self._tabs.addTab(scroll, "Reference")

    # ================================================================
    #  Tab 3: Limit Lines (hierarchical tree)
    # ================================================================
    def _build_limits_tab(self) -> None:
        """Add the Limit-Lines tab.

        Hosts an :class:`NFLimitsTab` whose tree reflects the ranges
        configured in NACD-Only or Reference (whichever is currently
        in focus).  Two separate :class:`LimitsLineState` objects are
        maintained -- one per mode -- so visibility/color preferences
        are remembered independently.
        """
        self._limits_tab = NFLimitsTab()
        self._limits_state_m1 = LimitsLineState()
        self._limits_state_m2 = LimitsLineState()
        self._active_limits_mode = "m1"  # 'm1' (NACD) or 'm2' (Reference)
        # NACD-Only: when Run is invoked with a single selected offset
        # we pin the V(f) curve used for cross-domain derivation to
        # that specific offset's arrays.  None = unset.
        self._m1_force_vf_idx: Optional[int] = None
        self._limits_tab.state_changed.connect(self._on_limits_state_changed)
        self._tabs.addTab(self._limits_tab, "Limit Lines")
        self._tabs.currentChanged.connect(self._on_top_tab_changed)

    def _current_limits_state(self) -> LimitsLineState:
        return (
            self._limits_state_m2
            if self._active_limits_mode == "m2"
            else self._limits_state_m1
        )

    def _current_eval_range(self) -> EvaluationRange:
        if self._active_limits_mode == "m2":
            return self._m2_ranges.get_range()
        return self._m1_ranges.get_range()

    def _get_vf_curve_for_limits(self):
        """Return the ``(f, v)`` curve used to derive cross-domain limits.

        * Reference mode -> the reference curve itself.
        * NACD-Only mode -> the curve of the single offset the user
          explicitly chose (via ``_m1_force_vf_idx``, set inside
          :meth:`_m1_run`).  We never silently fall back to "offset 0"
          here because that would silently derive lines from the wrong
          curve.
        """
        if self._active_limits_mode == "m2" and self.eval.has_reference:
            return self.eval._reference_f, self.eval._reference_v
        idx = getattr(self, "_m1_force_vf_idx", None)
        if idx is None and hasattr(self.eval, "_current_idx"):
            idx = self.eval._current_idx
        if idx is not None:
            try:
                f = np.asarray(self.c.frequency_arrays[idx], float)
                v = np.asarray(self.c.velocity_arrays[idx], float)
                return f, v
            except Exception:
                pass
        return None, None

    def _rebuild_limits_tree(self) -> None:
        """Recompute the DerivedLimitSet and refresh the tree + canvas."""
        eval_range = self._current_eval_range()
        f_curve, v_curve = self._get_vf_curve_for_limits()
        self._current_derived_set = derive_limits(eval_range, f_curve, v_curve)
        # Push the per-mode state into the tab before refreshing so
        # visibility/colours persist across mode switches.
        self._limits_tab.set_state(self._current_limits_state())
        self._limits_tab.refresh(self._current_derived_set)
        self._redraw_limit_lines_on_canvas()

    def _redraw_limit_lines_on_canvas(self) -> None:
        """Clear and redraw NF limit lines from the active DerivedLimitSet."""
        clear_nf_limit_lines(self._nf_limit_artists)
        limit_set = getattr(self, "_current_derived_set", None)
        if limit_set is None or not limit_set.lines:
            try:
                self.c.ax_freq.figure.canvas.draw_idle()
            except Exception:
                pass
            return
        active_ranges_widget = (
            self._m2_ranges if self._active_limits_mode == "m2"
            else self._m1_ranges
        )
        if not active_ranges_widget.show_lines():
            try:
                self.c.ax_freq.figure.canvas.draw_idle()
            except Exception:
                pass
            return
        state = self._current_limits_state()
        if not state.show_all:
            try:
                self.c.ax_freq.figure.canvas.draw_idle()
            except Exception:
                pass
            return

        def _style(key):
            # Band-level check must be ON too (a leaf can't override an
            # explicitly-hidden band).
            band_key = (key[0], "band", "band")
            group_key = (key[0], key[1], "group")
            if not state.get_visible(band_key, True):
                return False, "#000000"
            if not state.get_visible(group_key, True):
                return False, "#000000"
            if not state.get_visible(key, True):
                return False, "#000000"
            color = state.get_color(key, default="")
            if not color:
                color = state.get_color(
                    group_key,
                    default=state.get_color(band_key, default=""),
                )
            if not color:
                from dc_cut.gui.views.nf_limits_tab import default_band_color
                color = default_band_color(key[0])
            return True, color

        self._nf_limit_artists = draw_nf_limits_from_set(
            self.c.ax_freq, self.c.ax_wave,
            limit_set, style_fn=_style,
        )

    def _on_top_tab_changed(self, idx: int) -> None:
        """Remember which mode is active for the Limit Lines tab."""
        # Tab order: 0 NACD, 1 Reference, 2 Limit Lines, 3 Results.
        if idx == 0:
            self._active_limits_mode = "m1"
        elif idx == 1:
            self._active_limits_mode = "m2"
        # When the Limit Lines tab itself becomes visible, refresh.
        if idx == 2:
            self._rebuild_limits_tree()

    def _on_limits_state_changed(self) -> None:
        """React to visibility/color edits made in the Limit Lines tab."""
        state = self._limits_tab.state()
        if self._active_limits_mode == "m2":
            self._limits_state_m2 = state
        else:
            self._limits_state_m1 = state
        self._redraw_limit_lines_on_canvas()
        self._save_range_prefs()

    def _redraw_m1_limits_for_current_range(self) -> None:
        """Hook used when Tab 1's range changes -- rebuild limits set."""
        self._active_limits_mode = "m1"
        self._rebuild_limits_tree()

    def _redraw_m2_limits_for_current_range(self) -> None:
        """Hook used when Tab 2's range or reference changes."""
        self._active_limits_mode = "m2"
        self._rebuild_limits_tree()

    # ================================================================
    #  Tab 4: Results & Export
    # ================================================================
    def _build_results_tab(self) -> None:
        page = QtWidgets.QWidget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Batch Summary (collapsible) ──
        batch_sec = CollapsibleSection("Batch Summary", initially_expanded=True)
        self._batch_table = QtWidgets.QTableWidget()
        self._batch_table.setColumnCount(7)
        self._batch_table.setHorizontalHeaderLabels([
            "Offset", "x̄ (m)", "λ_max (m)", "Onset λ (m)",
            "Clean %", "Marginal %", "Contam %",
        ])
        try:
            self._batch_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Stretch
            )
        except AttributeError:
            self._batch_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeMode.Stretch
            )
        self._batch_table.setMaximumHeight(200)
        batch_sec.add_widget(self._batch_table)
        layout.addWidget(batch_sec)

        # ── Inspect Offset (collapsible) ──
        inspect_sec = CollapsibleSection("Inspect Offset", initially_expanded=True)
        inspect_form = QtWidgets.QFormLayout()

        self._inspect_combo = QtWidgets.QComboBox()
        self._inspect_combo.currentIndexChanged.connect(self._on_inspect_changed)
        inspect_form.addRow("Offset:", self._inspect_combo)

        self._inspect_summary = QtWidgets.QLabel("")
        inspect_form.addRow(self._inspect_summary)

        inspect_sec.add_layout(inspect_form)
        layout.addWidget(inspect_sec)

        # ── Points table ──
        self._points_table = QtWidgets.QTableWidget()
        self._points_table.setColumnCount(7)
        self._points_table.setHorizontalHeaderLabels(
            ["f (Hz)", "V (m/s)", "λ (m)", "NACD", "V_R", "Severity", "☑"]
        )
        try:
            self._points_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Stretch
            )
        except AttributeError:
            self._points_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeMode.Stretch
            )
        try:
            self._points_table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectRows
            )
        except AttributeError:
            self._points_table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
            )
        self._points_table.setMinimumHeight(180)
        self._points_table.itemChanged.connect(self._on_flag_toggled)
        layout.addWidget(self._points_table, stretch=1)

        # ── Filter + Actions ──
        filt_row = QtWidgets.QHBoxLayout()
        filt_row.addWidget(QtWidgets.QLabel("Auto-select:"))
        self._del_filter = QtWidgets.QComboBox()
        self._del_filter.addItems([
            "All flagged (NF ≥ marginal)",
            "Contaminated only (V_R < 0.85)",
            "NACD below threshold",
        ])
        filt_row.addWidget(self._del_filter, stretch=1)
        select_btn = QtWidgets.QPushButton("Select")
        select_btn.clicked.connect(self._on_auto_select)
        filt_row.addWidget(select_btn)
        layout.addLayout(filt_row)

        action_row = QtWidgets.QHBoxLayout()
        self._btn_apply = QtWidgets.QPushButton("Delete")
        self._btn_apply.setStyleSheet("font-weight: bold; color: #F44336;")
        self._btn_apply.clicked.connect(self._on_apply_deletions)
        action_row.addWidget(self._btn_apply)
        self._btn_cancel = QtWidgets.QPushButton("Cancel / Clear")
        self._btn_cancel.clicked.connect(self._on_cancel)
        action_row.addWidget(self._btn_cancel)
        layout.addLayout(action_row)

        # ── Export ──
        export_sec = CollapsibleSection("Export", initially_expanded=False)
        export_row = QtWidgets.QHBoxLayout()
        csv_btn = QtWidgets.QPushButton("Export CSV")
        csv_btn.clicked.connect(lambda: self._on_export("csv"))
        export_row.addWidget(csv_btn)
        json_btn = QtWidgets.QPushButton("Export JSON")
        json_btn.clicked.connect(lambda: self._on_export("json"))
        export_row.addWidget(json_btn)
        export_sec.add_layout(export_row)

        export_row2 = QtWidgets.QHBoxLayout()
        scatter_btn = QtWidgets.QPushButton("NACD vs V_R Scatter")
        scatter_btn.clicked.connect(self._open_scatter_window)
        export_row2.addWidget(scatter_btn)
        npz_btn = QtWidgets.QPushButton("Export NPZ (figure data)")
        npz_btn.clicked.connect(self._on_export_npz)
        export_row2.addWidget(npz_btn)
        export_sec.add_layout(export_row2)

        layout.addWidget(export_sec)

        layout.addStretch()
        self._tabs.addTab(scroll, "Results")

    # ================================================================
    #  Shared helpers
    # ================================================================
    def _make_color_button(self, hex_color: str, severity_key: str, mode: int) -> QtWidgets.QPushButton:
        """Create a colored button that opens a color picker."""
        btn = QtWidgets.QPushButton()
        btn.setFixedSize(28, 22)
        btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #888;")

        def _pick():
            chosen = QtWidgets.QColorDialog.getColor(
                QtGui.QColor(hex_color), self, f"Color for {severity_key}"
            )
            if chosen.isValid():
                new_hex = chosen.name()
                btn.setStyleSheet(f"background-color: {new_hex}; border: 1px solid #888;")
                if mode == 1:
                    self._mode1_colors[severity_key] = new_hex
                else:
                    self._mode2_colors[severity_key] = new_hex

        btn.clicked.connect(_pick)
        return btn

    def _refresh_offset_checks(self, checks_list: list, layout: QtWidgets.QVBoxLayout) -> None:
        """Rebuild offset checkboxes in the given layout."""
        for chk in checks_list:
            chk.setParent(None)
            chk.deleteLater()
        checks_list.clear()

        try:
            n = min(len(self.c.velocity_arrays), len(self.c.frequency_arrays))
            labels = list(self.c.offset_labels[:n])
        except Exception:
            labels = []

        for lbl in labels:
            chk = QtWidgets.QCheckBox(lbl)
            chk.setChecked(True)
            layout.addWidget(chk)
            checks_list.append(chk)

        # Whenever the NACD-Only offset list changes, re-apply the
        # "only-one-offset-can-have-a-range" gate.
        if checks_list is getattr(self, "_m1_offset_checks", None):
            for chk in checks_list:
                try:
                    chk.toggled.connect(self._m1_apply_range_gate)
                except Exception:
                    pass
            self._m1_apply_range_gate()

    def _set_all_offset_checks(self, checks_list: list, checked: bool) -> None:
        for chk in checks_list:
            chk.setChecked(checked)
        if checks_list is getattr(self, "_m1_offset_checks", None):
            self._m1_apply_range_gate()

    # ── NACD-Only range-editor gate ────────────────────────────────
    def _m1_apply_range_gate(self, *_args, **_kwargs) -> None:
        """Enable the range editor only when ONE offset is selected.

        Rationale: NACD-Only limit lines are derived using the evaluated
        offset's own V(f) curve, so a *per-row* evaluation range only
        makes sense for a single offset.  With multiple offsets selected
        the range is forced empty and only each offset's own auto-
        derived ``\u03bb_max`` is drawn at Run time.
        """
        if not hasattr(self, "_m1_ranges"):
            return
        sel = sum(1 for c in self._m1_offset_checks if c.isChecked())
        if sel == 1:
            self._m1_ranges.set_editing_enabled(True)
        else:
            self._m1_ranges.set_editing_enabled(
                False,
                reason=(
                    "Custom evaluation ranges are only editable when "
                    "exactly one offset is selected.  With multiple "
                    "offsets, only each offset's \u03bb_max line is "
                    "drawn after Run."
                ),
            )
        # Any stale limit lines from a previous run are now invalid
        # because the "single-offset" context may have changed.
        self._m1_invalidate_limit_lines()

    def _m1_invalidate_limit_lines(self) -> None:
        """Clear M1 limit-line artists and the derived set.

        Called when the user edits the range (before Run) or toggles
        the offset selection.  We do NOT recompute lines here -- that
        is deferred to :meth:`_m1_run`.
        """
        try:
            clear_nf_limit_lines(self._nf_limit_artists)
            self._nf_limit_artists = []
        except Exception:
            pass
        # Drop any stale DerivedLimitSet so the Limit-Lines tree is
        # also reset when the user switches back to that tab.
        if self._active_limits_mode == "m1":
            try:
                self._current_derived_set = None
                self._limits_tab.refresh(None)
            except Exception:
                pass
        try:
            self.c.ax_freq.figure.canvas.draw_idle()
        except Exception:
            pass

    def _get_selected_indices(self, checks_list: list) -> List[int]:
        return [i for i, chk in enumerate(checks_list) if chk.isChecked()]

    def _get_array_positions(self) -> np.ndarray:
        """Get receiver positions from tab1 geometry or controller."""
        n = self._m1_n_recv.value()
        dx = self._m1_dx.value()
        x0 = self._m1_first_pos.value()
        return np.arange(x0, x0 + dx * n, dx)

    def _active_eval_range(self) -> EvaluationRange:
        """Return the EvaluationRange from whichever tab is driving results."""
        if self._last_mode == "reference":
            return self._m2_ranges.get_range()
        return self._m1_ranges.get_range()

    def _m1_load_prefs(self) -> None:
        """Load geometry defaults from prefs."""
        try:
            from dc_cut.services.prefs import load_prefs
            P = load_prefs()
            self._m1_n_recv.setValue(int(P.get('default_n_phones', 24)))
            self._m1_dx.setValue(float(P.get('default_receiver_dx', 2.0)))
        except Exception:
            pass

    def _load_dock_prefs(self) -> None:
        """Restore evaluation-range widgets from prefs and wire auto-save."""
        try:
            from dc_cut.services.prefs import load_prefs
            P = load_prefs()
            m1_rng = EvaluationRange.from_dict(P.get("nf_m1_eval_range"))
            self._m1_ranges.set_range(m1_rng)
            self._m1_ranges.set_show_lines(
                bool(P.get("nf_m1_show_limit_lines", True))
            )
            m2_rng = EvaluationRange.from_dict(P.get("nf_m2_eval_range"))
            self._m2_ranges.set_range(m2_rng)
            self._m2_ranges.set_show_lines(
                bool(P.get("nf_m2_show_limit_lines", True))
            )
            self._limits_state_m1 = LimitsLineState.from_dict(
                P.get("nf_limits_state_m1")
            )
            self._limits_state_m2 = LimitsLineState.from_dict(
                P.get("nf_limits_state_m2")
            )
        except Exception:
            pass

        self._m1_ranges.range_changed.connect(self._save_range_prefs)
        self._m1_ranges.show_lines_toggled.connect(self._save_range_prefs)
        self._m2_ranges.range_changed.connect(self._save_range_prefs)
        self._m2_ranges.show_lines_toggled.connect(self._save_range_prefs)

        # NACD-Only mode: the user's range is interpreted against a
        # SINGLE selected offset's V(f) curve, so we do NOT draw any
        # limit lines until Run NACD Evaluation is pressed.  We just
        # clear any stale lines when the range is edited so the plot
        # doesn't show limits belonging to a previous Run.
        self._m1_ranges.range_changed.connect(self._m1_invalidate_limit_lines)
        self._m1_ranges.show_lines_toggled.connect(
            lambda _c: self._m1_invalidate_limit_lines()
        )

        # Reference mode: limit lines are tied to the reference curve
        # itself (not to a user-picked evaluated offset), so they can
        # update live as the user edits the range.
        self._m2_ranges.range_changed.connect(
            self._redraw_m2_limits_for_current_range
        )
        self._m2_ranges.show_lines_toggled.connect(
            lambda _checked: self._redraw_m2_limits_for_current_range()
        )

    def _save_range_prefs(self, *args) -> None:
        """Persist both evaluation-range widgets to user prefs."""
        try:
            from dc_cut.services.prefs import load_prefs, save_prefs
            prefs = load_prefs()
            prefs["nf_m1_eval_range"] = self._m1_ranges.get_range().to_dict()
            prefs["nf_m1_show_limit_lines"] = self._m1_ranges.show_lines()
            prefs["nf_m2_eval_range"] = self._m2_ranges.get_range().to_dict()
            prefs["nf_m2_show_limit_lines"] = self._m2_ranges.show_lines()
            try:
                prefs["nf_limits_state_m1"] = self._limits_state_m1.to_dict()
                prefs["nf_limits_state_m2"] = self._limits_state_m2.to_dict()
            except Exception:
                pass
            save_prefs(prefs)
        except Exception:
            pass

    # ================================================================
    #  Tab 1 handlers: NACD-Only
    # ================================================================
    def _m1_on_criteria_changed(self, _=None) -> None:
        try:
            from dc_cut.core.processing.nearfield.criteria import resolve_nacd_threshold
            st = self._m1_source_type.currentData() or "sledgehammer"
            el = self._m1_error_level.currentData() or "10_15pct"
            thr = resolve_nacd_threshold(source_type=st, error_level=el)
            self._m1_nacd_thr.setValue(thr)
        except Exception:
            pass

    def _m1_run(self) -> None:
        """Run NACD-only evaluation on selected offsets.

        Contamination rule per point:
            contaminated = (NACD >= thr)  OR  (point outside user's EvaluationRange)

        When the user provides no range at all, the mask reduces to the
        pure NACD rule (today's behaviour).
        """
        self._clear_nf_overlays()
        self._last_mode = "nacd"

        thr = self._m1_nacd_thr.value()
        recv = self._get_array_positions()
        selected = self._get_selected_indices(self._m1_offset_checks)

        if not selected:
            self._m1_status.setText("Select at least one offset.")
            return

        from dc_cut.core.processing.nearfield.nacd import compute_nacd_array
        from dc_cut.core.processing.wavelength_lines import parse_source_offset_from_label

        # Custom evaluation ranges only make sense for a single offset
        # (lines are derived from THAT offset's V(f) curve).  Guard it.
        single_offset = (len(selected) == 1)
        eval_range = (
            self._m1_ranges.get_range() if single_offset
            else EvaluationRange()
        )

        results = []
        for idx in selected:
            f = np.asarray(self.c.frequency_arrays[idx], float)
            v = np.asarray(self.c.velocity_arrays[idx], float)
            w = np.asarray(self.c.wavelength_arrays[idx], float)
            lbl = self.c.offset_labels[idx] if idx < len(self.c.offset_labels) else f"Offset {idx}"
            so = parse_source_offset_from_label(lbl)
            nacd = compute_nacd_array(recv, f, v, source_offset=so)
            in_range = compute_range_mask(f, v, eval_range)
            mask = (nacd >= thr) | (~in_range)
            x_bar = float(np.mean(np.abs(recv - (so if so is not None else 0.0))))
            lam_max = x_bar / max(thr, 1e-12)
            n_contam = int(np.sum(mask))

            results.append({
                "label": lbl,
                "offset_index": idx,
                "x_bar": x_bar,
                "lambda_max": lam_max,
                "n_total": len(f),
                "n_contaminated": n_contam,
                "n_clean": len(f) - n_contam,
                "clean_pct": 100.0 * (len(f) - n_contam) / max(len(f), 1),
                "contam_pct": 100.0 * n_contam / max(len(f), 1),
                "f": f, "v": v, "w": w, "nacd": nacd, "mask": mask,
            })

            self._draw_nacd_overlay(idx, f, v, w, mask)

        # ── Draw λ- and f-limit lines on the canvas (only now!) ────
        # NACD-Only lines are computed against a SPECIFIC offset's
        # V(f) curve.  So:
        # * single offset + user range -> derive the full DerivedLimit
        #   Set via the Limit Lines tab machinery;
        # * multiple offsets          -> just draw each offset's own
        #   auto-derived λ_max line (no cross-domain derivation, no
        #   user frequency bands);
        # * single offset + empty range -> legacy λ_max only.
        self._active_limits_mode = "m1"
        clear_nf_limit_lines(self._nf_limit_artists)
        self._nf_limit_artists = []

        if single_offset and not eval_range.is_empty():
            # Use the single selected offset's curve (not whichever
            # offset happens to be "current" in the evaluator).
            only_idx = selected[0]
            self._m1_force_vf_idx = only_idx
            try:
                self._rebuild_limits_tree()
            finally:
                self._m1_force_vf_idx = None
        elif self._m1_ranges.show_lines() and results:
            # Multi-offset (or empty-range) path: λ_max per offset.
            artists: list = []
            for r in results:
                lam = float(r.get("lambda_max", 0.0))
                if lam <= 0:
                    continue
                artists.extend(draw_nf_limit_lines(
                    self.c.ax_freq, self.c.ax_wave,
                    lambda_max=lam,
                    lambda_min=None,
                    freq_bands=None,
                ))
            self._nf_limit_artists = artists

        self._last_batch = results
        self._overlay_offsets = selected
        self._populate_batch_table(results)
        self._populate_inspect_combo(results)
        self._tabs.setCurrentIndex(3)  # Switch to Results

        n_total = sum(r["n_total"] for r in results)
        n_contam = sum(r["n_contaminated"] for r in results)
        self._m1_status.setText(
            f"Evaluated {len(results)} offset(s), {n_total} points. "
            f"{n_contam} contaminated."
        )

    def _draw_nacd_overlay(self, offset_idx, f, v, w, mask) -> None:
        """Draw red/blue circles on both axes for NACD-only mode."""
        c = self.c
        colors = self._mode1_colors
        for i in range(len(f)):
            col = colors["contaminated"] if mask[i] else colors["clean"]
            key = (offset_idx, i)
            lf = c.ax_freq.plot(
                [f[i]], [v[i]], 'o', linestyle='None',
                mfc='none', mec=col, mew=1.6, ms=6, zorder=10,
                label='_nf_overlay',
            )[0]
            lw = c.ax_wave.plot(
                [w[i]], [v[i]], 'o', linestyle='None',
                mfc='none', mec=col, mew=1.6, ms=6, zorder=10,
                label='_nf_overlay',
            )[0]
            if not hasattr(c, '_nf_point_overlay'):
                c._nf_point_overlay = {}
            c._nf_point_overlay[key] = (lf, lw)
        try:
            c.fig.canvas.draw_idle()
        except Exception:
            pass

    # ================================================================
    #  Tab 2 handlers: Reference-Based
    # ================================================================
    def _m2_on_ref_changed(self, idx: int) -> None:
        """Drive reference creation directly from the combo selection.

        * index 0 / 1 (longest / median) -- build immediately
        * index 2 (specific offset)      -- reveal offset combo, build
          when the offset is picked
        * index 3 (load file)            -- open file dialog now; if the
          user cancels, revert the combo to the previous selection so
          we don't leave a broken state
        """
        self._m2_custom_offset.setVisible(idx == 2)
        if idx == 2:
            self._refresh_offset_checks(self._m2_offset_checks, self._m2_offset_layout)
            # Populate offset combo from current labels.
            try:
                n = min(
                    len(self.c.velocity_arrays),
                    len(self.c.frequency_arrays),
                )
                labels = list(self.c.offset_labels[:n])
                self._m2_custom_offset.blockSignals(True)
                self._m2_custom_offset.clear()
                self._m2_custom_offset.addItems(labels)
                self._m2_custom_offset.blockSignals(False)
            except Exception:
                pass
            # Wait for user to pick the offset before building.
            self._m2_prev_ref_idx = idx
            return

        if idx == 3:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Load Reference Curve", "",
                "CSV files (*.csv);;NPZ files (*.npz);;All (*)",
            )
            if not path:
                # Revert silently.
                self._m2_ref_combo.blockSignals(True)
                self._m2_ref_combo.setCurrentIndex(self._m2_prev_ref_idx)
                self._m2_ref_combo.blockSignals(False)
                return
            try:
                self.eval.load_reference_file(path)
                self._publish_reference()
            except Exception as exc:
                self._m2_ref_status.setText(f"Error: {exc}")
            self._m2_prev_ref_idx = idx
            self._redraw_m2_limits_for_current_range()
            return

        # Auto-build for longest / median.
        mode = "longest_offset" if idx == 0 else "median"
        try:
            self.eval.compute_reference_from_offsets(mode)
            self._publish_reference()
        except Exception as exc:
            self._m2_ref_status.setText(f"Error: {exc}")
        self._m2_prev_ref_idx = idx
        self._redraw_m2_limits_for_current_range()

    def _m2_on_custom_offset_changed(self, idx: int) -> None:
        """Auto-build when the user picks a specific offset."""
        if self._m2_ref_combo.currentIndex() != 2 or idx < 0:
            return
        try:
            self.eval.compute_reference_from_offsets(
                "custom_offset", custom_index=idx,
            )
            self._publish_reference()
        except Exception as exc:
            self._m2_ref_status.setText(f"Error: {exc}")
        self._redraw_m2_limits_for_current_range()

    def _publish_reference(self) -> None:
        """Push the freshly built reference curve to the controller."""
        self.c._nf_reference_f = self.eval._reference_f
        self.c._nf_reference_v = self.eval._reference_v
        self.c._nf_reference_source = self.eval._reference_source
        self._m2_ref_status.setText(f"Reference: {self.eval._reference_source}")

    def _m2_on_criteria_changed(self, _=None) -> None:
        try:
            from dc_cut.core.processing.nearfield.criteria import resolve_nacd_threshold
            st = self._m2_source_type.currentData() or "sledgehammer"
            el = self._m2_error_level.currentData() or "10_15pct"
            thr = resolve_nacd_threshold(source_type=st, error_level=el)
            self._m2_nacd_thr.setValue(thr)
        except Exception:
            pass

    def _redraw_m2_limits_for_current_range(self) -> None:
        """Hook overridden below once the Limits tab + renderer exist."""
        # Placeholder; actual implementation lives in the limits-tab
        # integration in later todos.
        pass

    def _m2_run(self) -> None:
        """Run reference-based evaluation on selected offsets."""
        self._clear_nf_overlays()
        self._last_mode = "reference"

        # Update evaluator settings
        self.eval.thr = self._m2_nacd_thr.value()
        self.eval._vr_onset_threshold = self._m2_vr_onset.value()
        self.eval._clean_threshold = self._m2_clean_thr.value()
        self.eval._marginal_threshold = self._m2_marginal_thr.value()
        st = self._m2_source_type.currentData() or "sledgehammer"
        self.eval.set_source_type(st)

        # Build reference if needed
        if not self.eval.has_reference:
            try:
                ref_idx = self._m2_ref_combo.currentIndex()
                if ref_idx == 0:
                    self.eval.compute_reference_from_offsets("longest_offset")
                elif ref_idx == 1:
                    self.eval.compute_reference_from_offsets("median")
                else:
                    self.eval.compute_reference_from_offsets("longest_offset")
                self.c._nf_reference_f = self.eval._reference_f
                self.c._nf_reference_v = self.eval._reference_v
                self._m2_ref_status.setText(
                    f"Reference: {self.eval._reference_source}"
                )
            except Exception as exc:
                self._m2_status.setText(f"Reference error: {exc}")
                return

        selected = self._get_selected_indices(self._m2_offset_checks)
        if not selected:
            self._m2_status.setText("Select at least one offset.")
            return

        eval_range = self._m2_ranges.get_range()

        # Evaluate (batch summary with counts)
        try:
            all_results = self.eval.evaluate_all_offsets(eval_range=eval_range)
        except Exception as exc:
            self._m2_status.setText(f"Evaluation error: {exc}")
            return

        results = [r for r in all_results if r.get("offset_index") in selected]
        if not results:
            self._m2_status.setText("No matching offsets evaluated.")
            return

        self._last_batch = results
        self._overlay_offsets = selected

        # Per-point overlays using the shared range mask
        from dc_cut.core.processing.nearfield import (
            compute_nacd_array,
            compute_normalized_vr_with_validity,
            classify_nearfield_severity,
        )
        from dc_cut.core.processing.wavelength_lines import parse_source_offset_from_label
        recv = self._get_array_positions()

        f_ref_full = self.eval._reference_f
        v_ref_full = self.eval._reference_v

        for r in results:
            idx = r["offset_index"]
            f = np.asarray(self.c.frequency_arrays[idx], float)
            v = np.asarray(self.c.velocity_arrays[idx], float)
            w = np.asarray(self.c.wavelength_arrays[idx], float)
            lbl = r["label"]
            so = parse_source_offset_from_label(lbl)
            nacd = compute_nacd_array(recv, f, v, source_offset=so)

            user_lam_max = _m2_user_lambda_max(eval_range)
            vr = compute_normalized_vr_with_validity(
                f, v, f_ref_full, v_ref_full,
                self.eval._lambda_max_ref,
                user_lambda_max=user_lam_max,
            )

            # Restrict evaluation to the user's range: everything outside
            # the mask becomes V_R=NaN (classified as "unknown" or the
            # user-selected unknown_action).
            in_range = compute_range_mask(f, v, eval_range)
            if not eval_range.is_empty():
                vr = np.where(in_range, vr, np.nan)

            severity = classify_nearfield_severity(
                vr, self.eval._clean_threshold,
                self.eval._marginal_threshold,
                self.eval._unknown_action,
            )

            self._draw_reference_overlay(idx, f, v, w, severity)

        # Draw λ- and f-limit lines on the canvas via the shared
        # DerivedLimitSet renderer (driven by the Limit Lines tab).
        self._active_limits_mode = "m2"
        if not eval_range.is_empty():
            self._rebuild_limits_tree()
        else:
            clear_nf_limit_lines(self._nf_limit_artists)
            if self._m2_ranges.show_lines():
                lam_max_vals = [
                    r.get("lambda_max", 0.0)
                    for r in results if r.get("lambda_max", 0.0) > 0
                ]
                draw_max = max(lam_max_vals) if lam_max_vals else 0.0
                if draw_max > 0:
                    self._nf_limit_artists = draw_nf_limit_lines(
                        self.c.ax_freq, self.c.ax_wave,
                        lambda_max=float(draw_max),
                        lambda_min=None,
                        freq_bands=None,
                    )

        self._populate_batch_table(results)
        self._populate_inspect_combo(results)
        self._tabs.setCurrentIndex(3)

        n_total = sum(r.get("n_total", 0) for r in results)
        n_contam = sum(r.get("n_contaminated", 0) for r in results)
        msg = (
            f"Evaluated {len(results)} offset(s), {n_total} points. "
            f"{n_contam} contaminated."
        )
        warnings = reference_coverage_warnings(
            f_ref_full, v_ref_full, eval_range,
        )
        if warnings:
            msg += "\n• " + "\n• ".join(warnings)
        self._m2_status.setText(msg)

    def _draw_reference_overlay(self, offset_idx, f, v, w, severity) -> None:
        """Draw 4-color severity circles on both axes."""
        c = self.c
        colors = self._mode2_colors
        for i in range(len(f)):
            sev = severity[i] if severity is not None else "unknown"
            col = colors.get(sev, colors["unknown"])
            key = (offset_idx, i)
            lf = c.ax_freq.plot(
                [f[i]], [v[i]], 'o', linestyle='None',
                mfc='none', mec=col, mew=1.6, ms=6, zorder=10,
                label='_nf_overlay',
            )[0]
            lw = c.ax_wave.plot(
                [w[i]], [v[i]], 'o', linestyle='None',
                mfc='none', mec=col, mew=1.6, ms=6, zorder=10,
                label='_nf_overlay',
            )[0]
            if not hasattr(c, '_nf_point_overlay'):
                c._nf_point_overlay = {}
            c._nf_point_overlay[key] = (lf, lw)
        try:
            c.fig.canvas.draw_idle()
        except Exception:
            pass

    # ================================================================
    #  Results tab handlers
    # ================================================================
    def _populate_batch_table(self, results: list) -> None:
        self._batch_table.setRowCount(0)
        if not results:
            return
        self._batch_table.setRowCount(len(results))
        for row, entry in enumerate(results):
            lbl = entry.get("label", "?")
            if entry.get("is_reference"):
                lbl += " ★"
            ro_lam = entry.get("rolloff_wavelength", np.nan)
            vals = [
                lbl,
                f"{entry.get('x_bar', 0):.1f}",
                f"{entry.get('lambda_max', 0):.1f}",
                f"{ro_lam:.1f}" if np.isfinite(ro_lam) else "—",
                f"{entry.get('clean_pct', 0):.0f}",
                f"{100 * entry.get('n_marginal', 0) / max(entry.get('n_total', 1), 1):.0f}"
                    if 'n_marginal' in entry else "—",
                f"{entry.get('contam_pct', 0):.0f}",
            ]
            for col, txt in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(txt)
                item.setFlags(item.flags() & ~_ItemIsEditable)
                if entry.get("contam_pct", 0) > 30:
                    item.setForeground(QtGui.QColor("#F44336"))
                elif entry.get("is_reference"):
                    item.setForeground(QtGui.QColor("#1976D2"))
                self._batch_table.setItem(row, col, item)

    def _populate_inspect_combo(self, results: list) -> None:
        self._inspect_combo.blockSignals(True)
        self._inspect_combo.clear()
        for r in results:
            self._inspect_combo.addItem(r.get("label", "?"), r.get("offset_index"))
        self._inspect_combo.blockSignals(False)
        if results:
            self._inspect_combo.setCurrentIndex(0)
            self._on_inspect_changed(0)

    def _on_inspect_changed(self, idx: int) -> None:
        if idx < 0 or not self._last_batch:
            return
        offset_idx = self._inspect_combo.itemData(idx)
        if offset_idx is None:
            return

        thr = self._m1_nacd_thr.value() if self._last_mode == "nacd" else self._m2_nacd_thr.value()
        label = self._inspect_combo.currentText()

        self.eval.start_with(label, thr)
        self._populate_points_table()

    def _populate_points_table(self) -> None:
        rng = self._active_eval_range()
        data = self.eval.get_current_arrays(eval_range=rng)
        self._points_table.blockSignals(True)
        self._points_table.setRowCount(0)
        if not data:
            self._points_table.blockSignals(False)
            return

        idx, f_arr, v_arr, w_arr, nacd, mask, vr, severity = data
        n = len(f_arr)
        self._points_table.setRowCount(n)

        colors = self._mode1_colors if self._last_mode == "nacd" else self._mode2_colors
        n_flagged = 0
        for i in range(n):
            if severity is not None:
                issue = severity[i]
            else:
                issue = "contaminated" if mask[i] else "clean"

            row_color = QtGui.QColor(colors.get(issue, "#9E9E9E"))

            vals = [
                f"{f_arr[i]:.2f}",
                f"{v_arr[i]:.1f}",
                f"{w_arr[i]:.2f}",
                f"{nacd[i]:.3f}",
                f"{vr[i]:.3f}" if vr is not None and np.isfinite(vr[i]) else "—",
                issue,
            ]
            for col, txt in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(txt)
                item.setForeground(row_color)
                item.setFlags(item.flags() & ~_ItemIsEditable)
                self._points_table.setItem(i, col, item)

            flag_item = QtWidgets.QTableWidgetItem()
            flag_item.setFlags(
                flag_item.flags() | _ItemIsUserCheckable | _ItemIsEnabled
            )
            is_flagged = bool(mask[i])
            if severity is not None and severity[i] in ("contaminated", "marginal"):
                is_flagged = True
            flag_item.setCheckState(_Checked if is_flagged else _Unchecked)
            self._points_table.setItem(i, 6, flag_item)
            if is_flagged:
                n_flagged += 1

        self._points_table.blockSignals(False)
        pct = 100 * n_flagged / n if n else 0
        self._inspect_summary.setText(f"{n_flagged}/{n} flagged ({pct:.0f}%)")

    # ================================================================
    #  Overlay management
    # ================================================================
    def _clear_nf_overlays(self) -> None:
        try:
            for key, (lf, lw) in list(
                getattr(self.c, '_nf_point_overlay', {}).items()
            ):
                try:
                    lf.remove()
                    lw.remove()
                except Exception:
                    pass
            self.c._nf_point_overlay = {}
        except Exception:
            pass
        # Clear limit lines
        clear_nf_limit_lines(self._nf_limit_artists)
        try:
            self.c.fig.canvas.draw_idle()
        except Exception:
            pass

    # ================================================================
    #  Flag toggles / auto-select
    # ================================================================
    def _on_flag_toggled(self, changed_item) -> None:
        if changed_item is not None:
            col = changed_item.column() if hasattr(changed_item, 'column') else -1
            if col != 6:
                return

    def _on_auto_select(self) -> None:
        rng = self._active_eval_range()
        data = self.eval.get_current_arrays(eval_range=rng)
        if not data:
            return
        _, f_arr, v_arr, w_arr, nacd, mask, vr, severity = data
        filt = self._del_filter.currentIndex()

        self._points_table.blockSignals(True)
        for row in range(self._points_table.rowCount()):
            if row >= len(f_arr):
                break
            match = False
            if filt == 0:
                match = bool(mask[row])
                if severity is not None and severity[row] in ("contaminated", "marginal"):
                    match = True
            elif filt == 1:
                if severity is not None:
                    match = severity[row] == "contaminated"
                else:
                    match = bool(mask[row])
            elif filt == 2:
                match = bool(mask[row])

            flag_item = self._points_table.item(row, 6)
            if flag_item:
                flag_item.setCheckState(_Checked if match else _Unchecked)
        self._points_table.blockSignals(False)

    # ================================================================
    #  Apply / Cancel
    # ================================================================
    def _on_apply_deletions(self) -> None:
        indices = []
        for row in range(self._points_table.rowCount()):
            flag_item = self._points_table.item(row, 6)
            if flag_item and flag_item.checkState() == _Checked:
                indices.append(row)
        self.eval.apply_deletions(indices)
        self._clear_nf_overlays()
        self._points_table.setRowCount(0)
        self._inspect_summary.setText(f"Removed {len(indices)} point(s).")

    def _on_cancel(self) -> None:
        self._clear_nf_overlays()
        try:
            self.eval.cancel()
        except Exception:
            pass
        self._points_table.setRowCount(0)
        self._batch_table.setRowCount(0)
        self._inspect_summary.setText("")

    # ================================================================
    #  Export
    # ================================================================
    def _on_export(self, fmt: str) -> None:
        report = self._last_report
        if not report:
            try:
                report = self.eval.compute_full_report()
                self._last_report = report
            except Exception:
                self._inspect_summary.setText("Run evaluation first.")
                return
        ext = {"csv": "CSV files (*.csv)", "json": "JSON files (*.json)"}
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, f"Export NF Report ({fmt.upper()})", "",
            ext.get(fmt, "All files (*)"),
        )
        if not path:
            return
        try:
            from dc_cut.api.analysis_ops import export_nearfield_report
            result = export_nearfield_report(report, path, fmt=fmt)
            if result["success"]:
                self._inspect_summary.setText(f"Exported to {result['path']}")
            else:
                self._inspect_summary.setText(
                    f"Export error: {'; '.join(result['errors'])}"
                )
        except Exception as exc:
            self._inspect_summary.setText(f"Export error: {exc}")

    def _on_export_npz(self) -> None:
        """Export figure data as NPZ for Report Studio."""
        if not self._last_batch:
            self._inspect_summary.setText("Run evaluation first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export NF Figure Data", "nf_evaluation_data.npz",
            "NumPy files (*.npz);;All (*)",
        )
        if not path:
            return
        try:
            arrays = {}
            for i, r in enumerate(self._last_batch):
                prefix = f"offset_{i}"
                for key in ("f", "v", "w", "nacd", "mask"):
                    if key in r:
                        arrays[f"{prefix}_{key}"] = np.asarray(r[key])
                arrays[f"{prefix}_label"] = np.array(r.get("label", ""))
            arrays["n_offsets"] = np.array(len(self._last_batch))
            arrays["mode"] = np.array(self._last_mode or "")
            # Include reference if available
            if self.eval.has_reference:
                arrays["ref_f"] = self.eval._reference_f
                arrays["ref_v"] = self.eval._reference_v
            np.savez_compressed(path, **arrays)
            self._inspect_summary.setText(f"Exported to {path}")
        except Exception as exc:
            self._inspect_summary.setText(f"Export error: {exc}")

    def _open_scatter_window(self) -> None:
        from dc_cut.gui.views.nf_scatter_window import ScatterWindow
        if self._scatter_window is None or not self._scatter_window.isVisible():
            self._scatter_window = ScatterWindow(self.eval, parent=self)
        else:
            self._scatter_window.refresh()
        self._scatter_window.show()
        self._scatter_window.raise_()

    # ================================================================
    #  showEvent – refresh offset lists
    # ================================================================
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_offset_checks(self._m1_offset_checks, self._m1_offset_layout)
        self._refresh_offset_checks(self._m2_offset_checks, self._m2_offset_layout)

        # Sync reference status
        if self.eval.has_reference:
            self._m2_ref_status.setText(
                f"Reference: {self.eval._reference_source}"
            )
        elif (
            hasattr(self.c, '_nf_reference_f')
            and self.c._nf_reference_f is not None
        ):
            self.eval.set_reference_curve(
                self.c._nf_reference_f,
                self.c._nf_reference_v,
                self.c._nf_reference_source,
            )
            self._m2_ref_status.setText(
                f"Reference: {self.c._nf_reference_source}"
            )

        # Refresh custom offset combo
        try:
            n = min(len(self.c.velocity_arrays), len(self.c.frequency_arrays))
            labels = list(self.c.offset_labels[:n])
            self._m2_custom_offset.clear()
            self._m2_custom_offset.addItems(labels)
        except Exception:
            pass


# Backward-compat alias
NearFieldAnalysisDock = NearFieldEvalDock

