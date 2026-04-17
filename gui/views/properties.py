from __future__ import annotations

from typing import Optional
from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtGui     = qt_compat.QtGui
QtCore    = qt_compat.QtCore

from dc_cut.services.prefs import load_prefs, set_pref
from dc_cut.gui.widgets.collapsible_section import CollapsibleSection

# Qt5/Qt6 dock-widget feature compatibility
try:
    _DWMovable = QtWidgets.QDockWidget.DockWidgetMovable
    _DWFloatable = QtWidgets.QDockWidget.DockWidgetFloatable
except AttributeError:
    _DWMovable = QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
    _DWFloatable = QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable


class PropertiesDock(QtWidgets.QDockWidget):
    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Properties", parent)
        self.controller = controller
        self.setObjectName("PropertiesDock")
        self.setFeatures(_DWMovable | _DWFloatable)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        try:
            scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        except AttributeError:
            scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setSpacing(2)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── View Section (collapsible) ──
        view_sec = CollapsibleSection("View", initially_expanded=True)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["both", "freq_only", "wave_only"])
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("View mode:"))
        row.addWidget(self.mode_combo, stretch=1)
        view_sec.add_layout(row)
        layout.addWidget(view_sec)

        # ── Axes Section (collapsible) ──
        axes_sec = CollapsibleSection("Axes", initially_expanded=True)

        # Frequency X-axis
        freq_box = QtWidgets.QGroupBox("Frequency X-axis")
        fg = QtWidgets.QFormLayout(freq_box)
        self.freq_scale_combo = QtWidgets.QComboBox()
        self.freq_scale_combo.addItems(["Log", "Linear"])
        fg.addRow("Scale:", self.freq_scale_combo)
        self.freq_ticks_combo = QtWidgets.QComboBox()
        self.freq_ticks_combo.addItems(["decades", "one-two-five", "custom", "ruler"])
        fg.addRow("Tick style:", self.freq_ticks_combo)
        self.freq_custom_entry = QtWidgets.QLineEdit()
        self.freq_custom_entry.setPlaceholderText("e.g. 1,2,3,5,7,10,15,20")
        fg.addRow("Custom (Hz):", self.freq_custom_entry)
        axes_sec.add_widget(freq_box)

        # Phase Velocity Y-axis
        vel_box = QtWidgets.QGroupBox("Phase Velocity Y-axis")
        vg = QtWidgets.QFormLayout(vel_box)
        self.vel_scale_combo = QtWidgets.QComboBox()
        self.vel_scale_combo.addItems(["Linear", "Log"])
        vg.addRow("Scale:", self.vel_scale_combo)
        row_y = QtWidgets.QHBoxLayout()
        self.ymin_spin = QtWidgets.QDoubleSpinBox()
        self.ymin_spin.setRange(0.0, 1e6)
        self.ymin_spin.setDecimals(1)
        self.ymin_spin.setValue(0.0)
        self.ymax_spin = QtWidgets.QDoubleSpinBox()
        self.ymax_spin.setRange(10.0, 1e6)
        self.ymax_spin.setDecimals(1)
        self.ymax_spin.setValue(5000.0)
        row_y.addWidget(QtWidgets.QLabel("Min:"))
        row_y.addWidget(self.ymin_spin)
        row_y.addSpacing(6)
        row_y.addWidget(QtWidgets.QLabel("Max:"))
        row_y.addWidget(self.ymax_spin)
        vg.addRow("Clamp:", row_y)
        axes_sec.add_widget(vel_box)

        # Wavelength X-axis
        wave_box = QtWidgets.QGroupBox("Wavelength X-axis")
        wg = QtWidgets.QFormLayout(wave_box)
        self.wave_scale_combo = QtWidgets.QComboBox()
        self.wave_scale_combo.addItems(["Log", "Linear"])
        wg.addRow("Scale:", self.wave_scale_combo)
        axes_sec.add_widget(wave_box)

        layout.addWidget(axes_sec)

        # ── Overlays Section (collapsible) ──
        overlays_sec = CollapsibleSection("Overlays", initially_expanded=False)
        self.chk_grid = QtWidgets.QCheckBox("Show grid")
        overlays_sec.add_widget(self.chk_grid)
        self.chk_auto = QtWidgets.QCheckBox("Auto limits (padding)")
        overlays_sec.add_widget(self.chk_auto)
        layout.addWidget(overlays_sec)

        # Average checkboxes removed – now in Layers > Data tab
        # Hidden backward-compat stubs
        self.chk_avg_f = QtWidgets.QCheckBox()
        self.chk_avg_f.setVisible(False)
        self.chk_avg_w = QtWidgets.QCheckBox()
        self.chk_avg_w.setVisible(False)

        # K-limits checkbox removed – now in Layers > K-Limits tab
        # NACD spinner removed – now in λ Lines and NF Eval docks
        # Placeholder attribute for backward compat
        self.chk_k_guides = QtWidgets.QCheckBox()
        self.chk_k_guides.setVisible(False)
        self.nacd_spin = QtWidgets.QDoubleSpinBox()
        self.nacd_spin.setVisible(False)

        # ── Actions Section (collapsible) ──
        actions_sec = CollapsibleSection("Actions", initially_expanded=True)
        act_row = QtWidgets.QHBoxLayout()
        self.btn_apply_limits = QtWidgets.QPushButton("Apply limits")
        self.btn_reavg = QtWidgets.QPushButton("Recompute averages")
        act_row.addWidget(self.btn_apply_limits)
        act_row.addWidget(self.btn_reavg)
        actions_sec.add_layout(act_row)
        layout.addWidget(actions_sec)

        layout.addStretch(1)
        scroll.setWidget(w)
        self.setWidget(scroll)

        # ── Connections ──
        self.mode_combo.currentTextChanged.connect(self._on_mode)
        self.freq_scale_combo.currentTextChanged.connect(self._on_freq_scale)
        self.vel_scale_combo.currentTextChanged.connect(self._on_vel_scale)
        self.wave_scale_combo.currentTextChanged.connect(self._on_wave_scale)
        self.chk_auto.toggled.connect(self._on_auto)
        self.chk_avg_f.toggled.connect(self._on_avg_f)
        self.chk_avg_w.toggled.connect(self._on_avg_w)
        self.chk_grid.toggled.connect(self._on_grid)
        self.ymin_spin.valueChanged.connect(self._on_yclamp)
        self.ymax_spin.valueChanged.connect(self._on_yclamp)
        self.freq_ticks_combo.currentTextChanged.connect(self._on_freq_ticks)
        self.freq_custom_entry.editingFinished.connect(self._on_freq_custom)
        self.btn_apply_limits.clicked.connect(self._apply_limits)
        self.btn_reavg.clicked.connect(self._recompute_avg)

        self.sync_from_controller()
        try:
            P = load_prefs()
            if not hasattr(self.controller, 'nacd_thresh'):
                self.controller.nacd_thresh = float(P.get('nacd_thresh', 1.0))
            self.chk_grid.setChecked(bool(P.get('show_grid', True)))
            self.ymin_spin.setValue(float(getattr(self.controller, 'min_vel', 0.0)))
            self.ymax_spin.setValue(float(getattr(self.controller, 'max_vel', 5000.0)))
        except Exception:
            pass

    # ── Sync from controller ──

    def sync_from_controller(self) -> None:
        c = self.controller
        try:
            self.blockSignals(True)
            # Block individual widget signals to prevent cascading callbacks
            for widget in (self.mode_combo, self.freq_scale_combo, self.vel_scale_combo,
                           self.wave_scale_combo, self.chk_auto,
                           self.chk_avg_f, self.chk_avg_w,
                           self.freq_ticks_combo, self.chk_grid,
                           self.ymin_spin, self.ymax_spin):
                widget.blockSignals(True)

            idx = max(0, ["both", "freq_only", "wave_only"].index(getattr(c, 'view_mode', 'both')))
            self.mode_combo.setCurrentIndex(idx)
            self.chk_auto.setChecked(getattr(c, 'auto_limits', True))
            self.chk_avg_f.setChecked(getattr(c, 'show_average', True))
            self.chk_avg_w.setChecked(getattr(c, 'show_average_wave', True))

            # Axis scales
            freq_sc = getattr(c, 'freq_x_scale', 'log')
            self.freq_scale_combo.setCurrentIndex(0 if freq_sc == 'log' else 1)
            vel_sc = getattr(c, 'vel_y_scale', 'linear')
            self.vel_scale_combo.setCurrentIndex(0 if vel_sc == 'linear' else 1)
            wave_sc = getattr(c, 'wave_x_scale', 'log')
            self.wave_scale_combo.setCurrentIndex(0 if wave_sc == 'log' else 1)

            mode = getattr(c, 'freq_tick_style', 'decades')
            try:
                idx = ["decades", "one-two-five", "custom", "ruler"].index(mode)
            except ValueError:
                idx = 0
            self.freq_ticks_combo.setCurrentIndex(idx)
            cust = getattr(c, 'freq_custom_ticks', []) or []
            if cust:
                try:
                    self.freq_custom_entry.setText(
                        ",".join(str(int(x)) if float(x).is_integer() else str(float(x)) for x in cust)
                    )
                except Exception:
                    pass
        finally:
            for widget in (self.mode_combo, self.freq_scale_combo, self.vel_scale_combo,
                           self.wave_scale_combo, self.chk_auto,
                           self.chk_avg_f, self.chk_avg_w,
                           self.freq_ticks_combo, self.chk_grid,
                           self.ymin_spin, self.ymax_spin):
                widget.blockSignals(False)
            self.blockSignals(False)

    # ── Slot handlers ──

    def _on_mode(self, txt: str) -> None:
        self.controller._apply_view_mode(txt)

    def _on_freq_scale(self, txt: str) -> None:
        self.controller.freq_x_scale = 'log' if txt == 'Log' else 'linear'
        self.controller._apply_axis_scales()
        self.controller._apply_axis_limits()
        self.controller.fig.canvas.draw_idle()

    def _on_vel_scale(self, txt: str) -> None:
        self.controller.vel_y_scale = 'linear' if txt == 'Linear' else 'log'
        self.controller._apply_axis_scales()
        self.controller._apply_axis_limits()
        self.controller.fig.canvas.draw_idle()

    def _on_wave_scale(self, txt: str) -> None:
        self.controller.wave_x_scale = 'log' if txt == 'Log' else 'linear'
        self.controller._apply_axis_scales()
        self.controller._apply_axis_limits()
        self.controller.fig.canvas.draw_idle()

    def _on_auto(self, on: bool) -> None:
        self.controller.auto_limits = on
        self.controller._apply_axis_limits()
        self.controller.fig.canvas.draw_idle()

    def _on_avg_f(self, on: bool) -> None:
        self.controller.show_average = on
        self.controller._update_average_line()
        self.controller._update_legend()

    def _on_avg_w(self, on: bool) -> None:
        self.controller.show_average_wave = on
        self.controller._update_average_line()
        self.controller._update_legend()

    def _on_grid(self, on: bool) -> None:
        try:
            if on:
                self.controller.ax_freq.grid(True, which='both', alpha=0.25)
                self.controller.ax_wave.grid(True, which='both', alpha=0.25)
            else:
                self.controller.ax_freq.grid(False)
                self.controller.ax_wave.grid(False)
            self.controller.fig.canvas.draw_idle()
        except Exception:
            pass
        try:
            set_pref('show_grid', bool(on))
        except Exception:
            pass

    def _on_yclamp(self, *_):
        try:
            self.controller.min_vel = float(self.ymin_spin.value())
            self.controller.max_vel = float(self.ymax_spin.value())
            self.controller._apply_axis_limits()
            self.controller.fig.canvas.draw_idle()
        except Exception:
            pass

    def _on_freq_ticks(self, txt: str) -> None:
        self.controller.freq_tick_style = txt
        try:
            self.controller._apply_frequency_ticks()
            self.controller.fig.canvas.draw_idle()
        except Exception:
            pass
        try:
            set_pref('freq_tick_style', txt)
        except Exception:
            pass

    def _on_freq_custom(self) -> None:
        txt = (self.freq_custom_entry.text() or "").strip()
        if not txt:
            self.controller.freq_custom_ticks = []
        else:
            try:
                vals = []
                for tok in txt.replace(";", ",").split(','):
                    tok = tok.strip()
                    if not tok:
                        continue
                    vals.append(float(tok))
                vals = [v for v in vals if v > 0]
                self.controller.freq_custom_ticks = vals
            except Exception:
                return
        try:
            self.controller._apply_frequency_ticks()
            self.controller.fig.canvas.draw_idle()
        except Exception:
            pass
        try:
            set_pref('freq_custom_ticks', getattr(self.controller, 'freq_custom_ticks', []))
        except Exception:
            pass

    def _apply_limits(self) -> None:
        self.controller._apply_axis_limits()
        self.controller.fig.canvas.draw_idle()

    def _recompute_avg(self) -> None:
        self.controller._update_average_line()
        self.controller._update_legend()

    # Backward compatibility stubs
    def _rebuild_klimits_list(self) -> None:
        """No-op: K-limits are now in the Layers > K-Limits tab."""
        pass

    def _on_klimit_toggled(self, label: str, checked: bool) -> None:
        """No-op: K-limits are now in the Layers > K-Limits tab."""
        pass

    def _on_nacd(self, val: float) -> None:
        """No-op: NACD is now in the λ Lines and NF Eval docks."""
        pass

    def _on_k_guides(self, on: bool) -> None:
        """No-op: K-limit guides toggle is now in the K-Limits tab."""
        pass
