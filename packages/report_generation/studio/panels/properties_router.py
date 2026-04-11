"""Properties router -- context-sensitive right panel.

Swaps the visible panel set based on what is selected in the DataTree:
- Nothing / global -> Figure, Typography, Spectrum, Export
- Subplot selected  -> SubplotPropsPanel
- Data selected     -> DataStylePanel
"""
from __future__ import annotations

from ..qt_compat import QtWidgets, Signal, ScrollBarAlwaysOff

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QStackedWidget = QtWidgets.QStackedWidget
QTabWidget = QtWidgets.QTabWidget
QScrollArea = QtWidgets.QScrollArea
QLabel = QtWidgets.QLabel

from ..figure_model import FigureModel
from ..models import ReportStudioSettings
from .subplot_props_panel import SubplotPropsPanel
from .data_style_panel import DataStylePanel

_PAGE_GLOBAL = 0
_PAGE_SUBPLOT = 1
_PAGE_DATA = 2


class PropertiesRouter(QWidget):
    """Routes the right panel between global, subplot, and data-series views."""

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

        self._context_label = QLabel("Global Settings")
        self._context_label.setStyleSheet(
            "font-weight: bold; padding: 4px 8px; background: #eee;"
        )
        layout.addWidget(self._context_label)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        # Page 0: global tabs (existing panels)
        self._global_tabs = global_tabs
        self._stack.addWidget(self._global_tabs)

        # Page 1: subplot properties
        self._subplot_panel = SubplotPropsPanel()
        self._subplot_panel.changed.connect(self._on_subplot_changed)
        subplot_scroll = QScrollArea()
        subplot_scroll.setWidget(self._subplot_panel)
        subplot_scroll.setWidgetResizable(True)
        subplot_scroll.setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)
        self._stack.addWidget(subplot_scroll)

        # Page 2: data series properties
        self._data_panel = DataStylePanel()
        self._data_panel.changed.connect(self._on_data_changed)
        data_scroll = QScrollArea()
        data_scroll.setWidget(self._data_panel)
        data_scroll.setWidgetResizable(True)
        data_scroll.setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)
        self._stack.addWidget(data_scroll)

        self._model: FigureModel | None = None

    def set_model(self, model: FigureModel | None) -> None:
        self._model = model

    def show_for(
        self,
        item_type: str,
        key: str,
        settings: ReportStudioSettings,
    ) -> None:
        """Switch to the appropriate panel based on the selection."""
        model = settings.figure_model
        if not isinstance(model, FigureModel):
            model = self._model

        if item_type == "subplot" and model:
            sp = model.subplot_by_key(key)
            if sp:
                self._subplot_panel.load_from(sp)
                self._context_label.setText(f"Subplot: {sp.title or sp.key}")
                self._stack.setCurrentIndex(_PAGE_SUBPLOT)
                return

        if item_type == "data" and model:
            ds = model.series_by_uid(key)
            if ds:
                self._data_panel.load_from(ds)
                self._context_label.setText(f"Data: {ds.label}")
                self._stack.setCurrentIndex(_PAGE_DATA)
                return

        self._context_label.setText("Global Settings")
        self._stack.setCurrentIndex(_PAGE_GLOBAL)

    def show_global(self) -> None:
        self._context_label.setText("Global Settings")
        self._stack.setCurrentIndex(_PAGE_GLOBAL)

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

    @property
    def subplot_panel(self) -> SubplotPropsPanel:
        return self._subplot_panel

    @property
    def data_panel(self) -> DataStylePanel:
        return self._data_panel
