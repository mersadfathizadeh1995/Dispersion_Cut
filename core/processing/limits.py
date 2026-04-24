from __future__ import annotations

import numpy as np
from typing import Dict, Optional


def compute_padded_limits(
    v: np.ndarray,
    f: np.ndarray,
    w: np.ndarray,
    *,
    pad_frac: float = 0.08,
    robust_lower_pct: Optional[float] = None,
    robust_upper_pct: Optional[float] = None,
    clamp_v_max_mult: Optional[float] = None,
) -> Dict[str, float]:
    """Compute auto axis limits with percentage padding.

    Inputs are 1D arrays of visible phase velocity v, frequency f, and
    wavelength w. Returns a dict with keys: ymin, ymax, fmin, fmax, wmin, wmax.

    - NaN and inf are ignored
    - Frequency and wavelength mins are clamped to small positive values
    - Adds a percentage-based padding, with sensible minimum absolute pads
    - When ``clamp_v_max_mult`` is a positive float, the padded ``ymax``
      is clamped to ``clamp_v_max_mult * p99.5(v)`` so a single stray
      high-velocity sample (or guide-curve residue) cannot balloon the
      y-axis. Pass ``None`` or ``0`` to disable (default).
    """
    v = np.asarray(v, float)
    f = np.asarray(f, float)
    w = np.asarray(w, float)

    v = v[np.isfinite(v)]
    f = f[np.isfinite(f) & (f > 0)]
    w = w[np.isfinite(w) & (w > 0)]

    if v.size == 0 or f.size == 0 or w.size == 0:
        raise ValueError("Empty arrays after filtering NaNs")

    # Robust spread via percentiles to reduce impact of outliers
    p_lo = float(robust_lower_pct if robust_lower_pct is not None else 0.5)
    p_hi = float(robust_upper_pct if robust_upper_pct is not None else 99.5)
    p_lo = max(0.0, min(50.0, p_lo))
    p_hi = max(50.0, min(100.0, p_hi))

    def _robust_minmax(arr: np.ndarray) -> tuple[float, float]:
        if arr.size == 0:
            return (0.0, 1.0)
        try:
            lo = float(np.nanpercentile(arr, p_lo))
            hi = float(np.nanpercentile(arr, p_hi))
            if not np.isfinite(lo) or not np.isfinite(hi):
                raise ValueError
            return (lo, hi)
        except Exception:
            return (float(np.nanmin(arr)), float(np.nanmax(arr)))

    vmin, vmax = _robust_minmax(v)
    # For log axes use percentile in log-space, then convert back
    f_pos = f[f > 0]
    w_pos = w[w > 0]
    if f_pos.size:
        fl, fh = _robust_minmax(np.log10(f_pos))
        fmin_data, fmax_data = 10.0 ** fl, 10.0 ** fh
    else:
        fmin_data, fmax_data = (0.1, 1.0)
    if w_pos.size:
        wl, wh = _robust_minmax(np.log10(w_pos))
        wmin_data, wmax_data = 10.0 ** wl, 10.0 ** wh
    else:
        wmin_data, wmax_data = (1.0, 10.0)

    if not np.isfinite(vmin) or not np.isfinite(vmax):
        raise ValueError("Non-finite min/max in velocity array")

    # Handle degenerate ranges by synthesizing a small span
    if vmax <= vmin:
        vmax = vmin + 1.0
    if fmax_data <= fmin_data:
        fmax_data = fmin_data * 1.1 if fmin_data > 0 else 0.1
        if fmax_data <= fmin_data:
            fmax_data = fmin_data + 0.1
    if wmax_data <= wmin_data:
        wmax_data = wmin_data * 1.1 if wmin_data > 0 else 0.1
        if wmax_data <= wmin_data:
            wmax_data = wmin_data + 0.1

    # Percentage padding on Y with stronger floor and symmetric compensation if clamped at 0
    pad_frac_y = max(0.10, float(pad_frac))
    pad_v = max(30.0, (vmax - vmin) * pad_frac_y)
    ymin_raw = vmin - pad_v
    ymax = vmax + pad_v
    if ymin_raw < 0.0:
        # If we clamp bottom at 0, add the lost margin to the top to keep visual headroom
        compensate = -ymin_raw
        ymin = 0.0
        ymax = ymax + compensate
    else:
        ymin = ymin_raw

    # Optional outlier ceiling: keep the top axis sensible when a handful
    # of extreme velocity samples would otherwise stretch the view.
    try:
        mult = float(clamp_v_max_mult) if clamp_v_max_mult else 0.0
    except (TypeError, ValueError):
        mult = 0.0
    if mult > 0.0:
        v_pos = v[np.isfinite(v)]
        if v_pos.size:
            try:
                p = float(np.nanpercentile(v_pos, p_hi))
                ceiling = mult * p
                if np.isfinite(ceiling) and ceiling > ymin:
                    ymax = min(ymax, ceiling)
            except Exception:
                pass

    # Log-scaled X axes (frequency and wavelength): use multiplicative padding
    # to avoid huge empty space toward 0 on a log scale.
    # Use a slightly larger multiplicative padding on the log-scaled axes
    # so data never hugs the boundaries after Home/undo/redo.
    pad_dec = 0.14  # ≈ x1.38 factor on each side for sturdier margins
    factor = 10.0 ** pad_dec
    fmin = max(1e-3, fmin_data / factor)
    fmax = max(fmax_data * factor, fmin * 1.2)

    wmin = max(1e-3, wmin_data / factor)
    wmax = max(wmax_data * factor, wmin * 1.2)

    return {
        'ymin': ymin,
        'ymax': ymax,
        'fmin': fmin,
        'fmax': fmax,
        'wmin': wmin,
        'wmax': wmax,
    }

