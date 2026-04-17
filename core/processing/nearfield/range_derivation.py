"""Auto-derivation of NF limit lines from an ``EvaluationRange``.

Given a user-supplied ``EvaluationRange`` (frequency bands and/or
wavelength bounds) and a dispersion curve ``V(f)`` (from either a
reference curve or the current offset itself), produce a
:class:`DerivedLimitSet` describing every line the UI needs to draw:

* 2 lines per band on the frequency axis (``f_min``, ``f_max``)
* 2 lines per band on the wavelength axis (``\u03bb_min``, ``\u03bb_max``)

Missing members are derived by converting between frequency and
wavelength through the V(f) curve:

* ``\u03bb = V(f) / f``        (given f, interpolate V and divide)
* ``V(f) / f = \u03bb``         (given \u03bb, scan-and-linearly-interp for f)

When the requested value lies outside the curve's support, the
:class:`DerivedLine` is still emitted with ``valid=False`` so the UI
can grey it out and the renderer can skip it.

No framework imports.  Pure computation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple

import numpy as np

from dc_cut.core.processing.nearfield.ranges import EvaluationRange


LineKind = Literal["lambda", "freq"]
LineRole = Literal["min", "max"]
LineSource = Literal["user", "derived"]


@dataclass
class DerivedLine:
    """One draw-able NF limit line."""

    band_index: int
    kind: LineKind
    role: LineRole
    value: float
    source: LineSource
    valid: bool = True
    derived_from: Optional[float] = None

    def key(self) -> Tuple[int, str, str]:
        """Stable key for persistence / visibility state."""
        return (self.band_index, self.kind, self.role)


@dataclass
class DerivedLimitSet:
    """Collection of :class:`DerivedLine` items grouped by band."""

    lines: List[DerivedLine] = field(default_factory=list)

    def by_band(self) -> "dict[int, List[DerivedLine]]":
        out: "dict[int, List[DerivedLine]]" = {}
        for ln in self.lines:
            out.setdefault(ln.band_index, []).append(ln)
        return out

    def lambda_lines(self, valid_only: bool = True) -> List[DerivedLine]:
        return [
            ln for ln in self.lines
            if ln.kind == "lambda" and (ln.valid or not valid_only)
        ]

    def freq_lines(self, valid_only: bool = True) -> List[DerivedLine]:
        return [
            ln for ln in self.lines
            if ln.kind == "freq" and (ln.valid or not valid_only)
        ]

    def band_count(self) -> int:
        if not self.lines:
            return 0
        return max(ln.band_index for ln in self.lines) + 1

    def find(
        self, band_index: int, kind: LineKind, role: LineRole,
    ) -> Optional[DerivedLine]:
        for ln in self.lines:
            if (
                ln.band_index == band_index
                and ln.kind == kind
                and ln.role == role
            ):
                return ln
        return None


# ─── V(f) sampling helpers ──────────────────────────────────────────

def _interp_v_at_f(
    f_curve: np.ndarray, v_curve: np.ndarray, f_query: float,
) -> Tuple[float, bool]:
    """Linear-interp ``V`` at ``f_query``.

    Returns ``(value, valid)``.  ``valid=False`` when the query is
    outside the curve's support.
    """
    f_curve = np.asarray(f_curve, float)
    v_curve = np.asarray(v_curve, float)
    if f_curve.size == 0 or v_curve.size == 0:
        return 0.0, False
    order = np.argsort(f_curve)
    f_sorted = f_curve[order]
    v_sorted = v_curve[order]
    finite = np.isfinite(f_sorted) & np.isfinite(v_sorted) & (v_sorted > 0)
    if not np.any(finite):
        return 0.0, False
    f_sorted = f_sorted[finite]
    v_sorted = v_sorted[finite]
    if f_query < float(f_sorted[0]) - 1e-12 or f_query > float(f_sorted[-1]) + 1e-12:
        return 0.0, False
    v_at = float(np.interp(f_query, f_sorted, v_sorted))
    if not np.isfinite(v_at) or v_at <= 0:
        return 0.0, False
    return v_at, True


def _solve_f_for_lambda(
    f_curve: np.ndarray,
    v_curve: np.ndarray,
    lam_query: float,
    f_lo: Optional[float] = None,
    f_hi: Optional[float] = None,
) -> Tuple[float, bool]:
    """Find ``f`` such that ``V(f)/f == lam_query``.

    Scans the ``V(f)/f - \u03bb`` profile for a sign change, then linearly
    interpolates to locate the root.  If a band window ``(f_lo, f_hi)``
    is given, restricts the scan to that window first.  If no root is
    found, returns the f value that minimises ``|V(f)/f - \u03bb|`` with
    ``valid=False``.
    """
    f_curve = np.asarray(f_curve, float)
    v_curve = np.asarray(v_curve, float)
    if f_curve.size < 2 or v_curve.size < 2:
        return 0.0, False

    order = np.argsort(f_curve)
    f_sorted = f_curve[order]
    v_sorted = v_curve[order]
    finite = (
        np.isfinite(f_sorted) & np.isfinite(v_sorted)
        & (f_sorted > 0) & (v_sorted > 0)
    )
    f_sorted = f_sorted[finite]
    v_sorted = v_sorted[finite]
    if f_sorted.size < 2:
        return 0.0, False

    lam_curve = v_sorted / f_sorted

    # Restrict to band window when provided.
    if f_lo is not None and f_hi is not None and f_hi > f_lo:
        in_band = (f_sorted >= f_lo) & (f_sorted <= f_hi)
        f_search = f_sorted[in_band]
        lam_search = lam_curve[in_band]
    else:
        f_search = f_sorted
        lam_search = lam_curve

    if f_search.size < 2:
        # Fallback to full curve's nearest point.
        j = int(np.argmin(np.abs(lam_curve - lam_query)))
        return float(f_sorted[j]), False

    diff = lam_search - lam_query
    sign = np.sign(diff)
    for k in range(1, diff.size):
        if sign[k] == 0:
            return float(f_search[k]), True
        if sign[k - 1] == 0:
            return float(f_search[k - 1]), True
        if sign[k] != sign[k - 1]:
            d0, d1 = diff[k - 1], diff[k]
            f0, f1 = f_search[k - 1], f_search[k]
            frac = -d0 / (d1 - d0)
            return float(f0 + frac * (f1 - f0)), True

    # No root inside the window -> return closest and mark invalid.
    j = int(np.argmin(np.abs(diff)))
    return float(f_search[j]), False


# ─── public driver ──────────────────────────────────────────────────

def derive_limits(
    eval_range: Optional[EvaluationRange],
    f_curve: Optional[np.ndarray],
    v_curve: Optional[np.ndarray],
) -> DerivedLimitSet:
    """Produce a :class:`DerivedLimitSet` for drawing.

    Behaviour:

    * Each ``(f_lo, f_hi)`` **freq band** becomes one numbered band with
      user-supplied ``f`` lines and derived ``\u03bb`` lines at the two
      edges.
    * Each ``(\u03bb_lo, \u03bb_hi)`` **\u03bb band** becomes one numbered band
      with user-supplied ``\u03bb`` lines and derived ``f`` lines at the two
      edges.
    * When neither band kind is given but the legacy global
      ``\u03bb_min`` / ``\u03bb_max`` are set, a single synthetic band is
      emitted with those user-\u03bb lines plus derived f lines.
    * When ``f_curve``/``v_curve`` are missing or empty, derivations
      are skipped and ``valid=False`` is assigned to derived entries.
    """
    out = DerivedLimitSet()
    if eval_range is None or eval_range.is_empty():
        return out

    fc = np.asarray(f_curve, float) if f_curve is not None else np.asarray([])
    vc = np.asarray(v_curve, float) if v_curve is not None else np.asarray([])
    has_curve = fc.size >= 2 and vc.size >= 2

    freq_bands: List[Tuple[float, float]] = list(eval_range.freq_bands or [])
    lam_bands: List[Tuple[float, float]] = list(eval_range.lambda_bands or [])

    bi = 0
    for (f_lo, f_hi) in freq_bands:
        if f_hi <= f_lo or f_hi <= 0:
            continue
        _emit_band(
            out, band_index=bi, f_lo=f_lo, f_hi=f_hi,
            lam_min=None, lam_max=None,
            f_curve=fc, v_curve=vc, has_curve=has_curve,
        )
        bi += 1

    for (lam_lo, lam_hi) in lam_bands:
        if lam_hi <= lam_lo or lam_hi <= 0:
            continue
        _emit_band_from_lambda_only(
            out, band_index=bi,
            lam_min=lam_lo, lam_max=lam_hi,
            f_curve=fc, v_curve=vc, has_curve=has_curve,
        )
        bi += 1

    # Legacy global λ-only spec (when no explicit bands given).
    if bi == 0:
        lam_min = eval_range.lambda_min if eval_range.lambda_min else None
        lam_max = eval_range.lambda_max if eval_range.lambda_max else None
        if lam_min or lam_max:
            _emit_band_from_lambda_only(
                out, band_index=0,
                lam_min=lam_min, lam_max=lam_max,
                f_curve=fc, v_curve=vc, has_curve=has_curve,
            )

    return out


def _emit_band(
    out: DerivedLimitSet, *,
    band_index: int,
    f_lo: float, f_hi: float,
    lam_min: Optional[float], lam_max: Optional[float],
    f_curve: np.ndarray, v_curve: np.ndarray, has_curve: bool,
) -> None:
    # ── user-supplied f lines ───────────────────────────────────────
    out.lines.append(DerivedLine(
        band_index=band_index, kind="freq", role="min",
        value=float(f_lo), source="user", valid=True,
    ))
    out.lines.append(DerivedLine(
        band_index=band_index, kind="freq", role="max",
        value=float(f_hi), source="user", valid=True,
    ))

    # ── derived \u03bb lines from V(f)/f at the band edges ──────────────
    if has_curve:
        v_lo, ok_lo = _interp_v_at_f(f_curve, v_curve, f_lo)
        v_hi, ok_hi = _interp_v_at_f(f_curve, v_curve, f_hi)
        lam_lo = v_lo / f_lo if ok_lo and f_lo > 0 else 0.0
        lam_hi = v_hi / f_hi if ok_hi and f_hi > 0 else 0.0
        # Larger wavelength is at the lower frequency (usually).
        if lam_lo < lam_hi:
            lam_lo, lam_hi = lam_hi, lam_lo
            ok_lo, ok_hi = ok_hi, ok_lo
            src_lo, src_hi = f_hi, f_lo
        else:
            src_lo, src_hi = f_lo, f_hi
        out.lines.append(DerivedLine(
            band_index=band_index, kind="lambda", role="max",
            value=float(lam_lo), source="derived", valid=ok_lo,
            derived_from=float(src_lo),
        ))
        out.lines.append(DerivedLine(
            band_index=band_index, kind="lambda", role="min",
            value=float(lam_hi), source="derived", valid=ok_hi,
            derived_from=float(src_hi),
        ))
    else:
        out.lines.append(DerivedLine(
            band_index=band_index, kind="lambda", role="max",
            value=0.0, source="derived", valid=False,
            derived_from=float(f_lo),
        ))
        out.lines.append(DerivedLine(
            band_index=band_index, kind="lambda", role="min",
            value=0.0, source="derived", valid=False,
            derived_from=float(f_hi),
        ))

    # ── global \u03bb overrides (if user also gave \u03bb bounds) ─────────────
    if lam_min is not None and lam_min > 0:
        _replace_or_append(out, band_index, "lambda", "min",
                           DerivedLine(
                               band_index=band_index, kind="lambda",
                               role="min", value=float(lam_min),
                               source="user", valid=True,
                           ))
    if lam_max is not None and lam_max > 0:
        _replace_or_append(out, band_index, "lambda", "max",
                           DerivedLine(
                               band_index=band_index, kind="lambda",
                               role="max", value=float(lam_max),
                               source="user", valid=True,
                           ))


def _emit_band_from_lambda_only(
    out: DerivedLimitSet, *,
    band_index: int,
    lam_min: Optional[float], lam_max: Optional[float],
    f_curve: np.ndarray, v_curve: np.ndarray, has_curve: bool,
) -> None:
    """Emit a \u03bb-only band: user \u03bb lines + derived f lines."""
    if lam_min is not None and lam_min > 0:
        out.lines.append(DerivedLine(
            band_index=band_index, kind="lambda", role="min",
            value=float(lam_min), source="user", valid=True,
        ))
        if has_curve:
            f_val, ok = _solve_f_for_lambda(f_curve, v_curve, lam_min)
            out.lines.append(DerivedLine(
                band_index=band_index, kind="freq", role="max",
                value=float(f_val), source="derived", valid=ok,
                derived_from=float(lam_min),
            ))
        else:
            out.lines.append(DerivedLine(
                band_index=band_index, kind="freq", role="max",
                value=0.0, source="derived", valid=False,
                derived_from=float(lam_min),
            ))
    if lam_max is not None and lam_max > 0:
        out.lines.append(DerivedLine(
            band_index=band_index, kind="lambda", role="max",
            value=float(lam_max), source="user", valid=True,
        ))
        if has_curve:
            f_val, ok = _solve_f_for_lambda(f_curve, v_curve, lam_max)
            out.lines.append(DerivedLine(
                band_index=band_index, kind="freq", role="min",
                value=float(f_val), source="derived", valid=ok,
                derived_from=float(lam_max),
            ))
        else:
            out.lines.append(DerivedLine(
                band_index=band_index, kind="freq", role="min",
                value=0.0, source="derived", valid=False,
                derived_from=float(lam_max),
            ))


def _replace_or_append(
    out: DerivedLimitSet,
    band_index: int, kind: LineKind, role: LineRole,
    new_line: DerivedLine,
) -> None:
    for i, ln in enumerate(out.lines):
        if (
            ln.band_index == band_index
            and ln.kind == kind
            and ln.role == role
        ):
            out.lines[i] = new_line
            return
    out.lines.append(new_line)


def derive_limits_from_lambda_values(
    lam_values: List[Tuple[float, Optional[np.ndarray], Optional[np.ndarray]]],
) -> DerivedLimitSet:
    """Build a one-band-per-λ :class:`DerivedLimitSet`.

    For each tuple ``(lam, f_curve, v_curve)`` in ``lam_values`` a new
    band is emitted containing a single ``λ_max`` leaf and (when a
    V(f) curve is supplied) its derived ``f_min`` partner.  Bands
    where ``lam <= 0`` are skipped.

    This helper is the bridge the *no evaluation range* run paths
    (NACD-Only with multiple offsets; Reference with no user range)
    use to push λ_max lines into the Limit Lines tree so the user can
    toggle/recolor them like the range-driven ones.
    """
    out = DerivedLimitSet()
    bi = 0
    for lam, f_curve, v_curve in lam_values:
        if lam is None or lam <= 0 or not np.isfinite(lam):
            continue
        # λ_max itself is the primary user-driven value in the
        # no-range paths (it comes from the NACD λ_max metric, not
        # from a user-entered range).  We flag it as ``source="user"``
        # so the UI shows "(user)" rather than an (invalid) "(derived
        # from …)" label with no partner value attached.
        out.lines.append(DerivedLine(
            band_index=bi, kind="lambda", role="max",
            value=float(lam), source="user", valid=True,
        ))
        fc = np.asarray(f_curve, float) if f_curve is not None else np.asarray([])
        vc = np.asarray(v_curve, float) if v_curve is not None else np.asarray([])
        has_curve = fc.size >= 2 and vc.size >= 2
        if has_curve:
            f_val, ok = _solve_f_for_lambda(fc, vc, float(lam))
            out.lines.append(DerivedLine(
                band_index=bi, kind="freq", role="min",
                value=float(f_val), source="derived", valid=ok,
                derived_from=float(lam),
            ))
        bi += 1
    return out


__all__ = [
    "DerivedLine",
    "DerivedLimitSet",
    "derive_limits",
    "derive_limits_from_lambda_values",
    "LineKind",
    "LineRole",
    "LineSource",
]
