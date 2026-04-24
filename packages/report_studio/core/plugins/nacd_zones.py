"""
NACD Zones (multi-zone) figure plugin — loads a standalone NACD-zone
bundle (.pkl) exported from DC Cut and projects every offset's
DerivedLimitSet into Report Studio's :class:`NFAnalysis` model.

Unlike :mod:`nacd_only` this plugin does **not** recompute anything:
the bundle ships every selected offset's curve, NACD array, mask,
zone indices and DerivedLimitSet ready for rendering. The dispersion
PKL still provides the actual curve geometry; the spectrum NPZ still
provides the spectrogram. The bundle adds the zone overlay layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ..figure_types import FigureTypePlugin, registry
from .. import subplot_types as ST
from ..models import (
    NFAnalysis,
    NFLambdaLine,
    NFLine,
    NFOffsetResult,
    NFZoneArrow,
    NFZoneBand,
    NFZoneSpan,
)


def _line_label(kind: str, role: str, value: float) -> str:
    if kind == "lambda":
        return f"λ / {role} = {value:g} m"
    return f"f / {role} = {value:g} Hz"


def _build_zone_overrides_from_spec(
    zone_spec: Optional[Dict[str, Any]],
) -> tuple[List[NFZoneBand], List[NFZoneArrow], List[NFZoneSpan]]:
    """Materialise per-zone layer overrides from a bundle zone spec.

    Produces one :class:`NFZoneBand` + one :class:`NFZoneArrow` per
    zone per relevant axis (``freq`` when ``draw_freq`` is true,
    ``lambda`` when ``draw_lambda`` is true), plus one
    :class:`NFZoneSpan` per group per axis (for outer-band extension
    controls).  The arrow's ``enabled`` flag mirrors the spec so v1
    bundles stay arrow-free.  Returns empty lists when the spec is
    empty or unusable.
    """
    bands: List[NFZoneBand] = []
    arrows: List[NFZoneArrow] = []
    spans: List[NFZoneSpan] = []
    if not isinstance(zone_spec, dict):
        return bands, arrows, spans
    groups = zone_spec.get("groups") or []
    if not isinstance(groups, list):
        return bands, arrows, spans

    for gi, g in enumerate(groups):
        if not isinstance(g, dict):
            continue
        label_pos = str(g.get("label_position", "top") or "top")
        draw_freq = bool(g.get("draw_freq", True))
        draw_lambda = bool(g.get("draw_lambda", True))
        zones = g.get("zones") or []
        for zi, z in enumerate(zones):
            if not isinstance(z, dict):
                continue
            band_color = str(z.get("band_color", "") or "")
            band_alpha = float(z.get("band_alpha", 0.15) or 0.15)
            point_color = str(z.get("point_color", "") or "")
            zone_label = str(z.get("zone_label", "") or f"Zone {zi + 1}")
            arrow_d = z.get("arrow") if isinstance(z.get("arrow"), dict) else {}
            a_enabled = bool(arrow_d.get("enabled", False))
            a_color = str(arrow_d.get("color", "#C00000") or "#C00000")
            try:
                a_lw = float(arrow_d.get("linewidth", 1.8) or 1.8)
            except (TypeError, ValueError):
                a_lw = 1.8
            try:
                a_y = float(arrow_d.get("y_frac", 0.5) or 0.5)
            except (TypeError, ValueError):
                a_y = 0.5
            a_style = str(arrow_d.get("style", "<->") or "<->")
            a_text = str(arrow_d.get("text", "") or "")
            try:
                a_dy = float(arrow_d.get("text_y_offset", -0.06) or 0.0)
            except (TypeError, ValueError):
                a_dy = -0.06
            try:
                a_fs = int(arrow_d.get("text_fontsize", 11) or 11)
            except (TypeError, ValueError):
                a_fs = 11

            for axis, draw in (("freq", draw_freq), ("lambda", draw_lambda)):
                if not draw:
                    continue
                bands.append(NFZoneBand(
                    group_index=gi, zone_index=zi, axis=axis,
                    band_color=band_color, band_alpha=band_alpha,
                    point_color=point_color,
                    label=zone_label,
                    label_position=label_pos,
                ))
                arrows.append(NFZoneArrow(
                    group_index=gi, zone_index=zi, axis=axis,
                    enabled=a_enabled,
                    color=a_color, linewidth=a_lw, y_frac=a_y,
                    style=a_style, text=a_text,
                    text_y_offset=a_dy, text_fontsize=a_fs,
                ))

        # One NFZoneSpan per group per axis (request 6).
        for axis, draw in (("freq", draw_freq), ("lambda", draw_lambda)):
            if not draw:
                continue
            spans.append(NFZoneSpan(group_index=gi, axis=axis))

    return bands, arrows, spans


class NacdZonesPlugin:
    """Figure type for the multi-zone NACD bundle."""

    @property
    def type_id(self) -> str:
        return "nacd_zones"

    @property
    def display_name(self) -> str:
        return "NACD Zones (multi-zone)"

    @property
    def accepted_subplot_types(self) -> Sequence[str]:
        return (ST.COMBINED, ST.DISPERSION)

    def load_data(
        self,
        pkl_path: str = "",
        npz_path: str = "",
        bundle_path: str = "",
        figure_bundle_path: str = "",
        selected_offsets: Optional[List[str]] = None,
        *,
        layout: str = "single",
        active_offset: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        from ...io.nacd_zone_pkl import read_bundle
        from ...io.pkl_reader import curves_from_state
        from ...io.spectrum_reader import read_spectrum_npz

        # ``figure_bundle_path`` is the unified name used by the new
        # Add-Data dialog; ``bundle_path`` remains the legacy kw so
        # older callers still work. They resolve to the same file.
        effective_bundle = figure_bundle_path or bundle_path

        # Dispersion curves (from the original session PKL).
        curves: List = []
        if pkl_path and Path(pkl_path).exists():
            import pickle
            with open(pkl_path, "rb") as fh:
                state = pickle.load(fh)
            curves = curves_from_state(state)
            if selected_offsets is not None:
                curves = [c for c in curves if c.name in selected_offsets]

        # Spectrum NPZ (optional).
        spectra: List = []
        if npz_path and Path(npz_path).exists():
            try:
                spectra = read_spectrum_npz(npz_path)
            except Exception:
                spectra = []

        # NACD-zone bundle (the new third file).
        bundle = read_bundle(effective_bundle) if effective_bundle else None
        if bundle is None:
            return {
                "curves": curves,
                "spectra": spectra,
                "nf_analyses": [],
                "layout": layout,
                "nacd_zone_spec": None,
                "nacd_bundle": None,
            }

        bundle_offsets = list(bundle.get("offsets") or [])
        if selected_offsets is not None:
            sel = set(selected_offsets)
            bundle_offsets = [o for o in bundle_offsets if o.get("label") in sel]

        # Pick the active offset (defaults to first when unset / unknown).
        active_label = active_offset or (
            bundle_offsets[0].get("label", "") if bundle_offsets else ""
        )
        if active_label not in {o.get("label", "") for o in bundle_offsets}:
            active_label = bundle_offsets[0].get("label", "") if bundle_offsets else ""

        analyses: List[NFAnalysis] = []
        for offset in bundle_offsets:
            lbl = str(offset.get("label", ""))
            so = offset.get("source_offset")
            try:
                so_f = float(so) if so is not None else None
            except (TypeError, ValueError):
                so_f = None
            f_arr = np.asarray(offset.get("frequency", []) or [], float)
            v_arr = np.asarray(offset.get("velocity", []) or [], float)
            nacd_arr = np.asarray(offset.get("nacd", []) or [], float)
            mask = np.asarray(
                offset.get("mask_contaminated", []) or [], bool,
            )
            n_total = int(len(f_arr))
            n_contam = int(np.sum(mask)) if mask.size else 0

            per = NFOffsetResult(
                label=lbl,
                offset_index=0,
                source_offset=so_f,
                x_bar=float(offset.get("x_bar", 0.0)),
                lambda_max=0.0,
                f=f_arr,
                v=v_arr,
                nacd=nacd_arr,
                mask_contaminated=mask,
                n_total=n_total,
                n_clean=n_total - n_contam,
                n_contaminated=n_contam,
            )

            # Project DerivedLimitSet entries into NFLine instances.
            # Skip "zone" entries — those are rendered by the zone-band
            # drawer, not as guide lines.
            derived_lines = list(offset.get("derived_lines") or [])
            lines: List[NFLine] = []
            for d in derived_lines:
                kind = str(d.get("kind", ""))
                if kind not in ("lambda", "freq"):
                    continue
                if not bool(d.get("valid", True)):
                    continue
                value = float(d.get("value", 0.0) or 0.0)
                if value <= 0:
                    continue
                lines.append(NFLine(
                    band_index=int(d.get("band_index", 0)),
                    kind=kind,
                    role=str(d.get("role", "")),
                    value=value,
                    source=str(d.get("source", "derived")),
                    valid=True,
                    derived_from=d.get("derived_from"),
                    custom_label=str(d.get("custom_label", "") or ""),
                    source_offset=so_f,
                    offset_label=lbl,
                    display_label=_line_label(
                        kind, str(d.get("role", "")), value,
                    ),
                ))

            nf = NFAnalysis(
                name=f"NACD Zones — {lbl}" if lbl else "NACD Zones",
                mode="nacd",
                layout=layout,
                per_offset=[per],
                lines=lines,
                visible=(lbl == active_label),
                source_offset=so_f,
                offset_label=lbl,
            )
            analyses.append(nf)

        zone_spec = bundle.get("zone_spec") or None

        # Hydrate first-class zone layer overrides onto every analysis
        # so users can toggle/restyle bands and arrows through the
        # data tree without round-tripping back to DC Cut.  Build
        # independent lists per NFAnalysis so each gets its own
        # dataclass instances (and therefore its own uids).
        if zone_spec:
            for nf in analyses:
                bands, arrows, spans = _build_zone_overrides_from_spec(zone_spec)
                nf.zone_bands = bands
                nf.zone_arrows = arrows
                nf.zone_spans = spans

        return {
            "curves": curves,
            "spectra": spectra,
            "nf_analyses": analyses,
            "layout": layout,
            "nacd_zone_spec": zone_spec,
            "nacd_bundle": bundle,
            "active_offset": active_label,
        }

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
                "key": "active_offset",
                "label": "Active offset (initial)",
                "type": "str",
                "default": "",
                "group": "Display",
            },
        ]


_plugin = NacdZonesPlugin()
registry.register(_plugin)
