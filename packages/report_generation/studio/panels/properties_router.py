"""Properties router -- context-sensitive right panel.

Uses a vertical QSplitter:
- **Top**: Context zone — changes based on DataTree selection (subplot, data,
  spectrum, NF settings, or a "no selection" summary).
- **Bottom**: Global zone — the Figure/Typography/Axis/Legend/… tabs,
  **always visible** regardless of what is selected above.

This replaces the old single-QStackedWidget approach where selecting an item
would hide the global tabs entirely.
"""
from __future__ import annotations

from ..qt_compat import QtWidgets, Signal, Vertical, ScrollBarAlwaysOff

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QStackedWidget = QtWidgets.QStackedWidget
QTabWidget = QtWidgets.QTabWidget
QScrollArea = QtWidgets.QScrollArea
QLabel = QtWidgets.QLabel
QSplitter = QtWidgets.QSplitter
QFrame = QtWidgets.QFrame
QSizePolicy = QtWidgets.QSizePolicy

from ..figure_model import FigureModel
from ..models import ReportStudioSettings
from .subplot_props_panel import SubplotPropsPanel
from .data_style_panel import DataStylePanel
from .spectrum_series_panel import SpectrumSeriesPanel
from .nearfield_series_panel import NearFieldSeriesPanel

_PAGE_SUMMARY = 0
_PAGE_SUBPLOT = 1
_PAGE_DATA = 2
_PAGE_SPECTRUM = 3
_PAGE_NEARFIELD = 4


class _SelectionSummaryWidget(QWidget):
    """Compact widget shown when nothing is selected in the data tree."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        self._label = QLabel(
            "No selection\n\nClick an item in the Data Tree\n"
            "to view its properties here."
        )
        self._label.setWordWrap(True)
        self._label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self._label)
        layout.addStretch()

    def set_info(self, text: str) -> None:
        self._label.setText(text)


class PropertiesRouter(QWidget):
    """Routes the right panel between context-specific and always-visible global views.

    Layout (vertical QSplitter):
    ┌─────────────────────────────┐
    │  CONTEXT ZONE (top)         │  Switches based on tree selection
    │  Summary / Subplot / Data / │
    │  Spectrum / NF panels       │
    ├─── drag handle ─────────────┤
    │  GLOBAL ZONE (bottom)       │  ALWAYS visible
    │  [Figure] [Typo] [Axis] …  │
    └─────────────────────────────┘
    """

    style_changed = Signal()

    def __init__(
        self,
        global_tabs: QTabWidget,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Vertical splitter: context on top, global on bottom ---
        self._splitter = QSplitter(Vertical)
        layout.addWidget(self._splitter, stretch=1)

        # --- Top: context zone ---
        context_container = QWidget()
        ctx_layout = QVBoxLayout(context_container)
        ctx_layout.setContentsMargins(0, 0, 0, 0)
        ctx_layout.setSpacing(0)

        self._context_label = QLabel("No Selection")
        self._context_label.setStyleSheet(
            "font-weight: bold; padding: 4px 8px; background: #e8e8e8;"
            "border-bottom: 1px solid #ccc;"
        )
        ctx_layout.addWidget(self._context_label)

        self._context_stack = QStackedWidget()
        ctx_layout.addWidget(self._context_stack, stretch=1)

        # Page 0: summary (nothing selected)
        self._summary_widget = _SelectionSummaryWidget()
        self._context_stack.addWidget(self._summary_widget)

        # Page 1: subplot properties
        self._subplot_panel = SubplotPropsPanel()
        self._subplot_panel.changed.connect(self._on_subplot_changed)
        self._subplot_panel.apply_all_requested.connect(self._on_apply_all)
        self._subplot_panel.reset_to_global_requested.connect(self._on_reset_to_global)
        subplot_scroll = QScrollArea()
        subplot_scroll.setWidget(self._subplot_panel)
        subplot_scroll.setWidgetResizable(True)
        subplot_scroll.setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)
        self._context_stack.addWidget(subplot_scroll)

        # Page 2: data series properties
        self._data_panel = DataStylePanel()
        self._data_panel.changed.connect(self._on_data_changed)
        data_scroll = QScrollArea()
        data_scroll.setWidget(self._data_panel)
        data_scroll.setWidgetResizable(True)
        data_scroll.setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)
        self._context_stack.addWidget(data_scroll)

        # Page 3: per-series spectrum settings
        self._spectrum_series_panel = SpectrumSeriesPanel()
        self._spectrum_series_panel.changed.connect(self._on_spectrum_changed)
        spec_scroll = QScrollArea()
        spec_scroll.setWidget(self._spectrum_series_panel)
        spec_scroll.setWidgetResizable(True)
        spec_scroll.setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)
        self._context_stack.addWidget(spec_scroll)

        # Page 4: per-series near-field settings
        self._nf_series_panel = NearFieldSeriesPanel()
        self._nf_series_panel.changed.connect(self._on_nf_changed)
        nf_scroll = QScrollArea()
        nf_scroll.setWidget(self._nf_series_panel)
        nf_scroll.setWidgetResizable(True)
        nf_scroll.setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)
        self._context_stack.addWidget(nf_scroll)

        self._splitter.addWidget(context_container)

        # --- Bottom: global tabs (always visible) ---
        global_container = QWidget()
        gl_layout = QVBoxLayout(global_container)
        gl_layout.setContentsMargins(0, 0, 0, 0)
        gl_layout.setSpacing(0)

        global_header = QLabel("Global Settings")
        global_header.setStyleSheet(
            "font-weight: bold; padding: 4px 8px; background: #dde8f0;"
            "border-bottom: 1px solid #b0c4de;"
        )
        gl_layout.addWidget(global_header)

        self._global_tabs = global_tabs
        gl_layout.addWidget(self._global_tabs, stretch=1)

        self._splitter.addWidget(global_container)

        # Default split: ~35% context / ~65% global
        self._splitter.setSizes([250, 450])
        self._splitter.setChildrenCollapsible(True)

        self._model: FigureModel | None = None
        self._current_settings: ReportStudioSettings | None = None

    def set_model(self, model: FigureModel | None) -> None:
        self._model = model

    def show_for(
        self,
        item_type: str,
        key: str,
        settings: ReportStudioSettings,
    ) -> None:
        """Switch the context zone to the appropriate panel."""
        model = settings.figure_model
        if not isinstance(model, FigureModel):
            model = self._model
        self._current_settings = settings

        if item_type == "subplot" and model:
            sp = model.subplot_by_key(key)
            if sp:
                self._subplot_panel.load_from(sp)
                self._context_label.setText(f"Subplot: {sp.title or sp.key}")
                self._context_stack.setCurrentIndex(_PAGE_SUBPLOT)
                return

        if item_type == "data" and model:
            ds = model.series_by_uid(key)
            if ds:
                self._data_panel.load_from(ds)
                self._context_label.setText(f"Data: {ds.label}")
                self._context_stack.setCurrentIndex(_PAGE_DATA)
                return

        if item_type == "spectrum" and model:
            ds = model.series_by_uid(key)
            if ds:
                self._spectrum_series_panel.load_from(key, ds.spectrum)
                self._context_label.setText(f"Spectrum: {ds.label}")
                self._context_stack.setCurrentIndex(_PAGE_SPECTRUM)
                return

        if item_type == "nearfield" and model:
            ds = model.series_by_uid(key)
            if ds:
                self._nf_series_panel.load_from(key, ds.near_field)
                self._context_label.setText(f"Near-Field: {ds.label}")
                self._context_stack.setCurrentIndex(_PAGE_NEARFIELD)
                return

        # Fallback: show summary
        self.show_global()

    def show_global(self) -> None:
        """Show the 'no selection' summary in the context zone."""
        self._context_label.setText("No Selection")
        self._summary_widget.set_info(
            "No selection\n\nClick an item in the Data Tree\n"
            "to view its properties here."
        )
        self._context_stack.setCurrentIndex(_PAGE_SUMMARY)

    # ------------------------------------------------------------------
    # Write-back handlers (context panels -> model)
    # ------------------------------------------------------------------

    def _on_subplot_changed(self) -> None:
        model = self._model
        if model:
            key = self._subplot_panel.current_key
            sp = model.subplot_by_key(key)
            if sp:
                self._subplot_panel.write_to(sp)
        self.style_changed.emit()

    def _on_data_changed(self) -> None:
        model = self._model
        if model:
            uid = self._data_panel.current_uid
            ds = model.series_by_uid(uid)
            if ds:
                self._data_panel.write_to(ds)
        self.style_changed.emit()

    def _on_spectrum_changed(self) -> None:
        model = self._model
        if model:
            uid = self._spectrum_series_panel.current_uid
            ds = model.series_by_uid(uid)
            if ds:
                self._spectrum_series_panel.write_to(ds.spectrum)
        self.style_changed.emit()

    def _on_nf_changed(self) -> None:
        model = self._model
        if model:
            uid = self._nf_series_panel.current_uid
            ds = model.series_by_uid(uid)
            if ds:
                self._nf_series_panel.write_to(ds.near_field)
        self.style_changed.emit()

    # ------------------------------------------------------------------
    # Apply All / Reset to Global
    # ------------------------------------------------------------------

    def _on_apply_all(self) -> None:
        """Copy the current subplot's settings to all other subplots."""
        model = self._model
        if not model:
            return
        source_key = self._subplot_panel.current_key
        source_sp = model.subplot_by_key(source_key)
        if not source_sp:
            return

        for sp in model.subplots:
            if sp.key == source_key:
                continue
            sp.title = source_sp.title  # user may want different titles
            sp.x_scale = source_sp.x_scale
            sp.y_scale = source_sp.y_scale
            sp.x_label = source_sp.x_label
            sp.y_label = source_sp.y_label
            sp.auto_x = source_sp.auto_x
            sp.auto_y = source_sp.auto_y
            sp.x_min = source_sp.x_min
            sp.x_max = source_sp.x_max
            sp.y_min = source_sp.y_min
            sp.y_max = source_sp.y_max
            sp.show_grid = source_sp.show_grid
            sp.grid_alpha = source_sp.grid_alpha
            sp.grid_linestyle = source_sp.grid_linestyle
            sp.show_spectrum = source_sp.show_spectrum
            sp.spectrum_offset_index = source_sp.spectrum_offset_index
            sp.show_legend = source_sp.show_legend
            sp.legend_location = source_sp.legend_location
            sp.legend_ncol = source_sp.legend_ncol
        self.style_changed.emit()

    def _on_reset_to_global(self) -> None:
        """Reset the current subplot's axis/legend settings to global defaults."""
        settings = self._current_settings
        if not settings:
            return
        model = self._model
        if not model:
            return
        key = self._subplot_panel.current_key
        sp = model.subplot_by_key(key)
        if not sp:
            return

        # Reset axis settings from global
        ax = settings.axis
        sp.x_scale = "log"
        sp.y_scale = "linear"
        sp.auto_x = ax.auto_x
        sp.auto_y = ax.auto_y
        sp.x_min = ax.x_min if not ax.auto_x else None
        sp.x_max = ax.x_max if not ax.auto_x else None
        sp.y_min = ax.y_min if not ax.auto_y else None
        sp.y_max = ax.y_max if not ax.auto_y else None

        # Reset legend from global
        leg = settings.legend
        sp.show_legend = leg.show
        sp.legend_location = leg.location
        sp.legend_ncol = leg.ncol

        # Reload the panel
        self._subplot_panel.load_from(sp)
        self.style_changed.emit()

    # ------------------------------------------------------------------
    # Panel accessors
    # ------------------------------------------------------------------

    @property
    def subplot_panel(self) -> SubplotPropsPanel:
        return self._subplot_panel

    @property
    def data_panel(self) -> DataStylePanel:
        return self._data_panel

    @property
    def spectrum_series_panel(self) -> SpectrumSeriesPanel:
        return self._spectrum_series_panel

    @property
    def nf_series_panel(self) -> NearFieldSeriesPanel:
        return self._nf_series_panel
