from __future__ import annotations

from typing import Optional
from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtGui     = qt_compat.QtGui
QtCore    = qt_compat.QtCore


class SpectrumDock(QtWidgets.QDockWidget):
    """Dock widget for controlling power spectrum backgrounds."""

    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Spectrum", parent)
        self.setObjectName("SpectrumDock")
        self.c = controller

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

        # Main widget and layout
        w = QtWidgets.QWidget(self)
        v = QtWidgets.QVBoxLayout(w)
        self.setWidget(w)

        # Master controls section
        master_group = QtWidgets.QGroupBox("Master Controls", w)
        master_layout = QtWidgets.QVBoxLayout(master_group)

        # Master enable/disable checkbox
        self.chk_master_enable = QtWidgets.QCheckBox("Enable All Spectra", master_group)
        self.chk_master_enable.setChecked(True)
        self.chk_master_enable.toggled.connect(self._on_master_enable_changed)
        master_layout.addWidget(self.chk_master_enable)

        # Colormap selection
        cmap_layout = QtWidgets.QHBoxLayout()
        cmap_label = QtWidgets.QLabel("Colormap:", master_group)
        self.cmap_combo = QtWidgets.QComboBox(master_group)
        self.cmap_combo.addItems(["viridis", "plasma", "hot", "gray"])

        # Load current colormap from preferences
        try:
            from dc_cut.services.prefs import get_pref
            current_cmap = get_pref("spectrum_colormap", "viridis")
            idx = self.cmap_combo.findText(current_cmap)
            if idx >= 0:
                self.cmap_combo.setCurrentIndex(idx)
        except Exception:
            pass

        self.cmap_combo.currentTextChanged.connect(self._on_colormap_changed)
        cmap_layout.addWidget(cmap_label)
        cmap_layout.addWidget(self.cmap_combo, 1)
        master_layout.addLayout(cmap_layout)

        v.addWidget(master_group)

        # Per-layer controls section
        layers_group = QtWidgets.QGroupBox("Layer Spectrum Controls", w)
        self.layers_scroll = QtWidgets.QScrollArea(layers_group)
        self.layers_scroll.setWidgetResizable(True)
        self.layers_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame if hasattr(QtWidgets.QFrame, 'Shape') else QtWidgets.QFrame.NoFrame)

        layers_container = QtWidgets.QWidget()
        self.layers_layout = QtWidgets.QVBoxLayout(layers_container)
        self.layers_layout.setContentsMargins(0, 0, 0, 0)
        self.layers_scroll.setWidget(layers_container)

        layers_group_layout = QtWidgets.QVBoxLayout(layers_group)
        layers_group_layout.addWidget(self.layers_scroll)

        v.addWidget(layers_group)

        # Storage for per-layer widgets
        self.layer_widgets = {}  # {layer_idx: {widgets}}

        # Initial build
        self.rebuild()

    def showEvent(self, event) -> None:
        """Rebuild when dock is shown."""
        self.rebuild()
        super().showEvent(event)

    def rebuild(self) -> None:
        """Rebuild per-layer spectrum controls."""
        # Clear existing widgets
        for widgets in self.layer_widgets.values():
            try:
                widgets['container'].deleteLater()
            except Exception:
                pass
        self.layer_widgets.clear()

        # Check if controller has layers model
        if not hasattr(self.c, '_layers_model') or self.c._layers_model is None:
            return

        layers = self.c._layers_model.layers

        # Build controls for each layer with spectrum data
        for idx, layer in enumerate(layers):
            if layer.spectrum_data is None:
                continue

            # Container for this layer's controls
            container = QtWidgets.QWidget()
            h_layout = QtWidgets.QVBoxLayout(container)
            h_layout.setContentsMargins(5, 5, 5, 5)

            # Set background color to distinguish each layer
            container.setAutoFillBackground(True)
            palette = container.palette()
            try:
                palette.setColor(QtGui.QPalette.Window, QtGui.QColor(245, 245, 245))
            except AttributeError:
                palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(245, 245, 245))
            container.setPalette(palette)

            # Layer label (bold)
            label = QtWidgets.QLabel(f"<b>Layer {idx}: {layer.label}</b>")
            h_layout.addWidget(label)

            # Visibility checkbox
            chk_visible = QtWidgets.QCheckBox("Show Spectrum")
            chk_visible.setChecked(layer.spectrum_visible)
            chk_visible.toggled.connect(lambda checked, i=idx: self._on_spectrum_visibility_changed(i, checked))
            h_layout.addWidget(chk_visible)

            # Opacity control
            opacity_container = QtWidgets.QWidget()
            opacity_layout = QtWidgets.QHBoxLayout(opacity_container)
            opacity_layout.setContentsMargins(0, 0, 0, 0)

            opacity_label = QtWidgets.QLabel("Opacity:")
            opacity_layout.addWidget(opacity_label)

            opacity_slider = QtWidgets.QSlider()
            try:
                opacity_slider.setOrientation(QtCore.Qt.Horizontal)
            except AttributeError:
                opacity_slider.setOrientation(QtCore.Qt.Orientation.Horizontal)
            opacity_slider.setMinimum(0)
            opacity_slider.setMaximum(100)
            opacity_slider.setValue(int(layer.spectrum_alpha * 100))
            opacity_slider.valueChanged.connect(lambda val, i=idx: self._on_spectrum_alpha_changed(i, val / 100.0))
            opacity_layout.addWidget(opacity_slider, 1)

            opacity_val_label = QtWidgets.QLabel(f"{int(layer.spectrum_alpha * 100)}%")
            opacity_val_label.setMinimumWidth(40)
            opacity_slider.valueChanged.connect(lambda val, lbl=opacity_val_label: lbl.setText(f"{val}%"))
            opacity_layout.addWidget(opacity_val_label)

            h_layout.addWidget(opacity_container)

            # Add separator line
            separator = QtWidgets.QFrame()
            try:
                separator.setFrameShape(QtWidgets.QFrame.HLine)
                separator.setFrameShadow(QtWidgets.QFrame.Sunken)
            except AttributeError:
                separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
                separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
            h_layout.addWidget(separator)

            self.layers_layout.addWidget(container)

            # Store widgets for later updates
            self.layer_widgets[idx] = {
                'container': container,
                'checkbox': chk_visible,
                'slider': opacity_slider,
                'value_label': opacity_val_label
            }

        # Add spacer at the end
        self.layers_layout.addStretch()

    def _on_master_enable_changed(self, enabled: bool) -> None:
        """Handle master enable/disable toggle."""
        if hasattr(self.c, 'toggle_all_spectra'):
            self.c.toggle_all_spectra(enabled)
            # Save preference
            try:
                from dc_cut.services.prefs import set_pref
                set_pref("show_spectra", enabled)
            except Exception:
                pass

    def _on_colormap_changed(self, colormap: str) -> None:
        """Handle colormap selection change."""
        # Save preference
        try:
            from dc_cut.services.prefs import set_pref
            set_pref("spectrum_colormap", colormap)
        except Exception:
            pass

        # Re-render all spectra with new colormap
        if hasattr(self.c, '_render_spectrum_backgrounds'):
            self.c._render_spectrum_backgrounds()

    def _on_spectrum_visibility_changed(self, layer_idx: int, visible: bool) -> None:
        """Handle per-layer spectrum visibility change."""
        if hasattr(self.c, 'set_layer_spectrum_visibility'):
            self.c.set_layer_spectrum_visibility(layer_idx, visible)

    def _on_spectrum_alpha_changed(self, layer_idx: int, alpha: float) -> None:
        """Handle per-layer spectrum opacity change."""
        if hasattr(self.c, 'set_layer_spectrum_alpha'):
            self.c.set_layer_spectrum_alpha(layer_idx, alpha)
