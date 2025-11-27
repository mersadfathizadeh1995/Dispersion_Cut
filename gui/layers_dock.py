from __future__ import annotations

from typing import Optional
from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtGui     = qt_compat.QtGui
QtCore    = qt_compat.QtCore
from matplotlib import colors as mcolors


class LayersDock(QtWidgets.QDockWidget):
    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Layers", parent)
        self.setObjectName("LayersDock")
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

        w = QtWidgets.QWidget(self)
        v = QtWidgets.QVBoxLayout(w)
        self.setWidget(w)
        self.view = QtWidgets.QListView(w)
        self.model = QtGui.QStandardItemModel(self.view)
        self.view.setModel(self.model)
        try:
            self.view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        except AttributeError:
            self.view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        btn_row = QtWidgets.QHBoxLayout()
        btn_all_on = QtWidgets.QPushButton("All On", w)
        btn_all_off = QtWidgets.QPushButton("All Off", w)
        btn_all_on.clicked.connect(lambda: self._set_all_layers(True))
        btn_all_off.clicked.connect(lambda: self._set_all_layers(False))
        btn_row.addWidget(btn_all_on)
        btn_row.addWidget(btn_all_off)
        v.addLayout(btn_row)
        v.addWidget(self.view)

        # Spectrum controls section
        spectrum_group = QtWidgets.QGroupBox("Spectrum Backgrounds", w)
        spectrum_layout = QtWidgets.QVBoxLayout(spectrum_group)
        self.spectrum_controls_layout = spectrum_layout
        self.spectrum_controls_widgets = {}  # {layer_idx: {widgets}}
        v.addWidget(spectrum_group)
        self.spectrum_group = spectrum_group

        self.rebuild()
        self.model.itemChanged.connect(self._on_item_changed)

    def showEvent(self, event) -> None:
        self.rebuild(); super().showEvent(event)

    def _make_icon(self, mpl_line):
        col = mpl_line.get_markeredgecolor() or mpl_line.get_color() or 'k'
        r, g, b, _ = mcolors.to_rgba(col)
        r, g, b = int(r * 255), int(g * 255), int(b * 255)
        pix = QtGui.QPixmap(16, 16); pix.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pix)
        try: painter.setRenderHint(QtGui.QPainter.Antialiasing)
        except AttributeError: painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setBrush(QtGui.QColor(r, g, b))
        try: painter.setPen(QtCore.Qt.NoPen)
        except AttributeError: painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 12, 12); painter.end()
        return QtGui.QIcon(pix)

    def rebuild(self) -> None:
        self.model.clear()
        c = self.c
        try:
            chk_on = QtCore.Qt.Checked; chk_off = QtCore.Qt.Unchecked; role = QtCore.Qt.UserRole
        except AttributeError:
            chk_on = QtCore.Qt.CheckState.Checked; chk_off = QtCore.Qt.CheckState.Unchecked; role = QtCore.Qt.ItemDataRole.UserRole
        n = min(len(c.lines_wave), len(c.lines_freq))
        for idx in range(n):
            lbl = c.offset_labels[idx] if idx < len(c.offset_labels) else f"Offset {idx+1}"
            item = QtGui.QStandardItem(self._make_icon(c.lines_wave[idx]), lbl)
            item.setCheckable(True)
            item.setCheckState(chk_on if c.lines_freq[idx].get_visible() else chk_off)
            item.setData(idx, role)
            self.model.appendRow(item)
        item_f = QtGui.QStandardItem(c.average_label); item_f.setCheckable(True); item_f.setCheckState(chk_on if c.show_average else chk_off); item_f.setData("avg_f", role); self.model.appendRow(item_f)
        item_w = QtGui.QStandardItem(c.average_label_wave); item_w.setCheckable(True); item_w.setCheckState(chk_on if c.show_average_wave else chk_off); item_w.setData("avg_w", role); self.model.appendRow(item_w)

        # Rebuild spectrum controls
        self._rebuild_spectrum_controls()

    def _on_item_changed(self, item):
        c = self.c
        try: role = item.data(QtCore.Qt.UserRole)
        except AttributeError: role = item.data(QtCore.Qt.ItemDataRole.UserRole)
        try: chk_on = QtCore.Qt.Checked
        except AttributeError: chk_on = QtCore.Qt.CheckState.Checked
        visible = item.checkState() == chk_on
        if role == "avg_f":
            c.show_average = visible; c._update_average_line()
        elif role == "avg_w":
            c.show_average_wave = visible; c._update_average_line()
        else:
            try:
                idx = int(role)
            except Exception:
                return
            # Guard against stale indices after undo/redo or state changes
            if idx < 0 or idx >= len(c.lines_freq) or idx >= len(c.lines_wave):
                try: self.rebuild()
                except Exception: pass
                return
            c.lines_freq[idx].set_visible(visible); c.lines_wave[idx].set_visible(visible)
            # Reflect in model so autoscale uses correct visible set
            try:
                if getattr(c, '_layers_model', None) is not None:
                    c._layers_model.set_visible(idx, visible)  # type: ignore[attr-defined]
            except Exception:
                pass
            if c.show_average or c.show_average_wave: c._update_average_line()
        c._update_legend(); c._apply_axis_limits()
        # Update spectrum backgrounds if method exists
        try:
            if hasattr(c, '_render_spectrum_backgrounds'):
                c._render_spectrum_backgrounds()
        except Exception:
            pass
        c.fig.canvas.draw_idle()

    def _set_all_layers(self, visible: bool) -> None:
        c = self.c
        try: role = QtCore.Qt.UserRole
        except AttributeError: role = QtCore.Qt.ItemDataRole.UserRole
        try: chk_on = QtCore.Qt.Checked; chk_off = QtCore.Qt.Unchecked
        except AttributeError: chk_on = QtCore.Qt.CheckState.Checked; chk_off = QtCore.Qt.CheckState.Unchecked
        try: self.model.blockSignals(True)
        except Exception: pass
        for row in range(self.model.rowCount()):
            it = self.model.item(row)
            if it is None: continue
            it.setCheckState(chk_on if visible else chk_off)
        try: self.model.blockSignals(False)
        except Exception: pass
        # Use actual line count to avoid stale labels
        for idx in range(min(len(c.lines_freq), len(c.lines_wave))):
            c.lines_freq[idx].set_visible(visible); c.lines_wave[idx].set_visible(visible)
            try:
                if getattr(c, '_layers_model', None) is not None:
                    c._layers_model.set_visible(idx, visible)  # type: ignore[attr-defined]
            except Exception:
                pass
        c.show_average = bool(visible); c.show_average_wave = bool(visible)
        if c.show_average or c.show_average_wave: c._update_average_line()
        c._update_legend(); c._apply_axis_limits()
        # Update spectrum backgrounds if method exists
        try:
            if hasattr(c, '_render_spectrum_backgrounds'):
                c._render_spectrum_backgrounds()
        except Exception:
            pass
        c.fig.canvas.draw_idle()



    def _rebuild_spectrum_controls(self) -> None:
        """Rebuild spectrum controls for layers with spectrum data."""
        # Clear existing controls
        for widgets in self.spectrum_controls_widgets.values():
            try:
                widgets['container'].deleteLater()
            except Exception:
                pass
        self.spectrum_controls_widgets.clear()

        # Check if controller has layers model
        if not hasattr(self.c, '_layers_model') or self.c._layers_model is None:
            self.spectrum_group.setVisible(False)
            return

        layers = self.c._layers_model.layers
        has_any_spectrum = any(layer.spectrum_data is not None for layer in layers)
        
        if not has_any_spectrum:
            self.spectrum_group.setVisible(False)
            return

        self.spectrum_group.setVisible(True)

        # Build controls for each layer with spectrum
        for idx, layer in enumerate(layers):
            if layer.spectrum_data is None:
                continue

            # Container for this layer's controls
            container = QtWidgets.QWidget()
            h_layout = QtWidgets.QHBoxLayout(container)
            h_layout.setContentsMargins(0, 2, 0, 2)

            # Layer label
            label = QtWidgets.QLabel(f"{idx}: {layer.label}")
            label.setMinimumWidth(100)
            h_layout.addWidget(label)

            # Visibility checkbox
            chk_visible = QtWidgets.QCheckBox("Show")
            chk_visible.setChecked(layer.spectrum_visible)
            chk_visible.toggled.connect(lambda checked, i=idx: self._on_spectrum_visibility_changed(i, checked))
            h_layout.addWidget(chk_visible)

            # Opacity label
            opacity_label = QtWidgets.QLabel("Opacity:")
            h_layout.addWidget(opacity_label)

            # Opacity slider
            opacity_slider = QtWidgets.QSlider()
            try:
                opacity_slider.setOrientation(QtCore.Qt.Horizontal)
            except AttributeError:
                opacity_slider.setOrientation(QtCore.Qt.Orientation.Horizontal)
            opacity_slider.setMinimum(0)
            opacity_slider.setMaximum(100)
            opacity_slider.setValue(int(layer.spectrum_alpha * 100))
            opacity_slider.setMaximumWidth(100)
            opacity_slider.valueChanged.connect(lambda val, i=idx: self._on_spectrum_alpha_changed(i, val / 100.0))
            h_layout.addWidget(opacity_slider)

            # Opacity value label
            opacity_val_label = QtWidgets.QLabel(f"{int(layer.spectrum_alpha * 100)}%")
            opacity_val_label.setMinimumWidth(35)
            opacity_slider.valueChanged.connect(lambda val, lbl=opacity_val_label: lbl.setText(f"{val}%"))
            h_layout.addWidget(opacity_val_label)

            self.spectrum_controls_layout.addWidget(container)

            # Store widgets for later cleanup
            self.spectrum_controls_widgets[idx] = {
                'container': container,
                'checkbox': chk_visible,
                'slider': opacity_slider,
                'value_label': opacity_val_label
            }

    def _on_spectrum_visibility_changed(self, layer_idx: int, visible: bool) -> None:
        """Handle spectrum visibility change."""
        if hasattr(self.c, 'set_layer_spectrum_visibility'):
            self.c.set_layer_spectrum_visibility(layer_idx, visible)

    def _on_spectrum_alpha_changed(self, layer_idx: int, alpha: float) -> None:
        """Handle spectrum opacity change."""
        if hasattr(self.c, 'set_layer_spectrum_alpha'):
            self.c.set_layer_spectrum_alpha(layer_idx, alpha)
