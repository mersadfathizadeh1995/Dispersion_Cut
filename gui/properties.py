from __future__ import annotations

from typing import Optional
from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtGui     = qt_compat.QtGui
QtCore    = qt_compat.QtCore

from dc_cut.services.prefs import load_prefs, set_pref


class PropertiesDock(QtWidgets.QDockWidget):
    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Properties", parent)
        self.controller = controller
        self.setObjectName("PropertiesDock")
        try:
            self.setFeatures(
                QtWidgets.QDockWidget.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFloatable
            )
        except AttributeError:
            feats = (
                QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            self.setFeatures(feats)

        w = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(w)
        self.mode_combo = QtWidgets.QComboBox(w); self.mode_combo.addItems(["both", "freq_only", "wave_only"]); form.addRow("View:", self.mode_combo)
        self.chk_auto = QtWidgets.QCheckBox("Auto limits (padding)", w); form.addRow(self.chk_auto)
        self.nacd_spin = QtWidgets.QDoubleSpinBox(w); self.nacd_spin.setDecimals(2); self.nacd_spin.setRange(0.10, 3.00); self.nacd_spin.setSingleStep(0.02); form.addRow("NACD ≤", self.nacd_spin)
        self.chk_avg_f = QtWidgets.QCheckBox("Average (Freq)", w); self.chk_avg_w = QtWidgets.QCheckBox("Average (Wave)", w); form.addRow(self.chk_avg_f); form.addRow(self.chk_avg_w)
        self.chk_k_guides = QtWidgets.QCheckBox("Show k-limit guides", w); form.addRow(self.chk_k_guides)
        self.chk_grid = QtWidgets.QCheckBox("Show grid", w); form.addRow(self.chk_grid)
        # Y clamps
        row_y = QtWidgets.QHBoxLayout();
        self.ymin_spin = QtWidgets.QDoubleSpinBox(w); self.ymin_spin.setRange(0.0, 1e6); self.ymin_spin.setDecimals(1); self.ymin_spin.setValue(0.0)
        self.ymax_spin = QtWidgets.QDoubleSpinBox(w); self.ymax_spin.setRange(10.0, 1e6); self.ymax_spin.setDecimals(1); self.ymax_spin.setValue(5000.0)
        row_y.addWidget(QtWidgets.QLabel("Ymin:")); row_y.addWidget(self.ymin_spin); row_y.addSpacing(6)
        row_y.addWidget(QtWidgets.QLabel("Ymax:")); row_y.addWidget(self.ymax_spin)
        form.addRow("Velocity clamp:", row_y)
        self.freq_ticks_combo = QtWidgets.QComboBox(w); self.freq_ticks_combo.addItems(["decades", "one-two-five", "custom", "ruler"]); form.addRow("Freq ticks:", self.freq_ticks_combo)
        self.freq_custom_entry = QtWidgets.QLineEdit(w); self.freq_custom_entry.setPlaceholderText("e.g. 1,2,3,5,7,10,15,20"); form.addRow("Custom (Hz):", self.freq_custom_entry)
        btns = QtWidgets.QHBoxLayout(); self.btn_apply_limits = QtWidgets.QPushButton("Apply limits", w); self.btn_reavg = QtWidgets.QPushButton("Recompute averages", w); btns.addWidget(self.btn_apply_limits); btns.addWidget(self.btn_reavg); form.addRow(btns)
        self.setWidget(w)

        self.mode_combo.currentTextChanged.connect(self._on_mode)
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

        try:
            self._sc_both = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+1"), self); self._sc_both.activated.connect(lambda: self.controller._apply_view_mode('both'))
            self._sc_freq = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+2"), self); self._sc_freq.activated.connect(lambda: self.controller._apply_view_mode('freq_only'))
            self._sc_wave = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+3"), self); self._sc_wave.activated.connect(lambda: self.controller._apply_view_mode('wave_only'))
        except Exception:
            pass

        self.sync_from_controller()
        # Load NACD from prefs if controller lacks it
        try:
            P = load_prefs();
            if not hasattr(self.controller, 'nacd_thresh'):
                self.controller.nacd_thresh = float(P.get('nacd_thresh', 1.0))
            self.nacd_spin.setValue(float(getattr(self.controller, 'nacd_thresh', 1.0)))
            self.chk_grid.setChecked(bool(P.get('show_grid', True)))
            self.ymin_spin.setValue(float(getattr(self.controller, 'min_vel', 0.0)))
            self.ymax_spin.setValue(float(getattr(self.controller, 'max_vel', 5000.0)))
        except Exception:
            pass

    def sync_from_controller(self) -> None:
        c = self.controller
        try:
            self.blockSignals(True)
            idx = max(0, ["both", "freq_only", "wave_only"].index(getattr(c, 'view_mode', 'both'))); self.mode_combo.setCurrentIndex(idx)
            self.chk_auto.setChecked(getattr(c, 'auto_limits', True))
            self.nacd_spin.setValue(float(getattr(c, 'nacd_thresh', 1.0)))
            self.chk_avg_f.setChecked(getattr(c, 'show_average', True))
            self.chk_avg_w.setChecked(getattr(c, 'show_average_wave', True))
            self.chk_k_guides.setChecked(bool(getattr(c, 'show_k_guides', False)))
            mode = getattr(c, 'freq_tick_style', 'decades')
            try: idx = ["decades","one-two-five","custom","ruler"].index(mode)
            except ValueError: idx = 0
            self.freq_ticks_combo.setCurrentIndex(idx)
            cust = getattr(c, 'freq_custom_ticks', []) or []
            if cust:
                try: self.freq_custom_entry.setText(",".join(str(int(x)) if float(x).is_integer() else str(float(x)) for x in cust))
                except Exception: pass
        finally:
            self.blockSignals(False)

    def _on_mode(self, txt: str) -> None:
        self.controller._apply_view_mode(txt)

    def _on_auto(self, on: bool) -> None:
        self.controller.auto_limits = on; self.controller._apply_axis_limits(); self.controller.fig.canvas.draw_idle()

    def _on_nacd(self, val: float) -> None:
        self.controller.nacd_thresh = float(val)
        try:
            set_pref('nacd_thresh', float(val))
        except Exception:
            pass

    def _on_avg_f(self, on: bool) -> None:
        self.controller.show_average = on; self.controller._update_average_line(); self.controller._update_legend()

    def _on_avg_w(self, on: bool) -> None:
        self.controller.show_average_wave = on; self.controller._update_average_line(); self.controller._update_legend()

    def _on_k_guides(self, on: bool) -> None:
        self.controller.show_k_guides = bool(on)
        try: self.controller._draw_k_guides()
        except Exception: pass
        try: set_pref('show_k_guides_default', bool(on))
        except Exception: pass

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
        try: set_pref('show_grid', bool(on))
        except Exception: pass

    def _on_yclamp(self, *_):
        try:
            self.controller.min_vel = float(self.ymin_spin.value())
            self.controller.max_vel = float(self.ymax_spin.value())
            self.controller._apply_axis_limits(); self.controller.fig.canvas.draw_idle()
        except Exception:
            pass

    def _on_freq_ticks(self, txt: str) -> None:
        self.controller.freq_tick_style = txt
        try: self.controller._apply_frequency_ticks(); self.controller.fig.canvas.draw_idle()
        except Exception: pass
        try: set_pref('freq_tick_style', txt)
        except Exception: pass

    def _on_freq_custom(self) -> None:
        txt = (self.freq_custom_entry.text() or "").strip()
        if not txt:
            self.controller.freq_custom_ticks = []
        else:
            try:
                vals = []
                for tok in txt.replace(";", ",").split(','):
                    tok = tok.strip()
                    if not tok: continue
                    vals.append(float(tok))
                vals = [v for v in vals if v > 0]
                self.controller.freq_custom_ticks = vals
            except Exception:
                return
        try: self.controller._apply_frequency_ticks(); self.controller.fig.canvas.draw_idle()
        except Exception: pass
        try: set_pref('freq_custom_ticks', getattr(self.controller, 'freq_custom_ticks', []))
        except Exception: pass

    def _apply_limits(self) -> None:
        self.controller._apply_axis_limits(); self.controller.fig.canvas.draw_idle()

    def _recompute_avg(self) -> None:
        self.controller._update_average_line(); self.controller._update_legend()


