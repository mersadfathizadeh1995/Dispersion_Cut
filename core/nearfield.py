"""Near-field inspector (controller-bound) and backward-compat re-exports.

Pure NACD computation functions live in dc_cut.core.processing.nearfield.
This module re-exports them and provides the stateful NearFieldInspector.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np

from dc_cut.core.processing.nearfield import (  # noqa: F401 -- re-export
    compute_nacd,
    compute_nacd_array,
    compute_nacd_for_all_data,
    detect_nearfield_picks,
)

if TYPE_CHECKING:
    pass


class NearFieldInspector:
    """Simple NF evaluator wired to controller arrays.

    Provides a minimal API for the NF dock.
    """
    def __init__(self, controller):
        self.c = controller
        self.thr = float(getattr(controller, 'nacd_thresh', 1.0))
        self._current_idx = None

    def start_with(self, label: str, thr: float, open_checklist: bool = False):
        self.thr = float(thr)
        try:
            idx = list(self.c.offset_labels).index(label)
        except Exception:
            idx = 0
        self._current_idx = idx

    def cancel(self):
        try:
            for lf, lw in list(getattr(self.c, '_nf_point_overlay', {}).values()):
                try: lf.remove(); lw.remove()
                except Exception: pass
            self.c._nf_point_overlay = {}
        except Exception:
            pass
        self._current_idx = None

    def update_threshold(self, thr: float):
        self.thr = float(thr)

    def get_current_arrays(self):
        if self._current_idx is None:
            return None
        i = int(self._current_idx)
        v = np.asarray(self.c.velocity_arrays[i], float)
        f = np.asarray(self.c.frequency_arrays[i], float)
        w = np.asarray(self.c.wavelength_arrays[i], float)
        if hasattr(self.c, 'array_positions'):
            array_pos = self.c.array_positions
        else:
            try:
                from dc_cut.services.prefs import load_prefs
                P = load_prefs()
                n_phones = int(P.get('default_n_phones', 24))
                dx = float(P.get('default_receiver_dx', 2.0))
                array_pos = np.arange(0, dx * n_phones, dx)
            except Exception:
                array_pos = np.arange(0, 48, 2.0)
        nacd = compute_nacd_array(array_pos, f, v)
        mask = nacd < self.thr
        return i, f, v, w, nacd, mask

    def apply_deletions(self, indices):
        if self._current_idx is None:
            return
        try:
            from dc_cut.core.history import push_undo
            push_undo(self.c)
        except Exception:
            pass
        i = int(self._current_idx)
        v = np.asarray(self.c.velocity_arrays[i], float)
        f = np.asarray(self.c.frequency_arrays[i], float)
        w = np.asarray(self.c.wavelength_arrays[i], float)
        mask = np.ones_like(v, dtype=bool)
        for j in indices:
            if 0 <= j < mask.size:
                mask[j] = False
        self.c.velocity_arrays[i] = v[mask]
        self.c.frequency_arrays[i] = f[mask]
        self.c.wavelength_arrays[i] = w[mask]
        try:
            from dc_cut.core.plot import set_line_xy
            set_line_xy(self.c.lines_freq[i], self.c.frequency_arrays[i], self.c.velocity_arrays[i])
            set_line_xy(self.c.lines_wave[i], self.c.wavelength_arrays[i], self.c.velocity_arrays[i])
        except Exception:
            pass
        try:
            for lf, lw in list(getattr(self.c, '_nf_point_overlay', {}).values()):
                try: lf.remove(); lw.remove()
                except Exception: pass
            self.c._nf_point_overlay = {}
        except Exception:
            pass
        try:
            from dc_cut.core.model import LayersModel
            labels = list(self.c.offset_labels[:len(self.c.velocity_arrays)])
            self.c._layers_model = LayersModel.from_arrays(self.c.velocity_arrays, self.c.frequency_arrays, self.c.wavelength_arrays, labels)
        except Exception:
            pass
        try:
            if bool(getattr(self.c, 'show_average', False)) or bool(getattr(self.c, 'show_average_wave', False)):
                self.c._update_average_line()
            self.c._update_legend()
        except Exception:
            pass
        try:
            self.c._apply_axis_limits(); self.c.fig.canvas.draw_idle()
        except Exception:
            pass
        try:
            cb = getattr(self.c, 'on_layers_changed', None)
            if cb:
                cb()
        except Exception:
            pass
        try:
            self.c._apply_axis_limits(); self.c.fig.canvas.draw_idle()
        except Exception:
            pass
