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
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.models import (
    SheetState, OffsetCurve, SpectrumData,
    SubplotState, LegendConfig, TypographyConfig,
)

PROJECT_VERSION = 4


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
        # Point mask as list of booleans (compact)
        "point_mask": c.point_mask.tolist() if c.point_mask is not None else None,
    }


def _apply_curve_settings(curve: OffsetCurve, d: Dict) -> None:
    """Apply saved settings to a reloaded curve (in-place)."""
    for key in (
        "visible", "color", "line_width", "marker_size",
        "line_style", "marker_style", "line_visible", "marker_visible",
        "peak_color", "peak_outline", "peak_outline_color", "peak_outline_width",
        "subplot_key",
        "spectrum_uid", "spectrum_visible",
        "spectrum_cmap", "spectrum_alpha", "spectrum_colorbar",
        "spectrum_colorbar_orient", "spectrum_colorbar_position",
        "spectrum_colorbar_label",
    ):
        if key in d:
            setattr(curve, key, d[key])
    if d.get("point_mask") is not None:
        curve.point_mask = np.array(d["point_mask"], dtype=bool)


# ── Subplot serialization ────────────────────────────────────────────────

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
        "aggregated_uid": sp.aggregated_uid,
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
        aggregated_uid=d.get("aggregated_uid", ""),
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
    )


# ── Sheet serialization ──────────────────────────────────────────────────

def _sheet_to_dict(sheet: SheetState) -> Dict[str, Any]:
    """Serialize a sheet — settings only, no array data."""
    return {
        "name": sheet.name,
        "curves": {uid: _curve_settings_to_dict(c)
                   for uid, c in sheet.curves.items()},
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
    sheet.canvas_dpi = d.get("canvas_dpi", 72)
    sheet.pkl_path = d.get("pkl_path", "")
    sheet.npz_path = d.get("npz_path", "")

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

    # Restore saved aggregated curves (config only — arrays recomputed later)
    for uid, agg_d in d.get("aggregated", {}).items():
        sheet.aggregated[uid] = _dict_to_aggregated(agg_d)

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


def load_sheet_skeleton(sheet_path: str | Path) -> Tuple[SheetState, Dict]:
    """Load a sheet skeleton + saved curve settings (no array data).

    Returns (sheet, curve_settings_map) where curve_settings_map is
    {curve_name: settings_dict} for matching to reloaded data.
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

    return sheet, curve_settings


def load_project(
    project_dir: str | Path,
) -> Tuple[Dict[str, Any], List[Tuple[SheetState, Dict]]]:
    """Load project manifest + all sheet skeletons.

    Returns (manifest, [(sheet, curve_settings), ...])
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
) -> None:
    """Reload data arrays into a sheet skeleton and apply saved settings.

    Matches curves by name. Applies saved style settings to matched curves.
    Unmatched curves from the file are added with default settings.
    """
    from ..io.spectrum_reader import normalize_offset

    # Match saved settings to reloaded curves by name
    for curve in curves:
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
) -> Tuple[SheetState, Dict[str, Dict], Dict[str, str]]:
    """Load a sheet from ``{sheet_folder}/manifest.json``.

    Returns (sheet_skeleton, curve_settings_map, data_sources).
    - sheet_skeleton: SheetState with layout/config but no array data
    - curve_settings_map: {curve_name: settings_dict} for matching
    - data_sources: {"pkl_path": ..., "npz_path": ..., "fingerprint": ...}
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

    return sheet, curve_settings, data_sources


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
