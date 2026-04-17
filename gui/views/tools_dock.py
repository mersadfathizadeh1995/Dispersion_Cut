"""Tools dock – Roll-off Analysis and Mode Jump Detection.

Surfaces the core functions from ``onset.py`` and ``mode_detection.py``
as interactive tools with per-offset evaluation, canvas overlays,
results tables, and export capabilities.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore

from dc_cut.gui.widgets.collapsible_section import CollapsibleSection

# ── Qt5 / Qt6 enum compat ──────────────────────────────────────────
try:
    _Checked = QtCore.Qt.Checked
    _Unchecked = QtCore.Qt.Unchecked
except AttributeError:
    _Checked = QtCore.Qt.CheckState.Checked
    _Unchecked = QtCore.Qt.CheckState.Unchecked

try:
    _ItemIsUserCheckable = QtCore.Qt.ItemIsUserCheckable
    _ItemIsEnabled = QtCore.Qt.ItemIsEnabled
    _ItemIsEditable = QtCore.Qt.ItemIsEditable
except AttributeError:
    _ItemIsUserCheckable = QtCore.Qt.ItemFlag.ItemIsUserCheckable
    _ItemIsEnabled = QtCore.Qt.ItemFlag.ItemIsEnabled
    _ItemIsEditable = QtCore.Qt.ItemFlag.ItemIsEditable

# Rolloff overlay colours
_ROLLOFF_PALETTE = [
    '#E53935', '#1E88E5', '#43A047', '#FB8C00', '#8E24AA',
    '#00ACC1', '#D81B60', '#6D4C41', '#FDD835', '#546E7A',
]

# Mode-jump overlay colours
_DEFAULT_MJ_COLORS = {
    "mode_jump": "#E040FB",     # purple
    "mode_kissing": "#FFC107",  # amber
    "clean": "#4CAF50",         # green
}


class ToolsDock(QtWidgets.QDockWidget):
    """Tools dock – Roll-off Analysis | Mode Jump Detection."""

    def __init__(self, controller, parent=None):
        super().__init__("Tools", parent)
        self.setObjectName("ToolsDock")
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

        self._rolloff_overlays: list = []   # (line_freq, line_wave)
        self._mj_overlays: dict = {}        # (offset_idx, i) -> (lf, lw)
        self._last_rolloff_results: list = []
        self._last_mj_results: list = []

        self._mj_colors = dict(_DEFAULT_MJ_COLORS)

        self._build_rolloff_tab()
        self._build_mode_jump_tab()

    # ================================================================
    #  Tab 1: Roll-off Analysis
    # ================================================================
    def _build_rolloff_tab(self):
        page = QtWidgets.QWidget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Settings ──
        settings_sec = CollapsibleSection("Settings", initially_expanded=True)
        sf = QtWidgets.QFormLayout()

        self._ro_method = QtWidgets.QComboBox()
        self._ro_method.addItems([
            "running_max", "derivative", "curvature",
            "vr_drop (requires reference)", "multi (all + consensus)",
        ])
        self._ro_method.setCurrentIndex(0)
        self._ro_method.currentIndexChanged.connect(self._ro_on_method_changed)
        sf.addRow("Method:", self._ro_method)

        self._ro_smooth = QtWidgets.QSpinBox()
        self._ro_smooth.setRange(3, 21)
        self._ro_smooth.setValue(5)
        sf.addRow("Smoothing window:", self._ro_smooth)

        self._ro_min_drop = QtWidgets.QDoubleSpinBox()
        self._ro_min_drop.setRange(0.01, 0.50)
        self._ro_min_drop.setDecimals(2)
        self._ro_min_drop.setSingleStep(0.01)
        self._ro_min_drop.setValue(0.05)
        sf.addRow("Min drop (fraction):", self._ro_min_drop)

        self._ro_vr_thr = QtWidgets.QDoubleSpinBox()
        self._ro_vr_thr.setRange(0.50, 1.00)
        self._ro_vr_thr.setDecimals(2)
        self._ro_vr_thr.setSingleStep(0.01)
        self._ro_vr_thr.setValue(0.95)
        self._ro_vr_thr.setToolTip("V_R threshold for vr_drop method")
        sf.addRow("V_R threshold:", self._ro_vr_thr)

        self._ro_min_consec = QtWidgets.QSpinBox()
        self._ro_min_consec.setRange(1, 10)
        self._ro_min_consec.setValue(2)
        sf.addRow("Min consecutive:", self._ro_min_consec)

        settings_sec.add_layout(sf)
        layout.addWidget(settings_sec)

        # ── Reference status ──
        ref_sec = CollapsibleSection("Reference (for vr_drop)", initially_expanded=False)
        self._ro_ref_label = QtWidgets.QLabel("Reads from NF Eval dock")
        self._ro_ref_label.setWordWrap(True)
        ref_sec.add_widget(self._ro_ref_label)
        layout.addWidget(ref_sec)

        # ── Offset Selection ──
        offset_sec = CollapsibleSection("Offset Selection", initially_expanded=True)
        self._ro_offset_layout = QtWidgets.QVBoxLayout()
        btn_row = QtWidgets.QHBoxLayout()
        sel_all = QtWidgets.QPushButton("Select All")
        sel_all.clicked.connect(lambda: self._set_all_checks(self._ro_offset_checks, True))
        sel_none = QtWidgets.QPushButton("Select None")
        sel_none.clicked.connect(lambda: self._set_all_checks(self._ro_offset_checks, False))
        btn_row.addWidget(sel_all)
        btn_row.addWidget(sel_none)
        self._ro_offset_layout.addLayout(btn_row)
        self._ro_offset_checks: List[QtWidgets.QCheckBox] = []
        offset_sec.add_layout(self._ro_offset_layout)
        layout.addWidget(offset_sec)

        # ── Run / Clear ──
        run_btn = QtWidgets.QPushButton("▶  Run Roll-off Analysis")
        run_btn.setStyleSheet(
            "font-weight: bold; padding: 10px; font-size: 13px;"
            "background-color: #5E35B1; color: white; border-radius: 4px;"
        )
        run_btn.clicked.connect(self._ro_run)
        layout.addWidget(run_btn)

        clear_btn = QtWidgets.QPushButton("Clear Overlays")
        clear_btn.clicked.connect(self._ro_clear)
        layout.addWidget(clear_btn)

        self._ro_status = QtWidgets.QLabel("")
        self._ro_status.setWordWrap(True)
        layout.addWidget(self._ro_status)

        # ── Results ──
        results_sec = CollapsibleSection("Results", initially_expanded=True)
        self._ro_table = QtWidgets.QTableWidget()
        self._ro_table.setColumnCount(6)
        self._ro_table.setHorizontalHeaderLabels([
            "Offset", "Rolloff f (Hz)", "Rolloff λ (m)",
            "Rolloff V (m/s)", "Confidence", "Method",
        ])
        try:
            self._ro_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Stretch
            )
        except AttributeError:
            self._ro_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeMode.Stretch
            )
        self._ro_table.setMaximumHeight(200)
        results_sec.add_widget(self._ro_table)
        layout.addWidget(results_sec)

        # ── Export ──
        export_sec = CollapsibleSection("Export", initially_expanded=False)
        export_row = QtWidgets.QHBoxLayout()
        csv_btn = QtWidgets.QPushButton("Export CSV")
        csv_btn.clicked.connect(self._ro_export_csv)
        export_row.addWidget(csv_btn)
        npz_btn = QtWidgets.QPushButton("Export NPZ")
        npz_btn.clicked.connect(self._ro_export_npz)
        export_row.addWidget(npz_btn)
        export_sec.add_layout(export_row)
        layout.addWidget(export_sec)

        layout.addStretch()
        self._tabs.addTab(scroll, "Roll-off")

    # ================================================================
    #  Tab 2: Mode Jump Detection
    # ================================================================
    def _build_mode_jump_tab(self):
        page = QtWidgets.QWidget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Detection Mode ──
        mode_sec = CollapsibleSection("Detection Mode", initially_expanded=True)
        mf = QtWidgets.QFormLayout()

        self._mj_mode = QtWidgets.QComboBox()
        self._mj_mode.addItems(["reference_based", "standalone (no reference)"])
        self._mj_mode.currentIndexChanged.connect(self._mj_on_mode_changed)
        mf.addRow("Mode:", self._mj_mode)

        mode_sec.add_layout(mf)
        layout.addWidget(mode_sec)

        # ── Reference-Based Settings ──
        self._mj_ref_sec = CollapsibleSection("Reference-Based Settings", initially_expanded=True)
        rf = QtWidgets.QFormLayout()

        self._mj_rel_jump = QtWidgets.QDoubleSpinBox()
        self._mj_rel_jump.setRange(0.05, 0.50)
        self._mj_rel_jump.setDecimals(2)
        self._mj_rel_jump.setSingleStep(0.01)
        self._mj_rel_jump.setValue(0.15)
        self._mj_rel_jump.setToolTip("V_meas > V_ref × (1 + threshold) → flagged")
        rf.addRow("Relative jump (fraction):", self._mj_rel_jump)

        self._mj_min_consec_ref = QtWidgets.QSpinBox()
        self._mj_min_consec_ref.setRange(1, 10)
        self._mj_min_consec_ref.setValue(3)
        rf.addRow("Min consecutive:", self._mj_min_consec_ref)

        self._mj_ref_sec.add_layout(rf)
        layout.addWidget(self._mj_ref_sec)

        # ── Standalone Settings ──
        self._mj_sa_sec = CollapsibleSection("Standalone Settings", initially_expanded=True)
        sf2 = QtWidgets.QFormLayout()

        self._mj_sa_smooth = QtWidgets.QSpinBox()
        self._mj_sa_smooth.setRange(3, 21)
        self._mj_sa_smooth.setValue(7)
        sf2.addRow("Smoothing window:", self._mj_sa_smooth)

        self._mj_sa_sigma = QtWidgets.QDoubleSpinBox()
        self._mj_sa_sigma.setRange(1.0, 5.0)
        self._mj_sa_sigma.setDecimals(1)
        self._mj_sa_sigma.setSingleStep(0.5)
        self._mj_sa_sigma.setValue(2.5)
        sf2.addRow("Jump threshold (σ):", self._mj_sa_sigma)

        self._mj_sa_min_consec = QtWidgets.QSpinBox()
        self._mj_sa_min_consec.setRange(1, 10)
        self._mj_sa_min_consec.setValue(3)
        sf2.addRow("Min consecutive:", self._mj_sa_min_consec)

        self._mj_sa_n_seg = QtWidgets.QSpinBox()
        self._mj_sa_n_seg.setRange(2, 10)
        self._mj_sa_n_seg.setValue(4)
        sf2.addRow("N segments:", self._mj_sa_n_seg)

        self._mj_sa_jump_pct = QtWidgets.QDoubleSpinBox()
        self._mj_sa_jump_pct.setRange(1.0, 50.0)
        self._mj_sa_jump_pct.setDecimals(1)
        self._mj_sa_jump_pct.setSingleStep(1.0)
        self._mj_sa_jump_pct.setValue(10.0)
        sf2.addRow("Jump threshold (%):", self._mj_sa_jump_pct)

        self._mj_sa_sec.add_layout(sf2)
        self._mj_sa_sec.set_expanded(False)
        self._mj_sa_sec.setVisible(False)  # hidden when reference mode selected
        layout.addWidget(self._mj_sa_sec)

        # ── Reference Status ──
        ref_sec = CollapsibleSection("Reference", initially_expanded=False)
        self._mj_ref_label = QtWidgets.QLabel("Reads from NF Eval dock")
        self._mj_ref_label.setWordWrap(True)
        ref_sec.add_widget(self._mj_ref_label)
        layout.addWidget(ref_sec)

        # ── Colors ──
        color_sec = CollapsibleSection("Colors", initially_expanded=False)
        color_form = QtWidgets.QFormLayout()

        self._mj_jump_color_btn = self._make_color_button(
            self._mj_colors["mode_jump"], "mode_jump"
        )
        color_form.addRow("Mode jump:", self._mj_jump_color_btn)

        self._mj_kiss_color_btn = self._make_color_button(
            self._mj_colors["mode_kissing"], "mode_kissing"
        )
        color_form.addRow("Mode kissing:", self._mj_kiss_color_btn)

        color_sec.add_layout(color_form)
        layout.addWidget(color_sec)

        # ── Offset Selection ──
        offset_sec = CollapsibleSection("Offset Selection", initially_expanded=True)
        self._mj_offset_layout = QtWidgets.QVBoxLayout()
        btn_row = QtWidgets.QHBoxLayout()
        sel_all = QtWidgets.QPushButton("Select All")
        sel_all.clicked.connect(lambda: self._set_all_checks(self._mj_offset_checks, True))
        sel_none = QtWidgets.QPushButton("Select None")
        sel_none.clicked.connect(lambda: self._set_all_checks(self._mj_offset_checks, False))
        btn_row.addWidget(sel_all)
        btn_row.addWidget(sel_none)
        self._mj_offset_layout.addLayout(btn_row)
        self._mj_offset_checks: List[QtWidgets.QCheckBox] = []
        offset_sec.add_layout(self._mj_offset_layout)
        layout.addWidget(offset_sec)

        # ── Run / Clear ──
        run_btn = QtWidgets.QPushButton("▶  Run Mode Jump Detection")
        run_btn.setStyleSheet(
            "font-weight: bold; padding: 10px; font-size: 13px;"
            "background-color: #7B1FA2; color: white; border-radius: 4px;"
        )
        run_btn.clicked.connect(self._mj_run)
        layout.addWidget(run_btn)

        clear_btn = QtWidgets.QPushButton("Clear Overlays")
        clear_btn.clicked.connect(self._mj_clear)
        layout.addWidget(clear_btn)

        self._mj_status = QtWidgets.QLabel("")
        self._mj_status.setWordWrap(True)
        layout.addWidget(self._mj_status)

        # ── Batch Results ──
        batch_sec = CollapsibleSection("Batch Results", initially_expanded=True)
        self._mj_batch_table = QtWidgets.QTableWidget()
        self._mj_batch_table.setColumnCount(5)
        self._mj_batch_table.setHorizontalHeaderLabels([
            "Offset", "Mode jump?", "# Flagged",
            "Longest run", "Mode kissing?",
        ])
        try:
            self._mj_batch_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Stretch
            )
        except AttributeError:
            self._mj_batch_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeMode.Stretch
            )
        self._mj_batch_table.setMaximumHeight(180)
        batch_sec.add_widget(self._mj_batch_table)
        layout.addWidget(batch_sec)

        # ── Per-offset point table ──
        points_sec = CollapsibleSection("Per-Offset Points", initially_expanded=False)

        inspect_form = QtWidgets.QFormLayout()
        self._mj_inspect_combo = QtWidgets.QComboBox()
        self._mj_inspect_combo.currentIndexChanged.connect(self._mj_on_inspect_changed)
        inspect_form.addRow("Offset:", self._mj_inspect_combo)
        points_sec.add_layout(inspect_form)

        self._mj_points_table = QtWidgets.QTableWidget()
        self._mj_points_table.setColumnCount(6)
        self._mj_points_table.setHorizontalHeaderLabels([
            "f (Hz)", "V (m/s)", "λ (m)", "V/V_ref", "Magnitude", "☑",
        ])
        try:
            self._mj_points_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Stretch
            )
        except AttributeError:
            self._mj_points_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeMode.Stretch
            )
        self._mj_points_table.setMinimumHeight(160)
        points_sec.add_widget(self._mj_points_table)

        # ── Delete / Cancel ──
        action_row = QtWidgets.QHBoxLayout()
        del_btn = QtWidgets.QPushButton("Delete")
        del_btn.setStyleSheet("font-weight: bold; color: #F44336;")
        del_btn.clicked.connect(self._mj_delete)
        action_row.addWidget(del_btn)
        cancel_btn = QtWidgets.QPushButton("Cancel / Clear")
        cancel_btn.clicked.connect(self._mj_clear)
        action_row.addWidget(cancel_btn)
        points_sec.add_layout(action_row)

        layout.addWidget(points_sec)

        # ── Export ──
        export_sec = CollapsibleSection("Export", initially_expanded=False)
        export_row = QtWidgets.QHBoxLayout()
        csv_btn = QtWidgets.QPushButton("Export CSV")
        csv_btn.clicked.connect(self._mj_export_csv)
        export_row.addWidget(csv_btn)
        npz_btn = QtWidgets.QPushButton("Export NPZ")
        npz_btn.clicked.connect(self._mj_export_npz)
        export_row.addWidget(npz_btn)
        export_sec.add_layout(export_row)
        layout.addWidget(export_sec)

        layout.addStretch()
        self._tabs.addTab(scroll, "Mode Jump")

    # ================================================================
    #  Shared helpers
    # ================================================================
    def _make_color_button(self, hex_color: str, key: str):
        btn = QtWidgets.QPushButton()
        btn.setFixedSize(28, 22)
        btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #888;")

        def _pick():
            chosen = QtWidgets.QColorDialog.getColor(
                QtGui.QColor(hex_color), self, f"Color for {key}"
            )
            if chosen.isValid():
                new_hex = chosen.name()
                btn.setStyleSheet(f"background-color: {new_hex}; border: 1px solid #888;")
                self._mj_colors[key] = new_hex
        btn.clicked.connect(_pick)
        return btn

    def _refresh_offset_checks(self, checks_list, layout):
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

    def _set_all_checks(self, checks_list, checked):
        for chk in checks_list:
            chk.setChecked(checked)

    def _get_selected_indices(self, checks_list):
        return [i for i, chk in enumerate(checks_list) if chk.isChecked()]

    def _get_offset_color(self, idx):
        """Get a color for the offset (match data line or palette)."""
        try:
            from matplotlib.colors import to_hex
            line = self.c.lines_freq[idx]
            return to_hex(line.get_color())
        except Exception:
            return _ROLLOFF_PALETTE[idx % len(_ROLLOFF_PALETTE)]

    # ================================================================
    #  Roll-off: event handlers
    # ================================================================
    def _ro_on_method_changed(self, idx):
        # vr_drop needs reference
        needs_ref = idx in (3, 4)
        self._ro_vr_thr.setEnabled(needs_ref)
        self._ro_min_consec.setEnabled(needs_ref or True)

    def _ro_run(self):
        self._ro_clear()
        selected = self._get_selected_indices(self._ro_offset_checks)
        if not selected:
            self._ro_status.setText("Select at least one offset.")
            return

        from dc_cut.core.processing.nearfield.onset import (
            detect_rolloff_running_max,
            detect_rolloff_derivative,
            detect_rolloff_curvature,
            detect_rolloff_vr_drop,
            detect_rolloff_multi_method,
        )

        method_idx = self._ro_method.currentIndex()
        method_map = {
            0: "running_max",
            1: "derivative",
            2: "curvature",
            3: "vr_drop",
            4: "multi",
        }
        method_key = method_map.get(method_idx, "running_max")

        has_ref = self.eval.has_reference
        f_ref = self.eval._reference_f if has_ref else None
        v_ref = self.eval._reference_v if has_ref else None

        if method_key in ("vr_drop", "multi") and not has_ref:
            if method_key == "vr_drop":
                self._ro_status.setText("vr_drop requires a reference. Build one in NF Eval first.")
                return

        kwargs = {
            "smoothing_window": self._ro_smooth.value(),
            "min_drop": self._ro_min_drop.value(),
        }
        if method_key in ("vr_drop", "multi"):
            kwargs["vr_threshold"] = self._ro_vr_thr.value()
            kwargs["min_consecutive"] = self._ro_min_consec.value()

        results = []
        for idx in selected:
            f = np.asarray(self.c.frequency_arrays[idx], float)
            v = np.asarray(self.c.velocity_arrays[idx], float)
            lbl = self.c.offset_labels[idx] if idx < len(self.c.offset_labels) else f"Offset {idx}"

            if method_key == "multi":
                res = detect_rolloff_multi_method(
                    f, v, f_ref=f_ref, v_ref=v_ref, **kwargs,
                )
                ro_f = res.get("consensus_rolloff_freq", np.nan)
                ro_lam = res.get("consensus_rolloff_wavelength", np.nan)
                ro_v = np.nan
                conf = res.get("consensus_confidence", 0.0)
                method_str = f"multi ({res.get('n_methods_detected', 0)} detected)"
            elif method_key == "running_max":
                res = detect_rolloff_running_max(
                    f, v,
                    smoothing_window=kwargs.get("smoothing_window", 5),
                    min_drop=kwargs.get("min_drop", 0.05),
                )
                ro_f = res["rolloff_freq"]
                ro_lam = res["rolloff_wavelength"]
                ro_v = res.get("details", {}).get("rolloff_velocity", np.nan)
                conf = res["confidence"]
                method_str = "running_max"
            elif method_key == "derivative":
                res = detect_rolloff_derivative(
                    f, v,
                    smoothing_window=kwargs.get("smoothing_window", 5),
                )
                ro_f = res["rolloff_freq"]
                ro_lam = res["rolloff_wavelength"]
                ro_v = np.nan
                conf = res["confidence"]
                method_str = "derivative"
            elif method_key == "curvature":
                res = detect_rolloff_curvature(
                    f, v,
                    smoothing_window=kwargs.get("smoothing_window", 5),
                )
                ro_f = res["rolloff_freq"]
                ro_lam = res["rolloff_wavelength"]
                ro_v = np.nan
                conf = res["confidence"]
                method_str = "curvature"
            elif method_key == "vr_drop":
                res = detect_rolloff_vr_drop(
                    f, v, f_ref, v_ref,
                    vr_threshold=kwargs.get("vr_threshold", 0.95),
                    min_consecutive=kwargs.get("min_consecutive", 2),
                )
                ro_f = res["rolloff_freq"]
                ro_lam = res["rolloff_wavelength"]
                ro_v = np.nan
                conf = res["confidence"]
                method_str = "vr_drop"
            else:
                continue

            results.append({
                "label": lbl,
                "offset_index": idx,
                "rolloff_freq": ro_f,
                "rolloff_wavelength": ro_lam,
                "rolloff_velocity": ro_v,
                "confidence": conf,
                "method": method_str,
                "full_result": res,
            })

            # Draw overlay
            if np.isfinite(ro_f):
                self._ro_draw_line(idx, ro_f, ro_lam)

        self._last_rolloff_results = results
        self._ro_populate_table(results)

        detected = sum(1 for r in results if np.isfinite(r["rolloff_freq"]))
        self._ro_status.setText(
            f"Evaluated {len(results)} offset(s). Roll-off detected in {detected}."
        )

    def _ro_draw_line(self, offset_idx, ro_f, ro_lam):
        """Draw vertical dashed rolloff lines on both axes."""
        c = self.c
        col = self._get_offset_color(offset_idx)
        try:
            lf = c.ax_freq.axvline(
                ro_f, color=col, ls='--', lw=1.5, alpha=0.7,
                label='_rolloff_overlay',
            )
            lw = c.ax_wave.axvline(
                ro_lam, color=col, ls='--', lw=1.5, alpha=0.7,
                label='_rolloff_overlay',
            )
            self._rolloff_overlays.append((lf, lw))
            c.fig.canvas.draw_idle()
        except Exception:
            pass

    def _ro_clear(self):
        for lf, lw in self._rolloff_overlays:
            try:
                lf.remove()
            except Exception:
                pass
            try:
                lw.remove()
            except Exception:
                pass
        self._rolloff_overlays.clear()
        try:
            self.c.fig.canvas.draw_idle()
        except Exception:
            pass

    def _ro_populate_table(self, results):
        self._ro_table.setRowCount(0)
        self._ro_table.setRowCount(len(results))
        for row, r in enumerate(results):
            vals = [
                r["label"],
                f"{r['rolloff_freq']:.2f}" if np.isfinite(r["rolloff_freq"]) else "—",
                f"{r['rolloff_wavelength']:.2f}" if np.isfinite(r["rolloff_wavelength"]) else "—",
                f"{r['rolloff_velocity']:.1f}" if np.isfinite(r.get("rolloff_velocity", np.nan)) else "—",
                f"{r['confidence']:.2f}",
                r["method"],
            ]
            for col, txt in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(txt)
                item.setFlags(item.flags() & ~_ItemIsEditable)
                if np.isfinite(r["rolloff_freq"]):
                    item.setForeground(QtGui.QColor(self._get_offset_color(r["offset_index"])))
                self._ro_table.setItem(row, col, item)

    # ── Roll-off export ──
    def _ro_export_csv(self):
        if not self._last_rolloff_results:
            self._ro_status.setText("Run analysis first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Roll-off CSV", "rolloff_analysis.csv",
            "CSV files (*.csv);;All (*)",
        )
        if not path:
            return
        try:
            import csv
            with open(path, 'w', newline='', encoding='utf-8') as fh:
                w = csv.writer(fh)
                w.writerow(["offset", "rolloff_freq_hz", "rolloff_wavelength_m",
                            "rolloff_velocity_ms", "confidence", "method"])
                for r in self._last_rolloff_results:
                    w.writerow([
                        r["label"], r["rolloff_freq"], r["rolloff_wavelength"],
                        r.get("rolloff_velocity", ""), r["confidence"], r["method"],
                    ])
            self._ro_status.setText(f"Exported to {path}")
        except Exception as exc:
            self._ro_status.setText(f"Export error: {exc}")

    def _ro_export_npz(self):
        if not self._last_rolloff_results:
            self._ro_status.setText("Run analysis first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Roll-off NPZ", "rolloff_analysis.npz",
            "NumPy files (*.npz);;All (*)",
        )
        if not path:
            return
        try:
            arrays = {}
            labels = []
            ro_f = []
            ro_lam = []
            confs = []
            for r in self._last_rolloff_results:
                labels.append(r["label"])
                ro_f.append(r["rolloff_freq"])
                ro_lam.append(r["rolloff_wavelength"])
                confs.append(r["confidence"])
            arrays["labels"] = np.array(labels, dtype=object)
            arrays["rolloff_freq"] = np.array(ro_f)
            arrays["rolloff_wavelength"] = np.array(ro_lam)
            arrays["confidence"] = np.array(confs)
            np.savez_compressed(path, **arrays)
            self._ro_status.setText(f"Exported to {path}")
        except Exception as exc:
            self._ro_status.setText(f"Export error: {exc}")

    # ================================================================
    #  Mode Jump: event handlers
    # ================================================================
    def _mj_on_mode_changed(self, idx):
        is_ref = (idx == 0)
        self._mj_ref_sec.setVisible(is_ref)
        self._mj_sa_sec.setVisible(not is_ref)
        if not is_ref:
            self._mj_sa_sec.set_expanded(True)

    def _mj_run(self):
        self._mj_clear()
        selected = self._get_selected_indices(self._mj_offset_checks)
        if not selected:
            self._mj_status.setText("Select at least one offset.")
            return

        is_ref_mode = (self._mj_mode.currentIndex() == 0)
        has_ref = self.eval.has_reference

        if is_ref_mode and not has_ref:
            self._mj_status.setText("Reference-based mode requires a reference. Build one in NF Eval first.")
            return

        from dc_cut.core.processing.nearfield.mode_detection import (
            detect_mode_jump,
            detect_mode_jump_standalone,
            detect_mode_kissing,
        )

        f_ref = self.eval._reference_f if has_ref else None
        v_ref = self.eval._reference_v if has_ref else None

        results = []
        for idx in selected:
            f = np.asarray(self.c.frequency_arrays[idx], float)
            v = np.asarray(self.c.velocity_arrays[idx], float)
            w = np.asarray(self.c.wavelength_arrays[idx], float)
            lbl = self.c.offset_labels[idx] if idx < len(self.c.offset_labels) else f"Offset {idx}"

            if is_ref_mode:
                res = detect_mode_jump(
                    f, v, f_ref, v_ref,
                    relative_jump=self._mj_rel_jump.value(),
                    min_consecutive=self._mj_min_consec_ref.value(),
                )
                # Also run standalone mode-kissing detector as bonus
                kiss_res = detect_mode_kissing(
                    f, v,
                    smoothing_window=self._mj_sa_smooth.value(),
                )
            else:
                res = detect_mode_jump_standalone(
                    f, v,
                    smoothing_window=self._mj_sa_smooth.value(),
                    jump_threshold_sigma=self._mj_sa_sigma.value(),
                    min_consecutive=self._mj_sa_min_consec.value(),
                    n_segments=self._mj_sa_n_seg.value(),
                    jump_threshold_pct=self._mj_sa_jump_pct.value(),
                )
                kiss_res = detect_mode_kissing(
                    f, v,
                    smoothing_window=self._mj_sa_smooth.value(),
                )

            entry = {
                "label": lbl,
                "offset_index": idx,
                "has_mode_jump": res["has_mode_jump"],
                "n_flagged": res["n_flagged"],
                "longest_run": res["longest_run"],
                "jump_mask": res["jump_mask"],
                "has_kissing": kiss_res.get("has_kissing", False),
                "kissing_frequencies": kiss_res.get("kissing_frequencies", np.array([])),
                "f": f, "v": v, "w": w,
            }

            # Store V/V_ref ratios and magnitudes if ref-based
            if is_ref_mode:
                sort_r = np.argsort(f_ref)
                v_interp = np.interp(f, f_ref[sort_r], v_ref[sort_r],
                                     left=np.nan, right=np.nan)
                valid = np.isfinite(v_interp) & (v_interp > 0)
                ratio = np.where(valid, v / v_interp, np.nan)
                magnitudes = np.where(
                    res["jump_mask"], ratio - 1.0, 0.0
                )
                entry["ratio"] = ratio
                entry["magnitudes"] = magnitudes
            else:
                entry["ratio"] = np.full(len(f), np.nan)
                entry["magnitudes"] = np.zeros(len(f))

            results.append(entry)

            # Draw overlays
            self._mj_draw_overlay(idx, f, v, w, res["jump_mask"],
                                  kiss_res.get("kissing_frequencies", np.array([])))

        self._last_mj_results = results
        self._mj_populate_batch(results)
        self._mj_populate_inspect(results)

        total_flagged = sum(r["n_flagged"] for r in results)
        jumps = sum(1 for r in results if r["has_mode_jump"])
        self._mj_status.setText(
            f"Evaluated {len(results)} offset(s). {jumps} with mode jumps, "
            f"{total_flagged} points flagged."
        )

    def _mj_draw_overlay(self, offset_idx, f, v, w, mask, kiss_freqs):
        c = self.c
        col_jump = self._mj_colors["mode_jump"]
        col_kiss = self._mj_colors["mode_kissing"]

        # Mode jump points
        for i in range(len(f)):
            if not mask[i]:
                continue
            key = (offset_idx, i)
            try:
                lf = c.ax_freq.plot(
                    [f[i]], [v[i]], 'o', linestyle='None',
                    mfc=col_jump, mec=col_jump, ms=5, alpha=0.7,
                    zorder=11, label='_mj_overlay',
                )[0]
                lw = c.ax_wave.plot(
                    [w[i]], [v[i]], 'o', linestyle='None',
                    mfc=col_jump, mec=col_jump, ms=5, alpha=0.7,
                    zorder=11, label='_mj_overlay',
                )[0]
                self._mj_overlays[key] = (lf, lw)
            except Exception:
                pass

        # Mode kissing points (diamond markers)
        if len(kiss_freqs) > 0:
            w_kiss = v[np.isin(f, kiss_freqs)] / np.maximum(
                f[np.isin(f, kiss_freqs)], 1e-12
            ) if len(kiss_freqs) > 0 else np.array([])
            for kf in kiss_freqs:
                try:
                    # Find closest point
                    ki = np.argmin(np.abs(f - kf))
                    key = ("kiss", offset_idx, ki)
                    lf = c.ax_freq.plot(
                        [f[ki]], [v[ki]], 'D', linestyle='None',
                        mfc='none', mec=col_kiss, mew=1.5, ms=7, alpha=0.8,
                        zorder=11, label='_kiss_overlay',
                    )[0]
                    lw = c.ax_wave.plot(
                        [w[ki]], [v[ki]], 'D', linestyle='None',
                        mfc='none', mec=col_kiss, mew=1.5, ms=7, alpha=0.8,
                        zorder=11, label='_kiss_overlay',
                    )[0]
                    self._mj_overlays[key] = (lf, lw)
                except Exception:
                    pass

        try:
            c.fig.canvas.draw_idle()
        except Exception:
            pass

    def _mj_clear(self):
        for key, (lf, lw) in list(self._mj_overlays.items()):
            try:
                lf.remove()
            except Exception:
                pass
            try:
                lw.remove()
            except Exception:
                pass
        self._mj_overlays.clear()
        try:
            self.c.fig.canvas.draw_idle()
        except Exception:
            pass

    def _mj_populate_batch(self, results):
        self._mj_batch_table.setRowCount(0)
        self._mj_batch_table.setRowCount(len(results))
        for row, r in enumerate(results):
            vals = [
                r["label"],
                "✓" if r["has_mode_jump"] else "✗",
                str(r["n_flagged"]),
                str(r["longest_run"]),
                "✓" if r["has_kissing"] else "✗",
            ]
            for col, txt in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(txt)
                item.setFlags(item.flags() & ~_ItemIsEditable)
                if r["has_mode_jump"]:
                    item.setForeground(QtGui.QColor(self._mj_colors["mode_jump"]))
                self._mj_batch_table.setItem(row, col, item)

    def _mj_populate_inspect(self, results):
        self._mj_inspect_combo.blockSignals(True)
        self._mj_inspect_combo.clear()
        for r in results:
            self._mj_inspect_combo.addItem(r["label"], r["offset_index"])
        self._mj_inspect_combo.blockSignals(False)
        if results:
            self._mj_inspect_combo.setCurrentIndex(0)
            self._mj_on_inspect_changed(0)

    def _mj_on_inspect_changed(self, idx):
        if idx < 0 or not self._last_mj_results:
            return
        if idx >= len(self._last_mj_results):
            return
        r = self._last_mj_results[idx]
        f, v, w = r["f"], r["v"], r["w"]
        mask = r["jump_mask"]
        ratio = r.get("ratio", np.full(len(f), np.nan))
        mags = r.get("magnitudes", np.zeros(len(f)))

        self._mj_points_table.blockSignals(True)
        self._mj_points_table.setRowCount(0)
        self._mj_points_table.setRowCount(len(f))

        for i in range(len(f)):
            vals = [
                f"{f[i]:.2f}",
                f"{v[i]:.1f}",
                f"{w[i]:.2f}",
                f"{ratio[i]:.3f}" if np.isfinite(ratio[i]) else "—",
                f"{mags[i]:.3f}" if mags[i] != 0 else "—",
            ]
            for col, txt in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(txt)
                item.setFlags(item.flags() & ~_ItemIsEditable)
                if mask[i]:
                    item.setForeground(QtGui.QColor(self._mj_colors["mode_jump"]))
                self._mj_points_table.setItem(i, col, item)

            flag_item = QtWidgets.QTableWidgetItem()
            flag_item.setFlags(
                flag_item.flags() | _ItemIsUserCheckable | _ItemIsEnabled
            )
            flag_item.setCheckState(_Checked if mask[i] else _Unchecked)
            self._mj_points_table.setItem(i, 5, flag_item)

        self._mj_points_table.blockSignals(False)

    def _mj_delete(self):
        """Delete checked points from the currently inspected offset."""
        idx = self._mj_inspect_combo.currentIndex()
        if idx < 0 or idx >= len(self._last_mj_results):
            return
        r = self._last_mj_results[idx]
        offset_idx = r["offset_index"]

        to_delete = []
        for row in range(self._mj_points_table.rowCount()):
            flag = self._mj_points_table.item(row, 5)
            if flag and flag.checkState() == _Checked:
                to_delete.append(row)

        if not to_delete:
            self._mj_status.setText("No points selected for deletion.")
            return

        try:
            self.eval.start_with(r["label"], self.eval.thr)
            self.eval.apply_deletions(to_delete)
            self._mj_clear()
            self._mj_points_table.setRowCount(0)
            self._mj_status.setText(f"Deleted {len(to_delete)} point(s) from {r['label']}.")
        except Exception as exc:
            self._mj_status.setText(f"Delete error: {exc}")

    # ── Mode Jump export ──
    def _mj_export_csv(self):
        if not self._last_mj_results:
            self._mj_status.setText("Run detection first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Mode Jump CSV", "mode_jump_results.csv",
            "CSV files (*.csv);;All (*)",
        )
        if not path:
            return
        try:
            import csv
            with open(path, 'w', newline='', encoding='utf-8') as fh:
                w = csv.writer(fh)
                w.writerow(["offset", "has_mode_jump", "n_flagged",
                            "longest_run", "has_kissing"])
                for r in self._last_mj_results:
                    w.writerow([
                        r["label"], r["has_mode_jump"], r["n_flagged"],
                        r["longest_run"], r["has_kissing"],
                    ])
            self._mj_status.setText(f"Exported to {path}")
        except Exception as exc:
            self._mj_status.setText(f"Export error: {exc}")

    def _mj_export_npz(self):
        if not self._last_mj_results:
            self._mj_status.setText("Run detection first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Mode Jump NPZ", "mode_jump_data.npz",
            "NumPy files (*.npz);;All (*)",
        )
        if not path:
            return
        try:
            arrays = {}
            for i, r in enumerate(self._last_mj_results):
                prefix = f"offset_{i}"
                arrays[f"{prefix}_label"] = np.array(r["label"])
                arrays[f"{prefix}_f"] = r["f"]
                arrays[f"{prefix}_v"] = r["v"]
                arrays[f"{prefix}_w"] = r["w"]
                arrays[f"{prefix}_mask"] = r["jump_mask"]
                arrays[f"{prefix}_ratio"] = r.get("ratio", np.array([]))
            arrays["n_offsets"] = np.array(len(self._last_mj_results))
            np.savez_compressed(path, **arrays)
            self._mj_status.setText(f"Exported to {path}")
        except Exception as exc:
            self._mj_status.setText(f"Export error: {exc}")

    # ================================================================
    #  showEvent – refresh offset lists and reference status
    # ================================================================
    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_offset_checks(self._ro_offset_checks, self._ro_offset_layout)
        self._refresh_offset_checks(self._mj_offset_checks, self._mj_offset_layout)

        # Sync reference status
        if self.eval.has_reference:
            src = self.eval._reference_source
            self._ro_ref_label.setText(f"Reference: {src}")
            self._mj_ref_label.setText(f"Reference: {src}")
        else:
            self._ro_ref_label.setText("No reference set (build one in NF Eval)")
            self._mj_ref_label.setText("No reference set (build one in NF Eval)")
