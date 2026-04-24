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

    _TYPO_LAYOUT_KEYS = frozenset({
        "base_size", "title_scale", "axis_label_scale",
        "tick_label_scale", "legend_scale", "font_family",
        "font_weight", "freq_decimals", "lambda_decimals",
    })

    def _on_layout_changed(self, attr: str, value):
        """Layout / global typography (from Global panel).

        Global typography changes act as if the user changed every layer
        directly: font_family is pushed onto every SubplotState.font_family,
        and base_size proportionally rescales every non-zero per-subplot
        font size. After the propagation, the right-panel context is
        repopulated so per-layer panels show the new effective values.
        """
        sheet = self._current_sheet()
        if not sheet:
            return

        if attr in self._TYPO_LAYOUT_KEYS and hasattr(sheet.typography, attr):
            old_base = sheet.typography.base_size
            setattr(sheet.typography, attr, value)
            if attr == "base_size":
                sheet.legend.font_size = sheet.typography.legend_font_size
                self._propagate_base_size_to_subplots(
                    sheet, old_base, int(value))
            elif attr == "font_family":
                self._propagate_font_family_to_subplots(sheet, str(value))
        elif hasattr(sheet, attr):
            setattr(sheet, attr, value)

        if hasattr(self, "right_panel"):
            try:
                self.right_panel.refresh_current_context(sheet)
            except Exception:
                pass

        self._render_current()

    @staticmethod
    def _propagate_font_family_to_subplots(sheet, new_family: str) -> None:
        """Set sp.font_family on every subplot to ``new_family``."""
        if not new_family:
            return
        for sp in sheet.subplots.values():
            sp.font_family = new_family

    @staticmethod
    def _propagate_base_size_to_subplots(sheet, old_base: int,
                                         new_base: int) -> None:
        """Scale every non-zero per-subplot font size by new_base/old_base.

        Sizes that are 0 (the "inherit global" sentinel) stay 0 — the
        renderer will still pick up the new base via typography. Per-subplot
        overrides are scaled so the visual relationship the user set is
        preserved.
        """
        try:
            old_b = int(old_base)
            new_b = int(new_base)
        except (TypeError, ValueError):
            return
        if old_b <= 0 or new_b <= 0 or old_b == new_b:
            return
        ratio = new_b / float(old_b)
        size_attrs = (
            "title_font_size", "axis_label_font_size",
            "tick_label_font_size", "legend_font_size",
        )
        for sp in sheet.subplots.values():
            for a in size_attrs:
                cur = getattr(sp, a, 0) or 0
                if cur > 0:
                    scaled = max(6, int(round(cur * ratio)))
                    setattr(sp, a, scaled)
