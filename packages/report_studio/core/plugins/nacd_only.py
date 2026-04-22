"""
NACD-Only near-field figure plugin — loads embedded NF analysis from PKL
or recomputes from dispersion curves + array geometry.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ..figure_types import FigureTypePlugin, registry
from .. import subplot_types as ST
from ..models import NFAnalysis, NFLambdaLine, NFLine, NFOffsetResult


class NacdOnlyPlugin:
    """Figure type: NACD-Only severity + limit lines (single / grid / aggregated)."""

    @property
    def type_id(self) -> str:
        return "nacd_only"

    @property
    def display_name(self) -> str:
        return "NACD-Only (NF severity)"

    @property
    def accepted_subplot_types(self) -> Sequence[str]:
        return (ST.COMBINED, ST.DISPERSION)

    def load_data(
        self,
        pkl_path: str = "",
        npz_path: str = "",
        selected_offsets: Optional[List[str]] = None,
        *,
        layout: str = "single",
        recompute_if_missing: bool = True,
        receiver_positions: Optional[np.ndarray] = None,
        n_recv: int = 24,
        dx: float = 2.0,
        first_pos: float = 0.0,
        nacd_threshold: float = 1.0,
        eval_range: Optional[dict] = None,
        severity_palette: Optional[dict] = None,
        show_lambda_max: bool = True,
        show_user_range: bool = True,
        severity_overlay_mode: str = "scatter_on_top",
        nf_sidecar_path: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        from ...io.nf_sidecar import merge_into_state, read_sidecar
        from ...io.pkl_reader import (
            curves_from_state,
            read_nf_analysis,
            split_nf_per_offset,
        )
        from ...io.spectrum_reader import read_spectrum_npz

        if not pkl_path or not Path(pkl_path).exists():
            return {"curves": [], "spectra": [], "nf_analyses": [], "layout": layout}

        with open(pkl_path, "rb") as fh:
            state = pickle.load(fh)

        # Optional third-file override: NF evaluation sidecar (JSON)
        # exported from DC Cut. When present, its ``nf_results`` /
        # ``nf_settings`` replace whatever the PKL embedded so the
        # Report Studio figure reflects the explicit DC Cut NF session
        # state (including the full multi-band ``derived_lines`` set).
        sidecar = read_sidecar(nf_sidecar_path) if nf_sidecar_path else None
        if sidecar is not None:
            state = merge_into_state(state, sidecar)

        curves = curves_from_state(state)
        if selected_offsets is not None:
            curves = [c for c in curves if c.name in selected_offsets]

        spectra: List = []
        if npz_path and Path(npz_path).exists():
            try:
                spectra = read_spectrum_npz(npz_path)
            except Exception:
                spectra = []

        nf_list: List[NFAnalysis] = []
        nf = read_nf_analysis(state)
        if nf is not None:
            if selected_offsets is not None:
                sel = set(selected_offsets)
                nf.per_offset = [r for r in nf.per_offset if r.label in sel]
            nf_list = split_nf_per_offset(nf, curves=curves)

        if not nf_list and recompute_if_missing:
            nf_list = self._recompute_nf_list(
                curves,
                state=state,
                n_recv=n_recv,
                dx=dx,
                first_pos=first_pos,
                receiver_positions=receiver_positions,
                nacd_threshold=nacd_threshold,
                eval_range=eval_range,
                show_lambda_max=show_lambda_max,
            )

        for nf_one in nf_list:
            nf_one.layout = layout
            nf_one.show_lambda_max = show_lambda_max
            nf_one.show_user_range = show_user_range
            nf_one.severity_overlay_mode = severity_overlay_mode
            if severity_palette:
                nf_one.severity_palette = {**nf_one.severity_palette, **severity_palette}

        # Pass through the optional NACD zone spec for the caller to
        # attach to the sheet.  Sourced from merge_into_state (so
        # sidecar wins) or from the embedded nf_settings.
        zone_spec = state.get("nacd_zone_spec")
        if not zone_spec:
            nf_set = state.get("nf_settings") or {}
            if isinstance(nf_set, dict):
                zone_spec = nf_set.get("nacd_zone_spec")

        return {
            "curves": curves,
            "spectra": spectra,
            "nf_analyses": nf_list,
            "layout": layout,
            "nacd_zone_spec": zone_spec,
        }

    @staticmethod
    def _resolve_receiver_array(
        state: dict,
        *,
        n_recv: int,
        dx: float,
        first_pos: float,
        receiver_positions: Optional[np.ndarray],
    ) -> np.ndarray:
        if receiver_positions is not None:
            return np.asarray(receiver_positions, dtype=float)
        st = state.get("nf_settings") or {}
        n_recv = int(st.get("n_recv", n_recv))
        dx = float(st.get("dx", dx))
        first_pos = float(st.get("first_pos", first_pos))
        n_recv = max(2, n_recv)
        return np.linspace(
            first_pos, first_pos + dx * (n_recv - 1), n_recv, dtype=float
        )

    def _recompute_nf_list(
        self,
        curves: list,
        *,
        state: dict,
        n_recv: int,
        dx: float,
        first_pos: float,
        receiver_positions: Optional[np.ndarray],
        nacd_threshold: float,
        eval_range: Optional[dict],
        show_lambda_max: bool,
    ) -> List[NFAnalysis]:
        from dc_cut.core.processing.nearfield.nacd import compute_nacd_array
        from dc_cut.core.processing.nearfield.range_derivation import (
            derive_limits,
            derive_limits_from_lambda_values,
        )
        from dc_cut.core.processing.nearfield.ranges import (
            EvaluationRange,
            compute_range_mask,
        )
        from dc_cut.core.processing.wavelength_lines import (
            compute_lambda_max,
            parse_source_offset_from_label,
        )

        st = state.get("nf_settings") or {}
        thr = float(st.get("threshold", nacd_threshold))

        recv = self._resolve_receiver_array(
            state,
            n_recv=n_recv,
            dx=dx,
            first_pos=first_pos,
            receiver_positions=receiver_positions,
        )

        er = EvaluationRange.from_dict(eval_range) if eval_range else EvaluationRange()
        if er.is_empty() and st.get("eval_range"):
            er = EvaluationRange.from_dict(st.get("eval_range"))

        single = len(curves) == 1
        use_range_only = single and not er.is_empty()

        combined_per: List[NFOffsetResult] = []
        lam_triples: List[tuple] = []

        for curve in curves:
            f = np.asarray(curve.frequency, float)
            v = np.asarray(curve.velocity, float)
            lbl = curve.name
            so = parse_source_offset_from_label(lbl)
            nacd = compute_nacd_array(recv, f, v, source_offset=so)
            in_range = compute_range_mask(f, v, er)
            if use_range_only:
                mask = ~in_range
            else:
                mask = nacd < thr
            x_bar = float(
                np.mean(np.abs(recv - (so if so is not None else 0.0)))
            )
            lam_max = (
                float(compute_lambda_max(so or 0.0, recv, thr))
                if so is not None
                else 0.0
            )
            if lam_max <= 0 and so is not None:
                lam_max = float(x_bar / max(thr, 1e-12))

            combined_per.append(
                NFOffsetResult(
                    label=lbl,
                    offset_index=0,
                    source_offset=so,
                    x_bar=x_bar,
                    lambda_max=lam_max,
                    f=f,
                    v=v,
                    nacd=nacd,
                    mask_contaminated=mask,
                    in_range=in_range,
                    n_total=len(f),
                    n_clean=int(len(f) - np.sum(mask)),
                    n_contaminated=int(np.sum(mask)),
                )
            )
            if lam_max > 0:
                lam_triples.append((lam_max, f, v))

        lines_by_curve: Dict[str, List[NFLine]] = {}

        def _lim_label(kind: str, role: str, value: float) -> str:
            if kind == "lambda":
                return f"λ / {role} = {value:g} m"
            return f"f / {role} = {value:g} Hz"

        if single and not er.is_empty() and curves:
            f0 = np.asarray(curves[0].frequency, float)
            v0 = np.asarray(curves[0].velocity, float)
            derived = derive_limits(er, f0, v0)
            lbl0 = curves[0].name
            so0 = parse_source_offset_from_label(lbl0)
            lines_by_curve[lbl0] = [
                NFLine(
                    band_index=ln.band_index,
                    kind=ln.kind,
                    role=ln.role,
                    value=float(ln.value),
                    source=ln.source,
                    valid=ln.valid,
                    derived_from=ln.derived_from,
                    source_offset=so0,
                    offset_label=lbl0,
                    display_label=_lim_label(ln.kind, ln.role, float(ln.value)),
                )
                for ln in derived.lines
            ]
        else:
            for curve in curves:
                f = np.asarray(curve.frequency, float)
                v = np.asarray(curve.velocity, float)
                lbl = curve.name
                so = parse_source_offset_from_label(lbl)
                lam_row = next(
                    (p for p in combined_per if p.label == lbl), None
                )
                lam_max = float(lam_row.lambda_max) if lam_row else 0.0
                if lam_max <= 0 or f.size == 0 or v.size == 0:
                    lines_by_curve[lbl] = []
                    continue
                derived = derive_limits_from_lambda_values([(lam_max, f, v)])
                lines_by_curve[lbl] = [
                    NFLine(
                        band_index=ln.band_index,
                        kind=ln.kind,
                        role=ln.role,
                        value=float(ln.value),
                        source=ln.source,
                        valid=ln.valid,
                        derived_from=ln.derived_from,
                        source_offset=so,
                        offset_label=lbl,
                        display_label=_lim_label(ln.kind, ln.role, float(ln.value)),
                    )
                    for ln in derived.lines
                ]

        settings = {
            "n_recv": int(st.get("n_recv", n_recv)),
            "dx": float(st.get("dx", dx)),
            "first_pos": float(st.get("first_pos", first_pos)),
            "threshold": thr,
            "eval_range": er.to_dict(),
        }
        # Index curves by label for O(1) curve-owned λ lookup below.
        curves_by_label = {getattr(c, "name", ""): c for c in curves}

        analyses: List[NFAnalysis] = []
        for r in combined_per:
            lbl = r.label
            so = r.source_offset
            if so is not None and not isinstance(so, (int, float)):
                try:
                    so = float(so)
                except (TypeError, ValueError):
                    so = None
            elif so is not None:
                so = float(so)
            lines = list(lines_by_curve.get(lbl, []))
            # Promote the recomputed ``lambda_max`` onto the dispersion
            # curve's own λ lines (using the curve's color). This mirrors
            # :func:`_promote_per_offset_lambda_max` for the recompute
            # path so the hyperbola never shows up as a NACD layer.
            if r.lambda_max > 0:
                lam = float(r.lambda_max)
                curve = curves_by_label.get(lbl)
                if curve is not None:
                    already = False
                    for L in (getattr(curve, "lambda_lines", None) or []):
                        try:
                            if abs(float(L.lambda_value) - lam) < 1e-3:
                                already = True
                                break
                        except (TypeError, ValueError):
                            continue
                    if not already:
                        curve.add_lambda_line(
                            NFLambdaLine(
                                lambda_value=lam,
                                source_offset=so,
                                label=lbl,
                                color=(getattr(curve, "color", "") or "#000000"),
                                visible=True,
                                show_label=False,
                            )
                        )
            analyses.append(
                NFAnalysis(
                    uid="",
                    mode="nacd",
                    name="NACD-Only",
                    layout="single",
                    per_offset=[r],
                    lines=lines,
                    show_lambda_max=show_lambda_max,
                    settings=dict(settings),
                    source_offset=so,
                    offset_label=lbl,
                )
            )
        return analyses

    def settings_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "layout",
                "label": "Layout",
                "type": "combo",
                "default": "single",
                "options": ["single", "grid", "aggregated"],
                "group": "Layout",
            },
            {
                "key": "nacd_threshold",
                "label": "NACD threshold",
                "type": "float",
                "default": 1.0,
                "min": 0.1,
                "max": 5.0,
                "group": "Recompute / array geometry",
            },
            {
                "key": "recompute_if_missing",
                "label": "Recompute if PKL has no NF block",
                "type": "bool",
                "default": True,
                "group": "Recompute / array geometry",
            },
            {
                "key": "n_recv",
                "label": "# receivers (recompute)",
                "type": "int",
                "default": 24,
                "min": 2,
                "max": 200,
                "group": "Recompute / array geometry",
            },
            {
                "key": "dx",
                "label": "Receiver spacing dx (m)",
                "type": "float",
                "default": 2.0,
                "min": 0.1,
                "max": 50.0,
                "group": "Recompute / array geometry",
            },
            {
                "key": "first_pos",
                "label": "First receiver (m)",
                "type": "float",
                "default": 0.0,
                "min": -500.0,
                "max": 500.0,
                "group": "Recompute / array geometry",
            },
            {
                "key": "severity_overlay_mode",
                "label": "Severity overlay",
                "type": "combo",
                "default": "scatter_on_top",
                "options": ["scatter_on_top", "off"],
                "group": "Display",
            },
            {
                "key": "show_lambda_max",
                "label": "Draw λ_max hyperbola",
                "type": "bool",
                "default": True,
                "group": "Display",
            },
        ]


_plugin = NacdOnlyPlugin()
registry.register(_plugin)
