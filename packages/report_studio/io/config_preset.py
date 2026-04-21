"""Config preset (look-and-feel only) save / apply.

A *config preset* is a small JSON document holding general appearance
settings — typography, legend, NACD palette/overlay defaults, and
per-subplot visual settings — completely decoupled from data.

Use cases:
    * Save your favourite font/sizes/ranges/legend look once and apply
      it to any sheet later.
    * Share a uniform look across projects without copying data files.

The preset NEVER touches ``sheet.curves``, ``sheet.spectra``,
``sheet.aggregated`` or per-offset NACD arrays.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ..core.models import (
    CombinedSpectrumBarConfig,
    LegendConfig,
    SheetState,
    TypographyConfig,
)

CONFIG_PRESET_VERSION = 1


# ── Serialization ────────────────────────────────────────────────────────

def _typography_to_dict(t: TypographyConfig) -> Dict[str, Any]:
    return {
        "base_size": t.base_size,
        "title_scale": t.title_scale,
        "axis_label_scale": t.axis_label_scale,
        "tick_label_scale": t.tick_label_scale,
        "legend_scale": t.legend_scale,
        "font_family": t.font_family,
        "font_weight": getattr(t, "font_weight", "normal"),
        "freq_decimals": int(getattr(t, "freq_decimals", 1)),
        "lambda_decimals": int(getattr(t, "lambda_decimals", 1)),
    }


def _legend_to_dict(leg: LegendConfig) -> Dict[str, Any]:
    return {
        "visible": leg.visible,
        "position": leg.position,
        "font_size": leg.font_size,
        "frame_on": leg.frame_on,
        "alpha": leg.alpha,
    }


def _combined_spectrum_bar_to_dict(cfg: CombinedSpectrumBarConfig) -> Dict[str, Any]:
    if cfg is None:
        cfg = CombinedSpectrumBarConfig()
    return {
        "enabled": bool(cfg.enabled),
        "placement": str(cfg.placement),
        "orientation": str(cfg.orientation),
        "scale": float(cfg.scale),
        "label": str(cfg.label),
        "pad": float(cfg.pad),
    }


def _apply_combined_spectrum_bar(sheet: SheetState, d: Dict[str, Any]) -> None:
    """Apply combined-bar preset values to ``sheet`` in-place."""
    if not d:
        return
    cfg = getattr(sheet, "combined_spectrum_bar", None)
    if cfg is None:
        cfg = CombinedSpectrumBarConfig()
        sheet.combined_spectrum_bar = cfg
    if "enabled" in d:
        cfg.enabled = bool(d["enabled"])
    if "placement" in d:
        cfg.placement = str(d["placement"])
    if "orientation" in d:
        cfg.orientation = str(d["orientation"])
    if "scale" in d:
        try:
            cfg.scale = float(d["scale"])
        except (TypeError, ValueError):
            pass
    if "label" in d:
        cfg.label = str(d["label"])
    if "pad" in d:
        try:
            cfg.pad = float(d["pad"])
        except (TypeError, ValueError):
            pass


def _nacd_defaults_from_sheet(sheet: SheetState) -> Dict[str, Any]:
    """Pick the first NF analysis as a representative palette/style.

    Falls back to the dataclass defaults when no NACD layers exist so the
    preset is still useful on bare sheets.
    """
    nf = next(iter(sheet.nf_analyses.values()), None)
    if nf is None:
        return {
            "severity_palette": {
                "clean": "#1f77b4",
                "marginal": "#ff7f0e",
                "contaminated": "#d62728",
                "unknown": "#888888",
            },
            "severity_overlay_mode": "scatter_on_top",
            "show_lambda_max": True,
            "use_range_as_mask": False,
            "contaminated_edge_visible": True,
            "contaminated_edge_color": "#000000",
            "contaminated_edge_width": 0.5,
        }
    return {
        "severity_palette": dict(nf.severity_palette),
        "severity_overlay_mode": nf.severity_overlay_mode,
        "show_lambda_max": bool(nf.show_lambda_max),
        "use_range_as_mask": bool(nf.use_range_as_mask),
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


def _subplot_visuals_to_dict(sp) -> Dict[str, Any]:
    """Capture visual-only fields of a subplot (no curve_uids/nf_uids)."""
    return {
        "x_domain": sp.x_domain,
        "x_range": list(sp.x_range) if sp.x_range else None,
        "y_range": list(sp.y_range) if sp.y_range else None,
        "auto_x": bool(sp.auto_x),
        "auto_y": bool(sp.auto_y),
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
        "legend": _subplot_legend_to_dict(getattr(sp, "legend", None)),
    }


def _subplot_legend_to_dict(lc) -> Dict[str, Any] | None:
    """Serialize SubplotLegendConfig (visual-only)."""
    if lc is None:
        return None
    return {
        "visible": bool(lc.visible),
        "location": str(lc.location),
        "placement": str(lc.placement),
        "ncol": int(lc.ncol),
        "fontsize": (None if lc.fontsize is None else float(lc.fontsize)),
        "frame_on": bool(lc.frame_on),
        "frame_alpha": float(lc.frame_alpha),
        "shadow": bool(lc.shadow),
        "title": str(lc.title),
        "markerscale": float(lc.markerscale),
        "hidden_labels": list(lc.hidden_labels),
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


def _apply_subplot_legend(target_lc, d: Dict[str, Any]) -> None:
    """Apply preset values to an existing SubplotLegendConfig in-place."""
    if not d or target_lc is None:
        return
    for attr in (
        "visible", "frame_on", "shadow", "combine", "dedupe",
        "collapse_curves",
    ):
        if attr in d:
            setattr(target_lc, attr, bool(d[attr]))
    for attr in ("location", "placement", "title", "orientation",
                 "dedupe_kind", "curves_label", "entry_order"):
        if attr in d:
            setattr(target_lc, attr, str(d[attr]))
    if "ncol" in d:
        target_lc.ncol = int(d["ncol"])
    for attr in ("frame_alpha", "markerscale", "offset_x", "offset_y",
                 "scale"):
        if attr in d:
            setattr(target_lc, attr, float(d[attr]))
    if "fontsize" in d:
        v = d["fontsize"]
        target_lc.fontsize = None if v is None else float(v)
    if "hidden_labels" in d and isinstance(d["hidden_labels"], list):
        target_lc.hidden_labels = [str(x) for x in d["hidden_labels"]]


def build_preset(sheet: SheetState) -> Dict[str, Any]:
    """Return a JSON-friendly dict capturing only look-and-feel settings."""
    return {
        "_version": CONFIG_PRESET_VERSION,
        "kind": "report_studio.config_preset",
        "typography": _typography_to_dict(sheet.typography),
        "legend": _legend_to_dict(sheet.legend),
        "figure": {
            "figure_width": sheet.figure_width,
            "figure_height": sheet.figure_height,
            "canvas_dpi": sheet.canvas_dpi,
            "hspace": sheet.hspace,
            "wspace": sheet.wspace,
        },
        "nacd_defaults": _nacd_defaults_from_sheet(sheet),
        "combined_spectrum_bar": _combined_spectrum_bar_to_dict(
            getattr(sheet, "combined_spectrum_bar", None)
        ),
        "subplot_visuals": {
            k: _subplot_visuals_to_dict(sp) for k, sp in sheet.subplots.items()
        },
    }


def save_config(path: str | Path, sheet: SheetState) -> Path:
    """Write a config preset JSON file derived from ``sheet``."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = build_preset(sheet)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return p


# ── Application ──────────────────────────────────────────────────────────

def _apply_typography(sheet: SheetState, d: Dict[str, Any]) -> None:
    if not d:
        return
    t = sheet.typography
    if "base_size" in d:
        t.base_size = int(d["base_size"])
    if "title_scale" in d:
        t.title_scale = float(d["title_scale"])
    if "axis_label_scale" in d:
        t.axis_label_scale = float(d["axis_label_scale"])
    if "tick_label_scale" in d:
        t.tick_label_scale = float(d["tick_label_scale"])
    if "legend_scale" in d:
        t.legend_scale = float(d["legend_scale"])
    if "font_family" in d:
        t.font_family = str(d["font_family"])
    if "font_weight" in d and hasattr(t, "font_weight"):
        t.font_weight = str(d["font_weight"])
    if "freq_decimals" in d and hasattr(t, "freq_decimals"):
        t.freq_decimals = int(d["freq_decimals"])
    if "lambda_decimals" in d and hasattr(t, "lambda_decimals"):
        t.lambda_decimals = int(d["lambda_decimals"])


def _apply_legend(sheet: SheetState, d: Dict[str, Any]) -> None:
    if not d:
        return
    leg = sheet.legend
    if "visible" in d:
        leg.visible = bool(d["visible"])
    if "position" in d:
        leg.position = str(d["position"])
    if "font_size" in d:
        leg.font_size = int(d["font_size"])
    if "frame_on" in d:
        leg.frame_on = bool(d["frame_on"])
    if "alpha" in d:
        leg.alpha = float(d["alpha"])


def _apply_figure(sheet: SheetState, d: Dict[str, Any]) -> None:
    if not d:
        return
    if "figure_width" in d:
        sheet.figure_width = float(d["figure_width"])
    if "figure_height" in d:
        sheet.figure_height = float(d["figure_height"])
    if "canvas_dpi" in d:
        sheet.canvas_dpi = int(d["canvas_dpi"])
    if "hspace" in d:
        sheet.hspace = float(d["hspace"])
    if "wspace" in d:
        sheet.wspace = float(d["wspace"])


def _apply_nacd_defaults(sheet: SheetState, d: Dict[str, Any]) -> None:
    """Push palette/overlay defaults into every existing NF analysis."""
    if not d or not sheet.nf_analyses:
        return
    palette = d.get("severity_palette") or {}
    overlay_mode = d.get("severity_overlay_mode")
    show_lmax = d.get("show_lambda_max")
    use_range_as_mask = d.get("use_range_as_mask")
    edge_vis = d.get("contaminated_edge_visible")
    edge_col = d.get("contaminated_edge_color")
    edge_w = d.get("contaminated_edge_width")
    for nf in sheet.nf_analyses.values():
        if palette:
            nf.severity_palette.update({k: str(v) for k, v in palette.items()})
        if overlay_mode is not None:
            nf.severity_overlay_mode = str(overlay_mode)
        if show_lmax is not None:
            nf.show_lambda_max = bool(show_lmax)
        if use_range_as_mask is not None:
            nf.use_range_as_mask = bool(use_range_as_mask)
        if edge_vis is not None:
            nf.contaminated_edge_visible = bool(edge_vis)
        if edge_col is not None:
            nf.contaminated_edge_color = str(edge_col)
        if edge_w is not None:
            try:
                nf.contaminated_edge_width = float(edge_w)
            except (TypeError, ValueError):
                pass


def _remap_subplot_keys(
    sheet: SheetState, d: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """Pair preset subplot keys with the sheet's actual keys.

    Strategy:
      * If a preset key matches a sheet key, use it directly.
      * Otherwise, walk the sheet's ordered keys and consume one
        preset block per slot in iteration order. This lets a preset
        captured on a 2x2 grid still apply to a 1x1 ``main`` sheet
        (the first ``cell_0_0`` block lands on ``main``).
    """
    if not d:
        return {}
    sheet_keys = list(sheet.subplot_keys_ordered())
    matched: Dict[str, Dict[str, Any]] = {}
    leftovers: List[tuple] = []  # preserve preset order for key fallbacks
    for k, vd in d.items():
        if k in sheet.subplots:
            matched[k] = vd
        else:
            leftovers.append((k, vd))
    if not leftovers:
        return matched
    # Map remaining preset blocks onto unmatched sheet keys in order.
    free = [k for k in sheet_keys if k not in matched]
    for slot_key, (_, vd) in zip(free, leftovers):
        matched[slot_key] = vd
    return matched


def _apply_subplot_visuals(sheet: SheetState, d: Dict[str, Any]) -> None:
    if not d:
        return
    for key, vd in _remap_subplot_keys(sheet, d).items():
        sp = sheet.subplots.get(key)
        if sp is None:
            continue
        # Apply only opinionated values: empty strings / 0 / None signal
        # "no opinion" because the panel exposes those as the unset state.
        if vd.get("x_domain"):
            sp.x_domain = str(vd["x_domain"])
        if vd.get("x_range"):
            sp.x_range = tuple(vd["x_range"])  # type: ignore[assignment]
        if vd.get("y_range"):
            sp.y_range = tuple(vd["y_range"])  # type: ignore[assignment]
        if "auto_x" in vd:
            sp.auto_x = bool(vd["auto_x"])
        if "auto_y" in vd:
            sp.auto_y = bool(vd["auto_y"])
        if vd.get("x_scale"):
            sp.x_scale = str(vd["x_scale"])
        if vd.get("y_scale"):
            sp.y_scale = str(vd["y_scale"])
        if vd.get("font_family"):
            sp.font_family = str(vd["font_family"])
        if int(vd.get("title_font_size") or 0) > 0:
            sp.title_font_size = int(vd["title_font_size"])
        if int(vd.get("axis_label_font_size") or 0) > 0:
            sp.axis_label_font_size = int(vd["axis_label_font_size"])
        if int(vd.get("tick_label_font_size") or 0) > 0:
            sp.tick_label_font_size = int(vd["tick_label_font_size"])
        if vd.get("x_tick_format"):
            sp.x_tick_format = str(vd["x_tick_format"])
        if vd.get("y_tick_format"):
            sp.y_tick_format = str(vd["y_tick_format"])
        if vd.get("freq_tick_style"):
            v = str(vd["freq_tick_style"])
            sp.freq_tick_style = "one-two-five" if v == "one_two_five" else v
        if "freq_custom_ticks" in vd:
            sp.freq_custom_ticks = [
                float(x) for x in (vd.get("freq_custom_ticks") or [])
            ]
        if vd.get("x_label"):
            sp.x_label = str(vd["x_label"])
        if vd.get("y_label"):
            sp.y_label = str(vd["y_label"])
        if vd.get("legend_visible") is not None:
            sp.legend_visible = bool(vd["legend_visible"])
        if vd.get("legend_position"):
            sp.legend_position = str(vd["legend_position"])
        if int(vd.get("legend_font_size") or 0) > 0:
            sp.legend_font_size = int(vd["legend_font_size"])
        if vd.get("legend_frame_on") is not None:
            sp.legend_frame_on = bool(vd["legend_frame_on"])
        if vd.get("legend"):
            _apply_subplot_legend(getattr(sp, "legend", None), vd["legend"])


def apply_preset(sheet: SheetState, preset: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a preset dict to ``sheet`` in-place (data fields untouched).

    Returns a small summary dict useful for status feedback::

        {"sections": ["typography", "legend", ...],
         "subplots_applied": ["main"], "subplots_skipped": [...]}.
    """
    if not isinstance(preset, dict):
        raise TypeError("Config preset must be a dict")
    kind = preset.get("kind")
    if kind not in (None, "report_studio.config_preset"):
        raise ValueError("File is not a Report Studio config preset")
    # Sheet manifests (saved by project_v4) carry top-level "curves" /
    # "subplots" keys; reject them so users get a clear error rather than
    # silent partial application.
    if kind is None and ("curves" in preset or "included_curve_names" in preset):
        raise ValueError(
            "This file looks like a sheet manifest, not a config preset."
        )

    summary: Dict[str, Any] = {
        "sections": [], "subplots_applied": [], "subplots_skipped": [],
    }
    if preset.get("typography"):
        _apply_typography(sheet, preset["typography"])
        summary["sections"].append("typography")
    if preset.get("legend"):
        _apply_legend(sheet, preset["legend"])
        summary["sections"].append("legend")
    if preset.get("figure"):
        _apply_figure(sheet, preset["figure"])
        summary["sections"].append("figure")
    if preset.get("nacd_defaults"):
        _apply_nacd_defaults(sheet, preset["nacd_defaults"])
        summary["sections"].append("nacd_defaults")
    if preset.get("combined_spectrum_bar"):
        _apply_combined_spectrum_bar(sheet, preset["combined_spectrum_bar"])
        summary["sections"].append("combined_spectrum_bar")
    sv = preset.get("subplot_visuals") or {}
    if sv:
        remap = _remap_subplot_keys(sheet, sv)
        summary["subplots_applied"] = sorted(remap.keys())
        summary["subplots_skipped"] = sorted(
            k for k in sv if k not in remap
        )
        _apply_subplot_visuals(sheet, sv)
        summary["sections"].append("subplot_visuals")
    return summary


def load_config(path: str | Path) -> Dict[str, Any]:
    """Load a preset JSON file and return its dict (no application)."""
    p = Path(path)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def apply_config(path: str | Path, sheet: SheetState) -> Dict[str, Any]:
    """Convenience: load JSON file + apply it to ``sheet`` (returns summary)."""
    return apply_preset(sheet, load_config(path))


__all__ = [
    "CONFIG_PRESET_VERSION",
    "apply_config",
    "apply_preset",
    "build_preset",
    "load_config",
    "save_config",
]
