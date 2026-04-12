"""Subplot handlers mixin — layout changes, type management, legend, typography."""

from __future__ import annotations


class SubplotHandlersMixin:
    """Handles subplot layout, legend, and typography changes."""

    def _on_grid_changed(self, rows: int, cols: int):
        """Grid dimensions changed in the sheet panel."""
        sheet = self._current_sheet()
        if not sheet:
            return
        sheet.set_grid(rows, cols)
        if hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        self._render_current()

    def _on_domain_changed(self, subplot_key: str, x_domain: str):
        """X-axis domain changed (frequency/wavelength) for a subplot."""
        sheet = self._current_sheet()
        if not sheet or subplot_key not in sheet.subplots:
            return
        sheet.subplots[subplot_key].x_domain = x_domain
        self._render_current()

    def _on_subplot_renamed(self, key: str, name: str):
        """Subplot was renamed in the tree or sheet panel."""
        sheet = self._current_sheet()
        if not sheet or key not in sheet.subplots:
            return
        sheet.subplots[key].name = name
        self._render_current()

    def _on_col_ratios_changed(self, ratios: list):
        """Column width ratios changed."""
        sheet = self._current_sheet()
        if not sheet:
            return
        sheet.col_ratios = ratios
        self._render_current()

    def _on_legend_changed(self, attr: str, value):
        """Legend setting changed from sheet panel."""
        sheet = self._current_sheet()
        if not sheet:
            return
        if hasattr(sheet.legend, attr):
            setattr(sheet.legend, attr, value)
        self._render_current()

    def _on_typography_changed(self, attr: str, value):
        """Typography setting changed from sheet panel."""
        sheet = self._current_sheet()
        if not sheet:
            return
        if hasattr(sheet.typography, attr):
            setattr(sheet.typography, attr, value)
        self._render_current()

    def _on_layout_changed(self, attr: str, value):
        """Layout setting changed (hspace, wspace, figure_width, figure_height)."""
        sheet = self._current_sheet()
        if not sheet:
            return
        if hasattr(sheet, attr):
            setattr(sheet, attr, value)
        self._render_current()
