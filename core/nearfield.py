from __future__ import annotations

from typing import Iterable, List, Dict, Callable, Optional
import numpy as np


def compute_nacd(array_positions: Iterable[float], freq: float, velocity: float, *, eps: float = 1e-12) -> float:
    """Approximate NACD: normalized array coherence distance.

    Simple heuristic fallback: ratio of inter-sensor wavelength to array aperture.
    NACD = (min_aperture / wavelength). Values < 1 often indicate near-field risk.
    """
    try:
        arr = np.asarray(array_positions, float)
        if arr.size < 2 or not np.isfinite(freq) or not np.isfinite(velocity) or freq <= 0 or velocity <= 0:
            return 0.0
        aperture = float(np.nanmax(arr) - np.nanmin(arr))
        wavelength = float(velocity / freq)
        if wavelength <= 0:
            return 0.0
        nacd = aperture / max(wavelength, eps)
        return float(nacd)
    except Exception:
        return 0.0


def compute_nacd_array(array_positions: Iterable[float], freqs: np.ndarray, velocities: np.ndarray, *, eps: float = 1e-12) -> np.ndarray:
    """Vectorised NACD (NumPy array) using the heuristic fallback."""
    freqs = np.asarray(freqs, float); velocities = np.asarray(velocities, float)
    out = np.zeros_like(velocities, dtype=float)
    for i in range(out.size):
        out[i] = compute_nacd(array_positions, freqs[i], velocities[i], eps=eps)
    return out


def detect_nearfield_picks(picks: List[Dict[str, float]], array_positions: Iterable[float], *, threshold_nacd: Optional[float] = None, source_type: str = "hammer") -> List[Dict[str, float | bool]]:
    """Flag picks with NACD metadata and nearfield boolean.

    Standalone fallback: sets nacd=0.0 and nearfield=False for all picks.
    """
    out: List[Dict[str, float | bool]] = []
    thr = float(threshold_nacd) if threshold_nacd is not None else 1.0
    for p in picks:
        q = dict(p)
        q['nacd'] = 0.0
        q['nearfield'] = False
        q['source_type'] = source_type
        out.append(q)
    return out


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
        # Clear overlays when canceling
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
        nacd = compute_nacd_array(getattr(self.c, 'array_positions', np.arange(0, 48, 2.0)), f, v)
        mask = nacd < self.thr
        return i, f, v, w, nacd, mask

    def apply_deletions(self, indices):
        if self._current_idx is None:
            return
        # Snapshot for undo before mutating arrays
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
        # Clear any NF overlays on the plot
        try:
            for lf, lw in list(getattr(self.c, '_nf_point_overlay', {}).values()):
                try: lf.remove(); lw.remove()
                except Exception: pass
            self.c._nf_point_overlay = {}
        except Exception:
            pass
        # Rebuild model so Layers dock stays in sync
        try:
            from dc_cut.core.model import LayersModel
            labels = list(self.c.offset_labels[:len(self.c.velocity_arrays)])
            self.c._layers_model = LayersModel.from_arrays(self.c.velocity_arrays, self.c.frequency_arrays, self.c.wavelength_arrays, labels)
        except Exception:
            pass
        # Refresh averages, legend, limits, and UI
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
        # Notify layers UI if present
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


