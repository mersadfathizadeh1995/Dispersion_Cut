"""Near-field inspector -- controller-bound NF evaluator.

Supports two modes:
  1. Geometry-only (NACD threshold, binary mask)
  2. Reference-curve (V_R = V_measured / V_true, severity classification)

Pure computation functions live in dc_cut.core.processing.nearfield.
"""
from __future__ import annotations

from typing import List, Optional, Tuple
import numpy as np

from dc_cut.core.processing.nearfield import (
    compute_nacd_array,
    compute_normalized_vr_with_validity,
    classify_nearfield_severity,
    compute_composite_reference,
    compute_nearfield_report,
    load_reference_curve,
    select_reference_by_largest_xbar,
)
from dc_cut.core.processing.wavelength_lines import (
    parse_source_offset_from_label,
    compute_lambda_max,
)


class NearFieldInspector:
    """Stateful NF evaluator wired to controller arrays."""

    def __init__(self, controller):
        self.c = controller
        self.thr = float(getattr(controller, 'nacd_thresh', 1.0))
        self._current_idx: Optional[int] = None
        self._source_offset: Optional[float] = None

        self._reference_f: Optional[np.ndarray] = None
        self._reference_v: Optional[np.ndarray] = None
        self._reference_source: str = ""
        self._reference_index: Optional[int] = None
        self._lambda_max_ref: float = np.inf

        # Configurable reference frequency band
        self._ref_freq_range: Tuple[float, float] = (0.0, 9999.0)

        # Severity criteria
        self._clean_threshold: float = 0.95
        self._marginal_threshold: float = 0.85
        self._unknown_action: str = "unknown"
        self._vr_onset_threshold: float = 0.90

    # ── lifecycle ──────────────────────────────────────────────────

    def start_with(self, label: str, thr: float, open_checklist: bool = False):
        self.thr = float(thr)
        try:
            idx = list(self.c.offset_labels).index(label)
        except Exception:
            idx = 0
        self._current_idx = idx
        self._source_offset = parse_source_offset_from_label(label)

    def cancel(self):
        try:
            for lf, lw in list(getattr(self.c, '_nf_point_overlay', {}).values()):
                try:
                    lf.remove(); lw.remove()
                except Exception:
                    pass
            self.c._nf_point_overlay = {}
        except Exception:
            pass
        self._current_idx = None

    def update_threshold(self, thr: float):
        self.thr = float(thr)

    # ── reference curve ───────────────────────────────────────────

    def set_reference_curve(
        self, f_ref: np.ndarray, v_ref: np.ndarray,
        source: str = "custom",
        ref_index: Optional[int] = None,
        lambda_max_ref: float = np.inf,
    ):
        self._reference_f = np.asarray(f_ref, float)
        self._reference_v = np.asarray(v_ref, float)
        self._reference_source = source
        self._reference_index = ref_index
        self._lambda_max_ref = lambda_max_ref

    def clear_reference(self):
        self._reference_f = None
        self._reference_v = None
        self._reference_source = ""
        self._reference_index = None
        self._lambda_max_ref = np.inf

    @property
    def has_reference(self) -> bool:
        return self._reference_f is not None and len(self._reference_f) > 0

    def compute_reference_from_offsets(
        self, mode: str, custom_index: Optional[int] = None,
    ) -> None:
        """Build a reference curve from the loaded offsets.

        mode: 'longest_offset' | 'median' | 'custom_offset'
        custom_index: required when mode == 'custom_offset'
        """
        n_data = min(len(self.c.velocity_arrays), len(self.c.frequency_arrays))
        if n_data == 0:
            return

        labels = self.c.offset_labels[:n_data]
        offsets = []
        for lbl in labels:
            v = parse_source_offset_from_label(lbl)
            offsets.append(v if v is not None else 0.0)

        recv = self._get_array_positions()

        if mode == "longest_offset":
            ref_idx = select_reference_by_largest_xbar(offsets, recv)
        elif mode == "custom_offset" and custom_index is not None:
            ref_idx = int(custom_index)
        else:
            ref_idx = None

        if ref_idx is not None and mode != "median":
            f_ref = np.asarray(self.c.frequency_arrays[ref_idx], float)
            v_ref = np.asarray(self.c.velocity_arrays[ref_idx], float)
            lam_max = compute_lambda_max(offsets[ref_idx], recv, max(self.thr, 1e-12))
            label = labels[ref_idx] if ref_idx < len(labels) else f"Offset {ref_idx}"
            tag = "longest_offset" if mode == "longest_offset" else "custom_offset"
            self.set_reference_curve(
                f_ref, v_ref,
                source=f"{tag} ({label})",
                ref_index=ref_idx,
                lambda_max_ref=lam_max,
            )
        elif mode == "median":
            f_ref, v_ref = compute_composite_reference(
                self.c.frequency_arrays[:n_data],
                self.c.velocity_arrays[:n_data],
                source_offsets=offsets,
                receiver_positions=recv,
                nacd_threshold=max(self.thr, 1e-12),
                method="median",
            )
            self.set_reference_curve(
                f_ref, v_ref,
                source="median across offsets (NF-aware)",
                lambda_max_ref=np.inf,
            )

    def load_reference_file(self, path: str) -> None:
        f_ref, v_ref = load_reference_curve(path)
        self.set_reference_curve(
            f_ref, v_ref, source=path, lambda_max_ref=np.inf,
        )

    # ── configurable criteria ─────────────────────────────────────

    def set_reference_freq_range(self, fmin: float, fmax: float) -> None:
        self._ref_freq_range = (float(fmin), float(fmax))

    def set_severity_criteria(
        self,
        clean_threshold: float = 0.95,
        marginal_threshold: float = 0.85,
        unknown_action: str = "unknown",
        vr_onset_threshold: float = 0.90,
    ) -> None:
        self._clean_threshold = clean_threshold
        self._marginal_threshold = marginal_threshold
        self._unknown_action = unknown_action
        self._vr_onset_threshold = vr_onset_threshold

    def _get_trimmed_reference(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return reference arrays trimmed to the configured freq range."""
        f_ref = self._reference_f
        v_ref = self._reference_v
        fmin, fmax = self._ref_freq_range
        if fmin > 0 or fmax < 9999:
            mask = (f_ref >= fmin) & (f_ref <= fmax)
            if np.any(mask):
                f_ref = f_ref[mask]
                v_ref = v_ref[mask]
        return f_ref, v_ref

    # ── data retrieval ────────────────────────────────────────────

    def get_current_arrays(self):
        """Return (idx, f, v, w, nacd, mask, vr, severity).

        vr and severity are None when no reference curve is set.
        Uses validity masking (lambda_max_reference) for active-offset refs.
        """
        if self._current_idx is None:
            return None
        i = int(self._current_idx)
        v = np.asarray(self.c.velocity_arrays[i], float)
        f = np.asarray(self.c.frequency_arrays[i], float)
        w = np.asarray(self.c.wavelength_arrays[i], float)

        array_pos = self._get_array_positions()
        nacd = compute_nacd_array(array_pos, f, v, source_offset=self._source_offset)
        mask = nacd < self.thr

        vr: Optional[np.ndarray] = None
        severity: Optional[np.ndarray] = None

        if self.has_reference:
            f_ref, v_ref = self._get_trimmed_reference()
            vr = compute_normalized_vr_with_validity(
                f, v, f_ref, v_ref, self._lambda_max_ref,
            )
            severity = classify_nearfield_severity(
                vr, self._clean_threshold, self._marginal_threshold,
                self._unknown_action,
            )

        return i, f, v, w, nacd, mask, vr, severity

    def get_all_offsets_vr(self) -> List[Tuple[str, np.ndarray, np.ndarray]]:
        """Return [(label, nacd, vr)] for every offset -- used by diagnostics scatter."""
        if not self.has_reference:
            return []
        n_data = min(len(self.c.velocity_arrays), len(self.c.frequency_arrays))
        recv = self._get_array_positions()
        f_ref, v_ref = self._get_trimmed_reference()
        results = []
        for idx in range(n_data):
            f = np.asarray(self.c.frequency_arrays[idx], float)
            v = np.asarray(self.c.velocity_arrays[idx], float)
            lbl = self.c.offset_labels[idx] if idx < len(self.c.offset_labels) else f"Offset {idx}"
            so = parse_source_offset_from_label(lbl)
            nacd = compute_nacd_array(recv, f, v, source_offset=so)
            vr = compute_normalized_vr_with_validity(
                f, v, f_ref, v_ref, self._lambda_max_ref,
            )
            results.append((lbl, nacd, vr))
        return results

    def compute_full_report(self) -> List[dict]:
        """Compute a full NF diagnostic report for all offsets."""
        n_data = min(len(self.c.velocity_arrays), len(self.c.frequency_arrays))
        if n_data == 0:
            return []

        labels = self.c.offset_labels[:n_data]
        offsets = []
        for lbl in labels:
            v = parse_source_offset_from_label(lbl)
            offsets.append(v if v is not None else 0.0)

        recv = self._get_array_positions()

        f_ref, v_ref = (self._reference_f, self._reference_v)
        if self.has_reference:
            f_ref, v_ref = self._get_trimmed_reference()

        return compute_nearfield_report(
            self.c.frequency_arrays[:n_data],
            self.c.velocity_arrays[:n_data],
            offsets,
            recv,
            nacd_threshold=max(self.thr, 1e-12),
            vr_threshold=self._vr_onset_threshold,
            reference_index=self._reference_index,
            f_reference=f_ref,
            v_reference=v_ref,
            clean_threshold=self._clean_threshold,
            marginal_threshold=self._marginal_threshold,
            unknown_action=self._unknown_action,
        )

    # ── apply deletions ───────────────────────────────────────────

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
        keep = np.ones_like(v, dtype=bool)
        for j in indices:
            if 0 <= j < keep.size:
                keep[j] = False
        self.c.velocity_arrays[i] = v[keep]
        self.c.frequency_arrays[i] = f[keep]
        self.c.wavelength_arrays[i] = w[keep]
        try:
            from dc_cut.visualization.plot_helpers import set_line_xy
            set_line_xy(self.c.lines_freq[i], self.c.frequency_arrays[i], self.c.velocity_arrays[i])
            set_line_xy(self.c.lines_wave[i], self.c.wavelength_arrays[i], self.c.velocity_arrays[i])
        except Exception:
            pass
        self._clear_overlays()
        try:
            from dc_cut.core.models import LayersModel
            labels = list(self.c.offset_labels[:len(self.c.velocity_arrays)])
            self.c._layers_model = LayersModel.from_arrays(
                self.c.velocity_arrays, self.c.frequency_arrays,
                self.c.wavelength_arrays, labels,
            )
        except Exception:
            pass
        try:
            if bool(getattr(self.c, 'show_average', False)) or bool(getattr(self.c, 'show_average_wave', False)):
                self.c._update_average_line()
            self.c._update_legend()
        except Exception:
            pass
        try:
            self.c._apply_axis_limits()
            self.c.fig.canvas.draw_idle()
        except Exception:
            pass
        try:
            cb = getattr(self.c, 'on_layers_changed', None)
            if cb:
                cb()
        except Exception:
            pass

    # ── helpers ────────────────────────────────────────────────────

    def _get_array_positions(self) -> np.ndarray:
        if hasattr(self.c, 'array_positions'):
            return self.c.array_positions
        try:
            from dc_cut.services.prefs import load_prefs
            P = load_prefs()
            n_phones = int(P.get('default_n_phones', 24))
            dx = float(P.get('default_receiver_dx', 2.0))
            return np.arange(0, dx * n_phones, dx)
        except Exception:
            return np.arange(0, 48, 2.0)

    def _clear_overlays(self):
        try:
            for lf, lw in list(getattr(self.c, '_nf_point_overlay', {}).values()):
                try:
                    lf.remove(); lw.remove()
                except Exception:
                    pass
            self.c._nf_point_overlay = {}
        except Exception:
            pass
