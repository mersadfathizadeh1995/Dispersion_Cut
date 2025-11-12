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

        current_theme = self.prefs.get("theme", "light")
        if current_theme == "dark":
            self.theme_dark.setChecked(True)
        else:
            self.theme_light.setChecked(True)

        theme_layout.addWidget(self.theme_light)
        theme_layout.addWidget(self.theme_dark)

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
        """Gather all preference values from UI widgets."""
        prefs = {}

        # General
        prefs["auto_save_enabled"] = self.auto_save_check.isChecked()
        prefs["auto_save_interval_minutes"] = self.auto_save_interval.value()
        prefs["show_grid"] = self.show_grid_check.isChecked()
        prefs["show_k_guides_default"] = self.show_k_guides_check.isChecked()

        # Appearance
        prefs["theme"] = "dark" if self.theme_dark.isChecked() else "light"

        # Array
        prefs["default_n_phones"] = self.n_phones_spin.value()
        prefs["default_receiver_dx"] = self.receiver_dx_spin.value()
        prefs["nacd_thresh"] = self.nacd_thresh_spin.value()

        # Advanced
        prefs["robust_lower_pct"] = self.robust_lower_spin.value()
        prefs["robust_upper_pct"] = self.robust_upper_spin.value()
        prefs["freq_tick_style"] = "decades" if self.tick_decades.isChecked() else "custom"

        # Copy over values we don't have UI for
        prefs["freq_custom_ticks"] = self.prefs.get("freq_custom_ticks", [])

        return prefs

    def _on_apply(self):
        """Apply preferences without closing dialog."""
        new_prefs = self._gather_preferences()
        save_prefs(new_prefs)
        self.prefs = new_prefs

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
        self.accept()

    def _on_cancel(self):
        """Cancel and restore original preferences."""
        # Don't save, just close
        self.reject()
