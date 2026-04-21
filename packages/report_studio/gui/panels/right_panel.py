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
from .aggregated_settings import AggregatedSettingsPanel
from .lambda_settings import LambdaSettingsPanel
from .nf_settings_panel import NFSettingsPanel
from .nf_line_settings import NFLineSettingsPanel
from .nf_per_offset_panel import NFPerOffsetPanel
from .legend_layer_panel import LegendLayerPanel
from .global_panel import GlobalSettingsPanel
from .export_panel import ExportPanel

if TYPE_CHECKING:
    from ...core.models import (
        AggregatedCurve,
        NFAnalysis,
        OffsetCurve,
        SheetState,
        SubplotState,
    )


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
    aggregated_style_changed = Signal(str, str, object)
    lambda_style_changed = Signal(str, str, str, object)
    nf_setting_changed = Signal(str, str, object)
    nf_recompute_requested = Signal(str)
    nf_line_style_changed = Signal(str, str, str, object)
    nf_ranges_apply_requested = Signal(str)
    nf_per_offset_changed = Signal(str, int, str, object)
    grid_changed = Signal(int, int)
    layout_changed = Signal(str, object)
    legend_changed = Signal(str, object)
    # subplot-legend layer attribute changed: (subplot_key, attr, value)
    subplot_legend_changed = Signal(str, str, object)
    export_figure_requested = Signal(dict)
    export_subplots_requested = Signal(dict)
    export_data_requested = Signal(dict)

    # Indices in the context stack
    _IDX_EMPTY = 0
    _IDX_SUBPLOT = 1
    _IDX_CURVE = 2
    _IDX_SPECTRUM = 3
    _IDX_AGGREGATED = 4
    _IDX_LAMBDA = 5
    _IDX_NF = 6
    _IDX_NFLINE = 7
    _IDX_NF_PER_OFFSET = 8
    _IDX_LEGEND = 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_subplot = None
        self._last_sheet = None
        self._last_batch_keys: list = []
        self._last_batch_subplots: list = []
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

        # Index 4: aggregated curve settings
        self.aggregated_panel = AggregatedSettingsPanel()
        scroll_ag = _make_scroll(self.aggregated_panel)
        self._context_stack.addWidget(scroll_ag)

        self.lambda_panel = LambdaSettingsPanel()
        scroll_lm = _make_scroll(self.lambda_panel)
        self._context_stack.addWidget(scroll_lm)

        self.nf_panel = NFSettingsPanel()
        scroll_nf = _make_scroll(self.nf_panel)
        self._context_stack.addWidget(scroll_nf)

        self.nf_line_panel = NFLineSettingsPanel()
        scroll_nfl = _make_scroll(self.nf_line_panel)
        self._context_stack.addWidget(scroll_nfl)

        self.nf_per_offset_panel = NFPerOffsetPanel()
        scroll_nfo = _make_scroll(self.nf_per_offset_panel)
        self._context_stack.addWidget(scroll_nfo)

        self.legend_panel = LegendLayerPanel()
        scroll_lg = _make_scroll(self.legend_panel)
        self._context_stack.addWidget(scroll_lg)

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
        self.aggregated_panel.aggregated_style_changed.connect(
            self.aggregated_style_changed.emit)
        self.lambda_panel.style_changed.connect(self.lambda_style_changed.emit)
        self.nf_panel.nf_setting_changed.connect(self.nf_setting_changed.emit)
        self.nf_panel.nf_recompute_requested.connect(
            self.nf_recompute_requested.emit)
        self.nf_panel.nf_ranges_apply_requested.connect(
            self.nf_ranges_apply_requested.emit)
        self.nf_line_panel.style_changed.connect(
            self.nf_line_style_changed.emit)
        self.nf_per_offset_panel.per_offset_changed.connect(
            self.nf_per_offset_changed.emit
        )
        self.legend_panel.legend_changed.connect(
            self.subplot_legend_changed.emit
        )

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

    def show_subplot(self, sp: "SubplotState", sheet: "SheetState" = None):
        """Activate the subplot settings tab."""
        self._last_subplot = sp
        self._last_sheet = sheet
        typography = getattr(sheet, "typography", None) if sheet else None
        self.subplot_panel.show_subplot(sp, typography=typography)
        self._context_stack.setCurrentIndex(self._IDX_SUBPLOT)
        self._tabs.setCurrentIndex(0)  # switch to Context tab

    def show_subplots_batch(self, keys: list, subplots: list,
                            sheet: "SheetState" = None):
        """Activate subplot settings in batch mode."""
        self._last_subplot = subplots[0] if subplots else None
        self._last_sheet = sheet
        self._last_batch_keys = list(keys)
        self._last_batch_subplots = list(subplots)
        typography = getattr(sheet, "typography", None) if sheet else None
        self.subplot_panel.show_subplots_batch(
            keys, subplots, typography=typography)
        self._context_stack.setCurrentIndex(self._IDX_SUBPLOT)
        self._tabs.setCurrentIndex(0)

    def refresh_current_context(self, sheet: "SheetState"):
        """Repopulate whichever stacked context panel is currently visible.

        Used after a global change (e.g. typography) so per-layer panels
        show the new effective values without needing the user to re-click
        the tree item.
        """
        idx = self._context_stack.currentIndex()
        if idx == self._IDX_SUBPLOT:
            keys = getattr(self, "_last_batch_keys", []) or []
            if len(keys) > 1:
                subs = [
                    sheet.subplots[k] for k in keys
                    if k in sheet.subplots
                ]
                if subs:
                    self.subplot_panel.show_subplots_batch(
                        keys, subs, typography=sheet.typography)
                return
            sp = getattr(self, "_last_subplot", None)
            if sp is not None and sp.key in sheet.subplots:
                self.subplot_panel.show_subplot(
                    sheet.subplots[sp.key], typography=sheet.typography)

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

    def show_aggregated(self, agg: "AggregatedCurve"):
        """Activate the aggregated curve settings tab."""
        self.aggregated_panel.show_aggregated(agg)
        self._context_stack.setCurrentIndex(self._IDX_AGGREGATED)
        self._tabs.setCurrentIndex(0)

    def show_spectra_batch(self, uids: list, curves: list, combined_bar=None):
        """Activate spectrum settings in batch mode.

        ``combined_bar`` is the sheet's :class:`CombinedSpectrumBarConfig`
        so the panel's advanced section can seed its widgets from the
        current sheet-level values.
        """
        self.spectrum_panel.show_spectra_batch(
            uids, curves, combined_bar=combined_bar,
        )
        self._context_stack.setCurrentIndex(self._IDX_SPECTRUM)
        self._tabs.setCurrentIndex(0)

    def show_lambda_line(self, curve: "OffsetCurve", lam_uid: str):
        line = next((L for L in curve.lambda_lines if L.uid == lam_uid), None)
        if line is None:
            return
        self.lambda_panel.show_lambda_line(curve, line)
        self._context_stack.setCurrentIndex(self._IDX_LAMBDA)
        self._tabs.setCurrentIndex(0)

    def show_nf_analysis(self, nf: "NFAnalysis"):
        self.nf_panel.show_nf(nf)
        self._context_stack.setCurrentIndex(self._IDX_NF)
        self._tabs.setCurrentIndex(0)

    def show_nf_analyses_batch(self, nfs):
        """Activate the NF settings panel in batch mode for several NACD layers."""
        if not nfs:
            return
        self.nf_panel.show_nf_batch(list(nfs))
        self._context_stack.setCurrentIndex(self._IDX_NF)
        self._tabs.setCurrentIndex(0)

    def show_nf_line(self, nf: "NFAnalysis", line_uid: str):
        line = next((L for L in nf.lines if L.uid == line_uid), None)
        if line is None:
            return
        self.nf_line_panel.show_nf_line(nf, line)
        self._context_stack.setCurrentIndex(self._IDX_NFLINE)
        self._tabs.setCurrentIndex(0)

    def show_nf_lines_batch(self, pairs_with_lines):
        """Activate the NF-line panel in batch mode for several guide lines.

        ``pairs_with_lines`` is a list of ``(nf_uid, line_uid, line)``
        tuples. Pass through to :class:`NFLineSettingsPanel` and switch
        the context stack to the NF-line view.
        """
        if not pairs_with_lines:
            return
        self.nf_line_panel.show_nf_lines_batch(list(pairs_with_lines))
        self._context_stack.setCurrentIndex(self._IDX_NFLINE)
        self._tabs.setCurrentIndex(0)

    def show_nf_per_offset(self, nf: "NFAnalysis", offset_index: int):
        self.nf_per_offset_panel.show_per_offset(nf, offset_index)
        self._context_stack.setCurrentIndex(self._IDX_NF_PER_OFFSET)
        self._tabs.setCurrentIndex(0)

    def show_legend_layer(self, key: str, sp: "SubplotState"):
        """Activate the legend layer settings panel."""
        self.legend_panel.show_legend(key, sp)
        self._context_stack.setCurrentIndex(self._IDX_LEGEND)
        self._tabs.setCurrentIndex(0)

    def show_legends_batch(self, keys, subplots):
        """Activate the legend panel in batch mode for several subplots."""
        self.legend_panel.show_legends_batch(list(keys), dict(subplots))
        self._context_stack.setCurrentIndex(self._IDX_LEGEND)
        self._tabs.setCurrentIndex(0)

    def show_empty(self):
        """Show the empty placeholder."""
        self._context_stack.setCurrentIndex(self._IDX_EMPTY)

    def populate_global(self, sheet: "SheetState"):
        """Populate the Global tab from a SheetState."""
        self.global_panel.populate(sheet)

    def update_subplot_list(self, keys, display_names=None):
        """Refresh the export panel subplot checkboxes."""
        self.export_panel.update_subplots(keys, display_names)

    def set_export_sheet(self, sheet: "SheetState"):
        """Pass the current sheet to the export panel for dimension sync."""
        self.export_panel.set_sheet(sheet)


def _make_scroll(widget: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
    """Wrap a widget in a scroll area."""
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(widget)
    scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    return scroll
