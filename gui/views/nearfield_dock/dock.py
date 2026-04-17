"""Thin NF Evaluation dock orchestrator.

Wires four tabs (NACD-Only, Reference, Limit Lines, Results) plus a
:class:`LimitsCoordinator`.  All heavy logic now lives in the sibling
modules; this file only owns shared state, the dock-level overrides
(``showEvent``), and a set of backward-compat property shims so the
legacy private attribute names keep working for ``main_window.py``
and any reach-in tests.
"""
from __future__ import annotations

from typing import List, Optional

from .common import refresh_offset_checks
from .constants import QtWidgets
from .limits_coord import LimitsCoordinator
from .nacd_tab import NacdTab
from .overlays import clear_nf_overlays
from .prefs_io import load_dock_prefs, save_range_prefs
from .reference_tab import ReferenceTab
from .results_tab import ResultsTab

from dc_cut.core.processing.nearfield.ranges import EvaluationRange

from .constants import _MODE1_COLORS, _MODE2_COLORS


class NearFieldEvalDock(QtWidgets.QDockWidget):
    """Near-Field Evaluation dock – NACD-Only | Reference | Limit Lines | Results."""

    def __init__(
        self,
        controller,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
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

        # ── Shared state ────────────────────────────────────────────
        self._scatter_window = None
        self._last_report = None
        self._last_batch: Optional[list] = None
        self._last_mode: Optional[str] = None  # 'nacd' or 'reference'
        self._overlay_offsets: list = []
        self._nf_limit_artists: list = []

        # User-configurable severity colors (tabs write into these).
        self._mode1_colors = dict(_MODE1_COLORS)
        self._mode2_colors = dict(_MODE2_COLORS)

        # ── Tabs + coordinator ──────────────────────────────────────
        self._nacd_tab = NacdTab(self)
        self._tabs.addTab(self._nacd_tab, "NACD-Only")

        self._reference_tab = ReferenceTab(self)
        self._tabs.addTab(self._reference_tab, "Reference")

        self._limits = LimitsCoordinator(self)
        self._tabs.addTab(self._limits.tab, "Limit Lines")
        self._tabs.currentChanged.connect(self._limits.on_top_tab_changed)

        self._results_tab = ResultsTab(self)
        self._tabs.addTab(self._results_tab, "Results")

        # Wire preferences now that every widget exists.
        load_dock_prefs(self)

    # ================================================================
    #  Dock-level operations (used by tabs + external callers)
    # ================================================================
    def _clear_nf_overlays(self) -> None:
        clear_nf_overlays(self.c, self._nf_limit_artists)

    def _save_range_prefs(self, *args) -> None:
        save_range_prefs(self)

    def _m1_apply_range_gate(self, *_args, **_kwargs) -> None:
        if hasattr(self, "_nacd_tab"):
            self._nacd_tab.apply_range_gate()

    def _m1_invalidate_limit_lines(self) -> None:
        self._limits.invalidate_m1()

    def _redraw_m1_limits_for_current_range(self) -> None:
        self._limits.redraw_m1_for_current_range()

    def _redraw_m2_limits_for_current_range(self) -> None:
        self._limits.redraw_m2_for_current_range()

    def _get_selected_indices(self, checks_list: list) -> List[int]:
        return [i for i, chk in enumerate(checks_list) if chk.isChecked()]

    def _get_array_positions(self):
        return self._nacd_tab.array_positions()

    def _active_eval_range(self) -> EvaluationRange:
        """Return the EvaluationRange from whichever tab is driving results."""
        if self._last_mode == "reference":
            return self._reference_tab.ranges_widget.get_range()
        return self._nacd_tab.ranges_widget.get_range()

    # ================================================================
    #  Backward-compat property shims
    # ================================================================
    # ---- NACD tab -----------------------------------------------------
    @property
    def _m1_n_recv(self):
        return self._nacd_tab.n_recv

    @property
    def _m1_dx(self):
        return self._nacd_tab.dx

    @property
    def _m1_first_pos(self):
        return self._nacd_tab.first_pos

    @property
    def _m1_source_type(self):
        return self._nacd_tab.source_type

    @property
    def _m1_error_level(self):
        return self._nacd_tab.error_level

    @property
    def _m1_nacd_thr(self):
        return self._nacd_tab.nacd_thr

    @property
    def _m1_clean_color_btn(self):
        return self._nacd_tab.clean_color_btn

    @property
    def _m1_contam_color_btn(self):
        return self._nacd_tab.contam_color_btn

    @property
    def _m1_ranges(self):
        return self._nacd_tab.ranges_widget

    @property
    def _m1_offset_checks(self):
        return self._nacd_tab.offset_checks

    @property
    def _m1_offset_layout(self):
        return self._nacd_tab.offset_layout

    @property
    def _m1_status(self):
        return self._nacd_tab.status

    # ---- Reference tab -----------------------------------------------
    @property
    def _m2_ref_combo(self):
        return self._reference_tab.ref_combo

    @property
    def _m2_custom_offset(self):
        return self._reference_tab.custom_offset

    @property
    def _m2_ref_status(self):
        return self._reference_tab.ref_status

    @property
    def _m2_prev_ref_idx(self):
        return self._reference_tab.prev_ref_idx

    @_m2_prev_ref_idx.setter
    def _m2_prev_ref_idx(self, value):
        self._reference_tab.prev_ref_idx = value

    @property
    def _m2_ranges(self):
        return self._reference_tab.ranges_widget

    @property
    def _m2_source_type(self):
        return self._reference_tab.source_type

    @property
    def _m2_error_level(self):
        return self._reference_tab.error_level

    @property
    def _m2_nacd_thr(self):
        return self._reference_tab.nacd_thr

    @property
    def _m2_vr_onset(self):
        return self._reference_tab.vr_onset

    @property
    def _m2_clean_thr(self):
        return self._reference_tab.clean_thr

    @property
    def _m2_marginal_thr(self):
        return self._reference_tab.marginal_thr

    @property
    def _m2_clean_color_btn(self):
        return self._reference_tab.clean_color_btn

    @property
    def _m2_marginal_color_btn(self):
        return self._reference_tab.marginal_color_btn

    @property
    def _m2_contam_color_btn(self):
        return self._reference_tab.contam_color_btn

    @property
    def _m2_unknown_color_btn(self):
        return self._reference_tab.unknown_color_btn

    @property
    def _m2_offset_checks(self):
        return self._reference_tab.offset_checks

    @property
    def _m2_offset_layout(self):
        return self._reference_tab.offset_layout

    @property
    def _m2_status(self):
        return self._reference_tab.status

    # ---- Results tab --------------------------------------------------
    @property
    def _batch_table(self):
        return self._results_tab.batch_table

    @property
    def _points_table(self):
        return self._results_tab.points_table

    @property
    def _inspect_combo(self):
        return self._results_tab.inspect_combo

    @property
    def _inspect_summary(self):
        return self._results_tab.inspect_summary

    @property
    def _del_filter(self):
        return self._results_tab.del_filter

    @property
    def _btn_apply(self):
        return self._results_tab.btn_apply

    @property
    def _btn_cancel(self):
        return self._results_tab.btn_cancel

    # ---- Limits coordinator ------------------------------------------
    @property
    def _limits_tab(self):
        return self._limits.tab

    @property
    def _limits_state_m1(self):
        return self._limits.state_m1

    @_limits_state_m1.setter
    def _limits_state_m1(self, value):
        self._limits.state_m1 = value

    @property
    def _limits_state_m2(self):
        return self._limits.state_m2

    @_limits_state_m2.setter
    def _limits_state_m2(self, value):
        self._limits.state_m2 = value

    @property
    def _active_limits_mode(self):
        return self._limits.active_mode

    @_active_limits_mode.setter
    def _active_limits_mode(self, value):
        self._limits.active_mode = value

    @property
    def _current_derived_set(self):
        return self._limits.current_derived_set

    @_current_derived_set.setter
    def _current_derived_set(self, value):
        self._limits.current_derived_set = value

    @property
    def _m1_force_vf_idx(self):
        return self._limits.force_vf_idx

    @_m1_force_vf_idx.setter
    def _m1_force_vf_idx(self, value):
        self._limits.force_vf_idx = value

    # ================================================================
    #  showEvent – refresh offset lists
    # ================================================================
    def showEvent(self, event) -> None:
        super().showEvent(event)
        refresh_offset_checks(
            self, self._nacd_tab.offset_checks, self._nacd_tab.offset_layout,
            default_checked=False,
        )
        refresh_offset_checks(
            self, self._reference_tab.offset_checks, self._reference_tab.offset_layout
        )

        # Sync reference status
        if self.eval.has_reference:
            self._reference_tab.ref_status.setText(
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
            self._reference_tab.ref_status.setText(
                f"Reference: {self.c._nf_reference_source}"
            )

        # Refresh custom offset combo
        try:
            n = min(len(self.c.velocity_arrays), len(self.c.frequency_arrays))
            labels = list(self.c.offset_labels[:n])
            self._reference_tab.custom_offset.clear()
            self._reference_tab.custom_offset.addItems(labels)
        except Exception:
            pass


# Backward-compat alias
NearFieldAnalysisDock = NearFieldEvalDock


__all__ = ["NearFieldEvalDock", "NearFieldAnalysisDock"]
