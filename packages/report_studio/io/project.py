"""
Project persistence — save/load SheetState to/from JSON.

Numpy arrays are serialized via base64-encoded binary for compact storage.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np

from ..core.models import (
    SheetState, OffsetCurve, SpectrumData,
    SubplotState, LegendConfig, TypographyConfig,
)


def save_project(sheets: List[SheetState], path: str | Path) -> None:
    """Serialize a list of SheetState objects to a JSON file."""
    path = Path(path)
    data = {"version": 3, "sheets": [_sheet_to_dict(s) for s in sheets]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def load_project(path: str | Path) -> List[SheetState]:
    """Deserialize a list of SheetState from a JSON file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Project file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    version = data.get("version", 1)
    if version not in (2, 3):
        raise ValueError(f"Unsupported project version: {version}")

    return [_dict_to_sheet(sd) for sd in data.get("sheets", [])]


# ── Serialization helpers ─────────────────────────────────────────────

def _ndarray_to_json(arr: Optional[np.ndarray]) -> Optional[Dict]:
    """Encode numpy array as base64 dict."""
    if arr is None or (hasattr(arr, "size") and arr.size == 0):
        return None
    return {
        "dtype": str(arr.dtype),
        "shape": list(arr.shape),
        "data": base64.b64encode(arr.tobytes()).decode("ascii"),
    }


def _json_to_ndarray(d: Optional[Dict]) -> Optional[np.ndarray]:
    """Decode numpy array from base64 dict."""
    if d is None:
        return None
    buf = base64.b64decode(d["data"])
    arr = np.frombuffer(buf, dtype=np.dtype(d["dtype"]))
    return arr.reshape(d["shape"])


def _curve_to_dict(c: OffsetCurve) -> Dict[str, Any]:
    return {
        "uid": c.uid,
        "name": c.name,
        "frequency": _ndarray_to_json(c.frequency),
        "velocity": _ndarray_to_json(c.velocity),
        "wavelength": _ndarray_to_json(c.wavelength),
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
        "point_mask": _ndarray_to_json(c.point_mask),
        "spectrum_uid": c.spectrum_uid,
        "spectrum_visible": c.spectrum_visible,
        "spectrum_cmap": c.spectrum_cmap,
        "spectrum_alpha": c.spectrum_alpha,
        "spectrum_colorbar": c.spectrum_colorbar,
        "spectrum_colorbar_orient": c.spectrum_colorbar_orient,
        "spectrum_colorbar_position": c.spectrum_colorbar_position,
        "spectrum_colorbar_label": c.spectrum_colorbar_label,
    }


def _ndarray_or_empty(result):
    """Return result if it's a non-None array, otherwise an empty array."""
    if result is None:
        return np.array([])
    return result


def _dict_to_curve(d: Dict) -> OffsetCurve:
    return OffsetCurve(
        uid=d["uid"],
        name=d.get("name", ""),
        frequency=_ndarray_or_empty(_json_to_ndarray(d.get("frequency"))),
        velocity=_ndarray_or_empty(_json_to_ndarray(d.get("velocity"))),
        wavelength=_ndarray_or_empty(_json_to_ndarray(d.get("wavelength"))),
        visible=d.get("visible", True),
        color=d.get("color", "#2196F3"),
        line_width=d.get("line_width", 1.5),
        marker_size=d.get("marker_size", 4.0),
        line_style=d.get("line_style", "-"),
        marker_style=d.get("marker_style", "o"),
        line_visible=d.get("line_visible", True),
        marker_visible=d.get("marker_visible", True),
        peak_color=d.get("peak_color", ""),
        peak_outline=d.get("peak_outline", False),
        peak_outline_color=d.get("peak_outline_color", "#000000"),
        peak_outline_width=d.get("peak_outline_width", 1.0),
        subplot_key=d.get("subplot_key", "main"),
        point_mask=_json_to_ndarray(d.get("point_mask")),
        spectrum_uid=d.get("spectrum_uid", ""),
        spectrum_visible=d.get("spectrum_visible", False),
        spectrum_cmap=d.get("spectrum_cmap", "jet"),
        spectrum_alpha=d.get("spectrum_alpha", 0.85),
        spectrum_colorbar=d.get("spectrum_colorbar", False),
        spectrum_colorbar_orient=d.get("spectrum_colorbar_orient", "vertical"),
        spectrum_colorbar_position=d.get("spectrum_colorbar_position", "right"),
        spectrum_colorbar_label=d.get("spectrum_colorbar_label", ""),
    )


def _spectrum_to_dict(s: SpectrumData) -> Dict[str, Any]:
    return {
        "uid": s.uid,
        "offset_name": s.offset_name,
        "frequencies": _ndarray_to_json(s.frequencies),
        "velocities": _ndarray_to_json(s.velocities),
        "power": _ndarray_to_json(s.power),
        "method": s.method,
    }


def _dict_to_spectrum(d: Dict) -> SpectrumData:
    return SpectrumData(
        uid=d["uid"],
        offset_name=d.get("offset_name", ""),
        frequencies=_ndarray_or_empty(_json_to_ndarray(d.get("frequencies"))),
        velocities=_ndarray_or_empty(_json_to_ndarray(d.get("velocities"))),
        power=_ndarray_or_empty(_json_to_ndarray(d.get("power"))),
        method=d.get("method", "unknown"),
    )


def _migrate_nf_uids_project(d: Dict) -> list:
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
        "x_label": sp.x_label,
        "y_label": sp.y_label,
        "legend_visible": sp.legend_visible,
        "legend_position": sp.legend_position,
        "legend_font_size": sp.legend_font_size,
        "legend_frame_on": sp.legend_frame_on,
        "nf_uids": list(getattr(sp, "nf_uids", []) or []),
    }


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
        x_label=d.get("x_label", ""),
        y_label=d.get("y_label", ""),
        legend_visible=d.get("legend_visible"),
        legend_position=d.get("legend_position", ""),
        legend_font_size=d.get("legend_font_size", 0),
        legend_frame_on=d.get("legend_frame_on"),
        nf_uids=_migrate_nf_uids_project(d),
    )


def _sheet_to_dict(sheet: SheetState) -> Dict[str, Any]:
    return {
        "name": sheet.name,
        "curves": {uid: _curve_to_dict(c) for uid, c in sheet.curves.items()},
        "spectra": {uid: _spectrum_to_dict(s) for uid, s in sheet.spectra.items()},
        "subplots": {k: _subplot_to_dict(sp) for k, sp in sheet.subplots.items()},
        "grid_rows": sheet.grid_rows,
        "grid_cols": sheet.grid_cols,
        "col_ratios": sheet.col_ratios,
        "row_ratios": sheet.row_ratios,
        "hspace": sheet.hspace,
        "wspace": sheet.wspace,
        "figure_width": sheet.figure_width,
        "figure_height": sheet.figure_height,
        "canvas_dpi": sheet.canvas_dpi,
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
        },
    }


def _dict_to_sheet(d: Dict) -> SheetState:
    sheet = SheetState.__new__(SheetState)
    sheet.name = d.get("name", "Sheet")
    sheet.curves = {uid: _dict_to_curve(cd) for uid, cd in d.get("curves", {}).items()}
    sheet.spectra = {uid: _dict_to_spectrum(sd) for uid, sd in d.get("spectra", {}).items()}
    sheet.subplots = {k: _dict_to_subplot(spd) for k, spd in d.get("subplots", {}).items()}
    sheet.grid_rows = d.get("grid_rows", 1)
    sheet.grid_cols = d.get("grid_cols", 1)
    sheet.col_ratios = d.get("col_ratios", [1.0])
    sheet.row_ratios = d.get("row_ratios", [1.0])
    sheet.hspace = d.get("hspace", 0.3)
    sheet.wspace = d.get("wspace", 0.3)
    sheet.figure_width = d.get("figure_width", 10.0)
    sheet.figure_height = d.get("figure_height", 7.0)
    sheet.canvas_dpi = d.get("canvas_dpi", 600)

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
        )

    if not sheet.subplots:
        sheet.subplots = {"main": SubplotState(key="main", name="Main")}

    return sheet
