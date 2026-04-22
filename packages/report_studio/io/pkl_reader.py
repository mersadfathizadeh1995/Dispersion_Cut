"""
Read DC Cut .pkl state files → list of OffsetCurve.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.models import (
    CURVE_COLORS,
    NFAnalysis,
    NFLine,
    NFOffsetResult,
    NFLambdaLine,
    OffsetCurve,
)


def _attach_lambda_lines_from_state(curves: List[OffsetCurve], state: dict) -> None:
    """Map ``wavelength_lines_data`` entries onto curves by source offset / label."""
    try:
        from dc_cut.core.processing.wavelength_lines import (
            parse_source_offset_from_label,
        )
    except ImportError:
        return

    wl = state.get("wavelength_lines_data") or []
    if not wl:
        return
    wl_visibility = state.get("wl_visibility") or {}
    wl_colors = state.get("wl_colors") or {}
    wl_show_labels = bool(state.get("wl_show_labels", True))

    def _curve_offset(c: OffsetCurve) -> Optional[float]:
        try:
            return parse_source_offset_from_label(c.name)
        except Exception:
            return None

    for entry in wl:
        label = str(entry.get("label", ""))
        lam = float(entry.get("lambda_max", 0.0) or 0.0)
        if lam <= 0:
            continue
        so = entry.get("source_offset", None)
        if so is not None:
            try:
                so = float(so)
            except (TypeError, ValueError):
                so = None
        if so is None:
            so = parse_source_offset_from_label(label)

        key = label
        # When the PKL doesn't record an explicit color for this label,
        # fall back to the curve's own color so the lambda line matches
        # its dispersion curve instead of defaulting to generic black.
        explicit_color = wl_colors.get(key)
        visible = bool(wl_visibility.get(key, True))

        matched: List[OffsetCurve] = []
        for curve in curves:
            cso = _curve_offset(curve)
            if so is not None and cso is not None and abs(float(cso) - float(so)) < 0.05:
                matched.append(curve)
            elif label and (curve.name == label or label in curve.name):
                matched.append(curve)

        if not matched:
            continue
        for curve in matched:
            color = (
                str(explicit_color)
                if explicit_color
                else (curve.color or "#000000")
            )
            curve.add_lambda_line(
                NFLambdaLine(
                    lambda_value=lam,
                    source_offset=so,
                    label=label,
                    color=color,
                    visible=visible,
                    show_label=wl_show_labels,
                    transform_used=str(entry.get("transform_used", "") or ""),
                )
            )


def _promote_per_offset_lambda_max(curves: List[OffsetCurve], state: dict) -> None:
    """Promote ``nf_results.per_offset.lambda_max`` onto curve ``lambda_lines``.

    The lambda_max hyperbola used to live on the NACD-Only analysis as
    an explicit ``NFLine(lambda_max_curve=True)`` row. The new model is
    that the hyperbola belongs to the dispersion curve it was computed
    for — same color as the curve, listed under the curve's "λ guide
    lines" sub-tab — and never as a NACD layer.

    This helper walks ``state['nf_results']['per_offset']`` after
    :func:`_attach_lambda_lines_from_state` has already applied any
    user-owned ``wavelength_lines_data``. If a curve still has no
    ``NFLambdaLine`` within ``1e-3`` of the PKL's ``lambda_max``, we add
    one using the curve's own color. This way explicit user choices in
    ``wavelength_lines_data`` (colors, labels, visibility) always win
    and promotion only fills the gaps.
    """
    block = state.get("nf_results") or {}
    per = block.get("per_offset") or []
    if not per:
        return

    curves_by_label: Dict[str, OffsetCurve] = {}
    for c in curves:
        if c.name:
            curves_by_label[c.name] = c

    for row in per:
        label = str(row.get("label", ""))
        try:
            lam = float(row.get("lambda_max", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if lam <= 0:
            continue
        curve = curves_by_label.get(label)
        if curve is None:
            continue
        already = False
        for L in (getattr(curve, "lambda_lines", None) or []):
            try:
                if abs(float(L.lambda_value) - lam) < 1e-3:
                    already = True
                    break
            except (TypeError, ValueError):
                continue
        if already:
            continue
        try:
            so = row.get("source_offset", None)
            so_f = float(so) if so is not None else None
        except (TypeError, ValueError):
            so_f = None
        curve.add_lambda_line(
            NFLambdaLine(
                lambda_value=lam,
                source_offset=so_f,
                label=label,
                color=(curve.color or "#000000"),
                visible=True,
                show_label=False,
            )
        )


def read_nf_analysis(state: dict) -> Optional[NFAnalysis]:
    """Deserialize embedded ``nf_results`` / ``nf_settings`` from a DC Cut PKL."""
    block = state.get("nf_results") or {}
    per = block.get("per_offset") or []
    if not block or not per:
        return None

    st = dict(state.get("nf_settings") or {})
    nf = NFAnalysis(
        mode=str(block.get("mode", "nacd")),
        name=str(st.get("name", "NACD-Only")),
        layout="single",
        settings=dict(st),
    )
    # Normalise eval_range so Report Studio round-trips a clean dict (optional).
    try:
        from dc_cut.core.processing.nearfield.ranges import EvaluationRange
    except ImportError:
        EvaluationRange = None  # type: ignore
    er_raw = st.get("eval_range")
    if EvaluationRange is not None and er_raw is not None:
        try:
            nf.settings["eval_range"] = EvaluationRange.from_dict(
                er_raw if isinstance(er_raw, dict) else dict(er_raw)
            ).to_dict()
        except Exception:
            nf.settings["eval_range"] = (
                er_raw if isinstance(er_raw, dict) else dict(er_raw)
            )
    elif er_raw is not None:
        nf.settings["eval_range"] = (
            er_raw if isinstance(er_raw, dict) else dict(er_raw)
        )
    m1c = st.get("mode1_colors") or {}
    if isinstance(m1c, dict):
        pal = dict(nf.severity_palette)
        for k, v in m1c.items():
            if v:
                pal[str(k)] = str(v)
        nf.severity_palette = pal

    for row in per:
        mask = np.asarray(row.get("mask", []), dtype=bool)
        f_arr = np.asarray(row.get("f", []), dtype=float)
        nf.per_offset.append(
            NFOffsetResult(
                label=str(row.get("label", "")),
                offset_index=int(row.get("offset_index", 0)),
                source_offset=row.get("source_offset"),
                x_bar=float(row.get("x_bar", 0.0)),
                lambda_max=float(row.get("lambda_max", 0.0)),
                f=f_arr,
                v=np.asarray(row.get("v", []), dtype=float),
                nacd=np.asarray(row.get("nacd", []), dtype=float),
                mask_contaminated=mask,
                n_total=int(row.get("n_total", len(f_arr))),
                n_clean=int(row.get("n_clean", max(0, len(f_arr) - int(mask.sum())))),
                n_contaminated=int(row.get("n_contaminated", int(mask.sum()))),
            )
        )

    for d in block.get("derived_lines") or []:
        try:
            df = d.get("derived_from")
            df_f = None if df in (None, "") else float(df)
        except (TypeError, ValueError):
            df_f = None
        band_idx = int(d.get("band_index", 0))
        kind = str(d.get("kind", "lambda"))
        role = str(d.get("role", "max"))
        value = float(d.get("value", 0.0))
        # Default the color to DC Cut's band palette when the PKL
        # didn't ship one; that way multi-band tress render with the
        # same distinct per-band hues as in the DC Cut Limit Lines tab.
        raw_color = d.get("color")
        color = str(raw_color) if raw_color else _default_band_color(band_idx)
        nf.lines.append(
            NFLine(
                band_index=band_idx,
                kind=kind,
                role=role,
                value=value,
                source=str(d.get("source", "derived")),
                valid=bool(d.get("valid", True)),
                derived_from=df_f,
                color=color,
                display_label=_nf_line_display_label_parts(kind, role, value),
            )
        )
    return nf


# Mirrors ``dc_cut.gui.views.nf_limits_tab._BAND_PALETTE`` so multi-band
# limit lines show up with the same per-band hues as the DC Cut tree, but
# without importing from the GUI package (which would pull in Qt).
_NF_BAND_PALETTE = (
    "#000000",  # black
    "#4B0082",  # indigo / dark purple
    "#8B0000",  # dark red
    "#006400",  # dark green
    "#B8860B",  # dark goldenrod
    "#2F4F4F",  # dark slate
)


def _default_band_color(band_index: int) -> str:
    return _NF_BAND_PALETTE[int(band_index) % len(_NF_BAND_PALETTE)]


def _nf_line_display_label_parts(kind: str, role: str, value: float) -> str:
    """Label formatted like :func:`_nf_line_display_label` but from raw parts."""
    if kind == "lambda":
        return f"λ / {role} = {value:g} m"
    return f"f / {role} = {value:g} Hz"


def _nf_line_display_label(ln: Any) -> str:
    """Tree label for a limit line from DC Cut derivation."""
    if getattr(ln, "kind", "") == "lambda":
        return f"λ / {ln.role} = {ln.value:g} m"
    return f"f / {ln.role} = {ln.value:g} Hz"


def split_nf_per_offset(
    nf: NFAnalysis,
    curves: Optional[List[Any]] = None,
) -> List[NFAnalysis]:
    """One :class:`NFAnalysis` per source offset (grid / per-subplot linking).

    The ``lambda_max`` hyperbola is no longer emitted as a NACD layer —
    it lives on the dispersion curve (see
    :func:`_promote_per_offset_lambda_max`). The ``curves`` argument is
    kept for backwards compatibility but is no longer consulted.
    """
    del curves  # kept for API compat with older callers
    try:
        from dc_cut.core.processing.nearfield.range_derivation import (
            derive_limits_from_lambda_values,
        )
    except ImportError:
        derive_limits_from_lambda_values = None  # type: ignore

    def _dedupe_key(
        band_index: int, kind: str, role: str, value: float
    ) -> Tuple[int, str, str, float]:
        # Round value so recomputed 3.1415927 and PKL-stored 3.141593 dedupe.
        return (int(band_index), str(kind), str(role), round(float(value), 6))

    out: List[NFAnalysis] = []
    for r in nf.per_offset:
        so = r.source_offset
        if so is not None and not isinstance(so, (int, float)):
            try:
                so = float(so)
            except (TypeError, ValueError):
                so = None
        elif so is not None:
            so = float(so)
        lines: List[NFLine] = []
        seen: set = set()
        # 1. Seed from parent nf.lines (multi-band limits read from the
        #    PKL's ``derived_lines``). PKL data wins over recomputation.
        for parent in nf.lines:
            seeded = NFLine(
                band_index=parent.band_index,
                kind=parent.kind,
                role=parent.role,
                value=float(parent.value),
                source=parent.source,
                valid=parent.valid,
                derived_from=parent.derived_from,
                color=parent.color or _default_band_color(parent.band_index),
                visible=parent.visible,
                line_style=parent.line_style,
                line_width=parent.line_width,
                alpha=parent.alpha,
                show_label=parent.show_label,
                source_offset=so,
                offset_label=r.label,
                display_label=(
                    parent.display_label
                    or _nf_line_display_label_parts(
                        parent.kind, parent.role, float(parent.value)
                    )
                ),
                lambda_max_curve=parent.lambda_max_curve,
            )
            lines.append(seeded)
            seen.add(_dedupe_key(seeded.band_index, seeded.kind, seeded.role, seeded.value))
        # 2. Fall back to recomputing from lambda_max when the PKL has
        #    no derived_lines, and merge any new keys that the seed didn't
        #    already cover (so recomputed entries never shadow PKL lines).
        if (
            derive_limits_from_lambda_values
            and r.lambda_max > 0
            and r.f.size
            and r.v.size
        ):
            try:
                derived = derive_limits_from_lambda_values(
                    [(float(r.lambda_max), r.f, r.v)]
                )
                for ln in derived.lines:
                    key = _dedupe_key(ln.band_index, ln.kind, ln.role, ln.value)
                    if key in seen:
                        continue
                    lines.append(
                        NFLine(
                            band_index=ln.band_index,
                            kind=ln.kind,
                            role=ln.role,
                            value=float(ln.value),
                            source=ln.source,
                            valid=ln.valid,
                            derived_from=ln.derived_from,
                            color=_default_band_color(ln.band_index),
                            source_offset=so,
                            offset_label=r.label,
                            display_label=_nf_line_display_label(ln),
                        )
                    )
                    seen.add(key)
            except Exception:
                pass
        # The per-offset lambda_max hyperbola is no longer emitted as a
        # NACD layer here — it lives on the dispersion curve itself (see
        # :func:`_promote_per_offset_lambda_max`). Legacy projects that
        # still have ``NFLine(lambda_max_curve=True)`` rows survive via
        # the seeding loop above; we simply don't mint fresh ones.
        nf_one = NFAnalysis(
            uid="",
            name=nf.name,
            mode=nf.mode,
            layout=nf.layout,
            per_offset=[r],
            lines=lines,
            severity_palette=dict(nf.severity_palette),
            show_lambda_max=nf.show_lambda_max,
            show_user_range=nf.show_user_range,
            severity_overlay_mode=nf.severity_overlay_mode,
            settings=dict(nf.settings),
            source_offset=so,
            offset_label=r.label,
            use_range_as_mask=getattr(nf, "use_range_as_mask", False),
        )
        out.append(nf_one)
    return out


def curves_from_state(state: dict) -> List[OffsetCurve]:
    """Build :class:`OffsetCurve` list from a decoded DC Cut state dict."""
    velocity_arrays = state.get("velocity_arrays", [])
    frequency_arrays = state.get("frequency_arrays", [])
    wavelength_arrays = state.get("wavelength_arrays", [])
    labels = state.get("offset_labels", [])

    # Fallback for older state format
    if not labels:
        labels = state.get("set_leg", [])
    if isinstance(labels, set):
        labels = sorted(labels)

    n = min(len(velocity_arrays), len(frequency_arrays))
    while len(labels) < n:
        labels.append(f"Offset {len(labels)+1}")

    # Build wavelength if missing
    if not wavelength_arrays or len(wavelength_arrays) < n:
        wavelength_arrays = []
        for i in range(n):
            freq = frequency_arrays[i]
            vel = velocity_arrays[i]
            with np.errstate(divide="ignore", invalid="ignore"):
                wl = np.where(freq > 0, vel / freq, 0.0)
            wavelength_arrays.append(wl)

    curves: List[OffsetCurve] = []
    for i in range(n):
        freq = np.asarray(frequency_arrays[i], dtype=float)
        vel = np.asarray(velocity_arrays[i], dtype=float)
        wl = np.asarray(wavelength_arrays[i], dtype=float)
        label = str(labels[i]) if i < len(labels) else f"Offset {i+1}"

        curve = OffsetCurve(
            name=label,
            frequency=freq,
            velocity=vel,
            wavelength=wl,
            color=CURVE_COLORS[i % len(CURVE_COLORS)],
            subplot_key="main",
        )
        curves.append(curve)

    _attach_lambda_lines_from_state(curves, state)
    _promote_per_offset_lambda_max(curves, state)
    return curves


def read_pkl(path: str | Path) -> List[OffsetCurve]:
    """
    Load a DC Cut state file and return a list of OffsetCurve objects.

    The PKL file contains:
      velocity_arrays, frequency_arrays, wavelength_arrays, offset_labels,
      set_leg, layer_spectrum_settings, ...
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PKL file not found: {path}")

    with open(path, "rb") as fh:
        state = pickle.load(fh)
    return curves_from_state(state)


def read_pkl_metadata(path: str | Path) -> dict:
    """Read just metadata from PKL without full array loading."""
    path = Path(path)
    with open(path, "rb") as fh:
        state = pickle.load(fh)

    labels = state.get("offset_labels", state.get("set_leg", []))
    if isinstance(labels, set):
        labels = sorted(labels)

    n = len(state.get("velocity_arrays", []))
    return {
        "n_offsets": n,
        "labels": list(labels)[:n],
        "has_spectrum_settings": "layer_spectrum_settings" in state,
        "kmin": state.get("kmin"),
        "kmax": state.get("kmax"),
    }
