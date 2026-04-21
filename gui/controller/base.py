from __future__ import annotations

from typing import List, Optional, Tuple, Union

import numpy as np
import matplotlib
matplotlib.use("QtAgg")  # prefer Qt
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon


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

        # Array geometry (stored for NACD / wavelength-line computations)
        if array_positions is not None:
            self.array_positions = np.asarray(array_positions, float)
        else:
            self.array_positions = np.arange(0, receiver_dx * 24, receiver_dx)
        self.source_offsets = list(source_offsets or [])
        self.receiver_dx = float(receiver_dx)

        # Wavelength (lambda) reference lines
        self.show_wavelength_lines: bool = False
        self._wavelength_lines_data: List[dict] = []
        self._wavelength_lines_artists: List = []
        self._wavelength_lines_legend: List = []
        self._wl_visibility: dict = {}
        self._wl_colors: dict = {}
        self._wl_show_labels: bool = True
        self._wl_label_position: str = "upper"
        self._wl_label_fontsize: int = 9
        self._wl_label_bbox: bool = True
        self._wl_label_bbox_alpha: float = 0.7

        # NF overlay markers (geometry-only and V_R mode)
        self._nf_point_overlay: dict = {}

        # NF reference curve (for V_R mode)
        self._nf_reference_f: Optional[np.ndarray] = None
        self._nf_reference_v: Optional[np.ndarray] = None
        self._nf_reference_source: str = ""

        # NACD / NF evaluation snapshot for PKL persistence (Report Studio)
        self._nf_results: dict = {}
        self._nf_settings: dict = {}
        self._nf_dirty: bool = False
        # Last .pkl path used for full session load / explicit NF save (Save to PKL default)
        self._loaded_state_path: str = ""

        # Axis scales (log/linear)
        self.freq_x_scale: str = "log"
        self.vel_y_scale: str = "linear"
        self.wave_x_scale: str = "log"
        self.avg_line_freq = None
        self.avg_line_wave = None
        self.dummy_avg_line = None
        self.dummy_avg_wave_line = None
        self.avg_err_bars_f = None
        self.avg_err_bars_w = None

        # Preferences/state
        self.view_mode = 'freq_only'
        self.auto_limits = False
        self.freq_tick_style = 'ruler'
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
            lf = self.ax_freq.plot(
                self.frequency_arrays[i], self.velocity_arrays[i],
                marker=m, linestyle='', markerfacecolor='none',
                markeredgecolor=c, markeredgewidth=1.5, markersize=6
            )[0]
            lw = self.ax_wave.plot(
                self.wavelength_arrays[i], self.velocity_arrays[i],
                marker=m, linestyle='', markerfacecolor='none',
                markeredgecolor=c, markeredgewidth=1.5, markersize=6,
                label=self.offset_labels[i]
            )[0]
            self.lines_freq.append(lf)
            self.lines_wave.append(lw)

        # Selection overlays - axis-aligned rectangles
        self.bounding_boxes_freq: List[Tuple[float, float, float, float]] = []
        self.bounding_boxes_wave: List[Tuple[float, float, float, float]] = []
        self.freq_patches: List[mpatches.Rectangle] = []
        self.wave_patches: List[mpatches.Rectangle] = []
        self.rect_selector_freq = RectangleSelector(self.ax_freq, self._onselect_freq, useblit=False, interactive=False, button=[1], minspanx=0, minspany=0)
        self.rect_selector_wave = RectangleSelector(self.ax_wave, self._onselect_wave, useblit=False, interactive=False, button=[1], minspanx=0, minspany=0)

        # Selection overlays - inclined rectangles (polygons)
        self.inclined_boxes_freq: List[np.ndarray] = []  # List of (4,2) corner arrays
        self.inclined_boxes_wave: List[np.ndarray] = []
        self.inclined_patches_freq: List[Polygon] = []
        self.inclined_patches_wave: List[Polygon] = []

        # Guides artists (k-limits)
        self._k_guides_artists: List = []
        self._k_guides_legend = None

        # Initial labels
        self.ax_freq.set_xlabel("Frequency (Hz)")
        self.ax_freq.set_ylabel("Phase velocity (m/s)")
        self.ax_wave.set_xlabel("Wavelength (m)")
        self.ax_wave.set_ylabel("Phase velocity (m/s)")

        self._apply_axis_scales()

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

    def _apply_axis_scales(self):
        """Apply current axis scale settings (log/linear) to both axes."""
        try:
            self.ax_freq.set_xscale(getattr(self, 'freq_x_scale', 'log'))
            self.ax_freq.set_yscale(getattr(self, 'vel_y_scale', 'linear'))
            self.ax_wave.set_xscale(getattr(self, 'wave_x_scale', 'log'))
            self.ax_wave.set_yscale(getattr(self, 'vel_y_scale', 'linear'))
        except Exception:
            pass

    def _apply_frequency_ticks(self):
        try:
            from dc_cut.core.processing.ticks import make_freq_ticks
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
            # Clear axis-aligned selection rectangles
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
        # Clear inclined rectangle patches
        try:
            for p in list(getattr(self, 'inclined_patches_freq', [])):
                try: p.remove()
                except Exception: pass
            self.inclined_patches_freq.clear(); self.inclined_boxes_freq.clear()
        except Exception:
            pass
        try:
            for p in list(getattr(self, 'inclined_patches_wave', [])):
                try: p.remove()
                except Exception: pass
            self.inclined_patches_wave.clear(); self.inclined_boxes_wave.clear()
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
        state = {
            'velocity_arrays':   [np.asarray(a, float) for a in self.velocity_arrays],
            'frequency_arrays':  [np.asarray(a, float) for a in self.frequency_arrays],
            'wavelength_arrays': [np.asarray(a, float) for a in self.wavelength_arrays],
            'set_leg':           list(self.offset_labels),
            'kmin':              self.kmin,
            'kmax':              self.kmax,
            'show_k_guides':     bool(self.show_k_guides),
            'freq_tick_style':   getattr(self, 'freq_tick_style', 'decades'),
            'freq_custom_ticks': list(getattr(self, 'freq_custom_ticks', [])),
            'show_wavelength_lines': bool(self.show_wavelength_lines),
            'wavelength_lines_data': [
                {k: (v.tolist() if hasattr(v, 'tolist') else v)
                 for k, v in d.items()}
                for d in self._wavelength_lines_data
            ],
            'wl_visibility': dict(self._wl_visibility),
            'wl_colors': dict(self._wl_colors),
            'wl_show_labels': self._wl_show_labels,
            'wl_label_position': self._wl_label_position,
            'wl_label_fontsize': self._wl_label_fontsize,
            'wl_label_bbox': self._wl_label_bbox,
            'wl_label_bbox_alpha': self._wl_label_bbox_alpha,
            'freq_x_scale': getattr(self, 'freq_x_scale', 'log'),
            'vel_y_scale': getattr(self, 'vel_y_scale', 'linear'),
            'wave_x_scale': getattr(self, 'wave_x_scale', 'log'),
            'nf_reference_f': self._nf_reference_f.tolist() if self._nf_reference_f is not None else None,
            'nf_reference_v': self._nf_reference_v.tolist() if self._nf_reference_v is not None else None,
            'nf_reference_source': self._nf_reference_source,
            'nf_results': dict(self._nf_results),
            'nf_settings': dict(self._nf_settings),
        }
        return state

    def apply_state(self, S: dict) -> None:
        try:
            self.velocity_arrays   = [np.asarray(a, float) for a in S.get('velocity_arrays', self.velocity_arrays)]
            self.frequency_arrays  = [np.asarray(a, float) for a in S.get('frequency_arrays', self.frequency_arrays)]
            self.wavelength_arrays = [np.asarray(a, float) for a in S.get('wavelength_arrays', self.wavelength_arrays)]
            self.offset_labels     = list(S.get('set_leg', self.offset_labels))
        except Exception:
            pass
        # Update primary lines
        from dc_cut.visualization.plot_helpers import set_line_xy
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
        self.show_wavelength_lines = bool(S.get('show_wavelength_lines', self.show_wavelength_lines))
        raw_wl = S.get('wavelength_lines_data', [])
        if raw_wl:
            restored = []
            for d in raw_wl:
                rd = dict(d)
                for key in ('f_curve', 'v_curve'):
                    if key in rd and isinstance(rd[key], list):
                        rd[key] = np.asarray(rd[key], float)
                restored.append(rd)
            self._wavelength_lines_data = restored
        self._wl_visibility = dict(S.get('wl_visibility', self._wl_visibility))
        self._wl_colors = dict(S.get('wl_colors', self._wl_colors))
        self._wl_show_labels = bool(S.get('wl_show_labels', self._wl_show_labels))
        self._wl_label_position = S.get('wl_label_position', self._wl_label_position)
        self._wl_label_fontsize = int(S.get('wl_label_fontsize', self._wl_label_fontsize))
        self._wl_label_bbox = bool(S.get('wl_label_bbox', self._wl_label_bbox))
        self._wl_label_bbox_alpha = float(S.get('wl_label_bbox_alpha', self._wl_label_bbox_alpha))
        self.freq_x_scale = S.get('freq_x_scale', getattr(self, 'freq_x_scale', 'log'))
        self.vel_y_scale = S.get('vel_y_scale', getattr(self, 'vel_y_scale', 'linear'))
        self.wave_x_scale = S.get('wave_x_scale', getattr(self, 'wave_x_scale', 'log'))
        ref_f = S.get('nf_reference_f')
        ref_v = S.get('nf_reference_v')
        if ref_f is not None and ref_v is not None:
            self._nf_reference_f = np.asarray(ref_f, float)
            self._nf_reference_v = np.asarray(ref_v, float)
        else:
            self._nf_reference_f = None
            self._nf_reference_v = None
        self._nf_reference_source = S.get('nf_reference_source', '')
        self._nf_results = dict(S.get('nf_results', self._nf_results))
        self._nf_settings = dict(S.get('nf_settings', self._nf_settings))
        self._nf_dirty = False
        try:
            self._apply_axis_scales()
            self._apply_frequency_ticks()
            self._refresh()
        except Exception:
            pass


