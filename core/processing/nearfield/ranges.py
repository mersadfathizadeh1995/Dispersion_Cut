"""Evaluation ranges for near-field analysis.

Both the NACD-Only and Reference-based NF evaluation modes share the
same user-facing notion of an *evaluation range*: a list of rows where
each row specifies ONE band, either

* a **frequency band** ``(f_min, f_max)`` in Hz, or
* a **wavelength band** ``(λ_min, λ_max)`` in m.

A point ``(f, v)`` with implied wavelength ``λ = v / f`` is kept for
evaluation when it falls inside **any** band (frequency OR wavelength).
When no bands are specified at all, every point is kept.

Legacy global ``lambda_min`` / ``lambda_max`` bounds are still read
from persistence for backward compatibility -- when set, they act as
an additional intersection (AND) filter on top of the band union.

``reference_coverage_warnings`` compares a user-specified range against a
reference curve and returns human-readable warnings when the user asks
for evaluation in a region the reference does not cover.

No framework imports, no controller references.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class EvaluationRange:
    """User-specified domain over which NF evaluation should run."""

    freq_bands: List[Tuple[float, float]] = field(default_factory=list)
    lambda_bands: List[Tuple[float, float]] = field(default_factory=list)
    # Legacy global λ clamp (pre-unified-table persistence).
    lambda_min: Optional[float] = None
    lambda_max: Optional[float] = None

    def is_empty(self) -> bool:
        """True when the range imposes no restriction at all."""
        if self.freq_bands or self.lambda_bands:
            return False
        if self.lambda_min is not None and self.lambda_min > 0:
            return False
        if self.lambda_max is not None and self.lambda_max > 0:
            return False
        return True

    def has_freq_filter(self) -> bool:
        return bool(self.freq_bands)

    def has_lambda_filter(self) -> bool:
        if self.lambda_bands:
            return True
        lo = self.lambda_min if self.lambda_min is not None else 0.0
        hi = self.lambda_max if self.lambda_max is not None else 0.0
        return lo > 0.0 or hi > 0.0

    # ── persistence helpers ──────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "freq_bands": [
                [float(lo), float(hi)] for lo, hi in self.freq_bands
            ],
            "lambda_bands": [
                [float(lo), float(hi)] for lo, hi in self.lambda_bands
            ],
            "lambda_min": (
                None if self.lambda_min is None else float(self.lambda_min)
            ),
            "lambda_max": (
                None if self.lambda_max is None else float(self.lambda_max)
            ),
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "EvaluationRange":
        if not d:
            return cls()

        def _bands(raw) -> List[Tuple[float, float]]:
            out: List[Tuple[float, float]] = []
            for row in raw or []:
                try:
                    lo = float(row[0])
                    hi = float(row[1])
                    if hi > lo and hi > 0:
                        out.append((lo, hi))
                except (TypeError, ValueError, IndexError):
                    continue
            return out

        lmin = d.get("lambda_min")
        lmax = d.get("lambda_max")
        return cls(
            freq_bands=_bands(d.get("freq_bands")),
            lambda_bands=_bands(d.get("lambda_bands")),
            lambda_min=None if lmin in (None, 0, 0.0) else float(lmin),
            lambda_max=None if lmax in (None, 0, 0.0) else float(lmax),
        )


def compute_range_mask(
    f: np.ndarray,
    v: np.ndarray,
    rng: Optional[EvaluationRange],
) -> np.ndarray:
    """Return boolean mask of points that lie inside *rng*.

    ``True`` = keep for evaluation.

    * When ``rng`` is ``None`` or empty, all points are kept.
    * Frequency bands are combined with logical OR (a point that falls
      in ANY band is kept).
    * Wavelength bounds are applied on top as an intersection.
    """
    f = np.asarray(f, float)
    v = np.asarray(v, float)
    if rng is None or rng.is_empty():
        return np.ones_like(f, dtype=bool)

    mask = np.ones_like(f, dtype=bool)
    lam = v / np.maximum(f, 1e-12)

    # Unified band filter: union of freq-bands and lambda-bands.
    if rng.freq_bands or rng.lambda_bands:
        band_mask = np.zeros_like(f, dtype=bool)
        for lo, hi in rng.freq_bands:
            if hi <= lo:
                continue
            band_mask |= (f >= lo) & (f <= hi)
        for lo, hi in rng.lambda_bands:
            if hi <= lo:
                continue
            band_mask |= (lam >= lo) & (lam <= hi)
        mask &= band_mask

    # Legacy global λ clamps (applied as additional AND filter).
    if rng.lambda_min is not None and rng.lambda_min > 0:
        mask &= lam >= rng.lambda_min
    if rng.lambda_max is not None and rng.lambda_max > 0:
        mask &= lam <= rng.lambda_max

    return mask


def _reference_wavelength_range(
    f_ref: np.ndarray, v_ref: np.ndarray
) -> Tuple[float, float]:
    """Return (λ_min, λ_max) spanned by a reference curve."""
    f_ref = np.asarray(f_ref, float)
    v_ref = np.asarray(v_ref, float)
    if f_ref.size == 0 or v_ref.size == 0:
        return 0.0, 0.0
    f_safe = np.maximum(f_ref, 1e-12)
    lam = v_ref / f_safe
    finite = np.isfinite(lam) & (lam > 0)
    if not np.any(finite):
        return 0.0, 0.0
    return float(np.min(lam[finite])), float(np.max(lam[finite]))


def reference_coverage_warnings(
    f_ref: Optional[np.ndarray],
    v_ref: Optional[np.ndarray],
    rng: Optional[EvaluationRange],
) -> List[str]:
    """Return human-readable warnings when *rng* exceeds reference coverage.

    Scenarios handled:

    1. a band is completely outside the reference's frequency coverage
       (`"No reference data for band A–B Hz; ignored."`),
    2. a band is partially outside
       (`"Band A–B Hz only covered up to C Hz; upper points set to unknown."`),
    3. ``rng.lambda_max`` exceeds the reference's own max wavelength,
    4. ``rng.lambda_min`` is below the reference's own min wavelength.

    When no reference is available or the range is empty, an empty list
    is returned.
    """
    warnings: List[str] = []
    if rng is None or rng.is_empty():
        return warnings
    if f_ref is None or v_ref is None:
        return warnings
    f_ref = np.asarray(f_ref, float)
    v_ref = np.asarray(v_ref, float)
    if f_ref.size == 0 or v_ref.size == 0:
        return warnings

    f_ref_min = float(np.min(f_ref))
    f_ref_max = float(np.max(f_ref))
    lam_ref_min, lam_ref_max = _reference_wavelength_range(f_ref, v_ref)

    for lo, hi in rng.freq_bands:
        if hi <= lo:
            continue
        if hi < f_ref_min or lo > f_ref_max:
            warnings.append(
                f"No reference data for band {lo:g}–{hi:g} Hz; ignored."
            )
            continue
        partial_low = lo < f_ref_min
        partial_high = hi > f_ref_max
        if partial_low and partial_high:
            warnings.append(
                f"Band {lo:g}–{hi:g} Hz only covered from "
                f"{f_ref_min:g} Hz to {f_ref_max:g} Hz; points outside "
                f"use V_R=NaN."
            )
        elif partial_low:
            warnings.append(
                f"Band {lo:g}–{hi:g} Hz only covered from {f_ref_min:g} Hz; "
                f"lower points use V_R=NaN."
            )
        elif partial_high:
            warnings.append(
                f"Band {lo:g}–{hi:g} Hz only covered up to {f_ref_max:g} Hz; "
                f"upper points use V_R=NaN."
            )

    if rng.lambda_max is not None and rng.lambda_max > 0 and lam_ref_max > 0:
        if rng.lambda_max > lam_ref_max:
            warnings.append(
                f"λ_max {rng.lambda_max:g} m exceeds reference coverage "
                f"(max {lam_ref_max:g} m); points above use V_R=NaN."
            )

    if rng.lambda_min is not None and rng.lambda_min > 0 and lam_ref_min > 0:
        if rng.lambda_min < lam_ref_min:
            warnings.append(
                f"λ_min {rng.lambda_min:g} m is below reference coverage "
                f"(min {lam_ref_min:g} m); points below use V_R=NaN."
            )

    for lam_lo, lam_hi in rng.lambda_bands:
        if lam_hi <= lam_lo:
            continue
        if lam_ref_max <= 0 or lam_ref_min <= 0:
            continue
        if lam_hi < lam_ref_min or lam_lo > lam_ref_max:
            warnings.append(
                f"No reference data for λ-band {lam_lo:g}–{lam_hi:g} m; "
                f"ignored."
            )
            continue
        if lam_lo < lam_ref_min or lam_hi > lam_ref_max:
            warnings.append(
                f"λ-band {lam_lo:g}–{lam_hi:g} m partially outside "
                f"reference ({lam_ref_min:g}–{lam_ref_max:g} m); outer "
                f"points use V_R=NaN."
            )

    return warnings


__all__ = [
    "EvaluationRange",
    "compute_range_mask",
    "reference_coverage_warnings",
]
