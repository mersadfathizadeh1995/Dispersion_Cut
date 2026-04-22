"""
Lightweight directory-based project persistence (v4).

Instead of embedding numpy arrays (which produced 587 MB files),
this format stores only:
  - Source file paths (PKL, NPZ)
  - Data fingerprint (SHA256) for validation
  - All style/config settings per sheet

Project layout::

    my_project/
    ├── project.json          # manifest
    └── sheets/
        ├── Sheet 1.json
        └── Sheet 2.json

On load, curves and spectra are reloaded from original PKL/NPZ files
and matched to saved settings by offset name.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from ..core.models import (
    NFAnalysis,
    NFLine,
    NFOffsetResult,
    NFLambdaLine,
    OffsetCurve,
    SheetState,
    SpectrumData,
    SubplotState,
    LegendConfig,
    TypographyConfig,
)

PROJECT_VERSION = 4


# ── λ guide lines + NF analysis (project v4 extensions) ─────────────────

def _nflambda_line_to_dict(x: NFLambdaLine) -> Dict[str, Any]:
    return {
        "uid": x.uid,
        "lambda_value": x.lambda_value,
        "source_offset": x.source_offset,
        "label": x.label,
        "custom_label": x.custom_label,
        "color": x.color,
        "visible": x.visible,
        "line_style": x.line_style,
        "line_width": x.line_width,
        "alpha": x.alpha,
        "show_label": x.show_label,
        "label_position": float(x.label_position)
        if not isinstance(x.label_position, str) else x.label_position,
        "label_fontsize": x.label_fontsize,
        "label_rotation_mode": x.label_rotation_mode,
        "label_box": x.label_box,
        "label_box_facecolor": x.label_box_facecolor,
        "label_box_alpha": x.label_box_alpha,
        "label_box_edgecolor": x.label_box_edgecolor,
        "label_box_pad": x.label_box_pad,
        "label_scale": float(getattr(x, "label_scale", 1.0)),
        "transform_used": x.transform_used,
    }


def _dict_to_nflambda_line(d: Dict) -> NFLambdaLine:
    pos = d.get("label_position", 0.55)
    try:
        pos_val = float(pos) if not isinstance(pos, str) else pos
    except (TypeError, ValueError):
        pos_val = 0.55
    return NFLambdaLine(
        uid=d.get("uid", ""),
        lambda_value=float(d.get("lambda_value", 0.0)),
        source_offset=d.get("source_offset"),
        label=str(d.get("label", "")),
        custom_label=str(d.get("custom_label", "")),
        color=str(d.get("color", "#000000")),
        visible=bool(d.get("visible", True)),
        line_style=str(d.get("line_style", "--")),
        line_width=float(d.get("line_width", 1.5)),
        alpha=float(d.get("alpha", 0.85)),
        show_label=bool(d.get("show_label", True)),
        label_position=pos_val,
        label_fontsize=int(d.get("label_fontsize", 10)),
        label_rotation_mode=str(d.get("label_rotation_mode", "along")),
        label_box=bool(d.get("label_box", True)),
        label_box_facecolor=str(d.get("label_box_facecolor", "#ffffff")),
        label_box_alpha=float(d.get("label_box_alpha", 0.75)),
        label_box_edgecolor=str(d.get("label_box_edgecolor", "#888888")),
        label_box_pad=float(d.get("label_box_pad", 2.0)),
        label_scale=float(d.get("label_scale", 1.0)),
        transform_used=str(d.get("transform_used", "")),
    )


def _nf_line_to_dict(ln: NFLine) -> Dict[str, Any]:
    return {
        "uid": ln.uid,
        "band_index": ln.band_index,
        "kind": ln.kind,
        "role": ln.role,
        "value": ln.value,
        "source": ln.source,
        "valid": ln.valid,
        "derived_from": ln.derived_from,
        "color": ln.color,
        "visible": ln.visible,
        "line_style": ln.line_style,
        "line_width": ln.line_width,
        "alpha": ln.alpha,
        "show_label": ln.show_label,
        "custom_label": ln.custom_label,
        "label_position": ln.label_position,
        "label_fontsize": ln.label_fontsize,
        "label_rotation_mode": ln.label_rotation_mode,
        "label_box": ln.label_box,
        "label_box_facecolor": ln.label_box_facecolor,
        "label_box_alpha": ln.label_box_alpha,
        "label_box_edgecolor": ln.label_box_edgecolor,
        "label_box_pad": ln.label_box_pad,
        "label_scale": float(getattr(ln, "label_scale", 1.0)),
        "source_offset": ln.source_offset,
        "offset_label": ln.offset_label,
        "display_label": ln.display_label,
        "lambda_max_curve": ln.lambda_max_curve,
    }


def _dict_to_nf_line(d: Dict) -> NFLine:
    df = d.get("derived_from")
    try:
        df_f = None if df in (None, "") else float(df)
    except (TypeError, ValueError):
        df_f = None
    return NFLine(
        uid=d.get("uid", ""),
        band_index=int(d.get("band_index", 0)),
        kind=str(d.get("kind", "lambda")),
        role=str(d.get("role", "max")),
        value=float(d.get("value", 0.0)),
        source=str(d.get("source", "user")),
        valid=bool(d.get("valid", True)),
        derived_from=df_f,
        color=str(d.get("color", "#000000")),
        visible=bool(d.get("visible", True)),
        line_style=str(d.get("line_style", "--")),
        line_width=float(d.get("line_width", 1.5)),
        alpha=float(d.get("alpha", 0.85)),
        show_label=bool(d.get("show_label", True)),
        custom_label=str(d.get("custom_label", "")),
        label_position=d.get("label_position", 0.55),
        label_fontsize=int(d.get("label_fontsize", 0)),
        label_rotation_mode=str(d.get("label_rotation_mode", "along")),
        label_box=bool(d.get("label_box", True)),
        label_box_facecolor=str(d.get("label_box_facecolor", "#ffffff")),
        label_box_alpha=float(d.get("label_box_alpha", 0.75)),
        label_box_edgecolor=str(d.get("label_box_edgecolor", "#888888")),
        label_box_pad=float(d.get("label_box_pad", 2.0)),
        label_scale=float(d.get("label_scale", 1.0)),
        source_offset=d.get("source_offset"),
        offset_label=str(d.get("offset_label", "")),
        display_label=str(d.get("display_label", "")),
        lambda_max_curve=bool(d.get("lambda_max_curve", False)),
    )


def _nf_offset_to_dict(r: NFOffsetResult) -> Dict[str, Any]:
    hidden_indices = []
    if getattr(r, "point_hidden", None) is not None:
        try:
            hidden_indices = np.where(np.asarray(r.point_hidden, dtype=bool))[0].tolist()
        except Exception:
            hidden_indices = []
    return {
        "label": r.label,
        "offset_index": r.offset_index,
        "source_offset": r.source_offset,
        "x_bar": r.x_bar,
        "lambda_max": r.lambda_max,
        "f": r.f.tolist() if r.f is not None and len(r.f) else [],
        "v": r.v.tolist() if r.v is not None and len(r.v) else [],
        "nacd": r.nacd.tolist() if r.nacd is not None and len(r.nacd) else [],
        "mask_contaminated": r.mask_contaminated.tolist()
        if r.mask_contaminated is not None and len(r.mask_contaminated)
        else [],
        "scatter_visible": bool(getattr(r, "scatter_visible", True)),
        "point_hidden_indices": hidden_indices,
        "n_total": r.n_total,
        "n_clean": r.n_clean,
        "n_contaminated": r.n_contaminated,
    }


def _dict_to_nf_offset(d: Dict) -> NFOffsetResult:
    mask = np.asarray(d.get("mask_contaminated", []), dtype=bool)
    f_arr = np.asarray(d.get("f", []), dtype=float)
    hidden = np.zeros(mask.size, dtype=bool)
    for idx in d.get("point_hidden_indices") or []:
        try:
            ii = int(idx)
        except Exception:
            continue
        if 0 <= ii < hidden.size:
            hidden[ii] = True
    return NFOffsetResult(
        label=str(d.get("label", "")),
        offset_index=int(d.get("offset_index", 0)),
        source_offset=d.get("source_offset"),
        x_bar=float(d.get("x_bar", 0.0)),
        lambda_max=float(d.get("lambda_max", 0.0)),
        f=f_arr,
        v=np.asarray(d.get("v", []), dtype=float),
        nacd=np.asarray(d.get("nacd", []), dtype=float),
        mask_contaminated=mask,
        scatter_visible=bool(d.get("scatter_visible", True)),
        point_hidden=hidden if hidden.size else None,
        n_total=int(d.get("n_total", len(f_arr))),
        n_clean=int(d.get("n_clean", 0)),
        n_contaminated=int(d.get("n_contaminated", int(mask.sum()))),
    )


def _nf_analysis_to_dict(nf: NFAnalysis) -> Dict[str, Any]:
    return {
        "uid": nf.uid,
        "name": nf.name,
        "mode": nf.mode,
        "layout": nf.layout,
        "per_offset": [_nf_offset_to_dict(r) for r in nf.per_offset],
        "lines": [_nf_line_to_dict(ln) for ln in nf.lines],
        "severity_palette": dict(nf.severity_palette),
        "show_lambda_max": nf.show_lambda_max,
        "show_user_range": nf.show_user_range,
        "visible": bool(getattr(nf, "visible", True)),
        "severity_overlay_mode": nf.severity_overlay_mode,
        "settings": dict(nf.settings),
        "source_offset": nf.source_offset,
        "offset_label": nf.offset_label,
        "use_range_as_mask": nf.use_range_as_mask,
        "legend_label": getattr(nf, "legend_label", "") or "",
        "contaminated_edge_visible": bool(
            getattr(nf, "contaminated_edge_visible", True)
        ),
        "contaminated_edge_color": str(
            getattr(nf, "contaminated_edge_color", "#000000")
        ),
        "contaminated_edge_width": float(
            getattr(nf, "contaminated_edge_width", 0.5)
        ),
    }


def _dict_to_nf_analysis(d: Dict) -> NFAnalysis:
    pal = {
        "clean": "#1f77b4",
        "marginal": "#ff7f0e",
        "contaminated": "#d62728",
        "unknown": "#888888",
    }
    pal.update(d.get("severity_palette") or {})
    nf = NFAnalysis(
        uid=d.get("uid", ""),
        name=d.get("name", "NACD-Only"),
        mode=d.get("mode", "nacd"),
        layout=d.get("layout", "single"),
        settings=dict(d.get("settings") or {}),
        severity_palette=pal,
        show_lambda_max=bool(d.get("show_lambda_max", True)),
        show_user_range=bool(d.get("show_user_range", True)),
        visible=bool(d.get("visible", True)),
        severity_overlay_mode=d.get("severity_overlay_mode", "scatter_on_top"),
        source_offset=d.get("source_offset"),
        offset_label=str(d.get("offset_label", "")),
        use_range_as_mask=bool(d.get("use_range_as_mask", False)),
        legend_label=str(d.get("legend_label", "")),
        contaminated_edge_visible=bool(
            d.get("contaminated_edge_visible", True)
        ),
        contaminated_edge_color=str(
            d.get("contaminated_edge_color", "#000000")
        ),
        contaminated_edge_width=float(
            d.get("contaminated_edge_width", 0.5)
        ),
    )
    nf.per_offset = [_dict_to_nf_offset(x) for x in d.get("per_offset") or []]
    nf.lines = [_dict_to_nf_line(x) for x in d.get("lines") or []]
    return nf


# ── Fingerprinting ────────────────────────────────────────────────────────

def compute_fingerprint(curves: List[OffsetCurve]) -> str:
    """SHA256 fingerprint from curve labels + array shapes + boundary values."""
    h = hashlib.sha256()
    for c in sorted(curves, key=lambda c: c.name):
        h.update(c.name.encode("utf-8"))
        if c.frequency is not None and len(c.frequency) > 0:
            h.update(str(c.frequency.shape).encode())
            h.update(str(float(c.frequency[0])).encode())
            h.update(str(float(c.frequency[-1])).encode())
    return h.hexdigest()[:16]


# ── Curve settings (NO array data) ───────────────────────────────────────

def _curve_settings_to_dict(c: OffsetCurve) -> Dict[str, Any]:
    """Serialize curve style/config only — no numpy arrays."""
    return {
        "uid": c.uid,
        "name": c.name,
        "visible": c.visible,
        "color": c.color,
        "line_width": c.line_width,
        "marker_size": c.marker_size,
        "line_style": c.line_style,
        "marker_style": c.marker_style,
        "line_visible": c.line_visible,
        "marker_visible": c.marker_visible,
        "peak_color": c.peak_color,
        "peak_outline": c.peak_outline,
        "peak_outline_color": c.peak_outline_color,
        "peak_outline_width": c.peak_outline_width,
        "subplot_key": c.subplot_key,
        "spectrum_uid": c.spectrum_uid,
        "spectrum_visible": c.spectrum_visible,
        "spectrum_cmap": c.spectrum_cmap,
        "spectrum_alpha": c.spectrum_alpha,
        "spectrum_colorbar": c.spectrum_colorbar,
        "spectrum_colorbar_orient": c.spectrum_colorbar_orient,
        "spectrum_colorbar_position": c.spectrum_colorbar_position,
        "spectrum_colorbar_label": c.spectrum_colorbar_label,
        "spectrum_colorbar_scale": float(
            getattr(c, "spectrum_colorbar_scale", 1.0) or 1.0
        ),
        "legend_label": getattr(c, "legend_label", "") or "",
        # Point mask as list of booleans (compact)
        "point_mask": c.point_mask.tolist() if c.point_mask is not None else None,
        "lambda_lines": [_nflambda_line_to_dict(x) for x in c.lambda_lines],
    }


def _apply_curve_settings(curve: OffsetCurve, d: Dict) -> None:
    """Apply saved settings to a reloaded curve (in-place).

    Restores the original UID so that subplot curve_uids and
    aggregated shadow_curve_uids (saved with the old UID) remain valid.
    """
    # Restore original UID so all cross-references stay consistent
    if "uid" in d and d["uid"]:
        curve.uid = d["uid"]

    for key in (
        "visible", "color", "line_width", "marker_size",
        "line_style", "marker_style", "line_visible", "marker_visible",
        "peak_color", "peak_outline", "peak_outline_color", "peak_outline_width",
        "subplot_key",
        "spectrum_uid", "spectrum_visible",
        "spectrum_cmap", "spectrum_alpha", "spectrum_colorbar",
        "spectrum_colorbar_orient", "spectrum_colorbar_position",
        "spectrum_colorbar_label", "spectrum_colorbar_scale",
        "legend_label",
    ):
        if key in d:
            setattr(curve, key, d[key])
    if d.get("point_mask") is not None:
        curve.point_mask = np.array(d["point_mask"], dtype=bool)
    if d.get("lambda_lines") is not None:
        curve.lambda_lines = [
            _dict_to_nflambda_line(x) for x in d["lambda_lines"]
        ]


# ── Subplot serialization ────────────────────────────────────────────────

def _migrate_nf_uids(d: Dict) -> list:
    uids = d.get("nf_uids")
    if uids:
        return [str(u) for u in uids if u]
    legacy = d.get("nf_uid") or ""
    return [legacy] if legacy else []


def _subplot_to_dict(sp: SubplotState) -> Dict[str, Any]:
    return {
        "key": sp.key,
        "name": sp.name,
        "stype": sp.stype,
        "curve_uids": sp.curve_uids,
        "x_domain": sp.x_domain,
        "x_range": list(sp.x_range) if sp.x_range else None,
        "y_range": list(sp.y_range) if sp.y_range else None,
        "auto_x": sp.auto_x,
        "auto_y": sp.auto_y,
        "x_scale": sp.x_scale,
        "y_scale": sp.y_scale,
        "font_family": sp.font_family,
        "title_font_size": sp.title_font_size,
        "axis_label_font_size": sp.axis_label_font_size,
        "tick_label_font_size": sp.tick_label_font_size,
        "x_tick_format": sp.x_tick_format,
        "y_tick_format": sp.y_tick_format,
        "freq_tick_style": getattr(sp, "freq_tick_style", "one-two-five"),
        "freq_custom_ticks": [
            float(v) for v in (getattr(sp, "freq_custom_ticks", None) or [])
        ],
        "x_label": sp.x_label,
        "y_label": sp.y_label,
        "legend_visible": sp.legend_visible,
        "legend_position": sp.legend_position,
        "legend_font_size": sp.legend_font_size,
        "legend_frame_on": sp.legend_frame_on,
        "legend": _legend_to_dict(sp.legend) if getattr(sp, "legend", None) else None,
        "aggregated_uid": sp.aggregated_uid,
        "nf_uids": list(sp.nf_uids),
    }


def _legend_to_dict(lc) -> Dict[str, Any]:
    """Serialize a SubplotLegendConfig."""
    return {
        "visible": bool(lc.visible),
        "location": str(lc.location),
        "placement": str(lc.placement),
        "bbox_anchor": (
            list(lc.bbox_anchor) if lc.bbox_anchor is not None else None
        ),
        "ncol": int(lc.ncol),
        "fontsize": (None if lc.fontsize is None else float(lc.fontsize)),
        "frame_on": bool(lc.frame_on),
        "frame_alpha": float(lc.frame_alpha),
        "shadow": bool(lc.shadow),
        "title": str(lc.title),
        "markerscale": float(lc.markerscale),
        "hidden_labels": list(lc.hidden_labels),
        "adjacent_side": str(lc.adjacent_side),
        "adjacent_target": str(lc.adjacent_target),
        "offset_x": float(lc.offset_x),
        "offset_y": float(lc.offset_y),
        "scale": float(getattr(lc, "scale", 1.0)),
        "orientation": str(getattr(lc, "orientation", "auto")),
        "combine": bool(getattr(lc, "combine", True)),
        "dedupe": bool(getattr(lc, "dedupe", True)),
        "dedupe_kind": str(getattr(lc, "dedupe_kind", "exact")),
        "collapse_curves": bool(getattr(lc, "collapse_curves", False)),
        "curves_label": str(getattr(lc, "curves_label", "Source offset curves")),
        "entry_order": str(getattr(lc, "entry_order", "as_drawn")),
    }


def _dict_to_legend(d: Optional[Dict[str, Any]]):
    """Build a SubplotLegendConfig from dict (returns default on None)."""
    from ..core.models import SubplotLegendConfig
    if not d:
        return SubplotLegendConfig()
    bbox = d.get("bbox_anchor")
    return SubplotLegendConfig(
        visible=bool(d.get("visible", True)),
        location=str(d.get("location", "best")),
        placement=str(d.get("placement", "inside")),
        bbox_anchor=tuple(bbox) if bbox else None,
        ncol=int(d.get("ncol", 1)),
        fontsize=(None if d.get("fontsize") is None
                  else float(d.get("fontsize"))),
        frame_on=bool(d.get("frame_on", True)),
        frame_alpha=float(d.get("frame_alpha", 0.9)),
        shadow=bool(d.get("shadow", False)),
        title=str(d.get("title", "")),
        markerscale=float(d.get("markerscale", 1.0)),
        hidden_labels=list(d.get("hidden_labels", []) or []),
        adjacent_side=str(d.get("adjacent_side", "right")),
        adjacent_target=str(d.get("adjacent_target", "")),
        offset_x=float(d.get("offset_x", 0.0)),
        offset_y=float(d.get("offset_y", 0.0)),
        scale=float(d.get("scale", 1.0)),
        orientation=str(d.get("orientation", "auto")),
        combine=bool(d.get("combine", True)),
        dedupe=bool(d.get("dedupe", True)),
        dedupe_kind=str(d.get("dedupe_kind", "exact")),
        collapse_curves=bool(d.get("collapse_curves", False)),
        curves_label=str(d.get("curves_label", "Source offset curves")),
        entry_order=str(d.get("entry_order", "as_drawn")),
    )


def _dict_to_subplot(d: Dict) -> SubplotState:
    x_range = tuple(d["x_range"]) if d.get("x_range") else None
    y_range = tuple(d["y_range"]) if d.get("y_range") else None
    return SubplotState(
        key=d["key"],
        name=d.get("name", ""),
        stype=d.get("stype", "unset"),
        curve_uids=d.get("curve_uids", []),
        x_domain=d.get("x_domain", "frequency"),
        x_range=x_range,
        y_range=y_range,
        auto_x=d.get("auto_x", True),
        auto_y=d.get("auto_y", True),
        x_scale=d.get("x_scale", "linear"),
        y_scale=d.get("y_scale", "linear"),
        font_family=d.get("font_family", ""),
        title_font_size=d.get("title_font_size", 0),
        axis_label_font_size=d.get("axis_label_font_size", 0),
        tick_label_font_size=d.get("tick_label_font_size", 0),
        x_tick_format=d.get("x_tick_format", "plain"),
        y_tick_format=d.get("y_tick_format", "plain"),
        freq_tick_style=(
            "one-two-five"
            if d.get("freq_tick_style", "one-two-five") == "one_two_five"
            else d.get("freq_tick_style", "one-two-five")
        ),
        freq_custom_ticks=[
            float(v) for v in (d.get("freq_custom_ticks") or [])
        ],
        x_label=d.get("x_label", ""),
        y_label=d.get("y_label", ""),
        legend_visible=d.get("legend_visible"),
        legend_position=d.get("legend_position", ""),
        legend_font_size=d.get("legend_font_size", 0),
        legend_frame_on=d.get("legend_frame_on"),
        legend=_dict_to_legend(d.get("legend")),
        aggregated_uid=d.get("aggregated_uid", ""),
        nf_uids=_migrate_nf_uids(d),
    )


# ── Aggregated curve serialization ────────────────────────────────────────

def _aggregated_to_dict(agg) -> Dict[str, Any]:
    """Serialize AggregatedCurve settings (no array data — recomputed on load)."""
    return {
        "uid": agg.uid,
        "name": agg.name,
        "avg_color": agg.avg_color,
        "avg_line_width": agg.avg_line_width,
        "avg_line_style": agg.avg_line_style,
        "avg_marker_style": agg.avg_marker_style,
        "avg_marker_size": agg.avg_marker_size,
        "avg_visible": agg.avg_visible,
        "uncertainty_mode": agg.uncertainty_mode,
        "uncertainty_alpha": agg.uncertainty_alpha,
        "uncertainty_color": agg.uncertainty_color,
        "uncertainty_visible": agg.uncertainty_visible,
        "shadow_visible": agg.shadow_visible,
        "shadow_alpha": agg.shadow_alpha,
        "shadow_curve_uids": agg.shadow_curve_uids,
        "num_bins": agg.num_bins,
        "log_bias": agg.log_bias,
        "x_domain": agg.x_domain,
        "legend_label": getattr(agg, "legend_label", "") or "",
    }


def _dict_to_aggregated(d: Dict):
    """Reconstruct AggregatedCurve from dict (arrays will be recomputed)."""
    from ..core.models import AggregatedCurve
    import numpy as np

    return AggregatedCurve(
        uid=d["uid"],
        name=d.get("name", "Average"),
        bin_centers=np.array([]),
        avg_vals=np.array([]),
        std_vals=np.array([]),
        avg_color=d.get("avg_color", "#000000"),
        avg_line_width=d.get("avg_line_width", 2.0),
        avg_line_style=d.get("avg_line_style", "-"),
        avg_marker_style=d.get("avg_marker_style", "none"),
        avg_marker_size=d.get("avg_marker_size", 0.0),
        avg_visible=d.get("avg_visible", True),
        uncertainty_mode=d.get("uncertainty_mode", "band"),
        uncertainty_alpha=d.get("uncertainty_alpha", 0.25),
        uncertainty_color=d.get("uncertainty_color", ""),
        uncertainty_visible=d.get("uncertainty_visible", True),
        shadow_visible=d.get("shadow_visible", True),
        shadow_alpha=d.get("shadow_alpha", 0.15),
        shadow_curve_uids=d.get("shadow_curve_uids", []),
        num_bins=d.get("num_bins", 50),
        log_bias=d.get("log_bias", 0.7),
        x_domain=d.get("x_domain", "frequency"),
        legend_label=str(d.get("legend_label", "")),
    )


# ── Sheet serialization ──────────────────────────────────────────────────

def _sheet_to_dict(sheet: SheetState) -> Dict[str, Any]:
    """Serialize a sheet — settings only, no array data."""
    return {
        "name": sheet.name,
        "curves": {uid: _curve_settings_to_dict(c)
                   for uid, c in sheet.curves.items()},
        # Names of curves that were in this sheet at save time.  Used at load
        # time to filter out extra offsets present in the underlying PKL but
        # never added to the sheet by the user.
        "included_curve_names": [c.name for c in sheet.curves.values()],
        "subplots": {k: _subplot_to_dict(sp)
                     for k, sp in sheet.subplots.items()},
        "aggregated": {uid: _aggregated_to_dict(a)
                       for uid, a in sheet.aggregated.items()},
        "grid_rows": sheet.grid_rows,
        "grid_cols": sheet.grid_cols,
        "col_ratios": sheet.col_ratios,
        "row_ratios": sheet.row_ratios,
        "hspace": sheet.hspace,
        "wspace": sheet.wspace,
        "figure_width": sheet.figure_width,
        "figure_height": sheet.figure_height,
        "canvas_dpi": sheet.canvas_dpi,
        "pkl_path": sheet.pkl_path,
        "npz_path": sheet.npz_path,
        "nf_sidecar_path": getattr(sheet, "nf_sidecar_path", "") or "",
        "legend": {
            "visible": sheet.legend.visible,
            "position": sheet.legend.position,
            "font_size": sheet.legend.font_size,
            "frame_on": sheet.legend.frame_on,
            "alpha": sheet.legend.alpha,
        },
        "typography": {
            "base_size": sheet.typography.base_size,
            "title_scale": sheet.typography.title_scale,
            "axis_label_scale": sheet.typography.axis_label_scale,
            "tick_label_scale": sheet.typography.tick_label_scale,
            "legend_scale": sheet.typography.legend_scale,
            "font_family": sheet.typography.font_family,
            "font_weight": getattr(sheet.typography, "font_weight", "normal"),
            "freq_decimals": int(getattr(sheet.typography, "freq_decimals", 1)),
            "lambda_decimals": int(getattr(sheet.typography, "lambda_decimals", 1)),
        },
        "nf_analyses": {
            uid: _nf_analysis_to_dict(nf) for uid, nf in sheet.nf_analyses.items()
        },
        "combined_spectrum_bar": _combined_spectrum_bar_to_dict(
            getattr(sheet, "combined_spectrum_bar", None)
        ),
        "nacd_zone_spec": getattr(sheet, "nacd_zone_spec", None),
    }


def _combined_spectrum_bar_to_dict(cfg) -> Dict[str, Any]:
    """Serialize :class:`CombinedSpectrumBarConfig` (or defaults)."""
    if cfg is None:
        return {
            "enabled": False,
            "placement": "outside_right",
            "orientation": "auto",
            "scale": 1.0,
            "label": "",
            "pad": 0.05,
        }
    return {
        "enabled": bool(getattr(cfg, "enabled", False)),
        "placement": str(getattr(cfg, "placement", "outside_right")),
        "orientation": str(getattr(cfg, "orientation", "auto")),
        "scale": float(getattr(cfg, "scale", 1.0) or 1.0),
        "label": str(getattr(cfg, "label", "") or ""),
        "pad": float(getattr(cfg, "pad", 0.05) or 0.05),
    }


def _dict_to_combined_spectrum_bar(d: Dict):
    from ..core.models import CombinedSpectrumBarConfig
    if not isinstance(d, dict):
        return CombinedSpectrumBarConfig()
    return CombinedSpectrumBarConfig(
        enabled=bool(d.get("enabled", False)),
        placement=str(d.get("placement", "outside_right")),
        orientation=str(d.get("orientation", "auto")),
        scale=float(d.get("scale", 1.0) or 1.0),
        label=str(d.get("label", "") or ""),
        pad=float(d.get("pad", 0.05) or 0.05),
    )


def _dict_to_sheet_skeleton(d: Dict) -> SheetState:
    """Reconstruct SheetState from dict — curves are empty shells (no data)."""
    sheet = SheetState.__new__(SheetState)
    sheet.name = d.get("name", "Sheet")
    sheet.curves = {}  # populated later from reloaded data
    sheet.spectra = {}
    sheet.aggregated = {}  # populated after curves are reloaded
    sheet.subplots = {
        k: _dict_to_subplot(spd)
        for k, spd in d.get("subplots", {}).items()
    }
    sheet.grid_rows = d.get("grid_rows", 1)
    sheet.grid_cols = d.get("grid_cols", 1)
    sheet.col_ratios = d.get("col_ratios", [1.0])
    sheet.row_ratios = d.get("row_ratios", [1.0])
    sheet.hspace = d.get("hspace", 0.3)
    sheet.wspace = d.get("wspace", 0.3)
    sheet.figure_width = d.get("figure_width", 10.0)
    sheet.figure_height = d.get("figure_height", 7.0)
    sheet.canvas_dpi = d.get("canvas_dpi", 600)
    sheet.pkl_path = d.get("pkl_path", "")
    sheet.npz_path = d.get("npz_path", "")
    sheet.nf_sidecar_path = d.get("nf_sidecar_path", "")

    leg_d = d.get("legend", {})
    sheet.legend = LegendConfig(
        visible=leg_d.get("visible", True),
        position=leg_d.get("position", "best"),
        font_size=leg_d.get("font_size", 9),
        frame_on=leg_d.get("frame_on", True),
        alpha=leg_d.get("alpha", 0.8),
    )

    typo_d = d.get("typography", {})
    if typo_d.get("base_size") is not None:
        sheet.typography = TypographyConfig(
            base_size=int(typo_d.get("base_size", 10)),
            title_scale=float(typo_d.get("title_scale", 1.2)),
            axis_label_scale=float(typo_d.get("axis_label_scale", 1.0)),
            tick_label_scale=float(typo_d.get("tick_label_scale", 0.9)),
            legend_scale=float(typo_d.get("legend_scale", 0.9)),
            font_family=str(typo_d.get("font_family", "sans-serif")),
            font_weight=str(typo_d.get("font_weight", "normal")),
            freq_decimals=int(typo_d.get("freq_decimals", 1)),
            lambda_decimals=int(typo_d.get("lambda_decimals", 1)),
        )
    else:
        base = 10
        ts = int(typo_d.get("title_size", 12))
        als = int(typo_d.get("axis_label_size", 10))
        tls = int(typo_d.get("tick_label_size", 9))
        sheet.typography = TypographyConfig(
            base_size=base,
            title_scale=max(0.5, ts / base),
            axis_label_scale=max(0.5, als / base),
            tick_label_scale=max(0.5, tls / base),
            legend_scale=0.9,
            font_family=str(typo_d.get("font_family", "sans-serif")),
            font_weight=str(typo_d.get("font_weight", "normal")),
            freq_decimals=int(typo_d.get("freq_decimals", 1)),
            lambda_decimals=int(typo_d.get("lambda_decimals", 1)),
        )

    if not sheet.subplots:
        sheet.subplots = {"main": SubplotState(key="main", name="Main")}

    # Restore saved aggregated curves (config only — arrays recomputed later)
    for uid, agg_d in d.get("aggregated", {}).items():
        sheet.aggregated[uid] = _dict_to_aggregated(agg_d)

    sheet.nf_analyses = {}
    for uid, nd in d.get("nf_analyses", {}).items():
        sheet.nf_analyses[uid] = _dict_to_nf_analysis(nd)

    sheet.combined_spectrum_bar = _dict_to_combined_spectrum_bar(
        d.get("combined_spectrum_bar", {})
    )
    zone_spec = d.get("nacd_zone_spec")
    sheet.nacd_zone_spec = zone_spec if isinstance(zone_spec, dict) else None
    sheet._last_render_warnings = []

    return sheet


# ── Project-level operations ──────────────────────────────────────────────

def create_project(
    project_dir: str | Path,
    name: str,
    pkl_path: str = "",
    npz_path: str = "",
    fingerprint: str = "",
) -> Path:
    """Create a new project directory with manifest."""
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    sheets_dir = project_dir / "sheets"
    sheets_dir.mkdir(exist_ok=True)

    manifest = {
        "version": PROJECT_VERSION,
        "name": name,
        "data_sources": {
            "pkl_path": str(pkl_path),
            "npz_path": str(npz_path),
            "fingerprint": fingerprint,
        },
        "sheets": [],
    }

    manifest_path = project_dir / "project.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def save_sheet(project_dir: str | Path, sheet: SheetState) -> Path:
    """Save a single sheet to the project's sheets/ directory."""
    project_dir = Path(project_dir)
    sheets_dir = project_dir / "sheets"
    sheets_dir.mkdir(exist_ok=True)

    safe_name = "".join(
        c if c.isalnum() or c in " ._-" else "_" for c in sheet.name
    ).strip() or "sheet"

    sheet_path = sheets_dir / f"{safe_name}.json"
    data = _sheet_to_dict(sheet)
    with open(sheet_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return sheet_path


def save_project(
    project_dir: str | Path,
    sheets: List[SheetState],
    pkl_path: str = "",
    npz_path: str = "",
    fingerprint: str = "",
    name: str = "",
) -> Path:
    """Save entire project: manifest + all sheets."""
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    sheets_dir = project_dir / "sheets"
    sheets_dir.mkdir(exist_ok=True)

    sheet_files = []
    for sheet in sheets:
        sp = save_sheet(project_dir, sheet)
        sheet_files.append(sp.name)

    # Drop orphan sheet JSONs left over from a previous save (e.g. a
    # sheet that was renamed or removed in this session). Keep anything
    # not authored by us so we don't nuke user-placed files.
    keep = set(sheet_files)
    try:
        for entry in sheets_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() == ".json":
                if entry.name not in keep:
                    try:
                        entry.unlink()
                    except OSError:
                        pass
    except OSError:
        pass

    manifest = {
        "version": PROJECT_VERSION,
        "name": name or project_dir.name,
        "data_sources": {
            "pkl_path": str(pkl_path),
            "npz_path": str(npz_path),
            "fingerprint": fingerprint,
        },
        "sheets": sheet_files,
    }

    manifest_path = project_dir / "project.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def load_manifest(project_dir: str | Path) -> Dict[str, Any]:
    """Load the project manifest (does not load sheets)."""
    project_dir = Path(project_dir)
    manifest_path = project_dir / "project.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No project.json in {project_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_sheet_skeleton(
    sheet_path: str | Path,
) -> Tuple[SheetState, Dict, Optional[List[str]]]:
    """Load a sheet skeleton + saved curve settings (no array data).

    Returns ``(sheet, curve_settings_map, included_names)`` where
    ``curve_settings_map`` is ``{curve_name: settings_dict}`` for matching
    to reloaded data, and ``included_names`` is the explicit ordered list of
    curve names that were in the sheet at save time (or ``None`` for very
    old sheets that did not record it).
    """
    sheet_path = Path(sheet_path)
    with open(sheet_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sheet = _dict_to_sheet_skeleton(data)

    # Build name→settings map for matching reloaded curves
    curve_settings = {}
    for uid, cd in data.get("curves", {}).items():
        name = cd.get("name", "")
        curve_settings[name] = cd

    raw_included = data.get("included_curve_names")
    if raw_included is None:
        included_names: Optional[List[str]] = None
    else:
        included_names = [str(n) for n in raw_included]

    return sheet, curve_settings, included_names


def load_project(
    project_dir: str | Path,
) -> Tuple[Dict[str, Any], List[Tuple[SheetState, Dict, Optional[List[str]]]]]:
    """Load project manifest + all sheet skeletons.

    Returns ``(manifest, [(sheet, curve_settings, included_names), ...])``.
    ``included_names`` is the explicit list of curve names saved with the
    sheet (or ``None`` for very old sheets).
    """
    project_dir = Path(project_dir)
    manifest = load_manifest(project_dir)
    sheets_dir = project_dir / "sheets"

    sheets = []
    for fname in manifest.get("sheets", []):
        spath = sheets_dir / fname
        if spath.exists():
            sheets.append(load_sheet_skeleton(spath))

    return manifest, sheets


def reload_and_apply(
    sheet: SheetState,
    curve_settings: Dict[str, Dict],
    curves: List[OffsetCurve],
    spectra: List[SpectrumData],
    *,
    included_names: Optional[Iterable[str]] = None,
) -> None:
    """Reload data arrays into a sheet skeleton and apply saved settings.

    Matches curves by name. Applies saved style settings to matched curves.

    When ``included_names`` is supplied, ONLY curves whose ``name`` appears
    in that collection are added to the sheet. This prevents extra offsets
    that exist in the underlying PKL but were never part of the saved sheet
    from being silently injected on reload. Pass ``None`` (legacy) to keep
    the old behaviour where every curve from the source file is added.
    """
    from ..io.spectrum_reader import normalize_offset

    if included_names is None:
        allowed: Optional[set[str]] = None
    else:
        allowed = {str(n) for n in included_names}

    # Match saved settings to reloaded curves by name
    for curve in curves:
        if allowed is not None and curve.name not in allowed:
            # Skip extras that were not in the saved sheet
            continue
        settings = curve_settings.get(curve.name)
        if settings:
            # Preserve the loaded array data but apply saved styles
            _apply_curve_settings(curve, settings)
            subplot_key = settings.get("subplot_key", "main")
        else:
            subplot_key = "main"

        # Add to sheet
        sheet.curves[curve.uid] = curve
        curve.subplot_key = subplot_key
        if subplot_key in sheet.subplots:
            sp = sheet.subplots[subplot_key]
            if curve.uid not in sp.curve_uids:
                sp.curve_uids.append(curve.uid)

    # Link spectra
    for spec in spectra:
        sheet.spectra[spec.uid] = spec
        spec_norm = normalize_offset(spec.offset_name)
        for c in sheet.curves.values():
            offset_tag = c.name.split("/")[-1].strip()
            curve_norm = normalize_offset(offset_tag)
            if curve_norm == spec_norm:
                c.spectrum_uid = spec.uid
                break

    # Recompute aggregated curves from shadow data
    _restore_aggregated(sheet)


def _restore_aggregated(sheet: SheetState) -> None:
    """Recompute aggregated curve arrays from shadow curves after data reload."""
    from dc_cut.core.processing.averages import (
        compute_binned_avg_std,
        compute_binned_avg_std_wavelength,
    )
    import numpy as np

    for agg in sheet.aggregated.values():
        shadow = [
            sheet.curves[uid]
            for uid in agg.shadow_curve_uids
            if uid in sheet.curves and sheet.curves[uid].has_data
        ]
        if not shadow:
            continue
        all_x, all_y = [], []
        for c in shadow:
            if agg.x_domain == "wavelength" and c.wavelength.size > 0:
                all_x.append(c.wavelength)
            else:
                all_x.append(c.frequency)
            all_y.append(c.velocity)
        if not all_x:
            continue
        x_cat = np.concatenate(all_x)
        y_cat = np.concatenate(all_y)
        if agg.x_domain == "wavelength":
            agg.bin_centers, agg.avg_vals, agg.std_vals = (
                compute_binned_avg_std_wavelength(
                    x_cat, y_cat,
                    num_bins=agg.num_bins, log_bias=agg.log_bias))
        else:
            agg.bin_centers, agg.avg_vals, agg.std_vals = (
                compute_binned_avg_std(
                    x_cat, y_cat,
                    num_bins=agg.num_bins, log_bias=agg.log_bias))


# ── Session auto-save ────────────────────────────────────────────────────

def save_session(
    project_dir: str | Path,
    sheets: List[SheetState],
) -> Path:
    """Auto-save all sheet states to {project}/session/."""
    project_dir = Path(project_dir)
    session_dir = project_dir / "session"
    session_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for i, sheet in enumerate(sheets):
        fname = f"sheet_{i}.json"
        fpath = session_dir / fname
        data = _sheet_to_dict(sheet)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        entries.append({"name": sheet.name, "file": fname})

    manifest = {"sheets": entries}
    manifest_path = session_dir / "session_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def load_session_manifest(
    project_dir: str | Path,
) -> Optional[List[Dict[str, str]]]:
    """Load session manifest entries. Returns None if no session."""
    project_dir = Path(project_dir)
    manifest_path = project_dir / "session" / "session_manifest.json"
    if not manifest_path.exists():
        return None

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("sheets", [])


# ── Sheet-centric persistence (v2.7) ────────────────────────────────────

SHEET_MANIFEST_VERSION = 1


def save_sheet_manifest(
    project_dir: str | Path,
    sheet: SheetState,
    sheet_name: str = "",
) -> Path:
    """Save a single sheet to ``{project}/sheets/{name}/manifest.json``.

    Stores all settings, curve styles, and data source references (pkl/npz).
    The sheet folder can also hold generated data in the future.
    """
    project_dir = Path(project_dir)
    sheets_dir = project_dir / "sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)

    name = sheet_name or sheet.name
    # Sanitize for filesystem
    import re
    safe = re.sub(r'[<>:"/\\|?*]', '_', name).strip() or "sheet"
    sheet_dir = sheets_dir / safe

    # Remove old version if exists
    import shutil
    if sheet_dir.is_dir():
        shutil.rmtree(sheet_dir)
    sheet_dir.mkdir(parents=True, exist_ok=True)

    # Build fingerprint from current curves
    curves_list = list(sheet.curves.values())
    fp = compute_fingerprint(curves_list) if curves_list else ""

    manifest = {
        "_version": SHEET_MANIFEST_VERSION,
        "sheet_name": name,
        "data_sources": {
            "pkl_path": sheet.pkl_path,
            "npz_path": sheet.npz_path,
            "nf_sidecar_path": getattr(sheet, "nf_sidecar_path", "") or "",
            "fingerprint": fp,
        },
        "settings": _sheet_to_dict(sheet),
    }

    manifest_path = sheet_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return sheet_dir


def load_sheet_manifest(
    sheet_folder: str | Path,
) -> Tuple[SheetState, Dict[str, Dict], Dict[str, str], Optional[List[str]]]:
    """Load a sheet from ``{sheet_folder}/manifest.json``.

    Returns ``(sheet_skeleton, curve_settings_map, data_sources, included_names)``.

    - ``sheet_skeleton``: ``SheetState`` with layout/config but no array data.
    - ``curve_settings_map``: ``{curve_name: settings_dict}`` for matching.
    - ``data_sources``: ``{"pkl_path": ..., "npz_path": ..., "fingerprint": ...}``.
    - ``included_names``: explicit list of curve names that were in the sheet
      at save time, or ``None`` for very old sheets that did not record it.
    """
    sheet_folder = Path(sheet_folder)
    manifest_path = sheet_folder / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    settings = manifest.get("settings", {})
    data_sources = manifest.get("data_sources", {})
    sheet_name = manifest.get("sheet_name", sheet_folder.name)

    # Override name in settings dict
    settings["name"] = sheet_name

    sheet = _dict_to_sheet_skeleton(settings)

    # Build name→settings map for matching reloaded curves
    curve_settings: Dict[str, Dict] = {}
    for uid, cd in settings.get("curves", {}).items():
        name = cd.get("name", "")
        curve_settings[name] = cd

    raw_included = settings.get("included_curve_names")
    if raw_included is None:
        included_names: Optional[List[str]] = None
    else:
        included_names = [str(n) for n in raw_included]

    return sheet, curve_settings, data_sources, included_names


def list_sheets(project_dir: str | Path) -> List[Tuple[str, str]]:
    """Return ``[(sheet_name, folder_path), ...]`` for saved sheets.

    Scans ``{project_dir}/sheets/`` for folders containing ``manifest.json``.
    """
    project_dir = Path(project_dir)
    sheets_dir = project_dir / "sheets"
    if not sheets_dir.is_dir():
        return []

    results = []
    for entry in sorted(sheets_dir.iterdir()):
        if not entry.is_dir():
            continue
        manifest = entry / "manifest.json"
        if manifest.is_file():
            try:
                with open(manifest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                name = data.get("sheet_name", entry.name)
            except Exception:
                name = entry.name
            results.append((name, str(entry)))
    return results
