"""
Right panel — 3-tab QTabWidget: Context | Global | Export.

The Context tab uses a QStackedWidget to switch between
SubplotSettingsPanel, CurveSettingsPanel, and SpectrumSettingsPanel
depending on what is currently selected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...qt_compat import QtWidgets, QtCore, Signal

from .subplot_settings import SubplotSettingsPanel
from .curve_settings import CurveSettingsPanel
from .spectrum_settings import SpectrumSettingsPanel
from .global_panel import GlobalSettingsPanel
from .export_panel import ExportPanel

if TYPE_CHECKING:
    from ...core.models import SheetState, SubplotState, OffsetCurve


class RightPanel(QtWidgets.QWidget):
    """
    Wrapper around 3 tabs that hosts every settings panel.

    Public attributes
    -----------------
    subplot_panel : SubplotSettingsPanel
    curve_panel   : CurveSettingsPanel
    spectrum_panel: SpectrumSettingsPanel
    global_panel  : GlobalSettingsPanel
    export_panel  : ExportPanel
    """

    # Re-export convenience signals from child panels
    subplot_setting_changed = Signal(str, str, object)
    curve_style_changed = Signal(str, str, object)
    spectrum_style_changed = Signal(str, str, object)
    grid_changed = Signal(int, int)
    layout_changed = Signal(str, object)
    legend_changed = Signal(str, object)
    export_figure_requested = Signal(dict)
    export_subplots_requested = Signal(dict)
    export_data_requested = Signal(dict)

    # Indices in the context stack
    _IDX_EMPTY = 0
    _IDX_SUBPLOT = 1
    _IDX_CURVE = 2
    _IDX_SPECTRUM = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)

        self._tabs = QtWidgets.QTabWidget()
        main.addWidget(self._tabs)

        # ── Tab 1: Context ────────────────────────────────────────────
        ctx_container = QtWidgets.QWidget()
        ctx_layout = QtWidgets.QVBoxLayout(ctx_container)
        ctx_layout.setContentsMargins(0, 0, 0, 0)

        self._context_stack = QtWidgets.QStackedWidget()

        # Index 0: empty placeholder
        empty_lbl = QtWidgets.QLabel("Select a subplot, curve, or spectrum\n"
                                      "to see its settings here.")
        empty_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_lbl.setStyleSheet("color: #888; padding: 20px;")
        self._context_stack.addWidget(empty_lbl)

        # Index 1: subplot settings
        self.subplot_panel = SubplotSettingsPanel()
        scroll_sp = _make_scroll(self.subplot_panel)
        self._context_stack.addWidget(scroll_sp)

        # Index 2: curve settings
        self.curve_panel = CurveSettingsPanel()
        scroll_cv = _make_scroll(self.curve_panel)
        self._context_stack.addWidget(scroll_cv)

        # Index 3: spectrum settings
        self.spectrum_panel = SpectrumSettingsPanel()
        scroll_sx = _make_scroll(self.spectrum_panel)
        self._context_stack.addWidget(scroll_sx)

        ctx_layout.addWidget(self._context_stack)
        self._tabs.addTab(ctx_container, "Context")

        # ── Tab 2: Global ────────────────────────────────────────────
        self.global_panel = GlobalSettingsPanel()
        scroll_gl = _make_scroll(self.global_panel)
        self._tabs.addTab(scroll_gl, "Global")

        # ── Tab 3: Export ────────────────────────────────────────────
        self.export_panel = ExportPanel()
        scroll_ex = _make_scroll(self.export_panel)
        self._tabs.addTab(scroll_ex, "Export")

    def _connect_signals(self):
        """Relay child panel signals upward."""
        self.subplot_panel.setting_changed.connect(
            self.subplot_setting_changed.emit)
        self.curve_panel.style_changed.connect(
            self.curve_style_changed.emit)
        self.spectrum_panel.spectrum_style_changed.connect(
            self.spectrum_style_changed.emit)

        self.global_panel.grid_changed.connect(self.grid_changed.emit)
        self.global_panel.layout_changed.connect(self.layout_changed.emit)
        self.global_panel.legend_changed.connect(self.legend_changed.emit)

        self.export_panel.export_figure_requested.connect(
            self.export_figure_requested.emit)
        self.export_panel.export_subplots_requested.connect(
            self.export_subplots_requested.emit)
        self.export_panel.export_data_requested.connect(
            self.export_data_requested.emit)

    # ── Public API ────────────────────────────────────────────────────

    def show_subplot(self, sp: "SubplotState"):
        """Activate the subplot settings tab."""
        self.subplot_panel.show_subplot(sp)
        self._context_stack.setCurrentIndex(self._IDX_SUBPLOT)
        self._tabs.setCurrentIndex(0)  # switch to Context tab

    def show_subplots_batch(self, keys: list, subplots: list):
        """Activate subplot settings in batch mode."""
        self.subplot_panel.show_subplots_batch(keys, subplots)
        self._context_stack.setCurrentIndex(self._IDX_SUBPLOT)
        self._tabs.setCurrentIndex(0)

    def show_curve(self, curve: "OffsetCurve"):
        """Activate the curve settings tab."""
        self.curve_panel.show_curve(curve)
        self._context_stack.setCurrentIndex(self._IDX_CURVE)
        self._tabs.setCurrentIndex(0)

    def show_spectrum(self, curve: "OffsetCurve"):
        """Activate the spectrum settings tab (using curve's spectrum attrs)."""
        self.spectrum_panel.show_spectrum(curve)
        self._context_stack.setCurrentIndex(self._IDX_SPECTRUM)
        self._tabs.setCurrentIndex(0)

    def show_spectra_batch(self, uids: list, curves: list):
        """Activate spectrum settings in batch mode."""
        self.spectrum_panel.show_spectra_batch(uids, curves)
        self._context_stack.setCurrentIndex(self._IDX_SPECTRUM)
        self._tabs.setCurrentIndex(0)

    def show_empty(self):
        """Show the empty placeholder."""
        self._context_stack.setCurrentIndex(self._IDX_EMPTY)

    def populate_global(self, sheet: "SheetState"):
        """Populate the Global tab from a SheetState."""
        self.global_panel.populate(sheet)

    def update_subplot_list(self, keys):
        """Refresh the export panel subplot checkboxes."""
        self.export_panel.update_subplots(keys)


def _make_scroll(widget: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
    """Wrap a widget in a scroll area."""
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(widget)
    scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    return scroll
