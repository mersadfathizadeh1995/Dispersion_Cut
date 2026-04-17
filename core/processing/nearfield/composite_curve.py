"""NF-clean composite dispersion curve builder.

Constructs a composite dispersion curve suitable for inversion input
by only including data from offsets where NACD ≥ threshold at each
frequency bin.  This ensures the composite is free from near-field
contamination.

Rahimi et al. (2022) Section 4.4, practical recommendation.

No framework imports, no controller references.
"""
from __future__ import annotations

from typing import Dict, List, Optional
import numpy as np

from dc_cut.core.processing.nearfield.nacd import compute_nacd
from dc_cut.core.processing.nearfield.criteria import resolve_nacd_threshold


def build_nf_clean_composite_curve(
    frequency_arrays: List[np.ndarray],
    velocity_arrays: List[np.ndarray],
    source_offsets: List[float],
    receiver_positions: np.ndarray,
    *,
    nacd_threshold: Optional[float] = None,
    source_type: str = "sledgehammer",
    error_level: str = "10_15pct",
    transform: Optional[str] = None,
    num_bins: int = 200,
    min_contributors: int = 2,
    log_spaced: bool = True,
) -> Dict[str, np.ndarray]:
    """Build an NF-clean composite dispersion curve for inversion.

    At each frequency bin, only data from offsets where NACD ≥ threshold
    are included.  This produces a composite curve free from near-field
    contamination, suitable as input for VS profile inversion.

    Parameters
    ----------
    frequency_arrays : list of arrays
        Per-offset frequency pick arrays.
    velocity_arrays : list of arrays
        Per-offset velocity pick arrays.
    source_offsets : list of float
        Source offset for each dataset.
    receiver_positions : array
        Receiver positions in the array.
    nacd_threshold : float, optional
        Override NACD threshold.  If None, resolved from source_type.
    source_type, error_level, transform : str
        Passed to ``resolve_nacd_threshold()`` if nacd_threshold is None.
    num_bins : int
        Number of frequency bins for the composite.
    min_contributors : int
        Minimum number of clean offsets required at a bin.
    log_spaced : bool
        Use log-spaced frequency bins (recommended for DC data).

    Returns
    -------
    dict
        ``f`` — bin center frequencies.
        ``v`` — median velocity at each bin.
        ``v_lo``, ``v_hi`` — 16th and 84th percentile bounds.
        ``v_sigma`` — standard deviation at each bin.
        ``n_contributors`` — number of clean offsets contributing per bin.
        ``source_offset_labels`` — list of source offset labels used.
    """
    recv = np.asarray(receiver_positions, float)

    # Resolve threshold
    if nacd_threshold is None:
        nacd_threshold = resolve_nacd_threshold(source_type, error_level, transform)

    # Collect all frequencies to determine bin range
    all_f = np.concatenate([np.asarray(a, float) for a in frequency_arrays])
    all_f = all_f[all_f > 0]
    if all_f.size == 0:
        empty = np.array([])
        return {
            "f": empty, "v": empty, "v_lo": empty, "v_hi": empty,
            "v_sigma": empty, "n_contributors": np.array([], dtype=int),
            "source_offset_labels": [],
        }

    fmin, fmax = float(np.nanmin(all_f)), float(np.nanmax(all_f))
    if log_spaced:
        f_grid = np.geomspace(max(fmin, 0.1), fmax, num_bins)
    else:
        f_grid = np.linspace(fmin, fmax, num_bins)
    df = np.diff(f_grid, prepend=f_grid[0] * 0.9) * 0.5

    v_composite = np.full(num_bins, np.nan)
    v_lo = np.full(num_bins, np.nan)
    v_hi = np.full(num_bins, np.nan)
    v_sigma = np.full(num_bins, np.nan)
    n_contrib = np.zeros(num_bins, dtype=int)

    offset_labels_used = set()

    for k in range(num_bins):
        vals = []
        for i, (fa, va) in enumerate(zip(frequency_arrays, velocity_arrays)):
            fa = np.asarray(fa, float)
            va = np.asarray(va, float)
            # Find picks in this frequency bin
            freq_mask = np.abs(fa - f_grid[k]) < df[k]
            if not np.any(freq_mask):
                continue
            # Check NACD for each pick in bin
            v_at_bin = va[freq_mask]
            f_at_bin = fa[freq_mask]
            clean_in_bin = []
            for j in range(len(v_at_bin)):
                nacd_val = compute_nacd(
                    recv, f_at_bin[j], v_at_bin[j],
                    source_offset=source_offsets[i],
                )
                if nacd_val >= nacd_threshold:
                    clean_in_bin.append(v_at_bin[j])

            if clean_in_bin:
                vals.extend(clean_in_bin)
                offset_labels_used.add(f"{source_offsets[i]:+g} m")
                n_contrib[k] += 1

        if len(vals) >= min_contributors:
            arr = np.array(vals)
            v_composite[k] = float(np.median(arr))
            v_lo[k] = float(np.percentile(arr, 16))
            v_hi[k] = float(np.percentile(arr, 84))
            v_sigma[k] = float(np.std(arr))

    # Keep only bins with data
    valid = np.isfinite(v_composite)
    return {
        "f": f_grid[valid],
        "v": v_composite[valid],
        "v_lo": v_lo[valid],
        "v_hi": v_hi[valid],
        "v_sigma": v_sigma[valid],
        "n_contributors": n_contrib[valid],
        "source_offset_labels": sorted(offset_labels_used),
        "nacd_threshold_used": nacd_threshold,
        "num_bins_total": num_bins,
        "num_bins_valid": int(np.sum(valid)),
    }
