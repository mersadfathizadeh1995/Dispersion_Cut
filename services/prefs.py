from __future__ import annotations

import json
import os
from typing import Any, Dict


_DEFAULTS: Dict[str, Any] = {
    "freq_tick_style": "decades",
    "freq_custom_ticks": [1,2,3,4,5,6,7,8,9,10,15,20,30,40,50,60,80,100],
    "show_k_guides_default": True,
    "nacd_thresh": 1.0,
    "show_grid": True,
    "robust_lower_pct": 0.5,
    "robust_upper_pct": 99.5,
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


