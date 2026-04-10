"""Visualization handler for legend, average lines, and k-guides.

Handles plot visualization updates including legend assembly, average line
computation and rendering, axis limits, and k-limit guide curves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np
import matplotlib.lines as mlines

from dc_cut.visualization.plot_helpers import assemble_legend, set_line_xy
from dc_cut.core.processing.averages import compute_avg_by_frequency, compute_avg_by_wavelength
from dc_cut.core.limits import compute_padded_limits
from dc_cut.core.processing.guides import compute_k_guides
from dc_cut.services.prefs import get_pref
from dc_cut.services import log

if TYPE_CHECKING:
    from dc_cut.gui.controller.base import BaseInteractiveRemoval


class VisualizationHandler:
    """Handles visualization updates (legend, average, k-guides)."""

    # Color palettes for k-guides
    K_GUIDE_COLORS = {
        'aperture': '#7b2cbf',
        'aperture_half': '#ff7f0e',
        'aliasing': '#d62728',
        'aliasing_half': '#2ca02c',
    }

    MULTI_K_COLORS = {
        500: '#9b59b6',
        200: '#e67e22',
        50: '#3498db',
    }
    DEFAULT_K_COLOR = '#7b2cbf'

    def __init__(self, controller: "BaseInteractiveRemoval") -> None:
        """Initialize visualization handler.

        Parameters
        ----------
        controller : BaseInteractiveRemoval
            Parent controller instance.
        """
        self._ctrl = controller

    def update_legend(self) -> None:
        """Update legend on the appropriate axis."""
        try:
            self._ctrl._sync_line_lists()
            handles, labels = assemble_legend(
                self._ctrl.lines_wave,
                self._ctrl.offset_labels,
                show_average=self._ctrl.show_average,
                avg_handle=self._ctrl.dummy_avg_line,
                avg_label=self._ctrl.average_label,
                show_average_wave=self._ctrl.show_average_wave,
                avg_wave_handle=self._ctrl.dummy_avg_wave_line,
                avg_wave_label=self._ctrl.average_label_wave,
                k_guides_legend=(
                    self._ctrl._k_guides_legend
                    if bool(getattr(self._ctrl, 'show_k_guides', False))
                    else None
                ),
            )
        except Exception:
            return

        # Choose target axis
        if self._ctrl.view_mode == 'freq_only':
            target_ax = self._ctrl.ax_freq
        else:
            target_ax = self._ctrl.ax_wave

        # Remove existing legends
        for ax in (self._ctrl.ax_freq, self._ctrl.ax_wave):
            leg = ax.get_legend()
            if leg is not None:
                leg.remove()

        # Add new legend
        if handles:
            target_ax.legend(handles, labels, loc='best')

        try:
            self._ctrl._apply_axis_limits()
            self._ctrl._draw_k_guides()
            self._ctrl.fig.canvas.draw_idle()
        except Exception:
            pass

    def update_average_line(self) -> None:
        """Recompute and render average lines for freq and wave plots."""
        self._ctrl._sync_line_lists()

        if not self._ctrl.show_average and not self._ctrl.show_average_wave:
            self._remove_avg_line()
            return

        # Gather visible data
        all_freq, all_vel = [], []
        n_offsets = len(self._ctrl.velocity_arrays)

        for i in range(n_offsets):
            try:
                if self._ctrl.lines_freq[i].get_visible():
                    all_freq.extend(self._ctrl.frequency_arrays[i])
                    all_vel.extend(self._ctrl.velocity_arrays[i])
            except Exception:
                continue

        if not all_freq:
            self._remove_avg_line()
            return

        freq_arr = np.asarray(all_freq, float)
        vel_arr = np.asarray(all_vel, float)

        # Compute bins
        avg_bins = int(
            getattr(self._ctrl, 'avg_points_override', 0)
            or (
                getattr(self._ctrl, 'bins_for_average', 50)
                * getattr(self._ctrl, 'interp_factor', 1)
            )
        )

        # Frequency average
        if self._ctrl.show_average:
            self._render_freq_average(freq_arr, vel_arr, avg_bins)
        else:
            self._remove_avg_freq_line()

        # Wavelength average
        if self._ctrl.show_average_wave:
            self._render_wave_average(n_offsets, avg_bins)
        else:
            self._remove_avg_wave_line()

        log.info("Averages recomputed and lines updated")

    def _render_freq_average(
        self, freq_arr: np.ndarray, vel_arr: np.ndarray, bins: int
    ) -> None:
        """Render average line on frequency plot."""
        stats = compute_avg_by_frequency(
            vel_arr,
            freq_arr,
            min_freq=float(
                getattr(self._ctrl, 'min_freq', max(0.1, float(np.nanmin(freq_arr))))
            ),
            max_freq=float(getattr(self._ctrl, 'max_freq', float(np.nanmax(freq_arr)))),
            bins=int(max(2, bins)),
            bias=float(getattr(self._ctrl, 'low_bias', 1.0)),
        )

        fvals = stats['FreqMean']
        mvals = stats['VelMean']
        svals = stats['VelStd']
        mask = np.isfinite(fvals) & np.isfinite(mvals) & np.isfinite(svals)
        fvals, mvals, svals = fvals[mask], mvals[mask], svals[mask]

        self._remove_avg_freq_line()

        if fvals.size > 0:
            # Store arrays for export wizard access
            self._ctrl.avg_freq = fvals.copy()
            self._ctrl.avg_vel = mvals.copy()
            self._ctrl.avg_std = svals.copy()
            
            out = self._ctrl.ax_freq.errorbar(
                fvals,
                mvals,
                yerr=svals,
                fmt='k-o',
                ecolor='k',
                elinewidth=1,
                capsize=3,
                markersize=3,
                alpha=0.9,
            )
            self._ctrl.avg_line_freq = out[0]
            try:
                self._ctrl.avg_err_bars_f = (out[1], out[2])
                for art in out[1] + out[2]:
                    art.set_gid('_avg')
                self._ctrl.avg_line_freq.set_label('_avg')
            except Exception:
                pass

    def _render_wave_average(self, n_offsets: int, bins: int) -> None:
        """Render average line on wavelength plot."""
        all_wave, all_vel = [], []

        for i in range(n_offsets):
            try:
                if self._ctrl.lines_wave[i].get_visible():
                    all_wave.extend(self._ctrl.wavelength_arrays[i])
                    all_vel.extend(self._ctrl.velocity_arrays[i])
            except Exception:
                continue

        if not all_wave:
            self._remove_avg_wave_line()
            return

        wave_arr = np.asarray(all_wave, float)
        vel_arr = np.asarray(all_vel, float)

        stats = compute_avg_by_wavelength(
            vel_arr,
            wave_arr,
            min_wave=float(
                getattr(self._ctrl, 'min_wave', max(0.1, float(np.nanmin(wave_arr))))
            ),
            max_wave=float(getattr(self._ctrl, 'max_wave', float(np.nanmax(wave_arr)))),
            bins=int(max(2, bins)),
            bias=float(getattr(self._ctrl, 'low_bias', 1.0)),
        )

        wvals = stats['FreqMean']
        mwavs = stats['VelMean']
        swavs = stats['VelStd']
        mask = np.isfinite(wvals) & np.isfinite(mwavs) & np.isfinite(swavs)
        wvals, mwavs, swavs = wvals[mask], mwavs[mask], swavs[mask]

        self._remove_avg_wave_line()

        if wvals.size > 0:
            out = self._ctrl.ax_wave.errorbar(
                wvals,
                mwavs,
                yerr=swavs,
                fmt='k-o',
                ecolor='k',
                elinewidth=1,
                capsize=3,
                markersize=3,
                alpha=0.9,
            )
            self._ctrl.avg_line_wave = out[0]
            try:
                self._ctrl.avg_err_bars_w = (out[1], out[2])
            except Exception:
                pass

    def _remove_avg_line(self) -> None:
        """Remove all average lines."""
        self._remove_avg_freq_line()
        self._remove_avg_wave_line()

    def _remove_avg_freq_line(self) -> None:
        """Remove frequency average line and error bars."""
        try:
            if self._ctrl.avg_line_freq is not None:
                self._ctrl.avg_line_freq.remove()
                self._ctrl.avg_line_freq = None
        except Exception:
            pass

        try:
            if self._ctrl.avg_err_bars_f is not None:
                for container in self._ctrl.avg_err_bars_f:
                    for art in container:
                        try:
                            art.remove()
                        except Exception:
                            pass
                self._ctrl.avg_err_bars_f = None
        except Exception:
            pass

    def _remove_avg_wave_line(self) -> None:
        """Remove wavelength average line and error bars."""
        try:
            if self._ctrl.avg_line_wave is not None:
                self._ctrl.avg_line_wave.remove()
                self._ctrl.avg_line_wave = None
        except Exception:
            pass

        try:
            if self._ctrl.avg_err_bars_w is not None:
                for container in self._ctrl.avg_err_bars_w:
                    for art in container:
                        try:
                            art.remove()
                        except Exception:
                            pass
                self._ctrl.avg_err_bars_w = None
        except Exception:
            pass

    def apply_axis_limits(self) -> None:
        """Apply auto-scaled axis limits with padding."""
        if not bool(getattr(self._ctrl, 'auto_limits', True)):
            return

        self._ctrl._sync_line_lists()
        visible_v, visible_f, visible_w = self._gather_visible_data()

        if not visible_v:
            return

        v = np.asarray(visible_v)
        f = np.asarray(visible_f)
        w = np.asarray(visible_w)

        try:
            L = compute_padded_limits(v, f, w)
            ymin, ymax = L['ymin'], L['ymax']
            fmin, fmax = L['fmin'], L['fmax']
            wmin, wmax = L['wmin'], L['wmax']
        except Exception:
            ymin, ymax, fmin, fmax, wmin, wmax = self._fallback_limits(v, f, w)

        # Apply to frequency axis
        if self._ctrl.view_mode in ('both', 'freq_only'):
            self._apply_freq_limits(fmin, fmax, ymin, ymax)

        # Apply to wavelength axis
        if self._ctrl.view_mode in ('both', 'wave_only'):
            self._apply_wave_limits(wmin, wmax, ymin, ymax)

        try:
            self._ctrl._draw_k_guides()
        except Exception:
            pass

    def _gather_visible_data(self) -> Tuple[List, List, List]:
        """Gather data from visible layers."""
        visible_v, visible_f, visible_w = [], [], []

        # Try model first
        if getattr(self._ctrl, '_layers_model', None) is not None:
            try:
                v_list, f_list, w_list = self._ctrl._layers_model.get_visible_arrays()
                for v in v_list:
                    visible_v.extend(v)
                for f in f_list:
                    visible_f.extend(f)
                for w in w_list:
                    visible_w.extend(w)
            except Exception:
                pass

        # Fallback to lines
        if not visible_v:
            for i in range(len(self._ctrl.velocity_arrays)):
                if self._ctrl.lines_freq[i].get_visible():
                    visible_v.extend(self._ctrl.velocity_arrays[i])
                    visible_f.extend(self._ctrl.frequency_arrays[i])
                    visible_w.extend(self._ctrl.wavelength_arrays[i])

        # Include add-mode temp points
        if bool(getattr(self._ctrl, 'add_mode', False)):
            if getattr(self._ctrl, '_add_v', None) is not None:
                visible_v.extend(list(self._ctrl._add_v))
                visible_f.extend(list(self._ctrl._add_f))
                visible_w.extend(list(self._ctrl._add_w))

        return visible_v, visible_f, visible_w

    def _fallback_limits(
        self, v: np.ndarray, f: np.ndarray, w: np.ndarray
    ) -> Tuple[float, float, float, float, float, float]:
        """Compute fallback limits when compute_padded_limits fails."""
        v = v[np.isfinite(v)]
        f = f[np.isfinite(f)]
        w = w[np.isfinite(w)]

        if v.size == 0 or f.size == 0 or w.size == 0:
            return 0, 5000, 0.1, 100, 1, 100

        pad_v = 100.0
        ymin = max(0.0, float(v.min()) - pad_v)
        ymax = float(v.max()) + pad_v

        pad_low, pad_high = 2.0, 10.0
        fmin = max(0.1, float(f.min()) - pad_low)
        fmax = float(f.max()) + pad_high
        wmin = max(1.0, float(w.min()) - pad_low)
        wmax = float(w.max()) + pad_high

        return ymin, ymax, fmin, fmax, wmin, wmax

    def _apply_freq_limits(
        self, fmin: float, fmax: float, ymin: float, ymax: float
    ) -> None:
        """Apply limits to frequency axis."""
        fmin = max(1e-3, float(fmin))
        fmax = max(float(fmax), fmin * 1.2)

        y0 = max(float(getattr(self._ctrl, 'min_vel', 0.0)), ymin)
        y1 = min(float(getattr(self._ctrl, 'max_vel', 5000.0)), ymax)
        if y1 <= y0:
            y0, y1 = ymin, ymax

        self._ctrl.ax_freq.set_ylim(y0, y1)
        self._ctrl.ax_freq.set_xlim(fmin, fmax)

        # Grid preference
        show_grid = bool(get_pref('show_grid', True))
        if show_grid:
            self._ctrl.ax_freq.grid(True, which='both', alpha=0.25)
        else:
            self._ctrl.ax_freq.grid(False)

        try:
            self._ctrl._apply_frequency_ticks()
        except Exception:
            pass

    def _apply_wave_limits(
        self, wmin: float, wmax: float, ymin: float, ymax: float
    ) -> None:
        """Apply limits to wavelength axis."""
        wmin = max(1e-3, float(wmin))
        wmax = max(float(wmax), wmin * 1.2)

        y0 = max(float(getattr(self._ctrl, 'min_vel', 0.0)), ymin)
        y1 = min(float(getattr(self._ctrl, 'max_vel', 5000.0)), ymax)
        if y1 <= y0:
            y0, y1 = ymin, ymax

        self._ctrl.ax_wave.set_ylim(y0, y1)
        self._ctrl.ax_wave.set_xlim(wmin, wmax)

        # Grid preference
        show_grid = bool(get_pref('show_grid', True))
        if show_grid:
            self._ctrl.ax_wave.grid(True, which='both', alpha=0.25)
        else:
            self._ctrl.ax_wave.grid(False)

    def clear_k_guides(self) -> None:
        """Remove all k-guide artists from the plot."""
        for artist in getattr(self._ctrl, '_k_guides_artists', []):
            try:
                artist.remove()
            except Exception:
                pass

        self._ctrl._k_guides_artists = []
        self._ctrl._k_guides_legend = None

    def draw_k_guides(self) -> None:
        """Draw k-limit guide curves on both plots."""
        if not bool(getattr(self._ctrl, 'show_k_guides', False)):
            self.clear_k_guides()
            return

        self.clear_k_guides()

        # Check for multi k-limits
        multi_klimits = getattr(self._ctrl, '_multi_klimits', [])
        if multi_klimits:
            self._draw_multi_k_guides(multi_klimits)
            return

        # Single k-limits
        kmin = getattr(self._ctrl, 'kmin', None)
        kmax = getattr(self._ctrl, 'kmax', None)

        if kmin is None or kmax is None or kmin <= 0 or kmax <= 0:
            return

        self._draw_single_k_guides(float(kmin), float(kmax))

    def _draw_single_k_guides(self, kmin: float, kmax: float) -> None:
        """Draw k-guides for single array."""
        col_ap = self.K_GUIDE_COLORS['aperture']
        col_ap2 = self.K_GUIDE_COLORS['aperture_half']
        col_al = self.K_GUIDE_COLORS['aliasing']
        col_al2 = self.K_GUIDE_COLORS['aliasing_half']

        fmin, fmax = self._ctrl.ax_freq.get_xlim()

        try:
            G = compute_k_guides(kmin, kmax, fmin, fmax)
            f_curve = G['f_curve']
            v_ap, v_ap2 = G['v_ap'], G['v_ap2']
            v_al, v_al2 = G['v_al'], G['v_al2']
            w_ap, w_ap2 = G['w_ap'], G['w_ap2']
            w_al, w_al2 = G['w_al'], G['w_al2']
        except Exception:
            f_curve, v_ap, v_ap2, v_al, v_al2, w_ap, w_ap2, w_al, w_al2 = (
                self._fallback_k_guides(kmin, kmax, fmin, fmax)
            )

        # Draw on frequency axis
        ln_ap = self._ctrl.ax_freq.semilogx(
            f_curve, v_ap, '-', color=col_ap, lw=1.2, label='_kguide'
        )[0]
        ln_ap2 = self._ctrl.ax_freq.semilogx(
            f_curve, v_ap2, '--', color=col_ap2, lw=1.2, label='_kguide'
        )[0]
        ln_al = self._ctrl.ax_freq.semilogx(
            f_curve, v_al, '-', color=col_al, lw=1.2, label='_kguide'
        )[0]
        ln_al2 = self._ctrl.ax_freq.semilogx(
            f_curve, v_al2, '--', color=col_al2, lw=1.2, label='_kguide'
        )[0]

        # Draw on wavelength axis
        y0, y1 = self._ctrl.ax_wave.get_ylim()
        ln_w_ap = self._ctrl.ax_wave.semilogx(
            [w_ap, w_ap], [y0, y1], '-', color=col_ap, lw=1.2, label='_kguide'
        )[0]
        ln_w_ap2 = self._ctrl.ax_wave.semilogx(
            [w_ap2, w_ap2], [y0, y1], '--', color=col_ap2, lw=1.2, label='_kguide'
        )[0]
        ln_w_al = self._ctrl.ax_wave.semilogx(
            [w_al, w_al], [y0, y1], '-', color=col_al, lw=1.2, label='_kguide'
        )[0]
        ln_w_al2 = self._ctrl.ax_wave.semilogx(
            [w_al2, w_al2], [y0, y1], '--', color=col_al2, lw=1.2, label='_kguide'
        )[0]

        self._ctrl._k_guides_artists.extend(
            [ln_ap, ln_ap2, ln_al, ln_al2, ln_w_ap, ln_w_ap2, ln_w_al, ln_w_al2]
        )

        # Build legend
        self._ctrl._k_guides_legend = [
            mlines.Line2D([], [], color=col_ap, linestyle='-', label='Aperture Limit'),
            mlines.Line2D(
                [], [], color=col_ap2, linestyle='--', label='Aperture Limit (λ/2)'
            ),
            mlines.Line2D([], [], color=col_al, linestyle='-', label='Aliasing Limit'),
            mlines.Line2D(
                [], [], color=col_al2, linestyle='--', label='Aliasing Limit (λ/2)'
            ),
        ]

    def _draw_multi_k_guides(self, klimits_list: list) -> None:
        """Draw k-guides for multiple arrays with visibility filtering."""
        fmin, fmax = self._ctrl.ax_freq.get_xlim()
        fmin = max(1e-3, fmin)
        fmax = max(fmax, fmin * 1.1)
        f_curve = np.logspace(np.log10(fmin), np.log10(fmax), 300)
        y0, y1 = self._ctrl.ax_wave.get_ylim()

        legend_items = []
        
        # Get visibility settings
        visibility = getattr(self._ctrl, '_klimits_visibility', {})

        for label, kmin, kmax in klimits_list:
            # Skip if not visible
            if not visibility.get(label, True):
                continue
            
            # Use label for color lookup (try to extract diameter if numeric)
            try:
                diameter = int(float(label.replace('m', '').strip()))
            except (ValueError, AttributeError):
                diameter = label
            base_color = self.MULTI_K_COLORS.get(diameter, self.DEFAULT_K_COLOR)

            v_ap = (2 * np.pi * f_curve) / float(kmin)
            v_ap2 = (2 * np.pi * f_curve) / (float(kmin) / 2.0)
            v_al = (2 * np.pi * f_curve) / float(kmax)
            v_al2 = (2 * np.pi * f_curve) / (float(kmax) / 2.0)

            w_ap = 2 * np.pi / float(kmin)
            w_ap2 = 2 * np.pi / (float(kmin) / 2.0)
            w_al = 2 * np.pi / float(kmax)
            w_al2 = 2 * np.pi / (float(kmax) / 2.0)

            # Frequency axis
            ln_ap = self._ctrl.ax_freq.semilogx(
                f_curve, v_ap, '-', color=base_color, lw=1.5, label='_kguide'
            )[0]
            ln_ap2 = self._ctrl.ax_freq.semilogx(
                f_curve, v_ap2, '--', color=base_color, lw=1.2, label='_kguide'
            )[0]
            ln_al = self._ctrl.ax_freq.semilogx(
                f_curve, v_al, '-', color=base_color, lw=1.5, alpha=0.6, label='_kguide'
            )[0]
            ln_al2 = self._ctrl.ax_freq.semilogx(
                f_curve, v_al2, '--', color=base_color, lw=1.2, alpha=0.6, label='_kguide'
            )[0]

            # Wavelength axis
            ln_w_ap = self._ctrl.ax_wave.semilogx(
                [w_ap, w_ap], [y0, y1], '-', color=base_color, lw=1.5, label='_kguide'
            )[0]
            ln_w_ap2 = self._ctrl.ax_wave.semilogx(
                [w_ap2, w_ap2], [y0, y1], '--', color=base_color, lw=1.2, label='_kguide'
            )[0]
            ln_w_al = self._ctrl.ax_wave.semilogx(
                [w_al, w_al], [y0, y1], '-', color=base_color, lw=1.5, alpha=0.6, label='_kguide'
            )[0]
            ln_w_al2 = self._ctrl.ax_wave.semilogx(
                [w_al2, w_al2], [y0, y1], '--', color=base_color, lw=1.2, alpha=0.6, label='_kguide'
            )[0]

            self._ctrl._k_guides_artists.extend(
                [ln_ap, ln_ap2, ln_al, ln_al2, ln_w_ap, ln_w_ap2, ln_w_al, ln_w_al2]
            )

            legend_items.extend([
                mlines.Line2D(
                    [], [], color=base_color, linestyle='-', lw=1.5,
                    label=f'{label} Aperture'
                ),
                mlines.Line2D(
                    [], [], color=base_color, linestyle='--', lw=1.2,
                    label=f'{label} Aperture (λ/2)'
                ),
                mlines.Line2D(
                    [], [], color=base_color, linestyle='-', lw=1.5, alpha=0.6,
                    label=f'{label} Aliasing'
                ),
                mlines.Line2D(
                    [], [], color=base_color, linestyle='--', lw=1.2, alpha=0.6,
                    label=f'{label} Aliasing (λ/2)'
                ),
            ])

        self._ctrl._k_guides_legend = legend_items

    def _fallback_k_guides(
        self, kmin: float, kmax: float, fmin: float, fmax: float
    ) -> tuple:
        """Compute k-guides without using core.guides module."""
        fmin = max(1e-3, fmin)
        fmax = max(fmax, fmin * 1.1)
        f_curve = np.logspace(np.log10(fmin), np.log10(fmax), 300)

        v_ap = (2 * np.pi * f_curve) / kmin
        v_ap2 = (2 * np.pi * f_curve) / (kmin / 2.0)
        v_al = (2 * np.pi * f_curve) / kmax
        v_al2 = (2 * np.pi * f_curve) / (kmax / 2.0)

        w_ap = 2 * np.pi / kmin
        w_ap2 = 2 * np.pi / (kmin / 2.0)
        w_al = 2 * np.pi / kmax
        w_al2 = 2 * np.pi / (kmax / 2.0)

        return f_curve, v_ap, v_ap2, v_al, v_al2, w_ap, w_ap2, w_al, w_al2
