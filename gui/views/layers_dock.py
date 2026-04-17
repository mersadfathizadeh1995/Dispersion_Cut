"""Layers dock – 4-tab container.

Sub-tabs:
  1. Data     – source offset layer list with All On / All Off + per-layer checkboxes
  2. Spectrum – spectrum controls (colormap, render, per-layer show/opacity)
  3. λ Lines  – wavelength line compute + manage
  4. K-Limits – wavenumber limit guides
"""
from __future__ import annotations

from typing import Optional
from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore
from matplotlib import colors as mcolors


class LayersDock(QtWidgets.QDockWidget):
    """Multi-tab dock: Data | Spectrum | λ Lines | K-Limits."""

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

        host = QtWidgets.QWidget(self)
        self.setWidget(host)
        root_layout = QtWidgets.QVBoxLayout(host)
        root_layout.setContentsMargins(2, 2, 2, 2)
        root_layout.setSpacing(0)

        self._tabs = QtWidgets.QTabWidget()
        root_layout.addWidget(self._tabs)

        # ── Tab 1: Data ──
        self._build_data_tab()

        # ── Tab 2: Spectrum ──
        self._build_spectrum_tab()

        # ── Tab 3: λ Lines ──
        self._build_lambda_tab()

        # ── Tab 4: K-Limits ──
        self._build_klimits_tab()

    # ================================================================
    #  Tab 1: Data (source offset layers)
    # ================================================================
    def _build_data_tab(self) -> None:
        """The original layers list with All On / All Off + checkboxes."""
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(4, 4, 4, 4)

        self.view = QtWidgets.QListView(page)
        self.model = QtGui.QStandardItemModel(self.view)
        self.view.setModel(self.model)
        try:
            self.view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        except AttributeError:
            self.view.setEditTriggers(
                QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
            )

        btn_row = QtWidgets.QHBoxLayout()
        btn_all_on = QtWidgets.QPushButton("All On", page)
        btn_all_off = QtWidgets.QPushButton("All Off", page)
        btn_all_on.clicked.connect(lambda: self._set_all_layers(True))
        btn_all_off.clicked.connect(lambda: self._set_all_layers(False))
        btn_row.addWidget(btn_all_on)
        btn_row.addWidget(btn_all_off)
        v.addLayout(btn_row)
        v.addWidget(self.view)

        self.rebuild()
        self.model.itemChanged.connect(self._on_item_changed)

        self._tabs.addTab(page, "Data")

    # ================================================================
    #  Tab 2: Spectrum (embedded SpectrumDock content)
    # ================================================================
    def _build_spectrum_tab(self) -> None:
        from dc_cut.gui.views.spectrum_dock import SpectrumDock
        # Create the dock but use its internal widget only (not the dock frame)
        self._spectrum_dock = SpectrumDock(self.c, parent=None)
        # Extract the content widget from the dock
        content = self._spectrum_dock.widget()
        if content is not None:
            content.setParent(None)
            self._tabs.addTab(content, "Spectrum")
        else:
            self._tabs.addTab(QtWidgets.QWidget(), "Spectrum")

    # ================================================================
    #  Tab 3: λ Lines (embedded WavelengthLinesDock content)
    # ================================================================
    def _build_lambda_tab(self) -> None:
        from dc_cut.gui.views.wavelength_lines_dock import WavelengthLinesDock
        self._wavelength_dock = WavelengthLinesDock(self.c, parent=None)
        content = self._wavelength_dock.widget()
        if content is not None:
            content.setParent(None)
            self._tabs.addTab(content, "λ Lines")
        else:
            self._tabs.addTab(QtWidgets.QWidget(), "λ Lines")

    # ================================================================
    #  Tab 4: K-Limits (extracted from Properties)
    # ================================================================
    def _build_klimits_tab(self) -> None:
        from dc_cut.gui.views.klimits_panel import KLimitsPanel
        self._klimits_panel = KLimitsPanel(self.c)
        self._tabs.addTab(self._klimits_panel, "K-Limits")

    # ================================================================
    #  Data tab: rebuild + handlers (same as before)
    # ================================================================
    def showEvent(self, event) -> None:
        self.rebuild()
        super().showEvent(event)

    def _make_icon(self, mpl_line):
        col = mpl_line.get_markeredgecolor() or mpl_line.get_color() or 'k'
        r, g, b, _ = mcolors.to_rgba(col)
        r, g, b = int(r * 255), int(g * 255), int(b * 255)
        pix = QtGui.QPixmap(16, 16)
        pix.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pix)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
        except AttributeError:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setBrush(QtGui.QColor(r, g, b))
        try:
            painter.setPen(QtCore.Qt.NoPen)
        except AttributeError:
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()
        return QtGui.QIcon(pix)

    def rebuild(self) -> None:
        self.model.clear()
        c = self.c
        try:
            chk_on = QtCore.Qt.Checked
            chk_off = QtCore.Qt.Unchecked
            role = QtCore.Qt.UserRole
        except AttributeError:
            chk_on = QtCore.Qt.CheckState.Checked
            chk_off = QtCore.Qt.CheckState.Unchecked
            role = QtCore.Qt.ItemDataRole.UserRole

        # Get layers model for visibility info
        layers_model = getattr(c, '_layers_model', None) or getattr(c, 'model', None)

        n = min(len(c.lines_wave), len(c.lines_freq))
        for idx in range(n):
            # Check visibility from layers model
            layer_visible = True
            if (
                layers_model
                and hasattr(layers_model, 'layers')
                and idx < len(layers_model.layers)
            ):
                layer_visible = getattr(layers_model.layers[idx], 'visible', True)

            # Only show visible layers in the Layers dock
            if not layer_visible:
                continue

            lbl = (
                c.offset_labels[idx]
                if idx < len(c.offset_labels)
                else f"Offset {idx+1}"
            )
            item = QtGui.QStandardItem(self._make_icon(c.lines_wave[idx]), lbl)
            item.setCheckable(True)
            item.setCheckState(chk_on if c.lines_freq[idx].get_visible() else chk_off)
            item.setData(idx, role)
            self.model.appendRow(item)

        item_f = QtGui.QStandardItem(c.average_label)
        item_f.setCheckable(True)
        item_f.setCheckState(chk_on if c.show_average else chk_off)
        item_f.setData("avg_f", role)
        self.model.appendRow(item_f)

        item_w = QtGui.QStandardItem(c.average_label_wave)
        item_w.setCheckable(True)
        item_w.setCheckState(chk_on if c.show_average_wave else chk_off)
        item_w.setData("avg_w", role)
        self.model.appendRow(item_w)

    def _on_item_changed(self, item):
        c = self.c
        try:
            role = item.data(QtCore.Qt.UserRole)
        except AttributeError:
            role = item.data(QtCore.Qt.ItemDataRole.UserRole)
        try:
            chk_on = QtCore.Qt.Checked
        except AttributeError:
            chk_on = QtCore.Qt.CheckState.Checked
        visible = item.checkState() == chk_on
        if role == "avg_f":
            c.show_average = visible
            c._update_average_line()
        elif role == "avg_w":
            c.show_average_wave = visible
            c._update_average_line()
        else:
            try:
                idx = int(role)
            except Exception:
                return
            # Guard against stale indices after undo/redo or state changes
            if idx < 0 or idx >= len(c.lines_freq) or idx >= len(c.lines_wave):
                try:
                    self.rebuild()
                except Exception:
                    pass
                return
            c.lines_freq[idx].set_visible(visible)
            c.lines_wave[idx].set_visible(visible)
            # Reflect in model so autoscale uses correct visible set
            try:
                if getattr(c, '_layers_model', None) is not None:
                    c._layers_model.set_visible(idx, visible)
            except Exception:
                pass
            if c.show_average or c.show_average_wave:
                c._update_average_line()
        c._update_legend()
        c._apply_axis_limits()
        # Update spectrum backgrounds if method exists
        try:
            if hasattr(c, '_render_spectrum_backgrounds'):
                c._render_spectrum_backgrounds()
        except Exception:
            pass
        c.fig.canvas.draw_idle()

    def _set_all_layers(self, visible: bool) -> None:
        c = self.c
        try:
            role = QtCore.Qt.UserRole
        except AttributeError:
            role = QtCore.Qt.ItemDataRole.UserRole
        try:
            chk_on = QtCore.Qt.Checked
            chk_off = QtCore.Qt.Unchecked
        except AttributeError:
            chk_on = QtCore.Qt.CheckState.Checked
            chk_off = QtCore.Qt.CheckState.Unchecked
        try:
            self.model.blockSignals(True)
        except Exception:
            pass
        for row in range(self.model.rowCount()):
            it = self.model.item(row)
            if it is None:
                continue
            it.setCheckState(chk_on if visible else chk_off)
        try:
            self.model.blockSignals(False)
        except Exception:
            pass
        # Use actual line count to avoid stale labels
        for idx in range(min(len(c.lines_freq), len(c.lines_wave))):
            c.lines_freq[idx].set_visible(visible)
            c.lines_wave[idx].set_visible(visible)
            try:
                if getattr(c, '_layers_model', None) is not None:
                    c._layers_model.set_visible(idx, visible)
            except Exception:
                pass
        c.show_average = bool(visible)
        c.show_average_wave = bool(visible)
        if c.show_average or c.show_average_wave:
            c._update_average_line()
        c._update_legend()
        c._apply_axis_limits()
        # Update spectrum backgrounds if method exists
        try:
            if hasattr(c, '_render_spectrum_backgrounds'):
                c._render_spectrum_backgrounds()
        except Exception:
            pass
        c.fig.canvas.draw_idle()

    # ── Forwarding API so external code can still call spectrum/lambda methods ──

    @property
    def spectrum(self):
        """Access the embedded spectrum dock."""
        return getattr(self, '_spectrum_dock', None)

    @property
    def wavelength_lines(self):
        """Access the embedded wavelength lines dock."""
        return getattr(self, '_wavelength_dock', None)

    @property
    def klimits(self):
        """Access the embedded k-limits panel."""
        return getattr(self, '_klimits_panel', None)
