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
    data = {"version": 2, "sheets": [_sheet_to_dict(s) for s in sheets]}
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
    if version != 2:
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
        "subplot_key": c.subplot_key,
        "point_mask": _ndarray_to_json(c.point_mask),
        "spectrum_uid": c.spectrum_uid,
        "spectrum_visible": c.spectrum_visible,
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
        subplot_key=d.get("subplot_key", "main"),
        point_mask=_json_to_ndarray(d.get("point_mask")),
        spectrum_uid=d.get("spectrum_uid", ""),
        spectrum_visible=d.get("spectrum_visible", False),
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
        "legend": {
            "visible": sheet.legend.visible,
            "position": sheet.legend.position,
            "font_size": sheet.legend.font_size,
            "frame_on": sheet.legend.frame_on,
            "alpha": sheet.legend.alpha,
        },
        "typography": {
            "title_size": sheet.typography.title_size,
            "axis_label_size": sheet.typography.axis_label_size,
            "tick_label_size": sheet.typography.tick_label_size,
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

    leg_d = d.get("legend", {})
    sheet.legend = LegendConfig(
        visible=leg_d.get("visible", True),
        position=leg_d.get("position", "best"),
        font_size=leg_d.get("font_size", 9),
        frame_on=leg_d.get("frame_on", True),
        alpha=leg_d.get("alpha", 0.8),
    )

    typo_d = d.get("typography", {})
    sheet.typography = TypographyConfig(
        title_size=typo_d.get("title_size", 12),
        axis_label_size=typo_d.get("axis_label_size", 10),
        tick_label_size=typo_d.get("tick_label_size", 9),
        font_family=typo_d.get("font_family", "sans-serif"),
    )

    if not sheet.subplots:
        sheet.subplots = {"main": SubplotState(key="main", name="Main")}

    return sheet
