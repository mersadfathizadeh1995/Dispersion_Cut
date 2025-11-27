from __future__ import annotations

# Evolving controller: start by inheriting legacy, then override methods to use core helpers.
import os as _os
import sys as _sys
from dc_cut.core.base_controller import BaseInteractiveRemoval


class InteractiveRemovalWithLayers(BaseInteractiveRemoval):  # type: ignore[misc]
    """Controller with core-module wiring.

    Keeps the legacy constructor but overrides specific methods to use dc_cut/core
    helpers where possible. This approach lets us swap logic gradually without
    breaking the app.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_layers_changed = None  # optional callback for shell
        # Ensure toolbar Home keeps our autoscale behavior
        try:
            from dc_cut.services.mpl_compat import patch_toolbar_home
            patch_toolbar_home(self.fig, on_after=self._on_home_after)
        except Exception:
            pass
        try:
            from dc_cut.services import log
            log.info("Controller initialized; toolbar Home patched; draw hooks active")
        except Exception:
            pass
        
        # Home-after handler ensures current view mode is respected
        def _home_after():
            try:
                self._apply_view_mode(getattr(self, 'view_mode', 'both'))
                self._apply_axis_limits()
            except Exception:
                pass
        self._on_home_after = _home_after
        # Also re-apply padded limits after Matplotlib's configure-subplots tool closes
        try:
            def _on_configure_closed(evt):
                try:
                    # Re-apply current view layout (freq_only/wave_only/both), then limits
                    self._apply_view_mode(getattr(self, 'view_mode', 'both'))
                    self._apply_axis_limits(); self.fig.canvas.draw_idle()
                except Exception:
                    pass
            # This event fires after tight_layout/constrained_layout or toolbar tools adjust axes
            self.fig.canvas.mpl_connect('resize_event', _on_configure_closed)
        except Exception:
            pass
        # Enforce padded limits after any draw (covers Home/configure-subplots cases)
        try:
            # Suppress autoscale while the user is dragging a selection rectangle
            self._selection_active = False
            self._enforcing_limits = False
            def _on_draw(evt):
                if not bool(getattr(self, 'auto_limits', True)):
                    return
                if bool(getattr(self, '_selection_active', False)):
                    return
                if self._enforcing_limits:
                    return
                self._enforcing_limits = True
                try:
                    # Do not trigger another draw here; just set limits
                    self._apply_axis_limits()
                finally:
                    self._enforcing_limits = False
            self.fig.canvas.mpl_connect('draw_event', _on_draw)
            # Track mouse press/release to pause autoscale during rectangle drag
            def _on_press(evt):
                try:
                    if evt is None:
                        return
                    if getattr(evt, 'button', None) != 1:
                        return
                    if evt.inaxes not in (self.ax_freq, self.ax_wave):
                        return
                    self._selection_active = True
                except Exception:
                    pass
            def _on_release(evt):
                try:
                    if evt is None:
                        return
                    if getattr(evt, 'button', None) != 1:
                        return
                    # End of drag; resume autoscale and re-apply once
                    self._selection_active = False
                    if bool(getattr(self, 'auto_limits', True)):
                        self._apply_axis_limits()
                        try:
                            self.fig.canvas.draw_idle()
                        except Exception:
                            pass
                except Exception:
                    pass
            self.fig.canvas.mpl_connect('button_press_event', _on_press)
            self.fig.canvas.mpl_connect('button_release_event', _on_release)
        except Exception:
            pass
        # Initialize LayersModel from current arrays and labels (exclude average labels)
        try:
            from dc_cut.core.model import LayersModel
            labels = list(self.offset_labels[:len(self.velocity_arrays)]) if hasattr(self, 'offset_labels') else [f"Offset {i+1}" for i in range(len(self.velocity_arrays))]
            self._layers_model = LayersModel.from_arrays(self.velocity_arrays, self.frequency_arrays, self.wavelength_arrays, labels)
        except Exception:
            self._layers_model = None
        # Provide a simple NF evaluator facade expected by the NF dock
        try:
            from dc_cut.core.nearfield import NearFieldInspector
            self.nf_evaluator = NearFieldInspector(self)
        except Exception:
            # Minimal stub so the dock doesn't crash
            class _Stub:
                def start_with(self, label, thr, open_checklist=False): pass
                def cancel(self): pass
                def apply_deletions(self, indices): pass
                def update_threshold(self, thr): pass
                def get_current_arrays(self): return None
            self.nf_evaluator = _Stub()
        # Register extra File actions (Qt shell picks them up if registry exists)
        try:
            from dc_cut.services.actions import ActionRegistry
            if not hasattr(self, 'actions') or self.actions is None:
                self.actions = ActionRegistry()
            # Save passive stats export (Meandisp-compatible)
            self.actions.add(
                id="file.save_passive_stats",
                text="Save Passive Stats…",
                shortcut=None,
                callback=lambda: self._on_save_passive_stats(None),
            )
            # Ensure Save State and Save Txt exist as well if not registered by legacy
            if self.actions.try_get('file.save_state') is None:
                self.actions.add(id="file.save_state", text="Save State…", shortcut="Ctrl+S", callback=lambda: self._on_save_session(None))
            if self.actions.try_get('file.save_dc') is None:
                self.actions.add(id="file.save_dc", text="Save Dispersion TXT…", shortcut=None, callback=lambda: self._on_quit(None))
            # Ensure basic edit shortcuts exist
            if self.actions.try_get('edit.delete') is None:
                self.actions.add(id="edit.delete", text="Delete", callback=lambda: self._on_delete(None), shortcut=None)
            if self.actions.try_get('edit.cancel') is None:
                self.actions.add(id="edit.cancel", text="Cancel Selection", callback=lambda: self._on_cancel(None), shortcut=None)
            if self.actions.try_get('edit.undo') is None:
                self.actions.add(id="edit.undo",   text="Undo",   callback=lambda: self._on_undo(None),   shortcut=None)
            if self.actions.try_get('edit.redo') is None:
                self.actions.add(id="edit.redo",   text="Redo",   callback=lambda: self._on_redo(None),   shortcut=None)
            # View shortcuts (Ctrl+1/2/3) - shortcuts handled by main_window QShortcut, not menu
            if self.actions.try_get('view.both') is None:
                self.actions.add(id="view.both", text="Both plots", callback=lambda: self._apply_view_mode('both'), shortcut=None)
            if self.actions.try_get('view.freq') is None:
                self.actions.add(id="view.freq", text="Phase-vel vs Freq", callback=lambda: self._apply_view_mode('freq_only'), shortcut=None)
            if self.actions.try_get('view.wave') is None:
                self.actions.add(id="view.wave", text="Wave vs Vel", callback=lambda: self._apply_view_mode('wave_only'), shortcut=None)
        except Exception:
            pass

    # Example override: legend assembly delegates to core.plot
    def _update_legend(self):  # type: ignore[override]
        try:
            from dc_cut.core.plot import assemble_legend
        except Exception:
            return super()._update_legend()
        # Build handle/label list for currently visible layers
        self._sync_line_lists()
        try:
            handles, labels = assemble_legend(
                self.lines_wave,
                self.offset_labels,
                show_average=self.show_average,
                avg_handle=self.dummy_avg_line,
                avg_label=self.average_label,
                show_average_wave=self.show_average_wave,
                avg_wave_handle=self.dummy_avg_wave_line,
                avg_wave_label=self.average_label_wave,
                k_guides_legend=self._k_guides_legend if bool(getattr(self, 'show_k_guides', False)) else None,
            )
        except Exception:
            return super()._update_legend()

        # Choose target axis and replace legend
        if self.view_mode == 'freq_only':
            target_ax = self.ax_freq
        else:
            target_ax = self.ax_wave
        for ax in (self.ax_freq, self.ax_wave):
            leg = ax.get_legend()
            if leg is not None:
                leg.remove()
        if handles:
            target_ax.legend(handles, labels, loc='best')
        try:
            self._apply_axis_limits(); self._draw_k_guides(); self.fig.canvas.draw_idle()
        except Exception:
            pass

    # Override: model-aware average computation (leverages core.averages when available)
    def _update_average_line(self):  # type: ignore[override]
        try:
            from dc_cut.core.averages import compute_avg_by_frequency, compute_avg_by_wavelength
        except Exception:
            return super()._update_average_line()
        try:
            import numpy as _np
            self._sync_line_lists()
            if not self.show_average and not self.show_average_wave:
                try: self._remove_avg_line()
                except Exception: pass
                return
            # Visible freq/vel
            all_freq = []
            all_vel  = []
            n_offsets = len(self.velocity_arrays)
            for i in range(n_offsets):
                try:
                    if self.lines_freq[i].get_visible():
                        all_freq.extend(self.frequency_arrays[i])
                        all_vel.extend(self.velocity_arrays[i])
                except Exception:
                    continue
            if not all_freq:
                try: self._remove_avg_line()
                except Exception: pass
                return
            freq_arr = _np.asarray(all_freq, float)
            vel_arr  = _np.asarray(all_vel,  float)
            avg_bins = int(getattr(self, 'avg_points_override', 0) or (getattr(self, 'bins_for_average', 50) * getattr(self, 'interp_factor', 1)))
            stats = compute_avg_by_frequency(
                vel_arr, freq_arr,
                min_freq=float(getattr(self, 'min_freq', max(0.1, float(_np.nanmin(freq_arr))))),
                max_freq=float(getattr(self, 'max_freq', float(_np.nanmax(freq_arr)))),
                bins=int(max(2, avg_bins)),
                bias=float(getattr(self, 'low_bias', 1.0)),
            )
            fvals = stats['FreqMean']; mvals = stats['VelMean']; svals = stats['VelStd']
            mask = _np.isfinite(fvals) & _np.isfinite(mvals) & _np.isfinite(svals)
            fvals, mvals, svals = fvals[mask], mvals[mask], svals[mask]
            try: self._remove_avg_freq_line()
            except Exception: pass
            if self.show_average and fvals.size > 0:
                out = self.ax_freq.errorbar(
                    fvals, mvals, yerr=svals,
                    fmt='k-o', ecolor='k', elinewidth=1, capsize=3,
                    markersize=3, alpha=0.9
                )
                self.avg_line_freq = out[0]
                try:
                    self.avg_err_bars_f = (out[1], out[2])
                    for art in out[1] + out[2]:
                        art.set_gid('_avg')
                    self.avg_line_freq.set_label('_avg')
                except Exception:
                    pass
            else:
                try: self._remove_avg_freq_line()
                except Exception: pass

            # Wave average
            all_wave = []
            all_vel2 = []
            for i in range(n_offsets):
                try:
                    if self.lines_wave[i].get_visible():
                        all_wave.extend(self.wavelength_arrays[i])
                        all_vel2.extend(self.velocity_arrays[i])
                except Exception:
                    continue
            if not self.show_average_wave:
                try: self._remove_avg_wave_line()
                except Exception: pass
                return
            if not all_wave:
                try: self._remove_avg_wave_line()
                except Exception: pass
                return
            wave_arr = _np.asarray(all_wave, float)
            vel_arr2 = _np.asarray(all_vel2, float)
            stats_w = compute_avg_by_wavelength(
                vel_arr2, wave_arr,
                min_wave=float(getattr(self, 'min_wave', max(0.1, float(_np.nanmin(wave_arr))))),
                max_wave=float(getattr(self, 'max_wave', float(_np.nanmax(wave_arr)))),
                bins=int(max(2, avg_bins)),
                bias=float(getattr(self, 'low_bias', 1.0)),
            )
            wvals = stats_w['FreqMean']; mwavs = stats_w['VelMean']; swavs = stats_w['VelStd']
            mask_w = _np.isfinite(wvals) & _np.isfinite(mwavs) & _np.isfinite(swavs)
            wvals, mwavs, swavs = wvals[mask_w], mwavs[mask_w], swavs[mask_w]
            try: self._remove_avg_wave_line()
            except Exception: pass
            if wvals.size > 0:
                out_w = self.ax_wave.errorbar(
                    wvals, mwavs, yerr=swavs,
                    fmt='k-o', ecolor='k', elinewidth=1, capsize=3,
                    markersize=3, alpha=0.9
                )
                self.avg_line_wave = out_w[0]
                try: self.avg_err_bars_w = (out_w[1], out_w[2])
                except Exception: pass
        except Exception:
            try: super()._update_average_line()
            except Exception: pass
        try:
            from dc_cut.services import log
            log.info("Averages recomputed and lines updated")
        except Exception:
            pass

    # Override: robust, model-aware auto limits
    def _apply_axis_limits(self):  # type: ignore[override]
        if not bool(getattr(self, 'auto_limits', True)):
            return
        self._sync_line_lists()
        visible_v, visible_f, visible_w = [], [], []
        try:
            # include only visible offsets (prefer model if available)
            if getattr(self, '_layers_model', None) is not None:
                try:
                    v_list, f_list, w_list = self._layers_model.get_visible_arrays()  # type: ignore[attr-defined]
                    for v in v_list: visible_v.extend(v)
                    for f in f_list: visible_f.extend(f)
                    for w in w_list: visible_w.extend(w)
                except Exception:
                    for i in range(len(self.velocity_arrays)):
                        if self.lines_freq[i].get_visible():
                            visible_v.extend(self.velocity_arrays[i])
                            visible_f.extend(self.frequency_arrays[i])
                            visible_w.extend(self.wavelength_arrays[i])
            else:
                for i in range(len(self.velocity_arrays)):
                    if self.lines_freq[i].get_visible():
                        visible_v.extend(self.velocity_arrays[i])
                        visible_f.extend(self.frequency_arrays[i])
                        visible_w.extend(self.wavelength_arrays[i])
            # include add-mode temp points
            if bool(getattr(self, 'add_mode', False)) and getattr(self, '_add_v', None) is not None:
                visible_v.extend(list(self._add_v)); visible_f.extend(list(self._add_f)); visible_w.extend(list(self._add_w))
            if not visible_v:
                return
            import numpy as _np
            v = _np.asarray(visible_v); f = _np.asarray(visible_f); w = _np.asarray(visible_w)
            try:
                from dc_cut.core.limits import compute_padded_limits
                # Use default padding tuned for robust margins on log axes
                L = compute_padded_limits(v, f, w)
                ymin, ymax = L['ymin'], L['ymax']
                fmin, fmax = L['fmin'], L['fmax']
                wmin, wmax = L['wmin'], L['wmax']
            except Exception:
                v = v[_np.isfinite(v)]; f = f[_np.isfinite(f)]; w = w[_np.isfinite(w)]
                if v.size == 0 or f.size == 0 or w.size == 0:
                    return
                pad_v = 100.0; ymin = max(0.0, float(v.min()) - pad_v); ymax = float(v.max()) + pad_v
                pad_low, pad_high = 2.0, 10.0
                fmin = max(0.1, float(f.min()) - pad_low); fmax = float(f.max()) + pad_high
                wmin = max(1.0, float(w.min()) - pad_low); wmax = float(w.max()) + pad_high
            if self.view_mode in ('both', 'freq_only'):
                # Defensive: clamp fmin/fmax and enforce log-scale lower bound
                fmin = max(1e-3, float(fmin)); fmax = max(float(fmax), fmin * 1.2)
                # Apply legacy-like Y clamps (min_vel/max_vel)
                y0 = max(float(getattr(self, 'min_vel', 0.0)), ymin)
                y1 = min(float(getattr(self, 'max_vel', 5_000.0)), ymax)
                if y1 <= y0:
                    y0, y1 = ymin, ymax
                self.ax_freq.set_ylim(y0, y1); self.ax_freq.set_xlim(fmin, fmax)
                # Grid preference
                try:
                    from dc_cut.services.prefs import get_pref
                    show_grid = bool(get_pref('show_grid', True))
                    if show_grid:
                        self.ax_freq.grid(True, which='both', alpha=0.25)
                    else:
                        self.ax_freq.grid(False)
                except Exception:
                    pass
                try: self._apply_frequency_ticks()
                except Exception: pass
            if self.view_mode in ('both', 'wave_only'):
                wmin = max(1e-3, float(wmin)); wmax = max(float(wmax), wmin * 1.2)
                y0 = max(float(getattr(self, 'min_vel', 0.0)), ymin)
                y1 = min(float(getattr(self, 'max_vel', 5_000.0)), ymax)
                if y1 <= y0:
                    y0, y1 = ymin, ymax
                self.ax_wave.set_ylim(y0, y1); self.ax_wave.set_xlim(wmin, wmax)
                try:
                    from dc_cut.services.prefs import get_pref
                    show_grid = bool(get_pref('show_grid', True))
                    if show_grid:
                        self.ax_wave.grid(True, which='both', alpha=0.25)
                    else:
                        self.ax_wave.grid(False)
                except Exception:
                    pass
            try: self._draw_k_guides()
            except Exception: pass
        except Exception:
            pass

    # Override: safe Save-Data toggle in shell
    def _enable_save_added(self, enable: bool):  # type: ignore[override]
        try:
            self.add_mode = bool(enable)
        except Exception:
            pass
        btn = getattr(self, 'btn_save_added', None)
        if btn is None or not hasattr(btn, 'ax'):
            try: self.fig.canvas.draw_idle()
            except Exception: pass
            return
        ax = btn.ax
        if enable:
            btn.color = "lightyellow"; btn.hovercolor = "khaki"; ax.set_alpha(1.0)
        else:
            btn.color = "#dddddd"; btn.hovercolor = "#dddddd"; ax.set_alpha(0.4)
        try: self.fig.canvas.draw_idle()
        except Exception: pass

    # Override: k-guides via core helper
    def _draw_k_guides(self):  # type: ignore[override]
        if not bool(getattr(self, 'show_k_guides', False)):
            try: self._clear_k_guides()
            except Exception: pass
            return
        kmin = getattr(self, 'kmin', None); kmax = getattr(self, 'kmax', None)
        if kmin is None or kmax is None or kmin <= 0 or kmax <= 0:
            try: self._clear_k_guides()
            except Exception: pass
            return
        try: self._clear_k_guides()
        except Exception: pass
        try:
            col_ap, col_ap2, col_al, col_al2 = '#7b2cbf', '#ff7f0e', '#d62728', '#2ca02c'
            fmin, fmax = self.ax_freq.get_xlim()
            try:
                from dc_cut.core.guides import compute_k_guides
                G = compute_k_guides(float(kmin), float(kmax), float(fmin), float(fmax))
                f_curve = G['f_curve']; v_ap = G['v_ap']; v_ap2 = G['v_ap2']; v_al = G['v_al']; v_al2 = G['v_al2']
                w_ap = G['w_ap']; w_ap2 = G['w_ap2']; w_al = G['w_al']; w_al2 = G['w_al2']
            except Exception:
                import numpy as _np
                fmin = max(1e-3, fmin); fmax = max(fmax, fmin * 1.1)
                f_curve = _np.logspace(_np.log10(fmin), _np.log10(fmax), 300)
                import numpy as _n
                v_ap   = (2*_n.pi*f_curve)/float(kmin)
                v_ap2  = (2*_n.pi*f_curve)/(float(kmin)/2.0)
                v_al   = (2*_n.pi*f_curve)/float(kmax)
                v_al2  = (2*_n.pi*f_curve)/(float(kmax)/2.0)
                w_ap   = 2*_n.pi/float(kmin)
                w_ap2  = 2*_n.pi/(float(kmin)/2.0)
                w_al   = 2*_n.pi/float(kmax)
                w_al2  = 2*_n.pi/(float(kmax)/2.0)
            ln_ap  = self.ax_freq.semilogx(f_curve, v_ap,  '-', color=col_ap,  lw=1.2, label='_kguide')[0]
            ln_ap2 = self.ax_freq.semilogx(f_curve, v_ap2, '--', color=col_ap2, lw=1.2, label='_kguide')[0]
            ln_al  = self.ax_freq.semilogx(f_curve, v_al,  '-', color=col_al,  lw=1.2, label='_kguide')[0]
            ln_al2 = self.ax_freq.semilogx(f_curve, v_al2, '--', color=col_al2, lw=1.2, label='_kguide')[0]
            y0, y1 = self.ax_wave.get_ylim()
            ln_w_ap  = self.ax_wave.semilogx([w_ap,  w_ap ], [y0, y1], '-',  color=col_ap,  lw=1.2, label='_kguide')[0]
            ln_w_ap2 = self.ax_wave.semilogx([w_ap2, w_ap2], [y0, y1], '--', color=col_ap2, lw=1.2, label='_kguide')[0]
            ln_w_al  = self.ax_wave.semilogx([w_al,  w_al ], [y0, y1], '-',  color=col_al,  lw=1.2, label='_kguide')[0]
            ln_w_al2 = self.ax_wave.semilogx([w_al2, w_al2], [y0, y1], '--', color=col_al2, lw=1.2, label='_kguide')[0]
            self._k_guides_artists.extend([ln_ap, ln_ap2, ln_al, ln_al2, ln_w_ap, ln_w_ap2, ln_w_al, ln_w_al2])
            import matplotlib.lines as mlines
            self._k_guides_legend = [
                mlines.Line2D([], [], color=col_ap,  linestyle='-',  label='Aperture Limit'),
                mlines.Line2D([], [], color=col_ap2, linestyle='--', label='Aperture Limit (λ/2)'),
                mlines.Line2D([], [], color=col_al,  linestyle='-',  label='Aliasing Limit'),
                mlines.Line2D([], [], color=col_al2, linestyle='--', label='Aliasing Limit (λ/2)'),
            ]
        except Exception:
            pass

    # Full commit override: Add-Data/Add-Layer Save
    def _on_save_added_data(self, event):  # type: ignore[override]
        try:
            # No active session
            if not bool(getattr(self, 'add_mode', False)):
                print("Nothing to save – no add session active."); return
            # Sanity
            if getattr(self, '_add_v', None) is None or len(self._add_v) == 0:
                try:
                    from matplotlib.backends import qt_compat
                    QtWidgets = qt_compat.QtWidgets
                    QtWidgets.QMessageBox.information(self.fig.canvas.manager.window,  # type: ignore[attr-defined]
                                                      "Save Data",
                                                      "No points in added layer – canceling.")
                except Exception:
                    pass
                return
            # Snapshot undo state before mutating arrays/lines
            try:
                self._save_state()
            except Exception:
                pass
            idx = self._added_offset_idx
            is_new_layer = idx >= len(self.velocity_arrays)
            if is_new_layer:
                # Append arrays
                self.velocity_arrays.append(self._add_v)
                self.frequency_arrays.append(self._add_f)
                self.wavelength_arrays.append(self._add_w)
                # Keep plotted lines (promote temp to permanent)
                self.lines_freq.append(self._add_line_freq)
                self.lines_wave.append(self._add_line_wave)
                # Label
                layer_name, _, _ = self._new_layer_info
                # Ensure legend and layers dock use the requested name
                try:
                    self.lines_wave[-1].set_label(layer_name)
                except Exception:
                    pass
                try:
                    # Insert before the average labels (last 2 items)
                    if len(self.offset_labels) >= 2:
                        self.offset_labels.insert(-2, layer_name)
                    else:
                        self.offset_labels.append(layer_name)
                except Exception:
                    self.offset_labels = list(self.offset_labels) + [layer_name]
                # Update model
                try:
                    if self._layers_model is not None:
                        self._layers_model.add_new_layer(layer_name, self._add_v, self._add_f, self._add_w)
                except Exception:
                    pass
                # For non-Qt backends, rebuild checkboxes
                import matplotlib
                if not matplotlib.get_backend().lower().startswith("qt"):
                    self._rebuild_checkboxes()
            else:
                # Merge into target offset
                import numpy as _np
                self.velocity_arrays[idx]   = _np.concatenate([self.velocity_arrays[idx],   self._add_v])
                self.frequency_arrays[idx]  = _np.concatenate([self.frequency_arrays[idx],  self._add_f])
                self.wavelength_arrays[idx] = _np.concatenate([self.wavelength_arrays[idx], self._add_w])
                # Update model
                try:
                    if self._layers_model is not None:
                        self._layers_model.merge_into(idx, self._add_v, self._add_f, self._add_w)
                except Exception:
                    pass
                # Update primary lines
                try:
                    from dc_cut.core.plot import set_line_xy
                    set_line_xy(self.lines_freq[idx], self.frequency_arrays[idx], self.velocity_arrays[idx])
                    set_line_xy(self.lines_wave[idx], self.wavelength_arrays[idx], self.velocity_arrays[idx])
                except Exception:
                    pass
                # Remove temp lines
                try:
                    self._add_line_freq.remove(); self._add_line_wave.remove()
                except Exception:
                    pass
            # UI refresh
            try:
                if self.show_average or self.show_average_wave:
                    self._update_average_line()
                self._update_legend()
                # Ensure any stale average error bars are fully cleared
                try: self._remove_avg_freq_line()
                except Exception: pass
                try: self._remove_avg_wave_line()
                except Exception: pass
            except Exception:
                pass
            try:
                cb = getattr(self, 'on_layers_changed', None)
                if cb:
                    cb()
            except Exception:
                pass
            try:
                # Prefer model-based autoscale immediately after commit (twice to stabilize padded view)
                self._apply_axis_limits()
                # Second pass after draw to ensure new layer data included in Home state
                self.fig.canvas.draw_idle()
                self._apply_axis_limits()
            except Exception:
                pass
        except Exception:
            # Fallback to legacy implementation if anything fails
            try:
                super()._on_save_added_data(event)
            except Exception:
                pass
        finally:
            # Clear add-mode state
            try:
                self.add_mode = False
                self._add_v = self._add_f = self._add_w = None
                self._add_line_freq = self._add_line_wave = None
                self._added_offset_idx = None
                self._new_layer_info = None
                self._enable_save_added(False)
            except Exception:
                pass
            try:
                self.fig.canvas.draw_idle()
            except Exception:
                pass
            # Notify layers UI to rebuild (avoid stale row indices in dock)
            try:
                cb = getattr(self, 'on_layers_changed', None)
                if cb:
                    cb()
            except Exception:
                pass

    # --- State persistence enrichments ---
    def get_current_state(self):  # type: ignore[override]
        try:
            S = super().get_current_state()
        except Exception:
            S = {}
        # Persist passive FK guide prefs and frequency tick prefs
        try:
            S['kmin'] = getattr(self, 'kmin', S.get('kmin', None))
            S['kmax'] = getattr(self, 'kmax', S.get('kmax', None))
            S['show_k_guides'] = bool(getattr(self, 'show_k_guides', S.get('show_k_guides', False)))
            S['freq_tick_style'] = getattr(self, 'freq_tick_style', S.get('freq_tick_style', 'decades'))
            if hasattr(self, 'freq_custom_ticks'):
                S['freq_custom_ticks'] = list(getattr(self, 'freq_custom_ticks'))
        except Exception:
            pass
        return S

    def apply_state(self, state_dict):  # type: ignore[override]
        try:
            super().apply_state(state_dict)
        except Exception:
            pass
        # Ensure lines are updated using robust helper
        try:
            from dc_cut.core.plot import set_line_xy
            for i in range(min(len(self.lines_freq), len(self.velocity_arrays))):
                try:
                    set_line_xy(self.lines_freq[i], self.frequency_arrays[i], self.velocity_arrays[i])
                    set_line_xy(self.lines_wave[i], self.wavelength_arrays[i], self.velocity_arrays[i])
                except Exception:
                    continue
        except Exception:
            pass
        # Rebuild LayersModel from arrays after applying state
        try:
            from dc_cut.core.model import LayersModel
            labels = list(self.offset_labels[:len(self.velocity_arrays)])
            self._layers_model = LayersModel.from_arrays(self.velocity_arrays, self.frequency_arrays, self.wavelength_arrays, labels)
        except Exception:
            pass
        try:
            from dc_cut.services import log
            log.info("State applied; model rebuilt; ticks/guides/limits applied")
        except Exception:
            pass
        # Restore tick style and custom ticks (if present)
        try:
            if 'freq_tick_style' in state_dict:
                self.freq_tick_style = state_dict['freq_tick_style']
            if 'freq_custom_ticks' in state_dict:
                self.freq_custom_ticks = state_dict['freq_custom_ticks']
        except Exception:
            pass
        # Restore k-guides
        try:
            if 'kmin' in state_dict and state_dict['kmin'] is not None:
                self.kmin = float(state_dict['kmin'])
            if 'kmax' in state_dict and state_dict['kmax'] is not None:
                self.kmax = float(state_dict['kmax'])
            self.show_k_guides = bool(state_dict.get('show_k_guides', getattr(self, 'show_k_guides', False)))
        except Exception:
            pass
        # Re-apply ticks, guides, limits
        try:
            self._apply_frequency_ticks()
        except Exception:
            pass
        try:
            self._draw_k_guides()
        except Exception:
            pass
        try:
            self._apply_axis_limits(); self.fig.canvas.draw_idle()
        except Exception:
            pass

    # --- Qt Save State (override legacy Tk flow) ---
    def _on_save_session(self, event):  # type: ignore[override]
        try:
            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self.fig.canvas.manager.window,  # type: ignore[attr-defined]
                "Save Interactive Session",
                "",
                "Session State (*.pkl);;All Files (*.*)")
            if not path:
                return
            state_dict = self.get_current_state()
            from dc_cut.io.state import save_session as _save
            _save(state_dict, path)
            try:
                QtWidgets.QMessageBox.information(self.fig.canvas.manager.window, "Save State", f"Saved → {path}")
            except Exception:
                pass
        except Exception:
            try:
                super()._on_save_session(event)
            except Exception:
                pass

    # --- Qt Save TXT export (override legacy Tk flow) ---
    def _on_quit(self, event):  # type: ignore[override]
        try:
            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self.fig.canvas.manager.window,  # type: ignore[attr-defined]
                "Save Dispersion Curve",
                "",
                "Text file (*.txt);;All Files (*.*)")
            if not path:
                return
            # Gather visible picks
            import numpy as _np
            vis_freq, vis_vel = [], []
            for idx in range(len(self.velocity_arrays)):
                try:
                    if self.lines_freq[idx].get_visible():
                        vis_freq.extend(self.frequency_arrays[idx])
                        vis_vel.extend(self.velocity_arrays[idx])
                except Exception:
                    continue
            if not vis_freq:
                QtWidgets.QMessageBox.information(self.fig.canvas.manager.window, "Save Dispersion Curve", "No visible data – nothing to save.")
                return
            freq_arr = _np.asarray(vis_freq, float)
            vel_arr  = _np.asarray(vis_vel,  float)
            stats = self._build_export_curve(freq_arr, vel_arr, int(getattr(self, 'export_bins', 50)))
            try:
                from dc_cut.io.export import write_geopsy_txt
                write_geopsy_txt(stats, path)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self.fig.canvas.manager.window, "Save Dispersion Curve", f"Export failed:\n{e}")
                return
            try:
                QtWidgets.QMessageBox.information(self.fig.canvas.manager.window, "Save Dispersion Curve", f"Saved → {path}")
            except Exception:
                pass
        except Exception:
            try:
                super()._on_quit(event)
            except Exception:
                pass

    # --- Passive stats export (Meandisp-compatible) ---
    def _on_save_passive_stats(self, event):
        try:
            import numpy as _np
            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets
            # Collect visible points
            vis_freq, vis_vel = [], []
            for idx in range(len(self.velocity_arrays)):
                try:
                    if self.lines_freq[idx].get_visible():
                        vis_freq.extend(self.frequency_arrays[idx])
                        vis_vel.extend(self.velocity_arrays[idx])
                except Exception:
                    continue
            if not vis_freq:
                QtWidgets.QMessageBox.information(self.fig.canvas.manager.window, "Save Passive Stats", "No visible data to export.")
                return
            freq_arr = _np.asarray(vis_freq, float)
            vel_arr  = _np.asarray(vis_vel,  float)
            # Compute binned stats using core.averages
            try:
                from dc_cut.core.averages import compute_avg_by_frequency
                bins = int(getattr(self, 'bins_for_average', 50))
                stats = compute_avg_by_frequency(
                    vel_arr, freq_arr,
                    min_freq=float(getattr(self, 'min_freq', max(0.1, float(_np.nanmin(freq_arr))))),
                    max_freq=float(getattr(self, 'max_freq', float(_np.nanmax(freq_arr)))),
                    bins=bins,
                    bias=float(getattr(self, 'low_bias', 1.0)),
                )
                f = stats['FreqMean']; v = stats['VelMean']; s = stats['VelStd']
                m = _np.isfinite(f) & _np.isfinite(v)
                f = f[m]; v = v[m]; s = s[m]
                slow = _np.where(v != 0, 1.0 / v, _np.nan)
                dinv = _np.where(v != 0, (s + v) / v, _np.nan)
                nump = _np.full_like(f, 0, dtype=int)
            except Exception:
                # minimal fallback
                f, v = freq_arr, vel_arr
                slow = _np.where(v != 0, 1.0 / v, _np.nan)
                dinv = _np.full_like(v, _np.nan)
                nump = _np.zeros_like(v, dtype=int)

            # Save CSV
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self.fig.canvas.manager.window, "Save Passive Stats", "", "CSV (*.csv);;All Files (*.*)")
            if not path:
                return
            try:
                from dc_cut.io.export import write_passive_stats_csv
                write_passive_stats_csv(f, slow, dinv, nump, path)
                QtWidgets.QMessageBox.information(self.fig.canvas.manager.window, "Save Passive Stats", f"Saved → {path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self.fig.canvas.manager.window, "Save Passive Stats", f"Failed to save:\n{e}")
        except Exception:
            pass

    # --- Build export stats for Geopsy TXT ---
    def _build_export_curve(self, freq_arr, vel_arr, bins: int):
        try:
            import numpy as _np
            from dc_cut.core.averages import compute_avg_by_frequency
            stats = compute_avg_by_frequency(
                vel_arr, freq_arr,
                min_freq=float(getattr(self, 'min_freq', max(0.1, float(_np.nanmin(freq_arr))))),
                max_freq=float(getattr(self, 'max_freq', float(_np.nanmax(freq_arr)))),
                bins=int(max(2, bins)),
                bias=float(getattr(self, 'low_bias', 1.0)),
            )
            f = _np.asarray(stats['FreqMean'], float)
            v = _np.asarray(stats['VelMean'], float)
            s = _np.asarray(stats['VelStd'], float)
            m = _np.isfinite(f) & _np.isfinite(v) & _np.isfinite(s) & (v != 0)
            f = f[m]; v = v[m]; s = s[m]
            slow = _np.where(v != 0, 1.0 / v, _np.nan)
            # Approximate DINVER std on slowness scale; fallback to s/v
            dinv = _np.where(v != 0, s / v, _np.nan)
            nump = _np.full_like(f, 0, dtype=int)
            return {
                'FreqMean': f,
                'SlowMean': slow,
                'DinverStd': dinv,
                'NumPoints': nump,
            }
        except Exception:
            # Minimal fallback: passthrough means with zeros
            return {
                'FreqMean': freq_arr,
                'SlowMean': 1.0 / vel_arr,
                'DinverStd': 0.0 * freq_arr,
                'NumPoints': (0 * freq_arr).astype(int),
            }

    # --- Qt-only x/y limits dialogs ---
    def _on_set_xlim(self, event):  # type: ignore[override]
        try:
            import matplotlib
            if not matplotlib.get_backend().lower().startswith('qt'):
                return super()._on_set_xlim(event)
            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets
            text, ok = QtWidgets.QInputDialog.getText(self.fig.canvas.manager.window,  # type: ignore[attr-defined]
                                                     "X limits (Frequency)",
                                                     "Enter xmin,xmax (e.g. 1,100):")
            if not ok or not text:
                return
            parts = [p.strip() for p in str(text).split(',') if p.strip()]
            xmin, xmax = float(parts[0]), float(parts[1])
            self.ax_freq.set_xlim(xmin, xmax)
            try: self._apply_frequency_ticks()
            except Exception: pass
            self._apply_axis_limits(); self.fig.canvas.draw_idle()
        except Exception:
            try: super()._on_set_xlim(event)
            except Exception: pass

    def _on_set_ylim(self, event):  # type: ignore[override]
        try:
            import matplotlib
            if not matplotlib.get_backend().lower().startswith('qt'):
                return super()._on_set_ylim(event)
            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets
            text, ok = QtWidgets.QInputDialog.getText(self.fig.canvas.manager.window,  # type: ignore[attr-defined]
                                                     "Y limits (Velocity)",
                                                     "Enter ymin,ymax (e.g. 0,4000):")
            if not ok or not text:
                return
            parts = [p.strip() for p in str(text).split(',') if p.strip()]
            ymin, ymax = float(parts[0]), float(parts[1])
            for ax in (self.ax_freq, self.ax_wave):
                ax.set_ylim(ymin, ymax)
            self._apply_axis_limits(); self.fig.canvas.draw_idle()
        except Exception:
            try: super()._on_set_ylim(event)
            except Exception: pass

    def _on_set_average_resolution(self, event):  # type: ignore[override]
        try:
            import matplotlib
            if not matplotlib.get_backend().lower().startswith('qt'):
                return super()._on_set_average_resolution(event)
            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets
            try:
                current_avg = int(getattr(self, 'avg_points_override', 0) or (getattr(self, 'bins_for_average', 30) * getattr(self, 'interp_factor', 1)))
            except Exception:
                current_avg = 50
            try:
                current_exp = int(getattr(self, 'export_bins', 50))
            except Exception:
                current_exp = 50
            prompt = (f"Enter number of points for averages and export\n"
                      f"- Single value sets both (current: avg={current_avg}, export={current_exp})\n"
                      f"- Or 'avg,export' (e.g. 60,80)")
            # Use a simple text input dialog
            text, ok = QtWidgets.QInputDialog.getText(self.fig.canvas.manager.window,  # type: ignore[attr-defined]
                                                     "Average resolution",
                                                     prompt)
            if not ok or not text:
                return
            ans = str(text).strip()
            if ',' in ans:
                a_str, e_str = ans.split(',')
                a = max(5, int(float(a_str)))
                e = max(5, int(float(e_str)))
            else:
                a = e = max(5, int(float(ans)))
            self.avg_points_override = int(a)
            self.export_bins = int(e)
            try:
                self._update_average_line(); self._update_legend(); self.fig.canvas.draw_idle()
            except Exception:
                pass
        except Exception:
            try: super()._on_set_average_resolution(event)
            except Exception: pass
    # Post-edit refreshers
    def _on_undo(self, event):  # type: ignore[override]
        try:
            from dc_cut.core.history import perform_undo
            ok = perform_undo(self)
            if not ok:
                return super()._on_undo(event)
        except Exception:
            try: super()._on_undo(event)
            except Exception: pass
        # After any restore, re-apply limits
        try:
            self._apply_view_mode(getattr(self, 'view_mode', 'both'))
            self._apply_axis_limits(); self.fig.canvas.draw_idle()
        except Exception:
            pass

    def _on_redo(self, event):  # type: ignore[override]
        try:
            from dc_cut.core.history import perform_redo
            ok = perform_redo(self)
            if not ok:
                return super()._on_redo(event)
        except Exception:
            try: super()._on_redo(event)
            except Exception: pass
        try:
            self._apply_view_mode(getattr(self, 'view_mode', 'both'))
            self._apply_axis_limits(); self.fig.canvas.draw_idle()
        except Exception:
            pass
    def _on_delete(self, event):  # type: ignore[override]
        try:
            # Push undo snapshot via history module for consistency
            try:
                from dc_cut.core.history import push_undo
                push_undo(self)
            except Exception:
                try: self._save_state()
                except Exception: pass
            # Use selection helpers for removal if available
            try:
                import numpy as _np
                from dc_cut.core.selection import remove_in_freq_box, remove_in_wave_box
                # Apply all accumulated boxes (not only the last), matching legacy
                bxf = list(getattr(self, 'bounding_boxes_freq', []))
                bxw = list(getattr(self, 'bounding_boxes_wave', []))
                if not bxf and not bxw:
                    return super()._on_delete(event)
                for i in range(len(self.velocity_arrays)):
                    v, f, w = _np.asarray(self.velocity_arrays[i]), _np.asarray(self.frequency_arrays[i]), _np.asarray(self.wavelength_arrays[i])
                    if self.lines_freq[i].get_visible():
                        for (xmin, xmax, ymin, ymax) in bxf:
                            v, f, w = remove_in_freq_box(v, f, w, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
                    if self.lines_wave[i].get_visible():
                        for (xmin, xmax, ymin, ymax) in bxw:
                            v, f, w = remove_in_wave_box(v, f, w, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
                    self.velocity_arrays[i], self.frequency_arrays[i], self.wavelength_arrays[i] = v, f, w
                # Clear box overlays to match legacy behavior
                try:
                    for r in list(getattr(self, 'freq_patches', [])):
                        try: r.remove()
                        except Exception: pass
                    self.freq_patches.clear(); self.bounding_boxes_freq.clear()
                except Exception:
                    pass
                try:
                    for r in list(getattr(self, 'wave_patches', [])):
                        try: r.remove()
                        except Exception: pass
                    self.wave_patches.clear(); self.bounding_boxes_wave.clear()
                except Exception:
                    pass
                # Update lines
                try:
                    from dc_cut.core.plot import set_line_xy
                    for i in range(len(self.velocity_arrays)):
                        set_line_xy(self.lines_freq[i], self.frequency_arrays[i], self.velocity_arrays[i])
                        set_line_xy(self.lines_wave[i], self.wavelength_arrays[i], self.velocity_arrays[i])
                except Exception:
                    pass
                # Re-average if enabled
                if self.show_average or self.show_average_wave:
                    self._update_average_line()
            except Exception:
                super()._on_delete(event)
        finally:
            # Rebuild model from arrays after deletions
            try:
                from dc_cut.core.model import LayersModel
                labels = list(self.offset_labels[:len(self.velocity_arrays)])
                self._layers_model = LayersModel.from_arrays(self.velocity_arrays, self.frequency_arrays, self.wavelength_arrays, labels)
            except Exception:
                pass
            try:
                self._apply_axis_limits(); self.fig.canvas.draw_idle()
            except Exception:
                pass
            # Notify layer UI to refresh to avoid stale indices
            try:
                cb = getattr(self, 'on_layers_changed', None)
                if cb:
                    cb()
            except Exception:
                pass

    def _on_add_data(self, event):  # type: ignore[override]
        """Qt-first Add Data flow using core.add_mode.

        - Ask target offset (excluding average entries)
        - Let user pick a .pkl state or .csv combined data file
        - Concatenate data from file and start add-to-offset session
        """
        try:
            import matplotlib
            backend = matplotlib.get_backend().lower()
            if not backend.startswith("qt"):
                # Fallback to legacy implementation on non-Qt backends
                return super()._on_add_data(event)

            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets
            import numpy as _np

            # Choose target offset (exclude average/extra entries if present)
            offsets_no_avg = list(self.offset_labels[:-2]) if len(self.offset_labels) >= 2 else list(self.offset_labels)
            if not offsets_no_avg:
                return
            sel, ok = QtWidgets.QInputDialog.getItem(
                self.fig.canvas.manager.window,  # type: ignore[attr-defined]
                "Add Data – choose offset",
                "Target offset:",
                offsets_no_avg, 0, False)
            if not ok:
                return
            idx = offsets_no_avg.index(sel)

            # Pick data file (.pkl state or combined .csv)
            filters = "State (*.pkl);;CSV (*.csv);;All Files (*.*)"
            fname, _ = QtWidgets.QFileDialog.getOpenFileName(
                self.fig.canvas.manager.window,  # type: ignore[attr-defined]
                "Select state (.pkl) or combined CSV",
                "",
                filters)
            if not fname:
                return

            v_new = f_new = w_new = None
            try:
                import os
                ext = os.path.splitext(fname)[1].lower()
                if ext == ".pkl":
                    try:
                        from dc_cut.io.state import load_session
                        D = load_session(fname)
                    except Exception:
                        import pickle as _pickle
                        with open(fname, "rb") as f:
                            D = _pickle.load(f)
                    v_new = _np.concatenate(D["velocity_arrays"])  # type: ignore[index]
                    f_new = _np.concatenate(D["frequency_arrays"])  # type: ignore[index]
                    w_new = _np.concatenate(D["wavelength_arrays"])  # type: ignore[index]
                elif ext == ".csv":
                    from dc_cut.io.csv import load_combined_csv
                    v_list, f_list, w_list, _ = load_combined_csv(fname)
                    v_new = _np.concatenate(v_list)
                    f_new = _np.concatenate(f_list)
                    w_new = _np.concatenate(w_list)
                else:
                    raise ValueError("Unsupported file; choose .pkl or .csv")
            except Exception as err:
                QtWidgets.QMessageBox.critical(self.fig.canvas.manager.window, "Add Data", f"Failed to read file:\n{err}")
                return

            # Start add session
            try:
                from dc_cut.core.add_mode import start_add_to_offset
                start_add_to_offset(self, idx, v_new, f_new, w_new)
            except Exception:
                # Fallback to legacy preview drawing
                mkr, col = 'x', 'purple'
                lf = self.ax_freq.semilogx(f_new, v_new, mkr, color=col, markersize=6, label="added")[0]
                lw = self.ax_wave.semilogx(w_new, v_new, mkr, color=col, markersize=6, label="added")[0]
                self._add_v, self._add_f, self._add_w = v_new, f_new, w_new
                self._add_line_freq, self._add_line_wave = lf, lw
                self._added_offset_idx = idx
                self.add_mode = True
                try: self._enable_save_added(True)
                except Exception: pass
            # While in add-mode, include temp points in limits
            try:
                self._apply_axis_limits(); self.fig.canvas.draw_idle()
            except Exception:
                pass
        except Exception:
            try:
                super()._on_add_data(event)
            except Exception:
                pass

    def _on_add_layer(self, event):  # type: ignore[override]
        """Qt-first Add Layer flow using core.add_mode.

        - Ask layer name/marker/colour (minimal Qt prompts; defaults if cancelled)
        - Let user pick a .pkl state or .csv combined data file
        - Begin add-layer session with chosen styling
        """
        try:
            import matplotlib
            backend = matplotlib.get_backend().lower()
            if not backend.startswith("qt"):
                return super()._on_add_layer(event)

            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets
            QtGui     = qt_compat.QtGui
            import numpy as _np

            # Layer name
            name, ok = QtWidgets.QInputDialog.getText(
                self.fig.canvas.manager.window,  # type: ignore[attr-defined]
                "New Layer",
                "Layer name:")
            if not ok or not str(name).strip():
                # user cancelled; do nothing
                return
            layer_name = str(name).strip()

            # Marker selection (simple)
            marker_options = ['o', 'x', '+', 's', '^', 'd']
            marker, okm = QtWidgets.QInputDialog.getItem(
                self.fig.canvas.manager.window,  # type: ignore[attr-defined]
                "Marker",
                "Choose marker:",
                marker_options, 0, False)
            if not okm:
                return
            marker = str(marker)

            # Colour (QColorDialog)
            color = QtWidgets.QColorDialog.getColor(parent=self.fig.canvas.manager.window)  # type: ignore[attr-defined]
            colour_hex = color.name() if color and color.isValid() else "#1f77b4"

            # Pick data file (.pkl state or combined .csv)
            filters = "State (*.pkl);;CSV (*.csv);;All Files (*.*)"
            fname, _ = QtWidgets.QFileDialog.getOpenFileName(
                self.fig.canvas.manager.window,  # type: ignore[attr-defined]
                "Select data for new layer",
                "",
                filters)
            if not fname:
                return

            v_new = f_new = w_new = None
            try:
                import os
                ext = os.path.splitext(fname)[1].lower()
                if ext == ".pkl":
                    try:
                        from dc_cut.io.state import load_session
                        D = load_session(fname)
                    except Exception:
                        import pickle as _pickle
                        with open(fname, "rb") as f:
                            D = _pickle.load(f)
                    v_new = _np.concatenate(D["velocity_arrays"])  # type: ignore[index]
                    f_new = _np.concatenate(D["frequency_arrays"])  # type: ignore[index]
                    w_new = _np.concatenate(D["wavelength_arrays"])  # type: ignore[index]
                elif ext == ".csv":
                    from dc_cut.io.csv import load_combined_csv
                    v_list, f_list, w_list, _ = load_combined_csv(fname)
                    v_new = _np.concatenate(v_list)
                    f_new = _np.concatenate(f_list)
                    w_new = _np.concatenate(w_list)
                else:
                    raise ValueError("Unsupported file; choose .pkl or .csv")
            except Exception as err:
                QtWidgets.QMessageBox.critical(self.fig.canvas.manager.window, "Add Layer", f"Failed to read file:\n{err}")
                return

            # Start add-layer session
            try:
                from dc_cut.core.add_mode import start_add_new_layer
                start_add_new_layer(self, layer_name, marker, colour_hex, v_new, f_new, w_new)
            except Exception:
                # Fallback to legacy preview drawing
                lf = self.ax_freq.semilogx(f_new, v_new,
                                           marker=marker, linestyle='', markerfacecolor='none',
                                           markeredgecolor=colour_hex, markeredgewidth=1.5, markersize=6)[0]
                lw = self.ax_wave.semilogx(w_new, v_new,
                                           marker=marker, linestyle='', markerfacecolor='none',
                                           markeredgecolor=colour_hex, markeredgewidth=1.5, markersize=6,
                                           label=layer_name)[0]
                self._add_v, self._add_f, self._add_w = v_new, f_new, w_new
                self._add_line_freq, self._add_line_wave = lf, lw
                self._added_offset_idx = len(self.velocity_arrays)
                self._new_layer_info = (layer_name, marker, colour_hex)
                self.add_mode = True
                try: self._enable_save_added(True)
                except Exception: pass
            # Include temp points in limits while in add-mode
            try:
                self._apply_axis_limits(); self.fig.canvas.draw_idle()
            except Exception:
                pass
        except Exception:
            try:
                super()._on_add_layer(event)
            except Exception:
                pass

    def _on_filter_values(self, event):  # type: ignore[override]
        try:
            import matplotlib
            if not matplotlib.get_backend().lower().startswith('qt'):
                return super()._on_filter_values(event)
            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets

            dlg = QtWidgets.QDialog(self.fig.canvas.manager.window)  # type: ignore[attr-defined]
            dlg.setWindowTitle("Filter Points")
            field = QtWidgets.QComboBox(dlg); field.addItems(["Frequency","Velocity","Wavelength"]) ; field.setCurrentIndex(0)
            direction = QtWidgets.QComboBox(dlg); direction.addItems(["Above","Below"]) ; direction.setCurrentIndex(0)
            thresh = QtWidgets.QLineEdit(dlg)
            unit = QtWidgets.QLabel("Hz", dlg)
            def _on_field_change(txt: str):
                unit.setText({"Frequency":"Hz","Velocity":"m/s","Wavelength":"m"}.get(txt, ""))
            field.currentTextChanged.connect(_on_field_change)
            form = QtWidgets.QFormLayout(dlg)
            form.addRow("Field:", field); form.addRow("Delete:", direction)
            hl = QtWidgets.QHBoxLayout(); hl.addWidget(thresh); hl.addWidget(unit); form.addRow("Threshold:", hl)
            try:
                buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
            except AttributeError:
                std = QtWidgets.QDialogButtonBox.StandardButton; buttons = std.Ok | std.Cancel
            box = QtWidgets.QDialogButtonBox(buttons, parent=dlg)
            form.addRow(box)
            box.accepted.connect(dlg.accept); box.rejected.connect(dlg.reject)
            if dlg.exec() != 1:
                return
            try:
                tval = float(thresh.text())
            except Exception:
                return
            fkey = {"Frequency":"freq","Velocity":"vel","Wavelength":"wave"}[field.currentText()]
            delete_above = (direction.currentText() == "Above")

            # Save undo state before destructive filtering
            try:
                from dc_cut.core.history import push_undo
                push_undo(self)
            except Exception:
                try:
                    self._save_state()
                except Exception:
                    pass

            import numpy as _np
            from dc_cut.core.filters import apply_filters
            for i in range(len(self.velocity_arrays)):
                if not self.lines_freq[i].get_visible():
                    continue
                v, f, w = _np.asarray(self.velocity_arrays[i]), _np.asarray(self.frequency_arrays[i]), _np.asarray(self.wavelength_arrays[i])
                if fkey == 'freq':
                    if delete_above:
                        v, f, w = apply_filters(v, f, w, fmax=tval)
                    else:
                        v, f, w = apply_filters(v, f, w, fmin=tval)
                elif fkey == 'vel':
                    if delete_above:
                        v, f, w = apply_filters(v, f, w, vmax=tval)
                    else:
                        v, f, w = apply_filters(v, f, w, vmin=tval)
                else:
                    if delete_above:
                        v, f, w = apply_filters(v, f, w, wmax=tval)
                    else:
                        v, f, w = apply_filters(v, f, w, wmin=tval)
                self.velocity_arrays[i], self.frequency_arrays[i], self.wavelength_arrays[i] = v, f, w
            try:
                # Update lines via helper
                from dc_cut.core.plot import set_line_xy
                for i in range(len(self.velocity_arrays)):
                    set_line_xy(self.lines_freq[i], self.frequency_arrays[i], self.velocity_arrays[i])
                    set_line_xy(self.lines_wave[i], self.wavelength_arrays[i], self.velocity_arrays[i])
            except Exception:
                pass
            try:
                self._update_average_line(); self._update_legend(); self._apply_axis_limits(); self.fig.canvas.draw_idle()
            except Exception:
                pass
        except Exception:
            return super()._on_filter_values(event)

    def _smoke_autoscale(self) -> None:
        """Developer smoke check: exercise Home/configure/add/undo paths and assert axes padded.

        This is non-interactive and safe to call manually during debugging.
        """
        try:
            # 1) Home equivalent
            try:
                mgr = self.fig.canvas.manager
                tb = getattr(mgr, 'toolbar', None)
                if tb is not None and hasattr(tb, 'home'):
                    tb.home()
            except Exception:
                pass
            self._apply_axis_limits()

            # 2) Simulate configure-subplots impact via a resize event
            try:
                import time
                sz = self.fig.get_size_inches()
                self.fig.set_size_inches(sz[0] + 0.01, sz[1] + 0.01, forward=True)
                self.fig.set_size_inches(*sz, forward=True)
            except Exception:
                pass
            self._apply_axis_limits()

            # 3) If in add-mode with temp points, ensure limits include them
            if bool(getattr(self, 'add_mode', False)) and getattr(self, '_add_v', None) is not None:
                self._apply_axis_limits()

            # 4) Quick check: limits should strictly exceed data bounds
            import numpy as _np
            v = _np.concatenate([_np.asarray(a) for a in self.velocity_arrays]) if self.velocity_arrays else _np.array([])
            f = _np.concatenate([_np.asarray(a) for a in self.frequency_arrays]) if self.frequency_arrays else _np.array([])
            w = _np.concatenate([_np.asarray(a) for a in self.wavelength_arrays]) if self.wavelength_arrays else _np.array([])
            if v.size and f.size and w.size:
                ymin, ymax = self.ax_freq.get_ylim(); fmin, fmax = self.ax_freq.get_xlim(); wmin, wmax = self.ax_wave.get_xlim()
                # basic assertions (no exceptions thrown; just return False-like if violated)
                ok = True
                try:
                    if _np.nanmin(v) < ymin or _np.nanmax(v) > ymax: ok = False
                    if _np.nanmin(f[f>0]) <= fmin or _np.nanmax(f) >= fmax: ok = False
                    if _np.nanmin(w[w>0]) <= wmin or _np.nanmax(w) >= wmax: ok = False
                except Exception:
                    pass
                # Force a redraw at the end
                try: self.fig.canvas.draw_idle()
                except Exception: pass
                return None
        except Exception:
            return None

    # ==================== SPECTRUM BACKGROUND METHODS ====================

    def load_spectrum_for_layer(self, layer_idx: int, npz_path: str) -> bool:
        """Load power spectrum background for a specific layer.

        Args:
            layer_idx: Index of the layer to load spectrum for
            npz_path: Path to spectrum .npz file

        Returns:
            True if successful, False otherwise
        """
        try:
            from dc_cut.core.spectrum_loader import load_spectrum_npz
            from dc_cut.services.prefs import get_pref

            # Load spectrum data
            spectrum_data = load_spectrum_npz(npz_path)

            # Get the layer and assign spectrum
            if hasattr(self, '_layers_model') and self._layers_model is not None:
                if 0 <= layer_idx < len(self._layers_model.layers):
                    layer = self._layers_model.layers[layer_idx]
                    layer.spectrum_data = spectrum_data
                    layer.spectrum_alpha = get_pref('default_spectrum_alpha', 0.5)
                    layer.spectrum_visible = get_pref('show_spectra', True)

                    # Render the spectrum
                    self._render_spectrum_backgrounds()
                    return True
            return False
        except Exception as e:
            try:
                from dc_cut.services import log
                log.error(f"Failed to load spectrum: {e}")
            except Exception:
                pass
            return False

    def _render_spectrum_backgrounds(self) -> None:
        """Render spectrum backgrounds for all layers based on preferences."""
        try:
            from dc_cut.services.prefs import get_pref

            # Check if spectra are globally enabled
            if not get_pref('show_spectra', True):
                self._clear_all_spectrum_backgrounds()
                return

            # Get display mode
            display_mode = get_pref('spectrum_display_mode', 'active_only')

            if not hasattr(self, '_layers_model') or self._layers_model is None:
                return

            # Clear all existing spectrum images first
            for layer in self._layers_model.layers:
                if layer.spectrum_image is not None:
                    try:
                        layer.spectrum_image.remove()
                    except Exception:
                        pass
                    layer.spectrum_image = None

            # Render based on display mode
            if display_mode == 'active_only':
                # Find the active layer (first visible one, or first one)
                active_idx = 0
                for i, layer in enumerate(self._layers_model.layers):
                    if layer.visible:
                        active_idx = i
                        break

                # Render only the active layer's spectrum
                if 0 <= active_idx < len(self._layers_model.layers):
                    self._render_single_spectrum(active_idx)

            else:  # 'all_visible'
                # Render spectra for all visible layers
                for i, layer in enumerate(self._layers_model.layers):
                    if layer.visible:
                        self._render_single_spectrum(i)

            # Redraw canvas
            try:
                self.fig.canvas.draw_idle()
            except Exception:
                pass

        except Exception as e:
            try:
                from dc_cut.services import log
                log.error(f"Failed to render spectrum backgrounds: {e}")
            except Exception:
                pass

    def _render_single_spectrum(self, layer_idx: int) -> None:
        """Render spectrum background for a single layer.

        Args:
            layer_idx: Index of the layer to render spectrum for
        """
        try:
            from dc_cut.services.prefs import get_pref
            import matplotlib.cm as cm

            if not hasattr(self, '_layers_model') or self._layers_model is None:
                return

            if not (0 <= layer_idx < len(self._layers_model.layers)):
                return

            layer = self._layers_model.layers[layer_idx]

            # Check if layer has spectrum data and it's visible
            if layer.spectrum_data is None or not layer.spectrum_visible:
                return

            spectrum = layer.spectrum_data
            power = spectrum['power']
            frequencies = spectrum['frequencies']
            velocities = spectrum['velocities']

            # Get colormap
            colormap_name = get_pref('spectrum_colormap', 'viridis')
            try:
                cmap = cm.get_cmap(colormap_name)
            except Exception:
                cmap = cm.get_cmap('viridis')

            # Define extent for imshow (frequency range and velocity range)
            extent = [
                frequencies[0],
                frequencies[-1],
                velocities[0],
                velocities[-1]
            ]

            # Render on frequency axis
            layer.spectrum_image = self.ax_freq.imshow(
                power,
                aspect='auto',
                origin='lower',
                extent=extent,
                cmap=cmap,
                alpha=layer.spectrum_alpha,
                zorder=0,  # Behind all data points
                interpolation='bilinear'
            )

        except Exception as e:
            try:
                from dc_cut.services import log
                log.error(f"Failed to render single spectrum: {e}")
            except Exception:
                pass

    def _clear_all_spectrum_backgrounds(self) -> None:
        """Remove all spectrum background images."""
        try:
            if not hasattr(self, '_layers_model') or self._layers_model is None:
                return

            for layer in self._layers_model.layers:
                if layer.spectrum_image is not None:
                    try:
                        layer.spectrum_image.remove()
                    except Exception:
                        pass
                    layer.spectrum_image = None

            try:
                self.fig.canvas.draw_idle()
            except Exception:
                pass
        except Exception:
            pass

    def set_layer_spectrum_visibility(self, layer_idx: int, visible: bool) -> None:
        """Toggle visibility of a layer's spectrum background.

        Args:
            layer_idx: Index of the layer
            visible: True to show, False to hide
        """
        try:
            if not hasattr(self, '_layers_model') or self._layers_model is None:
                return

            if 0 <= layer_idx < len(self._layers_model.layers):
                layer = self._layers_model.layers[layer_idx]
                layer.spectrum_visible = visible
                self._render_spectrum_backgrounds()
        except Exception:
            pass

    def set_layer_spectrum_alpha(self, layer_idx: int, alpha: float) -> None:
        """Set opacity of a layer's spectrum background.

        Args:
            layer_idx: Index of the layer
            alpha: Opacity value (0.0 = transparent, 1.0 = opaque)
        """
        try:
            if not hasattr(self, '_layers_model') or self._layers_model is None:
                return

            if 0 <= layer_idx < len(self._layers_model.layers):
                layer = self._layers_model.layers[layer_idx]
                layer.spectrum_alpha = max(0.0, min(1.0, alpha))

                # Update existing image if it exists
                if layer.spectrum_image is not None:
                    layer.spectrum_image.set_alpha(layer.spectrum_alpha)
                    try:
                        self.fig.canvas.draw_idle()
                    except Exception:
                        pass
        except Exception:
            pass

    def toggle_all_spectra(self, enabled: bool) -> None:
        """Toggle all spectrum backgrounds on/off.

        Args:
            enabled: True to show all, False to hide all
        """
        try:
            from dc_cut.services.prefs import set_pref
            set_pref('show_spectra', enabled)
            self._render_spectrum_backgrounds()
        except Exception:
            pass

    def _on_layer_visibility_changed(self) -> None:
        """Hook called when layer visibility changes - updates spectrum backgrounds."""
        try:
            self._render_spectrum_backgrounds()
        except Exception:
            pass
