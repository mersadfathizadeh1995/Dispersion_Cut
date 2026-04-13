"""Data handlers mixin — curve selection, visibility, style updates."""

from __future__ import annotations


class DataHandlersMixin:
    """Handles data-related signals from the tree panel and properties panel."""

    def _on_curve_selected(self, uid: str):
        """A curve was selected in the tree or clicked on canvas."""
        sheet = self._current_sheet()
        if not sheet:
            return
        self._selected_uid = uid
        canvas = self.sheet_tabs.current_canvas()
        if canvas:
            canvas.set_selected(uid)
        # Update right panel context
        if hasattr(self, "right_panel") and uid in sheet.curves:
            curve = sheet.curves[uid]
            self.right_panel.show_curve(curve)
        self._render_current()

    def _on_curve_visibility_changed(self, uid: str, visible: bool):
        """Toggle curve visibility from tree checkbox."""
        sheet = self._current_sheet()
        if not sheet or uid not in sheet.curves:
            return
        sheet.curves[uid].visible = visible
        self._render_current()

    def _on_spectrum_visibility_changed(self, uid: str, visible: bool):
        """Toggle spectrum background visibility from tree checkbox."""
        sheet = self._current_sheet()
        if not sheet or uid not in sheet.curves:
            return
        sheet.curves[uid].spectrum_visible = visible
        self._render_current()

    def _on_spectrum_selected(self, uid: str):
        """A spectrum item was selected in the data tree."""
        sheet = self._current_sheet()
        if not sheet or uid not in sheet.curves:
            return
        curve = sheet.curves[uid]
        if hasattr(self, "right_panel"):
            self.right_panel.show_spectrum(curve)

    def _on_spectra_selected(self, uids: list):
        """Multiple spectrum items selected (Ctrl/Shift click)."""
        sheet = self._current_sheet()
        if not sheet:
            return
        curves = [sheet.curves[u] for u in uids if u in sheet.curves]
        if curves and hasattr(self, "right_panel"):
            self.right_panel.show_spectra_batch(uids, curves)

    def _on_subplot_selected(self, key: str):
        """A subplot was selected in the data tree."""
        sheet = self._current_sheet()
        if not sheet or key not in sheet.subplots:
            return
        sp = sheet.subplots[key]
        if hasattr(self, "right_panel"):
            self.right_panel.show_subplot(sp)
        self.statusBar().showMessage(f"Subplot: {sp.display_name}")

    def _on_subplots_selected(self, keys: list):
        """Multiple subplots selected (Ctrl/Shift click)."""
        sheet = self._current_sheet()
        if not sheet:
            return
        subplots = [sheet.subplots[k] for k in keys if k in sheet.subplots]
        if subplots and hasattr(self, "right_panel"):
            self.right_panel.show_subplots_batch(keys, subplots)
        self.statusBar().showMessage(f"{len(subplots)} subplots selected")

    def _on_curve_moved(self, uid: str, new_subplot_key: str):
        """Curve was dragged to a different subplot in the tree."""
        sheet = self._current_sheet()
        if not sheet:
            return
        sheet.move_curve(uid, new_subplot_key)
        if hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        self._render_current()

    def _on_curve_removed(self, uid: str):
        """Remove a curve from the sheet."""
        sheet = self._current_sheet()
        if not sheet:
            return
        sheet.remove_curve(uid)
        if hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        if hasattr(self, "right_panel"):
            self.right_panel.show_empty()
        self._selected_uid = None
        self._render_current()

    def _on_curves_removed(self, uids: list):
        """Remove multiple curves at once."""
        sheet = self._current_sheet()
        if not sheet:
            return
        sheet.remove_curves(uids)
        if hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        if hasattr(self, "right_panel"):
            self.right_panel.show_empty()
        self._selected_uid = None
        self._render_current()

    def _on_subplot_renamed(self, key: str, new_name: str):
        """User renamed a subplot via inline edit in data tree."""
        sheet = self._current_sheet()
        if not sheet or key not in sheet.subplots:
            return
        sheet.subplots[key].name = new_name
        # Refresh export panel + re-render title
        if hasattr(self, "right_panel"):
            pkeys, pnames = sheet.populated_subplot_info()
            self.right_panel.update_subplot_list(pkeys, pnames)
        self._render_current()

    def _on_style_changed(self, uid: str, attr: str, value):
        """Curve style changed from properties panel."""
        sheet = self._current_sheet()
        if not sheet or uid not in sheet.curves:
            return
        curve = sheet.curves[uid]
        if hasattr(curve, attr):
            setattr(curve, attr, value)
        # Refresh tree color swatch if color changed
        if attr == "color" and hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        self._render_current()

    def _on_subplot_setting_changed(self, key: str, attr: str, value):
        """Subplot setting changed from properties panel."""
        sheet = self._current_sheet()
        if not sheet or key not in sheet.subplots:
            return
        sp = sheet.subplots[key]
        if hasattr(sp, attr):
            setattr(sp, attr, value)
        self._render_current()

    def _on_subplot_clicked(self, key: str):
        """Subplot area clicked on canvas — show its settings."""
        sheet = self._current_sheet()
        if not sheet or key not in sheet.subplots:
            return
        sp = sheet.subplots[key]
        if hasattr(self, "right_panel"):
            self.right_panel.show_subplot(sp)
        self.statusBar().showMessage(f"Subplot: {sp.display_name}")

    def _on_curves_selected(self, uids: list):
        """Multiple curves selected (Ctrl/Shift click)."""
        sheet = self._current_sheet()
        if not sheet:
            return
        curves = [sheet.curves[u] for u in uids if u in sheet.curves]
        if curves and hasattr(self, "right_panel"):
            self.right_panel.curve_panel.show_curves_batch(uids, curves)

    def _on_curve_style_updated(self, uid: str, **kwargs):
        """Update curve style properties (color, line_width, etc.)."""
        sheet = self._current_sheet()
        if not sheet or uid not in sheet.curves:
            return
        curve = sheet.curves[uid]
        for key, value in kwargs.items():
            if hasattr(curve, key):
                setattr(curve, key, value)
        self._render_current()

    def _on_point_visibility_changed(self, uid: str, point_idx: int, visible: bool):
        """Toggle visibility of a single point on a curve."""
        sheet = self._current_sheet()
        if not sheet or uid not in sheet.curves:
            return
        curve = sheet.curves[uid]
        if curve.point_mask is not None and point_idx < len(curve.point_mask):
            curve.point_mask[point_idx] = visible
            self._render_current()

    # ── Aggregated curve handlers ─────────────────────────────────────

    def _on_aggregated_selected(self, uid: str):
        """An aggregated curve node selected in the data tree."""
        sheet = self._current_sheet()
        if not sheet or uid not in sheet.aggregated:
            return
        agg = sheet.aggregated[uid]
        if hasattr(self, "right_panel"):
            self.right_panel.show_aggregated(agg)

    def _on_aggregated_style_changed(self, uid: str, attr: str, value):
        """Aggregated curve style changed from the settings panel."""
        sheet = self._current_sheet()
        if not sheet or uid not in sheet.aggregated:
            return
        agg = sheet.aggregated[uid]
        if hasattr(agg, attr):
            setattr(agg, attr, value)
        # If binning params changed, recompute aggregates from shadow curves
        if attr in ("num_bins", "log_bias", "x_domain"):
            self._recompute_aggregated(sheet, agg)
        self._render_current()

    def _recompute_aggregated(self, sheet, agg):
        """Recompute binned avg/std from shadow curves."""
        from dc_cut.core.processing.averages import (
            compute_binned_avg_std,
            compute_binned_avg_std_wavelength,
        )
        import numpy as np

        shadow_curves = [
            sheet.curves[uid] for uid in agg.shadow_curve_uids
            if uid in sheet.curves and sheet.curves[uid].has_data
        ]
        if not shadow_curves:
            return
        all_x, all_y = [], []
        for c in shadow_curves:
            if agg.x_domain == "wavelength" and c.wavelength.size > 0:
                all_x.append(c.wavelength)
            else:
                all_x.append(c.frequency)
            all_y.append(c.velocity)
        if not all_x:
            return
        x_cat = np.concatenate(all_x)
        y_cat = np.concatenate(all_y)
        if agg.x_domain == "wavelength":
            bc, av, sd = compute_binned_avg_std_wavelength(
                x_cat, y_cat, num_bins=agg.num_bins, log_bias=agg.log_bias)
        else:
            bc, av, sd = compute_binned_avg_std(
                x_cat, y_cat, num_bins=agg.num_bins, log_bias=agg.log_bias)
        agg.bin_centers = bc
        agg.avg_vals = av
        agg.std_vals = sd

    def _on_aggregated_visibility_changed(self, uid: str, layer: str,
                                          visible: bool):
        """Aggregated sub-layer visibility toggled from tree checkbox."""
        sheet = self._current_sheet()
        if not sheet or uid not in sheet.aggregated:
            return
        agg = sheet.aggregated[uid]
        if layer == "all":
            agg.avg_visible = visible
            agg.uncertainty_visible = visible
            agg.shadow_visible = visible
            # Also toggle individual shadow curves
            for sc_uid in agg.shadow_curve_uids:
                sc = sheet.curves.get(sc_uid)
                if sc:
                    sc.visible = visible
        elif layer == "avg":
            agg.avg_visible = visible
        elif layer == "uncertainty":
            agg.uncertainty_visible = visible
        elif layer == "shadow":
            agg.shadow_visible = visible
            for sc_uid in agg.shadow_curve_uids:
                sc = sheet.curves.get(sc_uid)
                if sc:
                    sc.visible = visible
        self._render_current()

    def _on_remove_aggregated(self, uid: str):
        """Remove an entire aggregated figure (avg + uncertainty + shadows)."""
        sheet = self._current_sheet()
        if not sheet or uid not in sheet.aggregated:
            return
        agg = sheet.aggregated[uid]
        # Remove shadow curves from sheet
        for sc_uid in list(agg.shadow_curve_uids):
            if sc_uid in sheet.curves:
                del sheet.curves[sc_uid]
            # Remove from subplot curve_uids
            for sp in sheet.subplots.values():
                if sc_uid in sp.curve_uids:
                    sp.curve_uids.remove(sc_uid)
        # Clear subplot link
        for sp in sheet.subplots.values():
            if sp.aggregated_uid == uid:
                sp.aggregated_uid = ""
        # Remove from aggregated dict
        del sheet.aggregated[uid]
        # Refresh tree + canvas
        self.data_tree.populate(sheet)
        self._render_current()

    def _on_aggregated_moved(self, uid: str, new_subplot_key: str):
        """Move an aggregated figure (avg + shadows) to another subplot."""
        sheet = self._current_sheet()
        if not sheet or uid not in sheet.aggregated:
            return
        sheet.move_aggregated(uid, new_subplot_key)
        self.data_tree.populate(sheet)
        self._render_current()
