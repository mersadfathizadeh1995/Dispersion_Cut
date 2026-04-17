"""Wavelength (lambda) reference lines dock.

Two sub-tabs:
  * Compute  – configure array geometry, source offsets, NACD threshold
               and compute lambda_max lines (auto from labels or manual entry).
  * Lines    – per-line visibility checkboxes, master toggle, label style
               controls (font size, bbox frame, opacity), and per-line color editing.
"""
from __future__ import annotations

from typing import Optional

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore

import numpy as np

from dc_cut.core.processing.wavelength_lines import (
    compute_wavelength_lines_batch,
    compute_lambda_max_manual,
    parse_source_offset_from_label,
)

# Qt5 / Qt6 enum compat
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
except AttributeError:
    _ItemIsUserCheckable = QtCore.Qt.ItemFlag.ItemIsUserCheckable


class WavelengthLinesDock(QtWidgets.QDockWidget):
    """Dock widget for computing and managing wavelength reference lines."""

    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("λ Lines", parent)
        self.setObjectName("WavelengthLinesDock")
        self.c = controller
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
        main_layout = QtWidgets.QVBoxLayout(host)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(2)

        self._tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(self._tabs)

        self._build_compute_tab()
        self._build_lines_tab()

    # ──────────────────────────────────────────────────────────────
    # Compute Tab
    # ──────────────────────────────────────────────────────────────
    def _build_compute_tab(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Array geometry ---
        geo_group = QtWidgets.QGroupBox("Array Geometry")
        geo_form = QtWidgets.QFormLayout(geo_group)

        self._n_receivers = QtWidgets.QSpinBox()
        self._n_receivers.setRange(2, 200)
        self._n_receivers.setValue(int(getattr(self.c, 'array_positions', np.arange(24)).size))
        geo_form.addRow("Number of receivers:", self._n_receivers)

        self._receiver_dx = QtWidgets.QDoubleSpinBox()
        self._receiver_dx.setRange(0.1, 100.0)
        self._receiver_dx.setDecimals(2)
        self._receiver_dx.setValue(float(getattr(self.c, 'receiver_dx', 2.0)))
        self._receiver_dx.setSuffix(" m")
        geo_form.addRow("Receiver spacing (dx):", self._receiver_dx)

        self._first_receiver = QtWidgets.QDoubleSpinBox()
        self._first_receiver.setRange(-1000.0, 1000.0)
        self._first_receiver.setDecimals(2)
        self._first_receiver.setValue(0.0)
        self._first_receiver.setSuffix(" m")
        geo_form.addRow("First receiver position:", self._first_receiver)

        layout.addWidget(geo_group)

        # --- NACD threshold ---
        nacd_group = QtWidgets.QGroupBox("NACD Criterion")
        nacd_form = QtWidgets.QFormLayout(nacd_group)

        self._nacd_threshold = QtWidgets.QDoubleSpinBox()
        self._nacd_threshold.setRange(0.1, 5.0)
        self._nacd_threshold.setDecimals(2)
        self._nacd_threshold.setSingleStep(0.1)
        self._nacd_threshold.setValue(float(getattr(self.c, 'nacd_thresh', 1.0)))
        nacd_form.addRow("NACD threshold:", self._nacd_threshold)

        layout.addWidget(nacd_group)

        # --- Source offsets (auto + manual) ---
        src_group = QtWidgets.QGroupBox("Source Offsets")
        src_layout = QtWidgets.QVBoxLayout(src_group)

        auto_btn = QtWidgets.QPushButton("Auto-detect from layer labels")
        auto_btn.setToolTip(
            "Parse source offset distances from label names\n"
            "(e.g. 'Rayleigh/fdbf_+66' → 66 m)"
        )
        auto_btn.clicked.connect(self._auto_detect_offsets)
        src_layout.addWidget(auto_btn)

        src_layout.addWidget(QtWidgets.QLabel("Source offsets (one per line, in meters):"))
        self._offsets_edit = QtWidgets.QPlainTextEdit()
        self._offsets_edit.setMaximumHeight(120)
        self._offsets_edit.setPlaceholderText("e.g.\n2\n5\n10\n20")
        src_layout.addWidget(self._offsets_edit)

        layout.addWidget(src_group)

        # --- Manual lambda entry ---
        manual_group = QtWidgets.QGroupBox("Manual λ Entry")
        manual_form = QtWidgets.QFormLayout(manual_group)
        manual_group.setCheckable(True)
        manual_group.setChecked(False)

        manual_form.addRow(QtWidgets.QLabel(
            "Enter λ values directly (overrides auto-computation):"
        ))
        self._manual_lambda_edit = QtWidgets.QPlainTextEdit()
        self._manual_lambda_edit.setMaximumHeight(80)
        self._manual_lambda_edit.setPlaceholderText("e.g.\n19\n51\n80")
        manual_form.addRow(self._manual_lambda_edit)
        self._manual_group = manual_group

        layout.addWidget(manual_group)

        # --- Compute button ---
        compute_btn = QtWidgets.QPushButton("Compute λ Lines")
        compute_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        compute_btn.clicked.connect(self._on_compute)
        layout.addWidget(compute_btn)

        self._compute_status = QtWidgets.QLabel("")
        layout.addWidget(self._compute_status)

        layout.addStretch()
        self._tabs.addTab(page, "Compute")

    # ──────────────────────────────────────────────────────────────
    # Lines Tab
    # ──────────────────────────────────────────────────────────────
    def _build_lines_tab(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)

        # All On / All Off buttons (matching Data tab pattern)
        btn_row_master = QtWidgets.QHBoxLayout()
        btn_all_on = QtWidgets.QPushButton("All On")
        btn_all_off = QtWidgets.QPushButton("All Off")
        btn_all_on.clicked.connect(self._show_all)
        btn_all_off.clicked.connect(self._hide_all)
        btn_row_master.addWidget(btn_all_on)
        btn_row_master.addWidget(btn_all_off)
        layout.addLayout(btn_row_master)

        # ── Label style group ──
        style_group = QtWidgets.QGroupBox("Label Style")
        sg_form = QtWidgets.QFormLayout(style_group)

        self._show_labels_chk = QtWidgets.QCheckBox("Show labels")
        self._show_labels_chk.setChecked(bool(getattr(self.c, '_wl_show_labels', True)))
        self._show_labels_chk.toggled.connect(self._on_show_labels)
        sg_form.addRow(self._show_labels_chk)

        self._label_pos_combo = QtWidgets.QComboBox()
        self._label_pos_combo.addItems(["upper", "lower", "auto"])
        cur_pos = getattr(self.c, '_wl_label_position', 'upper')
        idx = max(0, ["upper", "lower", "auto"].index(cur_pos) if cur_pos in ("upper", "lower", "auto") else 0)
        self._label_pos_combo.setCurrentIndex(idx)
        self._label_pos_combo.currentTextChanged.connect(self._on_label_position)
        sg_form.addRow("Position:", self._label_pos_combo)

        self._label_fontsize_spin = QtWidgets.QSpinBox()
        self._label_fontsize_spin.setRange(6, 24)
        self._label_fontsize_spin.setValue(int(getattr(self.c, '_wl_label_fontsize', 9)))
        self._label_fontsize_spin.valueChanged.connect(self._on_label_fontsize)
        sg_form.addRow("Font size:", self._label_fontsize_spin)

        self._label_frame_chk = QtWidgets.QCheckBox("Show frame")
        self._label_frame_chk.setChecked(bool(getattr(self.c, '_wl_label_bbox', True)))
        self._label_frame_chk.toggled.connect(self._on_label_frame)
        sg_form.addRow(self._label_frame_chk)

        self._label_opacity_spin = QtWidgets.QDoubleSpinBox()
        self._label_opacity_spin.setRange(0.0, 1.0)
        self._label_opacity_spin.setDecimals(2)
        self._label_opacity_spin.setSingleStep(0.05)
        self._label_opacity_spin.setValue(float(getattr(self.c, '_wl_label_bbox_alpha', 0.7)))
        self._label_opacity_spin.valueChanged.connect(self._on_label_opacity)
        sg_form.addRow("Frame opacity:", self._label_opacity_spin)

        layout.addWidget(style_group)

        # ── Lines list ──
        layout.addWidget(QtWidgets.QLabel("Computed lines (double-click to change color):"))

        self._lines_list = QtWidgets.QListWidget()
        try:
            self._lines_list.setSelectionMode(
                QtWidgets.QAbstractItemView.SingleSelection
            )
        except AttributeError:
            self._lines_list.setSelectionMode(
                QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
            )
        self._lines_list.itemChanged.connect(self._on_line_toggled)
        self._lines_list.itemDoubleClicked.connect(self._on_line_color_edit)
        layout.addWidget(self._lines_list, stretch=1)

        btn_row = QtWidgets.QHBoxLayout()
        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        self._tabs.addTab(page, "Lines")

        self._populate_lines_list()

    # ──────────────────────────────────────────────────────────────
    # Auto-detect
    # ──────────────────────────────────────────────────────────────
    def _auto_detect_offsets(self) -> None:
        n_data = min(
            len(self.c.velocity_arrays),
            len(self.c.frequency_arrays),
        )
        labels = self.c.offset_labels[:n_data]
        detected = []
        for lbl in labels:
            val = parse_source_offset_from_label(lbl)
            if val is not None:
                detected.append(val)

        if not detected:
            self._compute_status.setText("No offsets detected from labels.")
            return

        unique = sorted(set(detected))
        self._offsets_edit.setPlainText(
            "\n".join(f"{v:+g}" if v != 0 else "0" for v in unique)
        )
        self._compute_status.setText(f"Detected {len(unique)} unique offset(s).")

    # ──────────────────────────────────────────────────────────────
    # Compute
    # ──────────────────────────────────────────────────────────────
    def _on_compute(self) -> None:
        nacd = self._nacd_threshold.value()

        if self._manual_group.isChecked():
            self._compute_manual(nacd)
        else:
            self._compute_from_geometry(nacd)

        self._populate_lines_list()

        if self.c._wavelength_lines_data:
            self.c.show_wavelength_lines = True
            self._show_all()
        else:
            self._compute_status.setText("No lines computed.")

    def _compute_from_geometry(self, nacd: float) -> None:
        n_recv = self._n_receivers.value()
        dx = self._receiver_dx.value()
        first_pos = self._first_receiver.value()
        receiver_positions = np.arange(first_pos, first_pos + dx * n_recv, dx)

        text = self._offsets_edit.toPlainText().strip()
        if not text:
            self._compute_status.setText("Enter source offsets first.")
            return

        offsets = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                offsets.append(float(line))
            except ValueError:
                pass

        if not offsets:
            self._compute_status.setText("No valid offsets found.")
            return

        self.c.array_positions = receiver_positions
        fmin, fmax = self.c.ax_freq.get_xlim()

        results = compute_wavelength_lines_batch(
            offsets, receiver_positions, fmin, fmax,
            nacd_threshold=nacd,
        )

        self.c._wavelength_lines_data = results
        self.c._wl_visibility = {d['label']: True for d in results}

        self._compute_status.setText(
            f"Computed {len(results)} λ line(s)."
        )

        self._tabs.setCurrentIndex(1)
        self._redraw()

    def _compute_manual(self, nacd: float) -> None:
        text = self._manual_lambda_edit.toPlainText().strip()
        if not text:
            self._compute_status.setText("Enter λ values.")
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
            from dc_cut.core.processing.wavelength_lines import compute_wavelength_line
            f_curve, v_curve = compute_wavelength_line(lam, fmin, fmax)
            results.append({
                "source_offset": 0.0,
                "label": f"λ={lam:.0f} m",
                "x_bar": 0.0,
                "lambda_max": lam,
                "f_curve": f_curve,
                "v_curve": v_curve,
            })

        self.c._wavelength_lines_data = results
        self.c._wl_visibility = {d['label']: True for d in results}

        self._compute_status.setText(
            f"Created {len(results)} manual λ line(s)."
        )

        self._tabs.setCurrentIndex(1)
        self._redraw()

    # ──────────────────────────────────────────────────────────────
    # Lines list management
    # ──────────────────────────────────────────────────────────────
    # Default color palette (must match VisualizationHandler.WL_COLORS)
    # Default color palettes (must match VisualizationHandler)
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
        """Resolve default λ-line color, matching the data layer color.

        This mirrors VisualizationHandler._resolve_wl_default_color so the
        icon in the list matches the line drawn on the canvas.
        """
        from dc_cut.core.processing.wavelength_lines import parse_source_offset_from_label
        from matplotlib.colors import to_hex
        so = entry.get('source_offset')
        if so is not None:
            n_data = min(len(self.c.velocity_arrays), len(self.c.frequency_arrays))
            labels = self.c.offset_labels[:n_data]
            for i, lbl in enumerate(labels):
                parsed = parse_source_offset_from_label(lbl)
                if parsed is not None and abs(parsed - so) < 0.01:
                    # Read color directly from the data line artist
                    try:
                        if i < len(self.c.lines_wave):
                            return to_hex(self.c.lines_wave[i].get_color())
                    except Exception:
                        pass
                    return self._OFFSET_PALETTE[i % len(self._OFFSET_PALETTE)]
        return self._WL_PALETTE[line_idx % len(self._WL_PALETTE)]

    def _color_icon(self, hex_color: str) -> QtGui.QIcon:
        """Create a small square icon filled with the given color."""
        pix = QtGui.QPixmap(16, 16)
        pix.fill(QtGui.QColor(hex_color))
        return QtGui.QIcon(pix)

    def _populate_lines_list(self) -> None:
        self._lines_list.blockSignals(True)
        self._lines_list.clear()

        wl_data = getattr(self.c, '_wavelength_lines_data', [])
        visibility = getattr(self.c, '_wl_visibility', {})
        wl_colors = getattr(self.c, '_wl_colors', {})

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
            color = wl_colors.get(label, default_color)

            item = QtWidgets.QListWidgetItem(self._color_icon(color), text)
            item.setFlags(item.flags() | _ItemIsUserCheckable)
            checked = _Checked if visibility.get(label, True) else _Unchecked
            item.setCheckState(checked)
            item.setData(_UserRole, label)
            self._lines_list.addItem(item)

        self._lines_list.blockSignals(False)

    def _on_line_toggled(self, item) -> None:
        label = item.data(_UserRole)
        is_checked = item.checkState() == _Checked
        if not hasattr(self.c, '_wl_visibility'):
            self.c._wl_visibility = {}
        self.c._wl_visibility[label] = is_checked
        # Auto-enable master flag when any line is turned on
        if is_checked:
            self.c.show_wavelength_lines = True
        self._redraw()

    def _on_master_toggle(self, checked: bool) -> None:
        """Backward compat stub (master checkbox removed)."""
        self.c.show_wavelength_lines = checked
        self._redraw()

    def _show_all(self) -> None:
        """Show all λ lines (also enables master flag)."""
        self.c.show_wavelength_lines = True
        self._lines_list.blockSignals(True)
        for i in range(self._lines_list.count()):
            self._lines_list.item(i).setCheckState(_Checked)
        self._lines_list.blockSignals(False)
        # Set all visibility flags at once
        if not hasattr(self.c, '_wl_visibility'):
            self.c._wl_visibility = {}
        for entry in getattr(self.c, '_wavelength_lines_data', []):
            label = entry.get('label', '?')
            self.c._wl_visibility[label] = True
        self._redraw()

    def _hide_all(self) -> None:
        """Hide all λ lines (also disables master flag)."""
        self.c.show_wavelength_lines = False
        self._lines_list.blockSignals(True)
        for i in range(self._lines_list.count()):
            self._lines_list.item(i).setCheckState(_Unchecked)
        self._lines_list.blockSignals(False)
        if not hasattr(self.c, '_wl_visibility'):
            self.c._wl_visibility = {}
        for entry in getattr(self.c, '_wavelength_lines_data', []):
            label = entry.get('label', '?')
            self.c._wl_visibility[label] = False
        self._redraw()

    def _clear_all(self) -> None:
        self.c._wavelength_lines_data = []
        self.c._wl_visibility = {}
        self.c._wl_colors = {}
        self.c.show_wavelength_lines = False
        self._populate_lines_list()
        self._redraw()

    # ── Label style handlers ──

    def _on_show_labels(self, checked: bool) -> None:
        self.c._wl_show_labels = checked
        self._redraw()

    def _on_label_position(self, txt: str) -> None:
        self.c._wl_label_position = txt
        self._redraw()

    def _on_label_fontsize(self, val: int) -> None:
        self.c._wl_label_fontsize = val
        self._redraw()

    def _on_label_frame(self, checked: bool) -> None:
        self.c._wl_label_bbox = checked
        self._redraw()

    def _on_label_opacity(self, val: float) -> None:
        self.c._wl_label_bbox_alpha = val
        self._redraw()

    def _on_line_color_edit(self, item) -> None:
        """Open a color dialog when a line item is double-clicked."""
        label = item.data(_UserRole)
        if label is None:
            return

        wl_colors = getattr(self.c, '_wl_colors', {})
        idx = self._lines_list.row(item)
        default_color = self._WL_PALETTE[idx % len(self._WL_PALETTE)]
        current_hex = wl_colors.get(label, default_color)

        initial = QtGui.QColor(current_hex)
        chosen = QtWidgets.QColorDialog.getColor(initial, self, f"Color for {label}")
        if chosen.isValid():
            new_hex = chosen.name()
            if not hasattr(self.c, '_wl_colors'):
                self.c._wl_colors = {}
            self.c._wl_colors[label] = new_hex
            item.setIcon(self._color_icon(new_hex))
            self._redraw()

    # ──────────────────────────────────────────────────────────────
    # Redraw helper
    # ──────────────────────────────────────────────────────────────
    def _redraw(self) -> None:
        try:
            self.c._draw_wavelength_lines()
            self.c._update_legend()
            self.c.fig.canvas.draw_idle()
        except Exception:
            pass

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._populate_lines_list()
