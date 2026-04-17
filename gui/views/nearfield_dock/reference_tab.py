"""Tab 2: Reference-Based mode.

Owns the reference-curve combo, the evaluation-range + severity
widgets, the offset-selection column, and the Run button that
computes V_R against the reference curve.
"""
from __future__ import annotations

from typing import List

import numpy as np

from dc_cut.core.processing.nearfield.criteria import (
    SOURCE_TYPE_LABELS,
    ERROR_LEVEL_LABELS,
)
from dc_cut.core.processing.nearfield.ranges import (
    compute_range_mask,
    reference_coverage_warnings,
)
from dc_cut.gui.widgets.collapsible_section import CollapsibleSection
from dc_cut.gui.widgets.nf_eval_ranges import NFEvalRangesWidget
from dc_cut.gui.widgets.nf_limit_lines import (
    clear_nf_limit_lines,
    draw_nf_limit_lines,
)

from .common import (
    get_selected_indices,
    m2_user_lambda_max,
    make_color_button,
    refresh_offset_checks,
    set_all_offset_checks,
)
from .constants import QtWidgets
from .overlays import draw_reference_overlay


class ReferenceTab(QtWidgets.QWidget):
    """The Reference-Based page of the NF Evaluation dock."""

    def __init__(self, dock) -> None:
        super().__init__()
        self.dock = dock
        self.prev_ref_idx = 0  # revert target for "Load file…" cancel
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

        # ── Reference Curve (collapsible) ──
        ref_sec = CollapsibleSection("Reference Curve", initially_expanded=True)
        ref_form = QtWidgets.QFormLayout()

        self.ref_combo = QtWidgets.QComboBox()
        self.ref_combo.addItems([
            "Longest offset (largest x̄)",
            "Median across offsets (NF-aware)",
            "Specific offset…",
            "Load file…",
        ])
        self.ref_combo.currentIndexChanged.connect(self.on_ref_changed)
        ref_form.addRow("Source:", self.ref_combo)

        self.custom_offset = QtWidgets.QComboBox()
        self.custom_offset.setVisible(False)
        self.custom_offset.currentIndexChanged.connect(
            self.on_custom_offset_changed
        )
        ref_form.addRow("Offset:", self.custom_offset)

        self.ref_status = QtWidgets.QLabel("No reference set")
        self.ref_status.setWordWrap(True)
        ref_form.addRow(self.ref_status)

        ref_sec.add_layout(ref_form)
        layout.addWidget(ref_sec)

        # ── Evaluation Ranges (collapsible) ──
        range_sec = CollapsibleSection(
            "Evaluation Ranges (f bands + λ bounds)", initially_expanded=True
        )
        self.ranges_widget = NFEvalRangesWidget()
        range_sec.add_widget(self.ranges_widget)
        layout.addWidget(range_sec)

        # ── Severity Criteria (collapsible) ──
        sev_sec = CollapsibleSection("Severity Criteria", initially_expanded=True)
        sev_form = QtWidgets.QFormLayout()

        self.source_type = QtWidgets.QComboBox()
        for key, label in SOURCE_TYPE_LABELS.items():
            self.source_type.addItem(label, key)
        self.source_type.currentIndexChanged.connect(self.on_criteria_changed)
        sev_form.addRow("Source type:", self.source_type)

        self.error_level = QtWidgets.QComboBox()
        for key, label in ERROR_LEVEL_LABELS.items():
            self.error_level.addItem(label, key)
        self.error_level.currentIndexChanged.connect(self.on_criteria_changed)
        sev_form.addRow("Error level:", self.error_level)

        self.nacd_thr = QtWidgets.QDoubleSpinBox()
        self.nacd_thr.setRange(0.1, 5.0)
        self.nacd_thr.setDecimals(2)
        self.nacd_thr.setSingleStep(0.1)
        self.nacd_thr.setValue(float(getattr(self.dock.c, 'nacd_thresh', 1.0)))
        sev_form.addRow("NACD threshold:", self.nacd_thr)

        self.vr_onset = QtWidgets.QDoubleSpinBox()
        self.vr_onset.setRange(0.5, 1.0)
        self.vr_onset.setDecimals(2)
        self.vr_onset.setSingleStep(0.05)
        self.vr_onset.setValue(0.90)
        sev_form.addRow("V_R onset threshold:", self.vr_onset)

        self.clean_thr = QtWidgets.QDoubleSpinBox()
        self.clean_thr.setRange(0.5, 1.0)
        self.clean_thr.setDecimals(2)
        self.clean_thr.setSingleStep(0.01)
        self.clean_thr.setValue(0.95)
        sev_form.addRow("Clean threshold:", self.clean_thr)

        self.marginal_thr = QtWidgets.QDoubleSpinBox()
        self.marginal_thr.setRange(0.3, 1.0)
        self.marginal_thr.setDecimals(2)
        self.marginal_thr.setSingleStep(0.01)
        self.marginal_thr.setValue(0.85)
        sev_form.addRow("Marginal threshold:", self.marginal_thr)

        sev_sec.add_layout(sev_form)
        layout.addWidget(sev_sec)

        # ── Colors (collapsible) ──
        color_sec = CollapsibleSection("Colors", initially_expanded=False)
        color_form = QtWidgets.QFormLayout()

        self.clean_color_btn = make_color_button(
            self.dock, self.dock._mode2_colors["clean"], "clean", 2
        )
        color_form.addRow("Clean:", self.clean_color_btn)

        self.marginal_color_btn = make_color_button(
            self.dock, self.dock._mode2_colors["marginal"], "marginal", 2
        )
        color_form.addRow("Marginal:", self.marginal_color_btn)

        self.contam_color_btn = make_color_button(
            self.dock, self.dock._mode2_colors["contaminated"], "contaminated", 2
        )
        color_form.addRow("Contaminated:", self.contam_color_btn)

        self.unknown_color_btn = make_color_button(
            self.dock, self.dock._mode2_colors["unknown"], "unknown", 2
        )
        color_form.addRow("Unknown:", self.unknown_color_btn)

        color_sec.add_layout(color_form)
        layout.addWidget(color_sec)

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
        run_btn = QtWidgets.QPushButton("▶  Run Reference Evaluation")
        run_btn.setStyleSheet(
            "font-weight: bold; padding: 10px; font-size: 13px;"
            "background-color: #1976D2; color: white; border-radius: 4px;"
        )
        run_btn.clicked.connect(self.run)
        layout.addWidget(run_btn)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addStretch()

    # ================================================================
    #  Reference-curve combo handlers
    # ================================================================
    def on_ref_changed(self, idx: int) -> None:
        """Drive reference creation directly from the combo selection."""
        self.custom_offset.setVisible(idx == 2)
        if idx == 2:
            refresh_offset_checks(self.dock, self.offset_checks, self.offset_layout)
            try:
                n = min(
                    len(self.dock.c.velocity_arrays),
                    len(self.dock.c.frequency_arrays),
                )
                labels = list(self.dock.c.offset_labels[:n])
                self.custom_offset.blockSignals(True)
                self.custom_offset.clear()
                self.custom_offset.addItems(labels)
                self.custom_offset.blockSignals(False)
            except Exception:
                pass
            self.prev_ref_idx = idx
            return

        if idx == 3:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Load Reference Curve", "",
                "CSV files (*.csv);;NPZ files (*.npz);;All (*)",
            )
            if not path:
                self.ref_combo.blockSignals(True)
                self.ref_combo.setCurrentIndex(self.prev_ref_idx)
                self.ref_combo.blockSignals(False)
                return
            try:
                self.dock.eval.load_reference_file(path)
                self.publish_reference()
            except Exception as exc:
                self.ref_status.setText(f"Error: {exc}")
            self.prev_ref_idx = idx
            self.dock._redraw_m2_limits_for_current_range()
            return

        mode = "longest_offset" if idx == 0 else "median"
        try:
            self.dock.eval.compute_reference_from_offsets(mode)
            self.publish_reference()
        except Exception as exc:
            self.ref_status.setText(f"Error: {exc}")
        self.prev_ref_idx = idx
        self.dock._redraw_m2_limits_for_current_range()

    def on_custom_offset_changed(self, idx: int) -> None:
        """Auto-build when the user picks a specific offset."""
        if self.ref_combo.currentIndex() != 2 or idx < 0:
            return
        try:
            self.dock.eval.compute_reference_from_offsets(
                "custom_offset", custom_index=idx,
            )
            self.publish_reference()
        except Exception as exc:
            self.ref_status.setText(f"Error: {exc}")
        self.dock._redraw_m2_limits_for_current_range()

    def publish_reference(self) -> None:
        """Push the freshly built reference curve to the controller."""
        c = self.dock.c
        ev = self.dock.eval
        c._nf_reference_f = ev._reference_f
        c._nf_reference_v = ev._reference_v
        c._nf_reference_source = ev._reference_source
        self.ref_status.setText(f"Reference: {ev._reference_source}")

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

    # ================================================================
    #  Run
    # ================================================================
    def run(self) -> None:
        """Run reference-based evaluation on selected offsets."""
        dock = self.dock
        dock._clear_nf_overlays()
        dock._last_mode = "reference"

        ev = dock.eval
        ev.thr = self.nacd_thr.value()
        ev._vr_onset_threshold = self.vr_onset.value()
        ev._clean_threshold = self.clean_thr.value()
        ev._marginal_threshold = self.marginal_thr.value()
        st = self.source_type.currentData() or "sledgehammer"
        ev.set_source_type(st)

        # Build reference if needed
        if not ev.has_reference:
            try:
                ref_idx = self.ref_combo.currentIndex()
                if ref_idx == 0:
                    ev.compute_reference_from_offsets("longest_offset")
                elif ref_idx == 1:
                    ev.compute_reference_from_offsets("median")
                else:
                    ev.compute_reference_from_offsets("longest_offset")
                dock.c._nf_reference_f = ev._reference_f
                dock.c._nf_reference_v = ev._reference_v
                self.ref_status.setText(f"Reference: {ev._reference_source}")
            except Exception as exc:
                self.status.setText(f"Reference error: {exc}")
                return

        selected = get_selected_indices(self.offset_checks)
        if not selected:
            self.status.setText("Select at least one offset.")
            return

        eval_range = self.ranges_widget.get_range()

        try:
            all_results = ev.evaluate_all_offsets(eval_range=eval_range)
        except Exception as exc:
            self.status.setText(f"Evaluation error: {exc}")
            return

        results = [r for r in all_results if r.get("offset_index") in selected]
        if not results:
            self.status.setText("No matching offsets evaluated.")
            return

        dock._last_batch = results
        dock._overlay_offsets = selected

        # Per-point overlays using the shared range mask
        from dc_cut.core.processing.nearfield import (
            compute_nacd_array,
            compute_normalized_vr_with_validity,
            classify_nearfield_severity,
        )
        from dc_cut.core.processing.wavelength_lines import (
            parse_source_offset_from_label,
        )
        recv = dock._nacd_tab.array_positions()

        f_ref_full = ev._reference_f
        v_ref_full = ev._reference_v

        for r in results:
            idx = r["offset_index"]
            f = np.asarray(dock.c.frequency_arrays[idx], float)
            v = np.asarray(dock.c.velocity_arrays[idx], float)
            w = np.asarray(dock.c.wavelength_arrays[idx], float)
            lbl = r["label"]
            so = parse_source_offset_from_label(lbl)
            nacd = compute_nacd_array(recv, f, v, source_offset=so)

            user_lam_max = m2_user_lambda_max(eval_range)
            vr = compute_normalized_vr_with_validity(
                f, v, f_ref_full, v_ref_full,
                ev._lambda_max_ref,
                user_lambda_max=user_lam_max,
            )

            in_range = compute_range_mask(f, v, eval_range)
            if not eval_range.is_empty():
                vr = np.where(in_range, vr, np.nan)

            severity = classify_nearfield_severity(
                vr, ev._clean_threshold,
                ev._marginal_threshold,
                ev._unknown_action,
            )

            draw_reference_overlay(
                dock.c, idx, f, v, w, severity, dock._mode2_colors
            )

        # Draw λ- and f-limit lines on the canvas via the shared
        # DerivedLimitSet renderer (driven by the Limit Lines tab).
        dock._limits.active_mode = "m2"
        if not eval_range.is_empty():
            dock._limits.rebuild_tree()
        else:
            # No evaluation range: publish every evaluated offset's
            # own λ_max AND the reference's λ_max into the Limit
            # Lines tree (each as its own band), together with their
            # derived f-partners computed from the reference V(f).
            # All are visible by default; the user can toggle/recolor
            # individual lines from the tree.
            if self.ranges_widget.show_lines():
                from dc_cut.core.processing.nearfield.range_derivation import (
                    derive_limits_from_lambda_values,
                )
                triples: list = []
                for r in results:
                    lam = float(r.get("lambda_max", 0.0))
                    if lam > 0:
                        triples.append((lam, f_ref_full, v_ref_full))
                ref_lam = float(getattr(ev, "_lambda_max_ref", 0.0) or 0.0)
                if np.isfinite(ref_lam) and ref_lam > 0:
                    triples.append((ref_lam, f_ref_full, v_ref_full))
                derived = derive_limits_from_lambda_values(triples)
                dock._limits.rebuild_tree_with_set(
                    derived, hide_freq_by_default=False,
                )
            else:
                clear_nf_limit_lines(dock._nf_limit_artists)
                dock._nf_limit_artists = []

        dock._results_tab.populate_batch_table(results)
        dock._results_tab.populate_inspect_combo(results)
        dock._tabs.setCurrentIndex(3)

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
        self.status.setText(msg)


__all__ = ["ReferenceTab"]
