from __future__ import annotations

import json
import os
from typing import Any, Dict


_DEFAULTS: Dict[str, Any] = {
    "freq_tick_style": "ruler",
    "freq_custom_ticks": [1,2,3,4,5,6,7,8,9,10,15,20,30,40,50,60,80,100],
    "show_k_guides_default": True,
    "nacd_thresh": 1.0,
    "show_grid": True,
    "robust_lower_pct": 0.5,
    "robust_upper_pct": 99.5,
    # Array configuration
    "default_n_phones": 24,
    "default_receiver_dx": 2.0,
    # Appearance
    "theme": "light",  # "light" or "dark"
    # General
    "auto_save_enabled": False,
    "auto_save_interval_minutes": 10,
    # Spectrum backgrounds
    "show_spectra": True,  # Master enable/disable for spectrum backgrounds
    "default_spectrum_alpha": 0.5,  # Default opacity for new spectrum backgrounds
    "spectrum_colormap": "viridis",  # Default colormap: viridis, plasma, hot, gray, jet
    "spectrum_display_mode": "per_layer",  # "active_only", "all_visible", or "per_layer"
    "spectrum_render_mode": "imshow",  # "imshow" (fast pixel grid) or "contour" (smooth contours)
    "auto_load_spectra": True,  # Auto-detect and load spectrum files at startup
    # Spectrum performance (all default ON; turn off to restore legacy behaviour)
    "spectrum_perf_downsample": True,        # stride-downsample large power arrays before imshow
    "spectrum_perf_max_px": 400,             # target max pixels per axis when downsampling is on
    "spectrum_perf_interpolation": "auto",   # "auto" | "bilinear" | "nearest"
    "spectrum_perf_rgba_cache": True,        # pre-bake colormap into RGBA uint8 once
    "spectrum_perf_rasterized": True,        # mark the AxesImage rasterized=True
    "spectrum_perf_contour_levels": 12,      # level count for contourf render mode (was 30)
    "spectrum_perf_incremental_update": True,  # re-use existing AxesImage on toggles
    "spectrum_perf_hide_during_gesture": True,  # blank spectrum while a cut/add drag is active
    "spectrum_perf_use_blitting": True,      # interactive tools use restore_region + blit
    "spectrum_perf_draw_throttle_ms": 0,     # 0 = off; positive int coalesces draw_idle via QTimer
}


def _prefs_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, ".dc_cut_prefs.json")


def load_prefs() -> Dict[str, Any]:
    path = _prefs_path()
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
    except Exception:
        data = {}
    # merge defaults
    out = dict(_DEFAULTS)
    out.update({k: v for k, v in data.items() if k in _DEFAULTS or True})

    # One-shot migration: the default frequency tick style used to be
    # "decades"; it was changed to "ruler".  If we detect a legacy
    # prefs file that still carries the old default (and the user
    # never migrated), flip it to "ruler" once so the new default
    # actually surfaces in the Properties dock without forcing the
    # user to edit a JSON file by hand.
    if not out.get("_migrated_freq_tick_ruler_v1"):
        if out.get("freq_tick_style") == "decades":
            out["freq_tick_style"] = "ruler"
        out["_migrated_freq_tick_ruler_v1"] = True
        try:
            save_prefs(out)
        except Exception:
            pass

    # One-shot migration for the spectrum performance knobs added in this
    # revision. Only touches the flag; the defaults above already provide
    # fast-path values on first read. The flag lets a future revision
    # distinguish "user explicitly accepted this default" from "never seen
    # the new pref before".
    if not out.get("_migrated_spectrum_perf_v1"):
        out["_migrated_spectrum_perf_v1"] = True
        try:
            save_prefs(out)
        except Exception:
            pass
    return out


def save_prefs(prefs: Dict[str, Any]) -> None:
    path = _prefs_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass


def set_pref(key: str, value: Any) -> None:
    prefs = load_prefs()
    prefs[key] = value
    save_prefs(prefs)


def get_pref(key: str, default: Any = None) -> Any:
    prefs = load_prefs()
    return prefs.get(key, default)


