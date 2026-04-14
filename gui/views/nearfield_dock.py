"""Unified Near-Field Analysis dock.

Four tabs:
  1. Setup      – array geometry, source offsets, NACD threshold
  2. Lambda Lines – compute & manage wavelength reference lines
  3. NF Evaluation – geometry-only (NACD) or reference-curve (V_R) mode
  4. Diagnostics  – embedded NACD-vs-V_R scatter plot
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.backends import qt_compat
from matplotlib.figure import Figure

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore

from dc_cut.core.processing.wavelength_lines import (
    compute_wavelength_lines_batch,
    compute_wavelength_line,
    parse_source_offset_from_label,
)

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


# ── severity colour map ────────────────────────────────────────────
_SEV_COLORS = {
    "clean": "#2196F3",       # blue
    "marginal": "#FF9800",    # orange
    "contaminated": "#F44336",  # red
    "unknown": "#9E9E9E",     # grey
}


class NearFieldAnalysisDock(QtWidgets.QDockWidget):
    """Unified dock combining lambda lines and NF evaluation."""

    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Near-Field Analysis", parent)
        self.setObjectName("NearFieldAnalysisDock")
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

        self._build_setup_tab()
        self._build_lambda_tab()
        self._build_nfeval_tab()
        self._build_diagnostics_tab()

    # ================================================================
    #  Tab 1: Setup
    # ================================================================
    def _build_setup_tab(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Array geometry ---
        geo = QtWidgets.QGroupBox("Array Geometry")
        gf = QtWidgets.QFormLayout(geo)

        self._n_receivers = QtWidgets.QSpinBox()
        self._n_receivers.setRange(2, 200)
        self._n_receivers.setValue(int(getattr(self.c, 'array_positions', np.arange(24)).size))
        gf.addRow("Number of receivers:", self._n_receivers)

        self._receiver_dx = QtWidgets.QDoubleSpinBox()
        self._receiver_dx.setRange(0.1, 100.0)
        self._receiver_dx.setDecimals(2)
        self._receiver_dx.setValue(float(getattr(self.c, 'receiver_dx', 2.0)))
        self._receiver_dx.setSuffix(" m")
        gf.addRow("Receiver spacing (dx):", self._receiver_dx)

        self._first_receiver = QtWidgets.QDoubleSpinBox()
        self._first_receiver.setRange(-1000.0, 1000.0)
        self._first_receiver.setDecimals(2)
        self._first_receiver.setValue(0.0)
        self._first_receiver.setSuffix(" m")
        gf.addRow("First receiver position:", self._first_receiver)

        layout.addWidget(geo)

        # --- Source offsets ---
        src = QtWidgets.QGroupBox("Source Offsets")
        sl = QtWidgets.QVBoxLayout(src)
        auto_btn = QtWidgets.QPushButton("Auto-detect from layer labels")
        auto_btn.setToolTip("Parse source offset distances from label names")
        auto_btn.clicked.connect(self._auto_detect_offsets)
        sl.addWidget(auto_btn)
        sl.addWidget(QtWidgets.QLabel("Source offsets (one per line, metres):"))
        self._offsets_edit = QtWidgets.QPlainTextEdit()
        self._offsets_edit.setMaximumHeight(120)
        self._offsets_edit.setPlaceholderText("e.g.\n2\n5\n10\n20")
        sl.addWidget(self._offsets_edit)
        layout.addWidget(src)

        # --- NACD threshold ---
        nacd_grp = QtWidgets.QGroupBox("NACD Criterion")
        nf = QtWidgets.QFormLayout(nacd_grp)
        self._nacd_threshold = QtWidgets.QDoubleSpinBox()
        self._nacd_threshold.setRange(0.1, 5.0)
        self._nacd_threshold.setDecimals(2)
        self._nacd_threshold.setSingleStep(0.1)
        self._nacd_threshold.setValue(float(getattr(self.c, 'nacd_thresh', 1.0)))
        nf.addRow("NACD threshold:", self._nacd_threshold)
        layout.addWidget(nacd_grp)

        self._setup_status = QtWidgets.QLabel("")
        layout.addWidget(self._setup_status)
        layout.addStretch()

        self._tabs.addTab(page, "Setup")

    # ================================================================
    #  Tab 2: Lambda Lines
    # ================================================================
    _WL_PALETTE = [
        '#e6194b', '#3cb44b', '#4363d8', '#f58231',
        '#911eb4', '#42d4f4', '#f032e6', '#bfef45',
        '#fabed4', '#469990',
    ]

    _OFFSET_PALETTE = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
    ]

    def _resolve_default_color(self, entry: dict, line_idx: int) -> str:
        """Resolve default lambda line colour, preferring offset-matched colour."""
        so = entry.get('source_offset')
        if so is not None:
            n = min(len(self.c.velocity_arrays), len(self.c.frequency_arrays))
            labels = self.c.offset_labels[:n]
            for i, lbl in enumerate(labels):
                parsed = parse_source_offset_from_label(lbl)
                if parsed is not None and abs(parsed - so) < 0.01:
                    return self._OFFSET_PALETTE[i % len(self._OFFSET_PALETTE)]
        return self._WL_PALETTE[line_idx % len(self._WL_PALETTE)]

    def _build_lambda_tab(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── Manual lambda entry ──
        manual_grp = QtWidgets.QGroupBox("Manual λ Entry")
        manual_grp.setCheckable(True)
        manual_grp.setChecked(False)
        mf = QtWidgets.QFormLayout(manual_grp)
        mf.addRow(QtWidgets.QLabel("Enter λ values directly (overrides auto):"))
        self._manual_lambda_edit = QtWidgets.QPlainTextEdit()
        self._manual_lambda_edit.setMaximumHeight(60)
        self._manual_lambda_edit.setPlaceholderText("e.g.\n19\n51\n80")
        mf.addRow(self._manual_lambda_edit)
        self._manual_group = manual_grp
        layout.addWidget(manual_grp)

        # ── Compute ──
        compute_btn = QtWidgets.QPushButton("Compute λ Lines")
        compute_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        compute_btn.clicked.connect(self._on_compute_lambda)
        layout.addWidget(compute_btn)

        self._lambda_status = QtWidgets.QLabel("")
        layout.addWidget(self._lambda_status)

        # ── Master toggle ──
        self._master_toggle = QtWidgets.QCheckBox("Show λ lines on canvas")
        self._master_toggle.setChecked(bool(getattr(self.c, 'show_wavelength_lines', False)))
        self._master_toggle.toggled.connect(self._on_master_toggle)
        layout.addWidget(self._master_toggle)

        # ── Label style group ──
        style_grp = QtWidgets.QGroupBox("Label Style")
        sf = QtWidgets.QFormLayout(style_grp)

        self._show_labels_chk = QtWidgets.QCheckBox("Show labels")
        self._show_labels_chk.setChecked(bool(getattr(self.c, '_wl_show_labels', True)))
        self._show_labels_chk.toggled.connect(self._on_show_labels)
        sf.addRow(self._show_labels_chk)

        self._label_pos_combo = QtWidgets.QComboBox()
        self._label_pos_combo.addItems(["upper", "lower", "auto"])
        cur_pos = getattr(self.c, '_wl_label_position', 'upper')
        idx = max(0, ["upper", "lower", "auto"].index(cur_pos) if cur_pos in ("upper", "lower", "auto") else 0)
        self._label_pos_combo.setCurrentIndex(idx)
        self._label_pos_combo.currentTextChanged.connect(self._on_label_position)
        sf.addRow("Position:", self._label_pos_combo)

        self._label_fontsize_spin = QtWidgets.QSpinBox()
        self._label_fontsize_spin.setRange(6, 24)
        self._label_fontsize_spin.setValue(int(getattr(self.c, '_wl_label_fontsize', 9)))
        self._label_fontsize_spin.valueChanged.connect(self._on_label_fontsize)
        sf.addRow("Font size:", self._label_fontsize_spin)

        self._label_frame_chk = QtWidgets.QCheckBox("Show frame")
        self._label_frame_chk.setChecked(bool(getattr(self.c, '_wl_label_bbox', True)))
        self._label_frame_chk.toggled.connect(self._on_label_frame)
        sf.addRow(self._label_frame_chk)

        self._label_opacity_spin = QtWidgets.QDoubleSpinBox()
        self._label_opacity_spin.setRange(0.0, 1.0)
        self._label_opacity_spin.setDecimals(2)
        self._label_opacity_spin.setSingleStep(0.05)
        self._label_opacity_spin.setValue(float(getattr(self.c, '_wl_label_bbox_alpha', 0.7)))
        self._label_opacity_spin.valueChanged.connect(self._on_label_opacity)
        sf.addRow("Frame opacity:", self._label_opacity_spin)

        layout.addWidget(style_grp)

        # ── Lines list ──
        layout.addWidget(QtWidgets.QLabel("Computed lines (double-click → colour):"))
        self._lines_list = QtWidgets.QListWidget()
        try:
            self._lines_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        except AttributeError:
            self._lines_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._lines_list.itemChanged.connect(self._on_line_toggled)
        self._lines_list.itemDoubleClicked.connect(self._on_line_color_edit)
        layout.addWidget(self._lines_list, stretch=1)

        btn_row = QtWidgets.QHBoxLayout()
        for txt, slot in [("Show All", self._show_all_lines), ("Hide All", self._hide_all_lines), ("Clear", self._clear_all_lines)]:
            b = QtWidgets.QPushButton(txt)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self._tabs.addTab(page, "λ Lines")
        self._populate_lines_list()

    # ================================================================
    #  Tab 3: NF Evaluation
    # ================================================================
    def _build_nfeval_tab(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── Mode selector ──
        mode_grp = QtWidgets.QGroupBox("Evaluation Mode")
        ml = QtWidgets.QVBoxLayout(mode_grp)
        self._mode_geom = QtWidgets.QRadioButton("Geometry Only (NACD)")
        self._mode_vr = QtWidgets.QRadioButton("Reference Curve (V_R)")
        self._mode_geom.setChecked(True)
        ml.addWidget(self._mode_geom)
        ml.addWidget(self._mode_vr)
        criteria_btn = QtWidgets.QPushButton("Criteria Settings…")
        criteria_btn.clicked.connect(self._on_open_criteria)
        ml.addWidget(criteria_btn)
        self._mode_vr.toggled.connect(self._on_mode_changed)
        layout.addWidget(mode_grp)

        # ── Reference curve options (only visible in V_R mode) ──
        self._ref_group = QtWidgets.QGroupBox("Reference Curve")
        rf = QtWidgets.QFormLayout(self._ref_group)
        self._ref_combo = QtWidgets.QComboBox()
        self._ref_combo.addItems([
            "Longest offset (largest x̄)",
            "Median across offsets (NF-aware)",
            "Specific offset…",
            "Load file…",
        ])
        self._ref_combo.currentIndexChanged.connect(self._on_ref_source_changed)
        rf.addRow("Source:", self._ref_combo)

        self._custom_offset_combo = QtWidgets.QComboBox()
        self._custom_offset_combo.setVisible(False)
        rf.addRow("Offset:", self._custom_offset_combo)

        self._ref_status = QtWidgets.QLabel("No reference set")
        rf.addRow(self._ref_status)

        ref_btn = QtWidgets.QPushButton("Build / Load Reference")
        ref_btn.clicked.connect(self._on_build_reference)
        rf.addRow(ref_btn)

        # ── Reference frequency band ──
        band_lbl = QtWidgets.QLabel("Restrict reference to frequency band:")
        rf.addRow(band_lbl)

        band_row = QtWidgets.QHBoxLayout()
        self._ref_fmin = QtWidgets.QDoubleSpinBox()
        self._ref_fmin.setRange(0.0, 9999.0)
        self._ref_fmin.setDecimals(1)
        self._ref_fmin.setValue(0.0)
        self._ref_fmin.setSuffix(" Hz")
        self._ref_fmin.setToolTip("Min frequency of reference band (0 = no lower limit)")
        self._ref_fmin.valueChanged.connect(self._on_ref_freq_band_changed)
        band_row.addWidget(QtWidgets.QLabel("Min:"))
        band_row.addWidget(self._ref_fmin)

        self._ref_fmax = QtWidgets.QDoubleSpinBox()
        self._ref_fmax.setRange(0.0, 9999.0)
        self._ref_fmax.setDecimals(1)
        self._ref_fmax.setValue(9999.0)
        self._ref_fmax.setSuffix(" Hz")
        self._ref_fmax.setToolTip("Max frequency of reference band (9999 = no upper limit)")
        self._ref_fmax.valueChanged.connect(self._on_ref_freq_band_changed)
        band_row.addWidget(QtWidgets.QLabel("Max:"))
        band_row.addWidget(self._ref_fmax)
        rf.addRow(band_row)

        self._ref_group.setVisible(False)
        layout.addWidget(self._ref_group)

        # ── Offset selector + action buttons ──
        form = QtWidgets.QFormLayout()
        self._eval_combo = QtWidgets.QComboBox()
        form.addRow("Offset:", self._eval_combo)
        layout.addLayout(form)

        btn_row = QtWidgets.QHBoxLayout()
        self._btn_start = QtWidgets.QPushButton("Start")
        self._btn_cancel = QtWidgets.QPushButton("Cancel")
        self._btn_apply = QtWidgets.QPushButton("Apply Deletions")
        for b in (self._btn_start, self._btn_cancel, self._btn_apply):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self._btn_start.clicked.connect(self._on_eval_start)
        self._btn_cancel.clicked.connect(self._on_eval_cancel)
        self._btn_apply.clicked.connect(self._on_eval_apply)

        # ── Deletion filter ──
        filt_row = QtWidgets.QHBoxLayout()
        filt_row.addWidget(QtWidgets.QLabel("Filter:"))
        self._del_filter = QtWidgets.QComboBox()
        self._del_filter.addItems([
            "All flagged",
            "Contaminated only",
            "Contaminated + Marginal",
            "Unknown only",
            "Custom NACD range…",
        ])
        self._del_filter.currentIndexChanged.connect(self._on_del_filter_changed)
        filt_row.addWidget(self._del_filter, stretch=1)

        self._nacd_range_min = QtWidgets.QDoubleSpinBox()
        self._nacd_range_min.setRange(0.0, 99.0)
        self._nacd_range_min.setDecimals(2)
        self._nacd_range_min.setValue(0.0)
        self._nacd_range_min.setPrefix("NACD ≥ ")
        self._nacd_range_min.setVisible(False)
        filt_row.addWidget(self._nacd_range_min)

        self._nacd_range_max = QtWidgets.QDoubleSpinBox()
        self._nacd_range_max.setRange(0.0, 99.0)
        self._nacd_range_max.setDecimals(2)
        self._nacd_range_max.setValue(1.0)
        self._nacd_range_max.setPrefix("NACD ≤ ")
        self._nacd_range_max.setVisible(False)
        filt_row.addWidget(self._nacd_range_max)

        layout.addLayout(filt_row)

        select_btn = QtWidgets.QPushButton("Select by Filter")
        select_btn.setToolTip("Auto-check rows matching the current filter")
        select_btn.clicked.connect(self._on_select_by_filter)
        layout.addWidget(select_btn)

        # ── Summary ──
        self._eval_summary = QtWidgets.QLabel("")
        layout.addWidget(self._eval_summary)

        # ── Points table ──
        self._points_table = QtWidgets.QTableWidget()
        self._points_table.setColumnCount(7)
        self._points_table.setHorizontalHeaderLabels(
            ["f (Hz)", "V (m/s)", "λ (m)", "NACD", "V_R", "Severity", "Flag"]
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
            self._points_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        except AttributeError:
            self._points_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._points_table.setMinimumHeight(160)
        self._points_table.itemChanged.connect(self._on_flag_toggled)
        layout.addWidget(self._points_table, stretch=1)

        # ── Per-offset summary table ──
        summary_grp = QtWidgets.QGroupBox("Per-Offset NF Summary")
        sg = QtWidgets.QVBoxLayout(summary_grp)
        self._summary_table = QtWidgets.QTableWidget()
        self._summary_table.setColumnCount(7)
        self._summary_table.setHorizontalHeaderLabels([
            "Offset", "x̄ (m)", "λ_max (m)", "Clean %", "Marginal %", "Contam. %", "Onset λ (m)",
        ])
        try:
            self._summary_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Stretch
            )
        except AttributeError:
            self._summary_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeMode.Stretch
            )
        self._summary_table.setMaximumHeight(160)
        sg.addWidget(self._summary_table)

        summary_btn = QtWidgets.QPushButton("Compute Full Report")
        summary_btn.clicked.connect(self._on_compute_full_report)
        sg.addWidget(summary_btn)
        layout.addWidget(summary_grp)

        self._tabs.addTab(page, "NF Eval")

    # ================================================================
    #  Tab 4: Diagnostics
    # ================================================================
    def _build_diagnostics_tab(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(QtWidgets.QLabel("NACD vs V_R scatter (requires reference curve)"))

        self._diag_fig = Figure(figsize=(4, 3), dpi=80)
        self._diag_ax = self._diag_fig.add_subplot(111)

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        self._diag_canvas = FigureCanvasQTAgg(self._diag_fig)
        layout.addWidget(self._diag_canvas, stretch=1)

        btn_row = QtWidgets.QHBoxLayout()
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_diagnostics)
        btn_row.addWidget(refresh_btn)

        export_btn = QtWidgets.QPushButton("Export Scatter")
        export_btn.clicked.connect(self._export_scatter)
        btn_row.addWidget(export_btn)

        open_win_btn = QtWidgets.QPushButton("Open in Window")
        open_win_btn.setToolTip("Open scatter plot in a larger standalone window with full settings")
        open_win_btn.clicked.connect(self._open_scatter_window)
        btn_row.addWidget(open_win_btn)

        layout.addLayout(btn_row)

        self._scatter_window = None
        self._tabs.addTab(page, "Diagnostics")

    # ================================================================
    #  Setup helpers
    # ================================================================
    def _auto_detect_offsets(self) -> None:
        n = min(len(self.c.velocity_arrays), len(self.c.frequency_arrays))
        labels = self.c.offset_labels[:n]
        detected = []
        for lbl in labels:
            val = parse_source_offset_from_label(lbl)
            if val is not None:
                detected.append(val)
        if not detected:
            self._setup_status.setText("No offsets detected from labels.")
            return
        unique = sorted(set(detected))
        self._offsets_edit.setPlainText(
            "\n".join(f"{v:+g}" if v != 0 else "0" for v in unique)
        )
        self._setup_status.setText(f"Detected {len(unique)} unique offset(s).")

    def _get_receiver_positions(self) -> np.ndarray:
        n = self._n_receivers.value()
        dx = self._receiver_dx.value()
        fp = self._first_receiver.value()
        return np.arange(fp, fp + dx * n, dx)

    def _get_source_offsets(self):
        text = self._offsets_edit.toPlainText().strip()
        if not text:
            return []
        offsets = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                offsets.append(float(line))
            except ValueError:
                pass
        return offsets

    # ================================================================
    #  Lambda Lines logic
    # ================================================================
    def _on_compute_lambda(self) -> None:
        nacd = self._nacd_threshold.value()
        if self._manual_group.isChecked():
            self._compute_manual(nacd)
        else:
            self._compute_from_geometry(nacd)
        self._populate_lines_list()
        if self.c._wavelength_lines_data:
            self._master_toggle.setChecked(True)
        else:
            self._lambda_status.setText("No lines computed.")

    def _compute_from_geometry(self, nacd: float) -> None:
        recv = self._get_receiver_positions()
        offsets = self._get_source_offsets()
        if not offsets:
            self._lambda_status.setText("Enter source offsets first (Setup tab).")
            return
        self.c.array_positions = recv
        fmin, fmax = self.c.ax_freq.get_xlim()
        results = compute_wavelength_lines_batch(offsets, recv, fmin, fmax, nacd_threshold=nacd)
        self.c._wavelength_lines_data = results
        self.c._wl_visibility = {d['label']: True for d in results}
        self._lambda_status.setText(f"Computed {len(results)} λ line(s).")
        self._redraw_wl()

    def _compute_manual(self, nacd: float) -> None:
        text = self._manual_lambda_edit.toPlainText().strip()
        if not text:
            self._lambda_status.setText("Enter λ values.")
            return
        fmin, fmax = self.c.ax_freq.get_xlim()
        results = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                lam = float(line)
            except ValueError:
                continue
            if lam <= 0:
                continue
            f_curve, v_curve = compute_wavelength_line(lam, fmin, fmax)
            results.append({
                "source_offset": 0.0, "label": f"λ={lam:.0f} m",
                "x_bar": 0.0, "lambda_max": lam,
                "f_curve": f_curve, "v_curve": v_curve,
            })
        self.c._wavelength_lines_data = results
        self.c._wl_visibility = {d['label']: True for d in results}
        self._lambda_status.setText(f"Created {len(results)} manual λ line(s).")
        self._redraw_wl()

    def _color_icon(self, hex_color: str) -> QtGui.QIcon:
        pix = QtGui.QPixmap(16, 16)
        pix.fill(QtGui.QColor(hex_color))
        return QtGui.QIcon(pix)

    def _populate_lines_list(self) -> None:
        self._lines_list.blockSignals(True)
        self._lines_list.clear()
        wl_data = getattr(self.c, '_wavelength_lines_data', [])
        vis = getattr(self.c, '_wl_visibility', {})
        colors = getattr(self.c, '_wl_colors', {})

        for i, entry in enumerate(wl_data):
            label = entry.get('label', '?')
            lam = entry.get('lambda_max', 0.0)
            x_bar = entry.get('x_bar', 0.0)
            text = f"λ = {lam:.1f} m"
            if x_bar > 0:
                text += f"  (x̄ = {x_bar:.1f} m, offset: {label})"
            else:
                text += f"  ({label})"
            default_color = self._resolve_default_color(entry, i)
            color = colors.get(label, default_color)
            item = QtWidgets.QListWidgetItem(self._color_icon(color), text)
            item.setFlags(item.flags() | _ItemIsUserCheckable)
            item.setCheckState(_Checked if vis.get(label, True) else _Unchecked)
            item.setData(_UserRole, label)
            self._lines_list.addItem(item)

        self._lines_list.blockSignals(False)

    def _on_line_toggled(self, item) -> None:
        label = item.data(_UserRole)
        self.c._wl_visibility[label] = item.checkState() == _Checked
        self._redraw_wl()

    def _on_master_toggle(self, checked: bool) -> None:
        self.c.show_wavelength_lines = checked
        self._redraw_wl()

    def _show_all_lines(self):
        for i in range(self._lines_list.count()):
            self._lines_list.item(i).setCheckState(_Checked)

    def _hide_all_lines(self):
        for i in range(self._lines_list.count()):
            self._lines_list.item(i).setCheckState(_Unchecked)

    def _clear_all_lines(self):
        self.c._wavelength_lines_data = []
        self.c._wl_visibility = {}
        self.c._wl_colors = {}
        self.c.show_wavelength_lines = False
        self._master_toggle.setChecked(False)
        self._populate_lines_list()
        self._redraw_wl()

    def _on_show_labels(self, checked):
        self.c._wl_show_labels = checked; self._redraw_wl()

    def _on_label_position(self, txt):
        self.c._wl_label_position = txt; self._redraw_wl()

    def _on_label_fontsize(self, val):
        self.c._wl_label_fontsize = val; self._redraw_wl()

    def _on_label_frame(self, checked):
        self.c._wl_label_bbox = checked; self._redraw_wl()

    def _on_label_opacity(self, val):
        self.c._wl_label_bbox_alpha = val; self._redraw_wl()

    def _on_line_color_edit(self, item) -> None:
        label = item.data(_UserRole)
        if label is None:
            return
        idx = self._lines_list.row(item)
        wl_data = getattr(self.c, '_wavelength_lines_data', [])
        entry = wl_data[idx] if idx < len(wl_data) else {}
        default = self._resolve_default_color(entry, idx)
        cur = getattr(self.c, '_wl_colors', {}).get(label, default)
        chosen = QtWidgets.QColorDialog.getColor(QtGui.QColor(cur), self, f"Colour for {label}")
        if chosen.isValid():
            self.c._wl_colors[label] = chosen.name()
            item.setIcon(self._color_icon(chosen.name()))
            self._redraw_wl()

    def _redraw_wl(self) -> None:
        try:
            self.c._draw_wavelength_lines()
            self.c._update_legend()
            self.c.fig.canvas.draw_idle()
        except Exception:
            pass

    # ================================================================
    #  NF Evaluation logic
    # ================================================================
    def _on_open_criteria(self) -> None:
        from dc_cut.gui.views.nf_criteria_dialog import NFCriteriaDialog
        try:
            _Accepted = QtWidgets.QDialog.Accepted
        except AttributeError:
            _Accepted = QtWidgets.QDialog.DialogCode.Accepted
        dlg = NFCriteriaDialog(
            self,
            clean_thr=self.eval._clean_threshold,
            marginal_thr=self.eval._marginal_threshold,
            unknown_action=self.eval._unknown_action,
            vr_onset=self.eval._vr_onset_threshold,
        )
        if dlg.exec() == _Accepted:
            vals = dlg.get_values()
            self.eval.set_severity_criteria(**vals)

    def _on_mode_changed(self, vr_checked: bool) -> None:
        self._ref_group.setVisible(vr_checked)

    def _on_ref_freq_band_changed(self, _=None) -> None:
        self.eval.set_reference_freq_range(
            self._ref_fmin.value(), self._ref_fmax.value(),
        )

    def _on_ref_source_changed(self, idx: int) -> None:
        is_custom = idx == 2
        self._custom_offset_combo.setVisible(is_custom)
        if is_custom:
            self._refresh_custom_offset_combo()

    def _refresh_custom_offset_combo(self) -> None:
        self._custom_offset_combo.blockSignals(True)
        self._custom_offset_combo.clear()
        n = min(len(self.c.velocity_arrays), len(self.c.frequency_arrays))
        labels = list(self.c.offset_labels[:n])
        self._custom_offset_combo.addItems(labels)
        self._custom_offset_combo.blockSignals(False)

    def _on_build_reference(self) -> None:
        idx = self._ref_combo.currentIndex()
        try:
            if idx == 0:
                self.eval.compute_reference_from_offsets("longest_offset")
            elif idx == 1:
                self.eval.compute_reference_from_offsets("median")
            elif idx == 2:
                custom_idx = self._custom_offset_combo.currentIndex()
                if custom_idx < 0:
                    self._ref_status.setText("Select an offset first.")
                    return
                self.eval.compute_reference_from_offsets(
                    "custom_offset", custom_index=custom_idx,
                )
            elif idx == 3:
                path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self, "Load Reference Curve", "",
                    "CSV files (*.csv);;NPZ files (*.npz);;All (*)",
                )
                if not path:
                    return
                self.eval.load_reference_file(path)
        except Exception as exc:
            self._ref_status.setText(f"Error: {exc}")
            return

        self.c._nf_reference_f = self.eval._reference_f
        self.c._nf_reference_v = self.eval._reference_v
        self.c._nf_reference_source = self.eval._reference_source
        self._ref_status.setText(f"Reference: {self.eval._reference_source}")

    def _refresh_eval_offsets(self) -> None:
        try:
            cur = self._eval_combo.currentText()
            self._eval_combo.blockSignals(True)
            self._eval_combo.clear()
            n = min(len(self.c.velocity_arrays), len(self.c.frequency_arrays))
            labels = list(self.c.offset_labels[:n])
            if len(labels) >= 2:
                labels = labels[:-2]
            self._eval_combo.addItems(labels)
            idx = self._eval_combo.findText(cur)
            if idx >= 0:
                self._eval_combo.setCurrentIndex(idx)
            self._eval_combo.blockSignals(False)
        except Exception:
            pass

    def _on_eval_start(self) -> None:
        self._refresh_eval_offsets()
        try:
            idx = int(self._eval_combo.currentIndex())
            label = self.c.offset_labels[idx]
        except Exception:
            label = self._eval_combo.currentText()

        thr = self._nacd_threshold.value()

        if self._mode_vr.isChecked() and self.eval.has_reference:
            pass  # reference already set
        elif self._mode_vr.isChecked() and not self.eval.has_reference:
            self._eval_summary.setText("Build a reference curve first.")
            return

        self.eval.start_with(label, thr)
        QtCore.QTimer.singleShot(0, self._populate_points_table)

    def _on_eval_cancel(self) -> None:
        self._clear_nf_overlays()
        try:
            self.eval.cancel()
        except Exception:
            pass
        self._points_table.setRowCount(0)
        self._eval_summary.setText("")

    def _on_eval_apply(self) -> None:
        data = self.eval.get_current_arrays()
        severity_arr = data[7] if data else None
        nacd_arr = data[4] if data else None
        filt = self._del_filter.currentIndex()

        indices = []
        for row in range(self._points_table.rowCount()):
            flag_item = self._points_table.item(row, 6)
            if not flag_item or flag_item.checkState() != _Checked:
                continue
            if filt == 0:
                indices.append(row)
            elif filt == 1:
                if severity_arr is not None and row < len(severity_arr):
                    if severity_arr[row] == "contaminated":
                        indices.append(row)
                else:
                    indices.append(row)
            elif filt == 2:
                if severity_arr is not None and row < len(severity_arr):
                    if severity_arr[row] in ("contaminated", "marginal"):
                        indices.append(row)
                else:
                    indices.append(row)
            elif filt == 3:
                if severity_arr is not None and row < len(severity_arr):
                    if severity_arr[row] == "unknown":
                        indices.append(row)
            elif filt == 4:
                if nacd_arr is not None and row < len(nacd_arr):
                    lo = self._nacd_range_min.value()
                    hi = self._nacd_range_max.value()
                    if lo <= nacd_arr[row] <= hi:
                        indices.append(row)
                else:
                    indices.append(row)

        self.eval.apply_deletions(indices)
        self._clear_nf_overlays()
        self._points_table.setRowCount(0)
        self._eval_summary.setText(f"Removed {len(indices)} point(s).")

    def _on_del_filter_changed(self, idx: int) -> None:
        custom = idx == 4
        self._nacd_range_min.setVisible(custom)
        self._nacd_range_max.setVisible(custom)

    def _on_select_by_filter(self) -> None:
        """Auto-check rows matching the current deletion filter."""
        data = self.eval.get_current_arrays()
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
                if severity is not None:
                    match = severity[row] in ("contaminated", "marginal")
                else:
                    match = bool(mask[row])
            elif filt == 3:
                if severity is not None:
                    match = severity[row] == "unknown"
                else:
                    match = False
            elif filt == 4:
                lo = self._nacd_range_min.value()
                hi = self._nacd_range_max.value()
                match = lo <= nacd[row] <= hi

            flag_item = self._points_table.item(row, 6)
            if flag_item:
                flag_item.setCheckState(_Checked if match else _Unchecked)
        self._points_table.blockSignals(False)
        self._on_flag_toggled(None)

    def _on_compute_full_report(self) -> None:
        """Compute NF report for all offsets and populate the summary table."""
        if not self.eval.has_reference:
            self._eval_summary.setText("Build a reference curve first (NF Eval → Reference Curve).")
            return
        try:
            report = self.eval.compute_full_report()
        except Exception as exc:
            self._eval_summary.setText(f"Report error: {exc}")
            return
        self._populate_summary_table(report)

    def _populate_summary_table(self, report: list) -> None:
        self._summary_table.setRowCount(0)
        if not report:
            return
        self._summary_table.setRowCount(len(report))
        for row, entry in enumerate(report):
            so = entry.get('source_offset', 0.0)
            label = f"{so:+g} m"
            if entry.get('is_reference'):
                label += "  ★REF"
            vals = [
                label,
                f"{entry.get('x_bar', 0):.1f}",
                f"{entry.get('lambda_max', 0):.1f}",
                f"{entry.get('clean_pct', 0):.0f}",
                f"{entry.get('marginal_pct', 0):.0f}",
                f"{entry.get('contaminated_pct', 0):.0f}",
                f"{entry.get('onset_wavelength', float('nan')):.1f}"
                if np.isfinite(entry.get('onset_wavelength', float('nan')))
                else "—",
            ]
            for col, txt in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(txt)
                try:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                except AttributeError:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if entry.get('contaminated_pct', 0) > 30:
                    item.setForeground(QtGui.QColor(_SEV_COLORS['contaminated']))
                elif entry.get('marginal_pct', 0) > 20:
                    item.setForeground(QtGui.QColor(_SEV_COLORS['marginal']))
                self._summary_table.setItem(row, col, item)

    def _populate_points_table(self) -> None:
        data = self.eval.get_current_arrays()
        self._points_table.blockSignals(True)
        self._points_table.setRowCount(0)
        if not data:
            self._points_table.blockSignals(False)
            return

        idx, f_arr, v_arr, w_arr, nacd, mask, vr, severity = data
        n = len(f_arr)
        self._points_table.setRowCount(n)

        n_flagged = 0
        for i in range(n):
            vals = [
                f"{f_arr[i]:.2f}",
                f"{v_arr[i]:.1f}",
                f"{w_arr[i]:.2f}",
                f"{nacd[i]:.3f}",
                f"{vr[i]:.3f}" if vr is not None and np.isfinite(vr[i]) else "—",
                severity[i] if severity is not None else ("NF" if mask[i] else "OK"),
            ]
            sev_key = severity[i] if severity is not None else ("contaminated" if mask[i] else "clean")
            row_color = QtGui.QColor(_SEV_COLORS.get(sev_key, "#9E9E9E"))

            for col, txt in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(txt)
                item.setForeground(row_color)
                try:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                except AttributeError:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                self._points_table.setItem(i, col, item)

            flag_item = QtWidgets.QTableWidgetItem()
            flag_item.setFlags(flag_item.flags() | _ItemIsUserCheckable | _ItemIsEnabled)
            is_flagged = bool(mask[i])
            if severity is not None and severity[i] in ("contaminated", "marginal"):
                is_flagged = True
            flag_item.setCheckState(_Checked if is_flagged else _Unchecked)
            self._points_table.setItem(i, 6, flag_item)
            if is_flagged:
                n_flagged += 1

        self._points_table.blockSignals(False)

        pct = 100 * n_flagged / n if n else 0
        self._eval_summary.setText(f"{n_flagged} of {n} points flagged ({pct:.0f}% contamination)")

        self._draw_nf_overlays(f_arr, v_arr, w_arr, nacd, mask, vr, severity)

    def _draw_nf_overlays(self, f_arr, v_arr, w_arr, nacd, mask, vr, severity):
        self._clear_nf_overlays()
        c = self.c
        for i in range(len(f_arr)):
            if severity is not None:
                color = _SEV_COLORS.get(severity[i], "#9E9E9E")
            else:
                color = "red" if mask[i] else "blue"
            lf = c.ax_freq.plot(
                [f_arr[i]], [v_arr[i]], 'o', linestyle='None',
                mfc='none', mec=color, mew=1.6, ms=6, zorder=10,
                label='_nf_overlay',
            )[0]
            lw = c.ax_wave.plot(
                [w_arr[i]], [v_arr[i]], 'o', linestyle='None',
                mfc='none', mec=color, mew=1.6, ms=6, zorder=10,
                label='_nf_overlay',
            )[0]
            c._nf_point_overlay[i] = (lf, lw)
        c.fig.canvas.draw_idle()

    def _on_flag_toggled(self, changed_item) -> None:
        """Redraw overlay colours when user toggles a Flag checkbox."""
        if changed_item is None:
            pass
        else:
            col = changed_item.column() if hasattr(changed_item, 'column') else -1
            if col != 6:
                return
        data = self.eval.get_current_arrays()
        if not data:
            return
        _, f_arr, v_arr, w_arr, nacd, mask, vr, severity = data
        self._clear_nf_overlays()
        c = self.c
        for i in range(self._points_table.rowCount()):
            if i >= len(f_arr):
                break
            flag_item = self._points_table.item(i, 6)
            is_checked = flag_item and flag_item.checkState() == _Checked
            if is_checked:
                color = "red"
            elif severity is not None:
                color = _SEV_COLORS.get(severity[i], "blue")
            else:
                color = "blue"
            lf = c.ax_freq.plot(
                [f_arr[i]], [v_arr[i]], 'o', linestyle='None',
                mfc='none', mec=color, mew=1.6, ms=6, zorder=10,
                label='_nf_overlay',
            )[0]
            lw = c.ax_wave.plot(
                [w_arr[i]], [v_arr[i]], 'o', linestyle='None',
                mfc='none', mec=color, mew=1.6, ms=6, zorder=10,
                label='_nf_overlay',
            )[0]
            c._nf_point_overlay[i] = (lf, lw)
        c.fig.canvas.draw_idle()

    def _clear_nf_overlays(self):
        try:
            for lf, lw in list(getattr(self.c, '_nf_point_overlay', {}).values()):
                try:
                    lf.remove(); lw.remove()
                except Exception:
                    pass
            self.c._nf_point_overlay = {}
            self.c.fig.canvas.draw_idle()
        except Exception:
            pass

    # ================================================================
    #  Diagnostics (NACD vs V_R scatter)
    # ================================================================
    def _refresh_diagnostics(self) -> None:
        ax = self._diag_ax
        ax.clear()

        if not self.eval.has_reference:
            ax.text(0.5, 0.5, "No reference curve set.\nBuild one in the NF Eval tab.",
                    ha='center', va='center', transform=ax.transAxes, fontsize=10)
            self._diag_canvas.draw_idle()
            return

        try:
            report = self.eval.compute_full_report()
        except Exception:
            report = None

        if report:
            from dc_cut.core.processing.nearfield import prepare_nacd_vr_scatter
            scatter = prepare_nacd_vr_scatter(report)
            nacd_all = scatter['nacd_all']
            vr_all = scatter['vr_all']
            oids = scatter['offset_ids']
            labels = scatter['labels']

            if len(nacd_all) == 0:
                ax.text(0.5, 0.5, "No non-reference data.", ha='center', va='center',
                        transform=ax.transAxes, fontsize=10)
            else:
                palette = self._OFFSET_PALETTE
                for gid in range(len(labels)):
                    sel = oids == gid
                    if not np.any(sel):
                        continue
                    c = palette[gid % len(palette)]
                    ax.scatter(nacd_all[sel], vr_all[sel], s=12, alpha=0.6,
                               label=labels[gid], color=c)
        else:
            all_data = self.eval.get_all_offsets_vr()
            if not all_data:
                ax.text(0.5, 0.5, "No data.", ha='center', va='center',
                        transform=ax.transAxes, fontsize=10)
                self._diag_canvas.draw_idle()
                return
            palette = self._OFFSET_PALETTE
            for i, (label, nacd, vr_arr) in enumerate(all_data):
                valid = np.isfinite(nacd) & np.isfinite(vr_arr) & (nacd > 0)
                if not np.any(valid):
                    continue
                c = palette[i % len(palette)]
                ax.scatter(nacd[valid], vr_arr[valid], s=12, alpha=0.6, label=label, color=c)

        ax.axhline(0.95, color='green', ls='--', lw=0.8, alpha=0.6)
        ax.axhline(0.85, color='orange', ls='--', lw=0.8, alpha=0.6)
        ax.axvline(1.0, color='grey', ls=':', lw=0.8, alpha=0.5)
        ax.axvline(1.5, color='grey', ls=':', lw=0.8, alpha=0.5)

        ax.fill_between([0, 10], 0.95, 1.10, alpha=0.05, color='green')
        ax.fill_between([0, 10], 0.85, 0.95, alpha=0.05, color='orange')
        ax.fill_between([0, 10], 0.0, 0.85, alpha=0.05, color='red')

        ax.set_xscale('log')
        ax.set_xlabel("NACD (x̄/λ)")
        ax.set_ylabel("V_R (V_meas / V_true)")
        ax.set_ylim(0.5, 1.15)
        ax.legend(fontsize=6, loc='lower right')
        ax.set_title("Near-Field Contamination Scatter", fontsize=9)
        self._diag_fig.tight_layout()
        self._diag_canvas.draw_idle()

    def _open_scatter_window(self) -> None:
        from dc_cut.gui.views.nf_scatter_window import ScatterWindow
        if self._scatter_window is None or not self._scatter_window.isVisible():
            self._scatter_window = ScatterWindow(self.eval, parent=self)
        else:
            self._scatter_window.refresh()
        self._scatter_window.show()
        self._scatter_window.raise_()

    def _export_scatter(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Scatter Plot", "nacd_vr_scatter.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)",
        )
        if path:
            self._diag_fig.savefig(path, dpi=200, bbox_inches='tight')

    # ================================================================
    #  showEvent – refresh on dock becoming visible
    # ================================================================
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._populate_lines_list()
        self._master_toggle.setChecked(bool(getattr(self.c, 'show_wavelength_lines', False)))
        self._refresh_eval_offsets()

        if self.eval.has_reference:
            self._ref_status.setText(f"Reference: {self.eval._reference_source}")
        elif self.c._nf_reference_f is not None:
            self.eval.set_reference_curve(
                self.c._nf_reference_f, self.c._nf_reference_v,
                self.c._nf_reference_source,
            )
            self._ref_status.setText(f"Reference: {self.c._nf_reference_source}")

        if self._ref_combo.currentIndex() == 2:
            self._refresh_custom_offset_combo()
