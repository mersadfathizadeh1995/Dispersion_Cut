"""Tab 1: NACD-Only mode (geometry-based, no reference required).

Owns its own widgets (geometry, criteria, colors, ranges, offset
checks, Run button) and implements:

* ``on_criteria_changed`` — auto-fill NACD threshold from source
  type + error level
* ``apply_range_gate`` — enable the range editor only when one
  offset is selected
* ``run`` — execute the NACD-only evaluation, draw overlays, and
  defer limit-line drawing to :class:`LimitsCoordinator`
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from dc_cut.core.processing.nearfield.criteria import (
    SOURCE_TYPE_LABELS,
    ERROR_LEVEL_LABELS,
)
from dc_cut.core.processing.nearfield.ranges import (
    EvaluationRange,
    compute_range_mask,
)
from dc_cut.gui.widgets.collapsible_section import CollapsibleSection
from dc_cut.gui.widgets.nf_eval_ranges import NFEvalRangesWidget
from dc_cut.gui.widgets.nf_limit_lines import (
    clear_nf_limit_lines,
    draw_nf_limit_lines,
)

from .common import (
    get_array_positions,
    get_selected_indices,
    make_color_button,
    set_all_offset_checks,
)
from .constants import QtWidgets
from .overlays import draw_nacd_overlay


class NacdTab(QtWidgets.QWidget):
    """The NACD-Only page of the NF Evaluation dock."""

    def __init__(self, dock) -> None:
        super().__init__()
        self.dock = dock
        self._build()

    # ================================================================
    #  UI build
    # ================================================================
    def _build(self) -> None:
        scroll_layout = QtWidgets.QVBoxLayout(self)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        page = QtWidgets.QWidget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        scroll_layout.addWidget(scroll)

        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Array Geometry (collapsible) ──
        geom_sec = CollapsibleSection("Array Geometry", initially_expanded=True)
        geom_form = QtWidgets.QFormLayout()

        self.n_recv = QtWidgets.QSpinBox()
        self.n_recv.setRange(2, 200)
        self.n_recv.setValue(24)
        geom_form.addRow("# Receivers:", self.n_recv)

        self.dx = QtWidgets.QDoubleSpinBox()
        self.dx.setRange(0.1, 50.0)
        self.dx.setDecimals(2)
        self.dx.setValue(2.0)
        geom_form.addRow("Spacing (dx, m):", self.dx)

        self.first_pos = QtWidgets.QDoubleSpinBox()
        self.first_pos.setRange(-500.0, 500.0)
        self.first_pos.setDecimals(1)
        self.first_pos.setValue(0.0)
        geom_form.addRow("First receiver (m):", self.first_pos)

        geom_sec.add_layout(geom_form)
        layout.addWidget(geom_sec)

        # ── NACD Criteria (collapsible) ──
        crit_sec = CollapsibleSection("NACD Criteria", initially_expanded=True)
        crit_form = QtWidgets.QFormLayout()

        self.source_type = QtWidgets.QComboBox()
        for key, label in SOURCE_TYPE_LABELS.items():
            self.source_type.addItem(label, key)
        self.source_type.currentIndexChanged.connect(self.on_criteria_changed)
        crit_form.addRow("Source type:", self.source_type)

        self.error_level = QtWidgets.QComboBox()
        for key, label in ERROR_LEVEL_LABELS.items():
            self.error_level.addItem(label, key)
        self.error_level.currentIndexChanged.connect(self.on_criteria_changed)
        crit_form.addRow("Error level:", self.error_level)

        self.nacd_thr = QtWidgets.QDoubleSpinBox()
        self.nacd_thr.setRange(0.1, 5.0)
        self.nacd_thr.setDecimals(2)
        self.nacd_thr.setSingleStep(0.1)
        self.nacd_thr.setValue(float(getattr(self.dock.c, 'nacd_thresh', 1.0)))
        crit_form.addRow("NACD threshold:", self.nacd_thr)

        crit_sec.add_layout(crit_form)
        layout.addWidget(crit_sec)

        # ── Colors (collapsible) ──
        color_sec = CollapsibleSection("Colors", initially_expanded=False)
        color_form = QtWidgets.QFormLayout()

        self.clean_color_btn = make_color_button(
            self.dock, self.dock._mode1_colors["clean"], "clean", 1
        )
        color_form.addRow("Clean:", self.clean_color_btn)

        self.contam_color_btn = make_color_button(
            self.dock, self.dock._mode1_colors["contaminated"], "contaminated", 1
        )
        color_form.addRow("Contaminated:", self.contam_color_btn)

        color_sec.add_layout(color_form)
        layout.addWidget(color_sec)

        # ── Evaluation Ranges (collapsible) ──
        lim_sec = CollapsibleSection(
            "Evaluation Ranges (f bands + λ bounds)", initially_expanded=True
        )
        self.ranges_widget = NFEvalRangesWidget()
        lim_sec.add_widget(self.ranges_widget)
        layout.addWidget(lim_sec)

        # ── Offset Selection ──
        offset_sec = CollapsibleSection("Offset Selection", initially_expanded=True)
        self.offset_layout = QtWidgets.QVBoxLayout()
        btn_row = QtWidgets.QHBoxLayout()
        sel_all = QtWidgets.QPushButton("Select All")
        sel_all.clicked.connect(
            lambda: set_all_offset_checks(self.dock, self.offset_checks, True)
        )
        sel_none = QtWidgets.QPushButton("Select None")
        sel_none.clicked.connect(
            lambda: set_all_offset_checks(self.dock, self.offset_checks, False)
        )
        btn_row.addWidget(sel_all)
        btn_row.addWidget(sel_none)
        self.offset_layout.addLayout(btn_row)
        self.offset_checks: List[QtWidgets.QCheckBox] = []
        offset_sec.add_layout(self.offset_layout)
        layout.addWidget(offset_sec)

        # ── Run Button ──
        run_btn = QtWidgets.QPushButton("▶  Run NACD Evaluation")
        run_btn.setStyleSheet(
            "font-weight: bold; padding: 10px; font-size: 13px;"
            "background-color: #1565C0; color: white; border-radius: 4px;"
        )
        run_btn.clicked.connect(self.run)
        layout.addWidget(run_btn)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addStretch()

        # Pre-fill from prefs (geometry only; ranges handled by load_dock_prefs).
        from .prefs_io import m1_load_geometry_prefs
        m1_load_geometry_prefs(self.dock)

    # ================================================================
    #  Handlers
    # ================================================================
    def on_criteria_changed(self, _=None) -> None:
        try:
            from dc_cut.core.processing.nearfield.criteria import (
                resolve_nacd_threshold,
            )
            st = self.source_type.currentData() or "sledgehammer"
            el = self.error_level.currentData() or "10_15pct"
            thr = resolve_nacd_threshold(source_type=st, error_level=el)
            self.nacd_thr.setValue(thr)
        except Exception:
            pass

    def apply_range_gate(self, *_args, **_kwargs) -> None:
        """Enable the range editor only when ONE offset is selected.

        Rationale: NACD-Only limit lines are derived using the evaluated
        offset's own V(f) curve, so a *per-row* evaluation range only
        makes sense for a single offset.  With multiple offsets selected
        the range is forced empty and only each offset's own auto-
        derived ``\u03bb_max`` is drawn at Run time.
        """
        sel = sum(1 for c in self.offset_checks if c.isChecked())
        if sel == 1:
            self.ranges_widget.set_editing_enabled(True)
        else:
            self.ranges_widget.set_editing_enabled(
                False,
                reason=(
                    "Custom evaluation ranges are only editable when "
                    "exactly one offset is selected.  With multiple "
                    "offsets, only each offset's \u03bb_max line is "
                    "drawn after Run."
                ),
            )
        # Any stale limit lines from a previous run are now invalid.
        self.dock._m1_invalidate_limit_lines()

    def array_positions(self) -> np.ndarray:
        return get_array_positions(
            self.n_recv.value(), self.dx.value(), self.first_pos.value()
        )

    # ================================================================
    #  Run
    # ================================================================
    def run(self) -> None:
        """Run NACD-only evaluation on selected offsets.

        Contamination rule per point:
            contaminated = (NACD >= thr)  OR  (point outside user's EvaluationRange)
        """
        dock = self.dock
        dock._clear_nf_overlays()
        dock._last_mode = "nacd"

        thr = self.nacd_thr.value()
        recv = self.array_positions()
        selected = get_selected_indices(self.offset_checks)

        if not selected:
            self.status.setText("Select at least one offset.")
            return

        from dc_cut.core.processing.nearfield.nacd import compute_nacd_array
        from dc_cut.core.processing.wavelength_lines import (
            parse_source_offset_from_label,
        )

        single_offset = (len(selected) == 1)
        eval_range = (
            self.ranges_widget.get_range() if single_offset
            else EvaluationRange()
        )

        results = []
        for idx in selected:
            f = np.asarray(dock.c.frequency_arrays[idx], float)
            v = np.asarray(dock.c.velocity_arrays[idx], float)
            w = np.asarray(dock.c.wavelength_arrays[idx], float)
            lbl = (
                dock.c.offset_labels[idx]
                if idx < len(dock.c.offset_labels)
                else f"Offset {idx}"
            )
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

            draw_nacd_overlay(dock.c, idx, f, v, w, mask, dock._mode1_colors)

        # ── Draw λ- and f-limit lines on the canvas (only now!) ────
        # NACD-Only lines are computed against a SPECIFIC offset's
        # V(f) curve.  So:
        # * single offset + user range -> derive the full DerivedLimitSet
        #   via the Limit Lines tab machinery;
        # * multiple offsets          -> draw each offset's own
        #   auto-derived λ_max line only (no cross-domain derivation);
        # * single offset + empty range -> legacy λ_max only.
        dock._limits.active_mode = "m1"
        clear_nf_limit_lines(dock._nf_limit_artists)
        dock._nf_limit_artists = []

        if single_offset and not eval_range.is_empty():
            only_idx = selected[0]
            dock._limits.force_vf_idx = only_idx
            try:
                dock._limits.rebuild_tree()
            finally:
                dock._limits.force_vf_idx = None
        elif self.ranges_widget.show_lines() and results:
            artists: list = []
            for r in results:
                lam = float(r.get("lambda_max", 0.0))
                if lam <= 0:
                    continue
                artists.extend(draw_nf_limit_lines(
                    dock.c.ax_freq, dock.c.ax_wave,
                    lambda_max=lam,
                    lambda_min=None,
                    freq_bands=None,
                ))
            dock._nf_limit_artists = artists

        dock._last_batch = results
        dock._overlay_offsets = selected
        dock._results_tab.populate_batch_table(results)
        dock._results_tab.populate_inspect_combo(results)
        dock._tabs.setCurrentIndex(3)

        n_total = sum(r["n_total"] for r in results)
        n_contam = sum(r["n_contaminated"] for r in results)
        self.status.setText(
            f"Evaluated {len(results)} offset(s), {n_total} points. "
            f"{n_contam} contaminated."
        )


__all__ = ["NacdTab"]
