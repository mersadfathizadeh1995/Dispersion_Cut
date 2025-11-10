from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import matplotlib
matplotlib.use("QtAgg")  # prefer Qt
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector
import matplotlib.patches as mpatches


class BaseInteractiveRemoval:
    """Minimal Qt-first controller base independent of legacy Tk code.

    Provides: figure/axes, data arrays, line creation, view switcher, box selection,
    simple state save/restore, and helpers expected by the modern controller.
    """

    def __init__(
        self,
        velocity_arrays: List[np.ndarray],
        frequency_arrays: List[np.ndarray],
        wavelength_arrays: List[np.ndarray],
        *,
        array_positions: Optional[np.ndarray] = None,
        source_offsets: Optional[List[float]] = None,
        set_leg: Optional[List[str]] = None,
        receiver_dx: float = 2.0,
        legacy_controls: bool = False,
    ) -> None:
        self.velocity_arrays = [np.asarray(a, float) for a in velocity_arrays]
        self.frequency_arrays = [np.asarray(a, float) for a in frequency_arrays]
        self.wavelength_arrays = [np.asarray(a, float) for a in wavelength_arrays]
        n = min(len(self.velocity_arrays), len(self.frequency_arrays), len(self.wavelength_arrays))
        self.velocity_arrays = self.velocity_arrays[:n]
        self.frequency_arrays = self.frequency_arrays[:n]
        self.wavelength_arrays = self.wavelength_arrays[:n]

        self.offset_labels = list(set_leg or [f"Offset {i+1}" for i in range(n)])
        # Add placeholders for average labels (kept from legacy API expectations)
        self.average_label = "Average (Freq)"
        self.average_label_wave = "Average (Wave)"
        # Append average labels to offset_labels list for compatibility
        self.offset_labels.append(self.average_label)
        self.offset_labels.append(self.average_label_wave)
        self.show_average = True
        self.show_average_wave = False
        self.avg_line_freq = None
        self.avg_line_wave = None
        self.dummy_avg_line = None
        self.dummy_avg_wave_line = None
        self.avg_err_bars_f = None
        self.avg_err_bars_w = None

        # Preferences/state
        self.view_mode = 'both'
        self.auto_limits = True
        self.freq_tick_style = 'decades'
        self.freq_custom_ticks: List[float] = []
        self.kmin: Optional[float] = None
        self.kmax: Optional[float] = None
        self.show_k_guides: bool = False
        self.nacd_thresh: float = 1.0
        # Default Y clamp to match legacy app behavior
        self.min_vel: float = 0.0
        self.max_vel: float = 5000.0

        # History stacks
        self.history: List[dict] = []
        self.redo_stack: List[dict] = []

        # Add-mode defaults (no legacy buttons in Qt)
        self.add_mode: bool = False
        self._add_v = self._add_f = self._add_w = None
        self._add_line_freq = self._add_line_wave = None
        self._added_offset_idx: Optional[int] = None
        self._new_layer_info: Optional[Tuple[str, str, str]] = None
        self.btn_save_added = None

        # Figure and axes
        self.fig = plt.figure(figsize=(9, 5))
        gs = self.fig.add_gridspec(1, 2, left=0.06, right=0.96, bottom=0.11, top=0.91, wspace=0.28)
        self.ax_freq = self.fig.add_subplot(gs[0, 0])
        self.ax_wave = self.fig.add_subplot(gs[0, 1])
        # Store original positions for view switching
        self._orig_pos_freq = self.ax_freq.get_position().frozen()
        self._orig_pos_wave = self.ax_wave.get_position().frozen()
        self._single_pos = [0.06, 0.11, 0.88, 0.80]
        self._shell_hosted = False

        # Lines with distinct styles per offset
        self.lines_freq = []
        self.lines_wave = []
        markers = ['o', 's', '^', 'v', '<', '>', 'D', 'd', 'p', 'h', 'H', '8', 'P', 'X', '*', '+', 'x', '1', '2', '4']
        palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        for i in range(n):
            m = markers[i % len(markers)]
            c = palette[i % len(palette)]
            lf = self.ax_freq.semilogx(
                self.frequency_arrays[i], self.velocity_arrays[i],
                marker=m, linestyle='', markerfacecolor='none',
                markeredgecolor=c, markeredgewidth=1.5, markersize=6
            )[0]
            lw = self.ax_wave.semilogx(
                self.wavelength_arrays[i], self.velocity_arrays[i],
                marker=m, linestyle='', markerfacecolor='none',
                markeredgecolor=c, markeredgewidth=1.5, markersize=6,
                label=self.offset_labels[i]
            )[0]
            self.lines_freq.append(lf)
            self.lines_wave.append(lw)

        # Selection overlays
        self.bounding_boxes_freq: List[Tuple[float, float, float, float]] = []
        self.bounding_boxes_wave: List[Tuple[float, float, float, float]] = []
        self.freq_patches: List[mpatches.Rectangle] = []
        self.wave_patches: List[mpatches.Rectangle] = []
        self.rect_selector_freq = RectangleSelector(self.ax_freq, self._onselect_freq, useblit=False, interactive=False, button=[1], minspanx=0, minspany=0)
        self.rect_selector_wave = RectangleSelector(self.ax_wave, self._onselect_wave, useblit=False, interactive=False, button=[1], minspanx=0, minspany=0)

        # Guides artists (k-limits)
        self._k_guides_artists: List = []
        self._k_guides_legend = None

        # Initial labels
        self.ax_freq.set_xlabel("Frequency (Hz)")
        self.ax_freq.set_ylabel("Phase velocity (m/s)")
        self.ax_wave.set_xlabel("Wavelength (m)")
        self.ax_wave.set_ylabel("Phase velocity (m/s)")

        try:
            self.fig.canvas.draw_idle()
        except Exception:
            pass

    # ------------------- selections -------------------
    def _onselect_freq(self, eclick, erelease):
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        if x1 is None or x2 is None:
            return
        xmin, xmax = sorted([x1, x2])
        ymin, ymax = sorted([y1, y2])
        self.bounding_boxes_freq.append((xmin, xmax, ymin, ymax))
        rect = mpatches.Rectangle((xmin, ymin), xmax - xmin, ymax - ymin, edgecolor='k', facecolor='none', linestyle='--', linewidth=1.5)
        self.ax_freq.add_patch(rect)
        self.freq_patches.append(rect)
        try: self.fig.canvas.draw_idle()
        except Exception: pass

    def _onselect_wave(self, eclick, erelease):
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        if x1 is None or x2 is None:
            return
        xmin, xmax = sorted([x1, x2])
        ymin, ymax = sorted([y1, y2])
        self.bounding_boxes_wave.append((xmin, xmax, ymin, ymax))
        rect = mpatches.Rectangle((xmin, ymin), xmax - xmin, ymax - ymin, edgecolor='k', facecolor='none', linestyle='--', linewidth=1.5)
        self.ax_wave.add_patch(rect)
        self.wave_patches.append(rect)
        try: self.fig.canvas.draw_idle()
        except Exception: pass

    # ------------------- helpers -------------------
    def _apply_view_mode(self, mode: str):
        self.view_mode = mode
        if mode == 'both':
            self.ax_freq.set_position(self._orig_pos_freq)
            self.ax_wave.set_position(self._orig_pos_wave)
            self.ax_freq.set_visible(True); self.ax_wave.set_visible(True)
            self.ax_freq.set_navigate(True); self.ax_wave.set_navigate(True)
        elif mode == 'freq_only':
            self.ax_freq.set_visible(True); self.ax_wave.set_visible(False)
            self.ax_freq.set_position(self._single_pos if self._shell_hosted else [0.06, 0.11, 0.88, 0.80])
            self.ax_freq.set_navigate(True); self.ax_wave.set_navigate(False)
        else:  # wave_only
            self.ax_freq.set_visible(False); self.ax_wave.set_visible(True)
            self.ax_wave.set_position(self._single_pos if self._shell_hosted else [0.06, 0.11, 0.88, 0.80])
            self.ax_freq.set_navigate(False); self.ax_wave.set_navigate(True)
        try:
            self.fig.canvas.draw_idle()
        except Exception:
            pass

    def _apply_frequency_ticks(self):
        try:
            from dc_cut.core.ticks import make_freq_ticks
            xmin, xmax = self.ax_freq.get_xlim()
            ticks, labels = make_freq_ticks(getattr(self, 'freq_tick_style', 'decades'), float(xmin), float(xmax), getattr(self, 'freq_custom_ticks', []))
            self.ax_freq.set_xticks(ticks)
            self.ax_freq.set_xticklabels(labels)
        except Exception:
            pass

    def _remove_avg_line(self):
        self._remove_avg_freq_line(); self._remove_avg_wave_line()

    def _remove_avg_freq_line(self):
        try:
            if self.avg_line_freq is not None:
                self.avg_line_freq.remove(); self.avg_line_freq = None
            # Remove errorbar artists if present
            if getattr(self, 'avg_err_bars_f', None):
                try:
                    for art in (self.avg_err_bars_f[0] + self.avg_err_bars_f[1]):
                        try: art.remove()
                        except Exception: pass
                finally:
                    self.avg_err_bars_f = None
        except Exception:
            pass

    def _remove_avg_wave_line(self):
        try:
            if self.avg_line_wave is not None:
                self.avg_line_wave.remove(); self.avg_line_wave = None
            if getattr(self, 'avg_err_bars_w', None):
                try:
                    for art in (self.avg_err_bars_w[0] + self.avg_err_bars_w[1]):
                        try: art.remove()
                        except Exception: pass
                finally:
                    self.avg_err_bars_w = None
        except Exception:
            pass

    def _sync_line_lists(self):
        # Ensure lines match array counts
        n = min(len(self.velocity_arrays), len(self.frequency_arrays), len(self.wavelength_arrays))
        self.lines_freq = self.lines_freq[:n]
        self.lines_wave = self.lines_wave[:n]

    def _save_state(self):
        try:
            self.history.append(self.get_current_state())
            self.redo_stack.clear()
        except Exception:
            pass

    def _refresh(self):
        try:
            self.fig.canvas.draw_idle()
        except Exception:
            pass

    def _enforce_shell_layout(self):
        # Mark as hosted by shell (single-window embedding)
        self._shell_hosted = True
        self._orig_pos_freq = self.ax_freq.get_position().frozen()
        self._orig_pos_wave = self.ax_wave.get_position().frozen()

    def suppress_mpl_controls_for_shell(self):
        # No legacy buttons in this base; nothing to hide
        return

    # ------------------- no-op fallbacks for overrides -------------------
    # These exist so that derived controllers can safely call super()._on_* even
    # when running standalone without legacy base.
    def _on_delete(self, event):
        return

    def _on_add_data(self, event):
        return

    def _on_add_layer(self, event):
        return

    def _on_set_xlim(self, event):
        return

    def _on_set_ylim(self, event):
        return

    def _on_set_average_resolution(self, event):
        return

    def _on_undo(self, event):
        return

    def _on_redo(self, event):
        return

    def _on_quit(self, event):
        return

    def _on_save_session(self, event):
        return

    def _on_cancel(self, event):
        # Cancel selection rectangles and add-mode previews
        try:
            # Clear selection rectangles
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
        try:
            if bool(getattr(self, 'add_mode', False)):
                if getattr(self, '_add_line_freq', None) is not None:
                    try: self._add_line_freq.remove()
                    except Exception: pass
                if getattr(self, '_add_line_wave', None) is not None:
                    try: self._add_line_wave.remove()
                    except Exception: pass
                self._add_v = self._add_f = self._add_w = None
                self._add_line_freq = self._add_line_wave = None
                self._added_offset_idx = None
                self._new_layer_info = None
                self.add_mode = False
                try:
                    self._enable_save_added(False)
                except Exception:
                    pass
        except Exception:
            pass
        self._refresh()

    # State API for history
    def get_current_state(self) -> dict:
        return {
            'velocity_arrays':   [np.asarray(a, float) for a in self.velocity_arrays],
            'frequency_arrays':  [np.asarray(a, float) for a in self.frequency_arrays],
            'wavelength_arrays': [np.asarray(a, float) for a in self.wavelength_arrays],
            'set_leg':           list(self.offset_labels),
            'kmin':              self.kmin,
            'kmax':              self.kmax,
            'show_k_guides':     bool(self.show_k_guides),
            'freq_tick_style':   getattr(self, 'freq_tick_style', 'decades'),
            'freq_custom_ticks': list(getattr(self, 'freq_custom_ticks', [])),
        }

    def apply_state(self, S: dict) -> None:
        try:
            self.velocity_arrays   = [np.asarray(a, float) for a in S.get('velocity_arrays', self.velocity_arrays)]
            self.frequency_arrays  = [np.asarray(a, float) for a in S.get('frequency_arrays', self.frequency_arrays)]
            self.wavelength_arrays = [np.asarray(a, float) for a in S.get('wavelength_arrays', self.wavelength_arrays)]
            self.offset_labels     = list(S.get('set_leg', self.offset_labels))
        except Exception:
            pass
        # Update primary lines
        from dc_cut.core.plot import set_line_xy
        for i in range(min(len(self.lines_freq), len(self.velocity_arrays))):
            try:
                set_line_xy(self.lines_freq[i], self.frequency_arrays[i], self.velocity_arrays[i])
                set_line_xy(self.lines_wave[i], self.wavelength_arrays[i], self.velocity_arrays[i])
            except Exception:
                pass
        self.kmin = S.get('kmin', self.kmin)
        self.kmax = S.get('kmax', self.kmax)
        self.show_k_guides = bool(S.get('show_k_guides', self.show_k_guides))
        self.freq_tick_style = S.get('freq_tick_style', self.freq_tick_style)
        self.freq_custom_ticks = S.get('freq_custom_ticks', self.freq_custom_ticks)
        try:
            self._apply_frequency_ticks(); self._refresh()
        except Exception:
            pass


