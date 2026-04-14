from __future__ import annotations

from typing import Optional
from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtGui     = qt_compat.QtGui
QtCore    = qt_compat.QtCore

from dc_cut.services.prefs import load_prefs, set_pref

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
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── View Section ──
        view_group = QtWidgets.QGroupBox("View")
        vg_layout = QtWidgets.QFormLayout(view_group)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["both", "freq_only", "wave_only"])
        vg_layout.addRow("View mode:", self.mode_combo)
        layout.addWidget(view_group)

        # ── Axes Section ──
        axes_group = QtWidgets.QGroupBox("Axes")
        ag_layout = QtWidgets.QVBoxLayout(axes_group)

        # Frequency X-axis
        freq_group = QtWidgets.QGroupBox("Frequency X-axis")
        fg_layout = QtWidgets.QFormLayout(freq_group)
        self.freq_scale_combo = QtWidgets.QComboBox()
        self.freq_scale_combo.addItems(["Log", "Linear"])
        fg_layout.addRow("Scale:", self.freq_scale_combo)
        self.freq_ticks_combo = QtWidgets.QComboBox()
        self.freq_ticks_combo.addItems(["decades", "one-two-five", "custom", "ruler"])
        fg_layout.addRow("Tick style:", self.freq_ticks_combo)
        self.freq_custom_entry = QtWidgets.QLineEdit()
        self.freq_custom_entry.setPlaceholderText("e.g. 1,2,3,5,7,10,15,20")
        fg_layout.addRow("Custom (Hz):", self.freq_custom_entry)
        ag_layout.addWidget(freq_group)

        # Phase Velocity Y-axis
        vel_group = QtWidgets.QGroupBox("Phase Velocity Y-axis")
        velg_layout = QtWidgets.QFormLayout(vel_group)
        self.vel_scale_combo = QtWidgets.QComboBox()
        self.vel_scale_combo.addItems(["Linear", "Log"])
        velg_layout.addRow("Scale:", self.vel_scale_combo)
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
        velg_layout.addRow("Clamp:", row_y)
        ag_layout.addWidget(vel_group)

        # Wavelength X-axis
        wave_group = QtWidgets.QGroupBox("Wavelength X-axis")
        wg_layout = QtWidgets.QFormLayout(wave_group)
        self.wave_scale_combo = QtWidgets.QComboBox()
        self.wave_scale_combo.addItems(["Log", "Linear"])
        wg_layout.addRow("Scale:", self.wave_scale_combo)
        ag_layout.addWidget(wave_group)

        layout.addWidget(axes_group)

        # ── Overlays Section ──
        overlays_group = QtWidgets.QGroupBox("Overlays")
        og_layout = QtWidgets.QVBoxLayout(overlays_group)
        self.chk_grid = QtWidgets.QCheckBox("Show grid")
        og_layout.addWidget(self.chk_grid)
        self.chk_avg_f = QtWidgets.QCheckBox("Average (Freq)")
        og_layout.addWidget(self.chk_avg_f)
        self.chk_avg_w = QtWidgets.QCheckBox("Average (Wave)")
        og_layout.addWidget(self.chk_avg_w)
        self.chk_k_guides = QtWidgets.QCheckBox("Show k-limit guides")
        og_layout.addWidget(self.chk_k_guides)

        self.klimits_group = QtWidgets.QGroupBox("K-Limits")
        self.klimits_group.setCheckable(False)
        klimits_layout = QtWidgets.QVBoxLayout(self.klimits_group)
        klimits_layout.setContentsMargins(4, 4, 4, 4)
        klimits_layout.setSpacing(2)
        self.klimits_list = QtWidgets.QWidget()
        self.klimits_list_layout = QtWidgets.QVBoxLayout(self.klimits_list)
        self.klimits_list_layout.setContentsMargins(0, 0, 0, 0)
        self.klimits_list_layout.setSpacing(2)
        klimits_layout.addWidget(self.klimits_list)
        self.klimits_checkboxes = {}
        og_layout.addWidget(self.klimits_group)
        self.klimits_group.setVisible(False)

        self.chk_auto = QtWidgets.QCheckBox("Auto limits (padding)")
        og_layout.addWidget(self.chk_auto)
        layout.addWidget(overlays_group)

        # ── NACD Section ──
        nacd_group = QtWidgets.QGroupBox("NACD")
        ng_layout = QtWidgets.QFormLayout(nacd_group)
        self.nacd_spin = QtWidgets.QDoubleSpinBox()
        self.nacd_spin.setDecimals(2)
        self.nacd_spin.setRange(0.10, 3.00)
        self.nacd_spin.setSingleStep(0.02)
        ng_layout.addRow("NACD ≤", self.nacd_spin)
        layout.addWidget(nacd_group)

        # ── Actions Section ──
        actions_group = QtWidgets.QGroupBox("Actions")
        act_layout = QtWidgets.QHBoxLayout(actions_group)
        self.btn_apply_limits = QtWidgets.QPushButton("Apply limits")
        self.btn_reavg = QtWidgets.QPushButton("Recompute averages")
        act_layout.addWidget(self.btn_apply_limits)
        act_layout.addWidget(self.btn_reavg)
        layout.addWidget(actions_group)

        layout.addStretch(1)
        scroll.setWidget(w)
        self.setWidget(scroll)

        # ── Connections ──
        self.mode_combo.currentTextChanged.connect(self._on_mode)
        self.freq_scale_combo.currentTextChanged.connect(self._on_freq_scale)
        self.vel_scale_combo.currentTextChanged.connect(self._on_vel_scale)
        self.wave_scale_combo.currentTextChanged.connect(self._on_wave_scale)
        self.chk_auto.toggled.connect(self._on_auto)
        self.nacd_spin.valueChanged.connect(self._on_nacd)
        self.chk_avg_f.toggled.connect(self._on_avg_f)
        self.chk_avg_w.toggled.connect(self._on_avg_w)
        self.chk_k_guides.toggled.connect(self._on_k_guides)
        self.chk_grid.toggled.connect(self._on_grid)
        self.ymin_spin.valueChanged.connect(self._on_yclamp)
        self.ymax_spin.valueChanged.connect(self._on_yclamp)
        self.freq_ticks_combo.currentTextChanged.connect(self._on_freq_ticks)
        self.freq_custom_entry.editingFinished.connect(self._on_freq_custom)
        self.btn_apply_limits.clicked.connect(self._apply_limits)
        self.btn_reavg.clicked.connect(self._recompute_avg)

        self.sync_from_controller()
        self._rebuild_klimits_list()
        try:
            P = load_prefs()
            if not hasattr(self.controller, 'nacd_thresh'):
                self.controller.nacd_thresh = float(P.get('nacd_thresh', 1.0))
            self.nacd_spin.setValue(float(getattr(self.controller, 'nacd_thresh', 1.0)))
            self.chk_grid.setChecked(bool(P.get('show_grid', True)))
            self.ymin_spin.setValue(float(getattr(self.controller, 'min_vel', 0.0)))
            self.ymax_spin.setValue(float(getattr(self.controller, 'max_vel', 5000.0)))
        except Exception:
            pass

    # ── K-Limits list ──

    def _rebuild_klimits_list(self) -> None:
        for cb in list(self.klimits_checkboxes.values()):
            cb.setParent(None)
            cb.deleteLater()
        self.klimits_checkboxes.clear()

        multi_klimits = getattr(self.controller, '_multi_klimits', [])
        visibility = getattr(self.controller, '_klimits_visibility', {})

        if not multi_klimits or len(multi_klimits) <= 1:
            self.klimits_group.setVisible(False)
            return

        self.klimits_group.setVisible(True)

        for label, kmin, kmax in multi_klimits:
            cb = QtWidgets.QCheckBox(f"{label} ({kmin:.3f} - {kmax:.3f})")
            cb.setChecked(visibility.get(label, True))
            cb.toggled.connect(lambda checked, lbl=label: self._on_klimit_toggled(lbl, checked))
            self.klimits_list_layout.addWidget(cb)
            self.klimits_checkboxes[label] = cb

    def _on_klimit_toggled(self, label: str, checked: bool) -> None:
        if not hasattr(self.controller, '_klimits_visibility'):
            self.controller._klimits_visibility = {}
        self.controller._klimits_visibility[label] = checked
        try:
            self.controller._draw_k_guides()
            self.controller.fig.canvas.draw_idle()
        except Exception:
            pass

    # ── Sync from controller ──

    def sync_from_controller(self) -> None:
        c = self.controller
        try:
            self.blockSignals(True)
            # Block individual widget signals to prevent cascading callbacks
            for widget in (self.mode_combo, self.freq_scale_combo, self.vel_scale_combo,
                           self.wave_scale_combo, self.chk_auto, self.nacd_spin,
                           self.chk_avg_f, self.chk_avg_w, self.chk_k_guides,
                           self.freq_ticks_combo, self.chk_grid,
                           self.ymin_spin, self.ymax_spin):
                widget.blockSignals(True)

            idx = max(0, ["both", "freq_only", "wave_only"].index(getattr(c, 'view_mode', 'both')))
            self.mode_combo.setCurrentIndex(idx)
            self.chk_auto.setChecked(getattr(c, 'auto_limits', True))
            self.nacd_spin.setValue(float(getattr(c, 'nacd_thresh', 1.0)))
            self.chk_avg_f.setChecked(getattr(c, 'show_average', True))
            self.chk_avg_w.setChecked(getattr(c, 'show_average_wave', True))
            self.chk_k_guides.setChecked(bool(getattr(c, 'show_k_guides', False)))

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
                           self.wave_scale_combo, self.chk_auto, self.nacd_spin,
                           self.chk_avg_f, self.chk_avg_w, self.chk_k_guides,
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

    def _on_nacd(self, val: float) -> None:
        self.controller.nacd_thresh = float(val)
        try:
            set_pref('nacd_thresh', float(val))
        except Exception:
            pass

    def _on_avg_f(self, on: bool) -> None:
        self.controller.show_average = on
        self.controller._update_average_line()
        self.controller._update_legend()

    def _on_avg_w(self, on: bool) -> None:
        self.controller.show_average_wave = on
        self.controller._update_average_line()
        self.controller._update_legend()

    def _on_k_guides(self, on: bool) -> None:
        self.controller.show_k_guides = bool(on)
        try:
            self.controller._draw_k_guides()
        except Exception:
            pass
        try:
            set_pref('show_k_guides_default', bool(on))
        except Exception:
            pass

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
