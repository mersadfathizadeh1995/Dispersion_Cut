from __future__ import annotations

from typing import Optional
from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore

from dc_cut.services.prefs import load_prefs, save_prefs
from dc_cut.services.theme import apply_theme, apply_matplotlib_theme


class PreferencesDialog(QtWidgets.QDialog):
    """Preferences dialog for DC Cut application settings."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(500, 400)

        # Load current preferences
        self.prefs = load_prefs()
        self.original_prefs = dict(self.prefs)  # Keep copy for cancel

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)

        # Tab widget for organized sections
        self.tabs = QtWidgets.QTabWidget(self)
        layout.addWidget(self.tabs)

        # Create tabs
        self._build_general_tab()
        self._build_appearance_tab()
        self._build_array_tab()
        self._build_performance_tab()
        self._build_advanced_tab()

        # Buttons
        button_box = QtWidgets.QDialogButtonBox(self)
        try:
            ok = QtWidgets.QDialogButtonBox.Ok
            cancel = QtWidgets.QDialogButtonBox.Cancel
            apply_btn = QtWidgets.QDialogButtonBox.Apply
        except AttributeError:
            ok = QtWidgets.QDialogButtonBox.StandardButton.Ok
            cancel = QtWidgets.QDialogButtonBox.StandardButton.Cancel
            apply_btn = QtWidgets.QDialogButtonBox.StandardButton.Apply

        button_box.setStandardButtons(ok | cancel | apply_btn)
        button_box.accepted.connect(self._on_ok)
        button_box.rejected.connect(self._on_cancel)

        # Get the Apply button and connect it
        try:
            apply_button = button_box.button(apply_btn)
            if apply_button:
                apply_button.clicked.connect(self._on_apply)
        except Exception:
            pass

        layout.addWidget(button_box)

    def _build_general_tab(self):
        """Build the General preferences tab."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        # Auto-save group
        auto_save_group = QtWidgets.QGroupBox("Auto-Save")
        auto_save_layout = QtWidgets.QVBoxLayout(auto_save_group)

        self.auto_save_check = QtWidgets.QCheckBox("Enable auto-save")
        self.auto_save_check.setChecked(self.prefs.get("auto_save_enabled", False))
        auto_save_layout.addWidget(self.auto_save_check)

        interval_layout = QtWidgets.QHBoxLayout()
        interval_layout.addWidget(QtWidgets.QLabel("Interval (minutes):"))
        self.auto_save_interval = QtWidgets.QSpinBox()
        self.auto_save_interval.setRange(1, 60)
        self.auto_save_interval.setValue(self.prefs.get("auto_save_interval_minutes", 10))
        interval_layout.addWidget(self.auto_save_interval)
        interval_layout.addStretch()
        auto_save_layout.addLayout(interval_layout)

        layout.addWidget(auto_save_group)

        # Grid settings
        grid_group = QtWidgets.QGroupBox("Display")
        grid_layout = QtWidgets.QVBoxLayout(grid_group)

        self.show_grid_check = QtWidgets.QCheckBox("Show grid by default")
        self.show_grid_check.setChecked(self.prefs.get("show_grid", True))
        grid_layout.addWidget(self.show_grid_check)

        self.show_k_guides_check = QtWidgets.QCheckBox("Show K-limit guides by default")
        self.show_k_guides_check.setChecked(self.prefs.get("show_k_guides_default", True))
        grid_layout.addWidget(self.show_k_guides_check)

        layout.addWidget(grid_group)

        layout.addStretch()
        self.tabs.addTab(tab, "General")

    def _build_appearance_tab(self):
        """Build the Appearance preferences tab."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        # Theme group
        theme_group = QtWidgets.QGroupBox("Theme")
        theme_layout = QtWidgets.QVBoxLayout(theme_group)

        theme_label = QtWidgets.QLabel("Choose a color theme:")
        theme_layout.addWidget(theme_label)

        self.theme_light = QtWidgets.QRadioButton("Light (Default)")
        self.theme_dark = QtWidgets.QRadioButton("Dark (Dim Dracula)")
        self.theme_dark_hc = QtWidgets.QRadioButton("Dark High Contrast (Better Visibility)")

        current_theme = self.prefs.get("theme", "light")
        if current_theme == "dark":
            self.theme_dark.setChecked(True)
        elif current_theme == "dark-high-contrast":
            self.theme_dark_hc.setChecked(True)
        else:
            self.theme_light.setChecked(True)

        theme_layout.addWidget(self.theme_light)
        theme_layout.addWidget(self.theme_dark)
        theme_layout.addWidget(self.theme_dark_hc)

        note_label = QtWidgets.QLabel("Note: Theme changes will be applied when you restart the application.")
        note_label.setWordWrap(True)
        try:
            note_label.setStyleSheet("color: gray; font-style: italic;")
        except Exception:
            pass
        theme_layout.addWidget(note_label)

        layout.addWidget(theme_group)
        layout.addStretch()
        self.tabs.addTab(tab, "Appearance")

    def _build_array_tab(self):
        """Build the Array Configuration tab."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        array_group = QtWidgets.QGroupBox("Array Defaults")
        array_layout = QtWidgets.QFormLayout(array_group)

        self.n_phones_spin = QtWidgets.QSpinBox()
        self.n_phones_spin.setRange(1, 1000)
        self.n_phones_spin.setValue(self.prefs.get("default_n_phones", 24))
        array_layout.addRow("Number of receivers:", self.n_phones_spin)

        self.receiver_dx_spin = QtWidgets.QDoubleSpinBox()
        self.receiver_dx_spin.setRange(0.1, 100.0)
        self.receiver_dx_spin.setDecimals(2)
        self.receiver_dx_spin.setSingleStep(0.5)
        self.receiver_dx_spin.setValue(self.prefs.get("default_receiver_dx", 2.0))
        array_layout.addRow("Receiver spacing (m):", self.receiver_dx_spin)

        layout.addWidget(array_group)

        # Near-field settings
        nf_group = QtWidgets.QGroupBox("Near-Field Analysis")
        nf_layout = QtWidgets.QFormLayout(nf_group)

        self.nacd_thresh_spin = QtWidgets.QDoubleSpinBox()
        self.nacd_thresh_spin.setRange(0.1, 10.0)
        self.nacd_thresh_spin.setDecimals(2)
        self.nacd_thresh_spin.setSingleStep(0.1)
        self.nacd_thresh_spin.setValue(self.prefs.get("nacd_thresh", 1.0))
        nf_layout.addRow("NACD threshold:", self.nacd_thresh_spin)

        layout.addWidget(nf_group)
        layout.addStretch()
        self.tabs.addTab(tab, "Array Config")

    def _build_performance_tab(self):
        """Build the Performance tab exposing every spectrum-rendering
        optimization as a user-toggleable pref. Fast defaults mirror the
        values in :mod:`dc_cut.services.prefs`; users can turn any of
        them off individually to restore the legacy behaviour.
        """
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        # ---- Spectrum rendering ------------------------------------
        render_group = QtWidgets.QGroupBox("Spectrum rendering")
        render_layout = QtWidgets.QFormLayout(render_group)

        self.perf_downsample_check = QtWidgets.QCheckBox(
            "Downsample large spectra before rendering"
        )
        self.perf_downsample_check.setChecked(
            bool(self.prefs.get("spectrum_perf_downsample", True))
        )
        render_layout.addRow(self.perf_downsample_check)

        self.perf_max_px_spin = QtWidgets.QSpinBox()
        self.perf_max_px_spin.setRange(64, 4096)
        self.perf_max_px_spin.setSingleStep(50)
        self.perf_max_px_spin.setValue(
            int(self.prefs.get("spectrum_perf_max_px", 400))
        )
        render_layout.addRow("Max pixels per axis:", self.perf_max_px_spin)

        self.perf_interp_combo = QtWidgets.QComboBox()
        for key, label in (
            ("auto", "Auto (nearest when input ≥ output)"),
            ("bilinear", "Bilinear (smooth)"),
            ("nearest", "Nearest (fastest)"),
        ):
            self.perf_interp_combo.addItem(label, userData=key)
        current = str(self.prefs.get("spectrum_perf_interpolation", "auto")).lower()
        idx = max(
            0,
            self.perf_interp_combo.findData(current)
            if hasattr(self.perf_interp_combo, "findData")
            else 0,
        )
        self.perf_interp_combo.setCurrentIndex(idx)
        render_layout.addRow("Interpolation mode:", self.perf_interp_combo)

        self.perf_rgba_check = QtWidgets.QCheckBox(
            "Cache colormapped RGBA image (skip per-draw normalize)"
        )
        self.perf_rgba_check.setChecked(
            bool(self.prefs.get("spectrum_perf_rgba_cache", True))
        )
        render_layout.addRow(self.perf_rgba_check)

        self.perf_raster_check = QtWidgets.QCheckBox(
            "Rasterize spectrum artist (faster composite)"
        )
        self.perf_raster_check.setChecked(
            bool(self.prefs.get("spectrum_perf_rasterized", True))
        )
        render_layout.addRow(self.perf_raster_check)

        self.perf_contour_levels_spin = QtWidgets.QSpinBox()
        self.perf_contour_levels_spin.setRange(3, 64)
        self.perf_contour_levels_spin.setValue(
            int(self.prefs.get("spectrum_perf_contour_levels", 12))
        )
        render_layout.addRow(
            "Contour levels (contourf mode):",
            self.perf_contour_levels_spin,
        )

        layout.addWidget(render_group)

        # ---- Interactive canvas ------------------------------------
        interactive_group = QtWidgets.QGroupBox("Interactive canvas")
        interactive_layout = QtWidgets.QFormLayout(interactive_group)

        self.perf_blit_check = QtWidgets.QCheckBox(
            "Use blitting for live previews (line / rect / add tools)"
        )
        self.perf_blit_check.setChecked(
            bool(self.prefs.get("spectrum_perf_use_blitting", True))
        )
        interactive_layout.addRow(self.perf_blit_check)

        self.perf_hide_gesture_check = QtWidgets.QCheckBox(
            "Hide spectrum during drag (fallback when blitting is off)"
        )
        self.perf_hide_gesture_check.setChecked(
            bool(self.prefs.get("spectrum_perf_hide_during_gesture", True))
        )
        interactive_layout.addRow(self.perf_hide_gesture_check)

        self.perf_throttle_spin = QtWidgets.QSpinBox()
        self.perf_throttle_spin.setRange(0, 200)
        self.perf_throttle_spin.setSuffix(" ms")
        self.perf_throttle_spin.setValue(
            int(self.prefs.get("spectrum_perf_draw_throttle_ms", 0))
        )
        interactive_layout.addRow(
            "Draw-idle throttle (0 = off):",
            self.perf_throttle_spin,
        )

        layout.addWidget(interactive_group)

        # ---- Advanced ----------------------------------------------
        advanced_group = QtWidgets.QGroupBox("Advanced")
        advanced_layout = QtWidgets.QVBoxLayout(advanced_group)
        self.perf_incremental_check = QtWidgets.QCheckBox(
            "Incremental update: reuse the spectrum artist on alpha / "
            "visibility toggles"
        )
        self.perf_incremental_check.setChecked(
            bool(self.prefs.get("spectrum_perf_incremental_update", True))
        )
        advanced_layout.addWidget(self.perf_incremental_check)
        layout.addWidget(advanced_group)

        note = QtWidgets.QLabel(
            "Every option defaults to the fast path. Turn any of them off "
            "individually to restore the legacy behaviour."
        )
        note.setWordWrap(True)
        try:
            note.setStyleSheet("color: gray; font-style: italic;")
        except Exception:
            pass
        layout.addWidget(note)

        layout.addStretch()
        self.tabs.addTab(tab, "Performance")

    def _build_advanced_tab(self):
        """Build the Advanced preferences tab."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        # Axis limits
        limits_group = QtWidgets.QGroupBox("Axis Limits (Percentiles)")
        limits_layout = QtWidgets.QFormLayout(limits_group)

        self.robust_lower_spin = QtWidgets.QDoubleSpinBox()
        self.robust_lower_spin.setRange(0.0, 50.0)
        self.robust_lower_spin.setDecimals(1)
        self.robust_lower_spin.setSingleStep(0.5)
        self.robust_lower_spin.setValue(self.prefs.get("robust_lower_pct", 0.5))
        limits_layout.addRow("Lower percentile:", self.robust_lower_spin)

        self.robust_upper_spin = QtWidgets.QDoubleSpinBox()
        self.robust_upper_spin.setRange(50.0, 100.0)
        self.robust_upper_spin.setDecimals(1)
        self.robust_upper_spin.setSingleStep(0.5)
        self.robust_upper_spin.setValue(self.prefs.get("robust_upper_pct", 99.5))
        limits_layout.addRow("Upper percentile:", self.robust_upper_spin)

        # Data-only autoscale policy -- keep k-guides / NF lines out of
        # matplotlib's autoscale so the passive-mode y axis is driven
        # purely by the visible dispersion data.
        self.axis_exclude_kguides_check = QtWidgets.QCheckBox(
            "Ignore k-limit curves when auto-scaling"
        )
        self.axis_exclude_kguides_check.setChecked(
            bool(self.prefs.get("axis_exclude_kguides", True))
        )
        limits_layout.addRow(self.axis_exclude_kguides_check)

        self.axis_exclude_nf_check = QtWidgets.QCheckBox(
            "Ignore NACD / near-field guide lines when auto-scaling"
        )
        self.axis_exclude_nf_check.setChecked(
            bool(self.prefs.get("axis_exclude_nf_lines", True))
        )
        limits_layout.addRow(self.axis_exclude_nf_check)

        self.axis_pad_frac_spin = QtWidgets.QDoubleSpinBox()
        self.axis_pad_frac_spin.setRange(0.0, 1.0)
        self.axis_pad_frac_spin.setDecimals(2)
        self.axis_pad_frac_spin.setSingleStep(0.01)
        self.axis_pad_frac_spin.setValue(
            float(self.prefs.get("axis_pad_frac", 0.08))
        )
        limits_layout.addRow("Padding fraction:", self.axis_pad_frac_spin)

        self.axis_v_clamp_spin = QtWidgets.QDoubleSpinBox()
        self.axis_v_clamp_spin.setRange(0.0, 100.0)
        self.axis_v_clamp_spin.setDecimals(2)
        self.axis_v_clamp_spin.setSingleStep(0.25)
        self.axis_v_clamp_spin.setValue(
            float(self.prefs.get("axis_v_outlier_clamp_mult", 2.5))
        )
        self.axis_v_clamp_spin.setToolTip(
            "Clamp the top of the velocity axis to "
            "(multiplier \u00D7 99.5-percentile of V). 0 disables."
        )
        limits_layout.addRow(
            "V outlier clamp (\u00D7 p99.5, 0 = off):",
            self.axis_v_clamp_spin,
        )

        layout.addWidget(limits_group)

        # Frequency tick style
        tick_group = QtWidgets.QGroupBox("Frequency Ticks")
        tick_layout = QtWidgets.QVBoxLayout(tick_group)

        self.tick_decades = QtWidgets.QRadioButton("Decades (1, 10, 100, ...)")
        self.tick_custom = QtWidgets.QRadioButton("Custom list")

        tick_style = self.prefs.get("freq_tick_style", "decades")
        if tick_style == "decades":
            self.tick_decades.setChecked(True)
        else:
            self.tick_custom.setChecked(True)

        tick_layout.addWidget(self.tick_decades)
        tick_layout.addWidget(self.tick_custom)

        layout.addWidget(tick_group)
        layout.addStretch()
        self.tabs.addTab(tab, "Advanced")

    def _gather_preferences(self) -> dict:
        """Gather all preference values from UI widgets.

        Starts from a copy of the currently loaded prefs so keys that
        do not have a UI representation in this dialog (spectrum
        display prefs, migration flags, colormap, alpha, …) are
        preserved on save. The gathered UI values are then overlaid on
        top. Prior to this fix the method returned a fresh dict, which
        silently wiped every key not explicitly listed here.
        """
        prefs = dict(self.prefs)

        # General
        prefs["auto_save_enabled"] = self.auto_save_check.isChecked()
        prefs["auto_save_interval_minutes"] = self.auto_save_interval.value()
        prefs["show_grid"] = self.show_grid_check.isChecked()
        prefs["show_k_guides_default"] = self.show_k_guides_check.isChecked()

        # Appearance
        if self.theme_dark.isChecked():
            prefs["theme"] = "dark"
        elif self.theme_dark_hc.isChecked():
            prefs["theme"] = "dark-high-contrast"
        else:
            prefs["theme"] = "light"

        # Array
        prefs["default_n_phones"] = self.n_phones_spin.value()
        prefs["default_receiver_dx"] = self.receiver_dx_spin.value()
        prefs["nacd_thresh"] = self.nacd_thresh_spin.value()

        # Advanced
        prefs["robust_lower_pct"] = self.robust_lower_spin.value()
        prefs["robust_upper_pct"] = self.robust_upper_spin.value()
        prefs["axis_exclude_kguides"] = (
            self.axis_exclude_kguides_check.isChecked()
        )
        prefs["axis_exclude_nf_lines"] = (
            self.axis_exclude_nf_check.isChecked()
        )
        prefs["axis_pad_frac"] = float(self.axis_pad_frac_spin.value())
        prefs["axis_v_outlier_clamp_mult"] = float(
            self.axis_v_clamp_spin.value()
        )
        prefs["freq_tick_style"] = "decades" if self.tick_decades.isChecked() else "custom"

        # Performance
        prefs["spectrum_perf_downsample"] = self.perf_downsample_check.isChecked()
        prefs["spectrum_perf_max_px"] = int(self.perf_max_px_spin.value())
        prefs["spectrum_perf_rgba_cache"] = self.perf_rgba_check.isChecked()
        prefs["spectrum_perf_rasterized"] = self.perf_raster_check.isChecked()
        prefs["spectrum_perf_contour_levels"] = int(
            self.perf_contour_levels_spin.value()
        )
        prefs["spectrum_perf_use_blitting"] = self.perf_blit_check.isChecked()
        prefs["spectrum_perf_hide_during_gesture"] = (
            self.perf_hide_gesture_check.isChecked()
        )
        prefs["spectrum_perf_draw_throttle_ms"] = int(self.perf_throttle_spin.value())
        prefs["spectrum_perf_incremental_update"] = (
            self.perf_incremental_check.isChecked()
        )
        interp_data = None
        try:
            interp_data = self.perf_interp_combo.currentData()
        except Exception:
            interp_data = None
        if interp_data:
            prefs["spectrum_perf_interpolation"] = str(interp_data)
        else:
            # Fallback: preserve existing pref if combo data is unavailable.
            prefs["spectrum_perf_interpolation"] = str(
                self.prefs.get("spectrum_perf_interpolation", "auto")
            )

        # freq_custom_ticks preserved implicitly by dict(self.prefs) above,
        # but keep the explicit fallback as a belt-and-braces guard.
        prefs.setdefault("freq_custom_ticks", self.prefs.get("freq_custom_ticks", []))

        return prefs

    def _apply_live_perf_changes(self, new_prefs: dict) -> None:
        """Push performance-relevant prefs to the live controller/blit
        manager so the user doesn't need to restart the app after
        toggling a perf option. Safe no-op when no controller is
        reachable.
        """
        parent = self.parent()
        controller = getattr(parent, "_controller", None) or getattr(
            parent, "controller", None
        )
        if controller is None and hasattr(parent, "get_controller"):
            try:
                controller = parent.get_controller()
            except Exception:
                controller = None
        if controller is None:
            return

        # Blit manager state.
        bm = getattr(controller, "blit_manager", None)
        if bm is not None:
            try:
                bm.set_enabled(bool(new_prefs.get("spectrum_perf_use_blitting", True)))
            except Exception:
                pass
            try:
                bm.set_throttle_ms(int(new_prefs.get("spectrum_perf_draw_throttle_ms", 0)))
            except Exception:
                pass

        # Re-render the active spectrum so the new downsample / RGBA /
        # interpolation / rasterize / contour-level prefs take effect
        # immediately.
        spectrum_handler = getattr(controller, "spectrum", None)
        if spectrum_handler is not None:
            try:
                # Force a full rebuild rather than the incremental path.
                layers = getattr(
                    getattr(controller, "_layers_model", None), "layers", []
                )
                for layer in layers:
                    if hasattr(layer, "_spectrum_render_key"):
                        layer._spectrum_render_key = None
                spectrum_handler.render_backgrounds()
            except Exception:
                pass

        # Invalidate the blit cache so the next preview uses the new
        # static background.
        if bm is not None:
            try:
                bm.invalidate()
            except Exception:
                pass

    def _on_apply(self):
        """Apply preferences without closing dialog."""
        new_prefs = self._gather_preferences()
        save_prefs(new_prefs)
        self.prefs = new_prefs
        self._apply_live_perf_changes(new_prefs)

        # Show confirmation
        QtWidgets.QMessageBox.information(
            self,
            "Preferences Saved",
            "Preferences have been saved. Some changes may require restarting the application."
        )

    def _on_ok(self):
        """Save preferences and close dialog."""
        new_prefs = self._gather_preferences()
        save_prefs(new_prefs)
        self.prefs = new_prefs
        self._apply_live_perf_changes(new_prefs)
        self.accept()

    def _on_cancel(self):
        """Cancel and restore original preferences."""
        # Don't save, just close
        self.reject()
