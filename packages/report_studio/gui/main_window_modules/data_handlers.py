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
            combined_bar = getattr(sheet, "combined_spectrum_bar", None)
            self.right_panel.show_spectra_batch(
                uids, curves, combined_bar=combined_bar,
            )

    def _on_combined_spectrum_bar_changed(self, attr: str, value):
        """Write one attr onto ``SheetState.combined_spectrum_bar``."""
        sheet = self._current_sheet()
        if not sheet:
            return
        cfg = getattr(sheet, "combined_spectrum_bar", None)
        if cfg is None:
            return
        if not hasattr(cfg, attr):
            return
        setattr(cfg, attr, value)
        self._render_current()

    def _on_subplot_selected(self, key: str):
        """A subplot was selected in the data tree."""
        sheet = self._current_sheet()
        if not sheet or key not in sheet.subplots:
            return
        sp = sheet.subplots[key]
        if hasattr(self, "right_panel"):
            self.right_panel.show_subplot(sp, sheet=sheet)
        self.statusBar().showMessage(f"Subplot: {sp.display_name}")

    def _on_subplots_selected(self, keys: list):
        """Multiple subplots selected (Ctrl/Shift click)."""
        sheet = self._current_sheet()
        if not sheet:
            return
        subplots = [sheet.subplots[k] for k in keys if k in sheet.subplots]
        if subplots and hasattr(self, "right_panel"):
            self.right_panel.show_subplots_batch(keys, subplots, sheet=sheet)
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

    def _on_clear_subplot(self, key: str):
        """User asked to wipe a subplot cell but keep it in the grid."""
        sheet = self._current_sheet()
        if not sheet or key not in sheet.subplots:
            return
        sheet.clear_subplot(key)
        if hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        if hasattr(self, "right_panel"):
            self.right_panel.show_empty()
            pkeys, pnames = sheet.populated_subplot_info()
            self.right_panel.update_subplot_list(pkeys, pnames)
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
            self.right_panel.show_subplot(sp, sheet=sheet)
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
        # Sync subplot x_domain when aggregated x_domain changes
        if attr == "x_domain" and agg.subplot_key:
            sp = sheet.subplots.get(agg.subplot_key)
            if sp:
                sp.x_domain = value
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

    def _on_lambda_visibility_changed(
        self, curve_uid: str, lam_uid: str, visible: bool
    ):
        sheet = self._current_sheet()
        if not sheet or curve_uid not in sheet.curves:
            return
        curve = sheet.curves[curve_uid]
        for L in curve.lambda_lines:
            if L.uid == lam_uid:
                L.visible = visible
                break
        self._render_current()

    def _on_lambda_line_selected(self, curve_uid: str, lam_uid: str):
        sheet = self._current_sheet()
        if not sheet or curve_uid not in sheet.curves:
            return
        curve = sheet.curves[curve_uid]
        if hasattr(self, "right_panel"):
            self.right_panel.show_lambda_line(curve, lam_uid)

    def _on_lambda_style_changed(
        self, curve_uid: str, lam_uid: str, attr: str, value
    ):
        sheet = self._current_sheet()
        if not sheet or curve_uid not in sheet.curves:
            return
        curve = sheet.curves[curve_uid]
        for L in curve.lambda_lines:
            if L.uid == lam_uid and hasattr(L, attr):
                setattr(L, attr, value)
                break
        if hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        self._render_current()

    def _on_nf_analysis_selected(self, nf_uid: str):
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        if hasattr(self, "right_panel"):
            self.right_panel.show_nf_analysis(nf)

    def _on_nf_setting_changed(self, nf_uid: str, attr: str, value):
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        if attr.startswith("palette:"):
            key = attr.split(":", 1)[1]
            nf.severity_palette[key] = str(value)
        elif hasattr(nf, attr):
            setattr(nf, attr, value)
        self._render_current()

    def _on_nf_recompute_requested(self, nf_uid: str):
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(
                "Re-open Add Data with the same PKL to refresh NF analysis."
            )

    def _on_nf_guide_visibility_changed(
        self, nf_uid: str, line_uid: str, visible: bool
    ):
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        for L in nf.lines:
            if L.uid == line_uid:
                L.visible = visible
                break
        self._render_current()

    def _on_nf_guide_line_selected(self, nf_uid: str, line_uid: str):
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        if hasattr(self, "right_panel"):
            self.right_panel.show_nf_line(nf, line_uid)

    def _on_nf_layer_visibility_changed(self, nf_uid: str, visible: bool):
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        nf.visible = bool(visible)
        self._render_current()

    def _on_nf_per_offset_visibility_changed(
        self, nf_uid: str, offset_index: int, visible: bool
    ):
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        if 0 <= int(offset_index) < len(nf.per_offset):
            nf.per_offset[int(offset_index)].scatter_visible = bool(visible)
            self._render_current()

    def _on_nf_zone_visibility_changed(
        self, nf_uid: str, kind: str, zone_uid: str, visible: bool
    ):
        """Toggle a single NFZoneBand / NFZoneArrow visible flag."""
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        target = None
        if str(kind) == "band":
            for zb in getattr(nf, "zone_bands", None) or []:
                if zb.uid == zone_uid:
                    target = zb
                    break
        elif str(kind) == "arrow":
            for za in getattr(nf, "zone_arrows", None) or []:
                if za.uid == zone_uid:
                    target = za
                    break
        if target is None:
            return
        target.visible = bool(visible)
        self._render_current()

    def _on_nf_zone_selected(
        self, nf_uid: str, kind: str, zone_uid: str
    ):
        """Surface the zone in the right-side settings panel if any."""
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        if not hasattr(self, "right_panel"):
            return
        # Right panel may not implement zone editing yet — prefer a
        # dedicated hook, fall back to the generic NFAnalysis editor.
        show_zone = getattr(self.right_panel, "show_nf_zone", None)
        if callable(show_zone):
            try:
                show_zone(
                    nf, str(kind), str(zone_uid),
                    zone_spec=getattr(sheet, "nacd_zone_spec", None),
                )
                return
            except TypeError:
                # Older right_panel.show_nf_zone signature (no kwargs).
                try:
                    show_zone(nf, str(kind), str(zone_uid))
                    return
                except Exception:
                    pass
            except Exception:
                pass
        show_nf = getattr(self.right_panel, "show_nf_analysis", None)
        if callable(show_nf):
            try:
                show_nf(nf)
            except Exception:
                pass

    def _on_nf_per_offset_selected(self, nf_uid: str, offset_index: int):
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        if hasattr(self, "right_panel"):
            self.right_panel.show_nf_per_offset(nf, int(offset_index))

    def _on_nf_zone_style_changed(
        self, nf_uid: str, kind: str, zone_uid: str, attr: str, value
    ):
        """Mutate a single NFZoneBand / NFZoneArrow attribute by uid.

        For bands, NACD-domain attributes (``point_color``,
        ``band_color``, ``band_alpha``, ``label``) are mirrored to
        the twin-axis band (same ``group_index`` + ``zone_index``)
        because those properties are x-axis-agnostic — editing the
        λ-band must also retint the f-band and vice versa.  Without
        this mirror the renderer's merge step would see two bands
        carrying stale-vs-fresh colours and silently pick the wrong
        one depending on iteration order.
        """
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        target = None
        if str(kind) == "band":
            for zb in getattr(nf, "zone_bands", None) or []:
                if zb.uid == zone_uid:
                    target = zb
                    break
        else:
            for za in getattr(nf, "zone_arrows", None) or []:
                if za.uid == zone_uid:
                    target = za
                    break
        if target is None or not hasattr(target, attr):
            return
        setattr(target, attr, value)

        # Twin-axis mirror for NACD-domain band attributes.
        _NACD_DOMAIN_ATTRS = {
            "point_color", "band_color", "band_alpha", "label",
        }
        if str(kind) == "band" and attr in _NACD_DOMAIN_ATTRS:
            gi = int(getattr(target, "group_index", 0))
            zi = int(getattr(target, "zone_index", 0))
            own_axis = str(getattr(target, "axis", ""))
            for zb in getattr(nf, "zone_bands", None) or []:
                if (
                    int(getattr(zb, "group_index", -1)) == gi
                    and int(getattr(zb, "zone_index", -1)) == zi
                    and str(getattr(zb, "axis", "")) != own_axis
                    and hasattr(zb, attr)
                ):
                    setattr(zb, attr, value)

        if hasattr(self, "data_tree"):
            try:
                self.data_tree.populate(sheet)
            except Exception:
                pass
        self._render_current()

    def _on_nf_line_style_changed(
        self, nf_uid: str, line_uid: str, attr: str, value
    ):
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        for L in nf.lines:
            if L.uid == line_uid and hasattr(L, attr):
                setattr(L, attr, value)
                break
        if hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        self._render_current()

    def _on_nf_ranges_apply_requested(self, nf_uid: str):
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        from ...core.nf_eval_range import apply_eval_range_to_nf

        er = {}
        if hasattr(self, "right_panel"):
            er = self.right_panel.nf_panel.get_eval_range_dict()
        apply_eval_range_to_nf(nf, er)
        if hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        self._render_current()

    # ── Legend layer ──────────────────────────────────────────────────

    def _on_legend_layer_selected(self, key: str):
        """Open the legend layer panel for a subplot."""
        sheet = self._current_sheet()
        if not sheet or key not in sheet.subplots:
            return
        sp = sheet.subplots[key]
        if hasattr(self, "right_panel"):
            self.right_panel.show_legend_layer(key, sp)

    def _on_legends_selected(self, keys):
        """Open the legend layer panel in batch mode for several subplots."""
        sheet = self._current_sheet()
        if not sheet or not keys:
            return
        valid = [k for k in keys if k in sheet.subplots]
        if not valid:
            return
        if hasattr(self, "right_panel"):
            self.right_panel.show_legends_batch(
                valid, {k: sheet.subplots[k] for k in valid}
            )

    def _on_nacd_analyses_selected(self, uids):
        """Open the NF settings panel in batch mode for several NACD layers.

        Every attribute edit (outline, palette, legend name, overlay,
        show-λ_max, etc.) fans out to each ``nf_uid`` via the existing
        ``nf_setting_changed`` signal so the change lands on every
        selected analysis.
        """
        sheet = self._current_sheet()
        if not sheet or not uids:
            return
        nfs = [sheet.nf_analyses[u] for u in uids if u in sheet.nf_analyses]
        if len(nfs) < 2:
            return
        if hasattr(self, "right_panel"):
            self.right_panel.show_nf_analyses_batch(nfs)

    def _on_nf_guides_selected(self, pairs):
        """Open the NF-line panel in batch mode for several guide lines.

        ``pairs`` is ``list[tuple[nf_uid, line_uid]]`` from the data
        tree. We resolve each pair to the actual :class:`NFLine` and
        hand the triples to the panel so widgets can seed from the
        first line and fan every edit out to all of them.
        """
        sheet = self._current_sheet()
        if not sheet or not pairs:
            return
        triples = []
        for nf_uid, line_uid in pairs:
            nf = sheet.nf_analyses.get(nf_uid)
            if not nf:
                continue
            line = next((L for L in nf.lines if L.uid == line_uid), None)
            if line is None:
                continue
            triples.append((nf_uid, line_uid, line))
        if not triples:
            return
        if hasattr(self, "right_panel"):
            self.right_panel.show_nf_lines_batch(triples)

    def _on_legend_visibility_changed(self, key: str, visible: bool):
        """Toggle ``SubplotLegendConfig.visible`` from the data tree."""
        sheet = self._current_sheet()
        if not sheet or key not in sheet.subplots:
            return
        sp = sheet.subplots[key]
        if getattr(sp, "legend", None) is None:
            return
        sp.legend.visible = bool(visible)
        self._render_current()

    def _on_subplot_legend_changed(self, key: str, attr: str, value):
        """Apply a legend layer attribute change to the model."""
        sheet = self._current_sheet()
        if not sheet or key not in sheet.subplots:
            return
        sp = sheet.subplots[key]
        if getattr(sp, "legend", None) is None or not hasattr(sp.legend, attr):
            return
        setattr(sp.legend, attr, value)
        # Mirror visibility on the data tree without rebuilding everything.
        if attr == "visible" and hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        self._render_current()

    def _on_nf_per_offset_changed(
        self, nf_uid: str, offset_index: int, attr: str, value
    ):
        sheet = self._current_sheet()
        if not sheet or nf_uid not in sheet.nf_analyses:
            return
        nf = sheet.nf_analyses[nf_uid]
        oi = int(offset_index)
        if oi < 0 or oi >= len(nf.per_offset):
            return
        r = nf.per_offset[oi]
        if attr == "scatter_visible":
            r.scatter_visible = bool(value)
        elif attr == "point_hidden":
            import numpy as np

            arr = np.asarray(value, dtype=bool)
            m = np.asarray(r.mask_contaminated, dtype=bool)
            if arr.size != m.size:
                arr = np.zeros(m.size, dtype=bool)
            r.point_hidden = arr
        if hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        self._render_current()
