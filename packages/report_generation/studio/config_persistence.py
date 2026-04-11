"""Config persistence -- save/load ReportStudioSettings as JSON.

Adapted from geo_figure's render_config.py pattern: recursively converts
nested dataclasses to/from dicts, stores them as human-readable JSON
in a ``render/`` sub-folder of the project directory.
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
from typing import get_type_hints, get_origin, get_args

from .models import (
    ReportStudioSettings,
    FigureConfig,
    TypographyConfig,
    GridConfig,
    TickConfig,
    AxisConfig,
    LegendConfig,
    ExportConfig,
    OutputConfig,
    SpectrumConfig,
    CurveOverlayConfig,
    NearFieldConfig,
)

CONFIG_VERSION = 1
RENDER_DIR = "render"

_DATACLASS_MAP = {
    "FigureConfig": FigureConfig,
    "TypographyConfig": TypographyConfig,
    "GridConfig": GridConfig,
    "TickConfig": TickConfig,
    "AxisConfig": AxisConfig,
    "LegendConfig": LegendConfig,
    "ExportConfig": ExportConfig,
    "OutputConfig": OutputConfig,
    "SpectrumConfig": SpectrumConfig,
    "CurveOverlayConfig": CurveOverlayConfig,
    "NearFieldConfig": NearFieldConfig,
    "ReportStudioSettings": ReportStudioSettings,
}


def _to_dict(obj) -> dict:
    """Recursively convert a dataclass to a plain dict."""
    if not dataclasses.is_dataclass(obj) or isinstance(obj, type):
        return obj
    result = {}
    for f in dataclasses.fields(obj):
        val = getattr(obj, f.name)
        if dataclasses.is_dataclass(val) and not isinstance(val, type):
            result[f.name] = _to_dict(val)
        elif isinstance(val, dict):
            result[f.name] = {
                k: _to_dict(v) if dataclasses.is_dataclass(v) else v
                for k, v in val.items()
            }
        elif isinstance(val, (list, tuple)):
            result[f.name] = [
                _to_dict(v) if dataclasses.is_dataclass(v) else v
                for v in val
            ]
        else:
            result[f.name] = val
    return result


def _from_dict(cls, d: dict):
    """Reconstruct a dataclass from a plain dict, ignoring unknown keys."""
    if d is None:
        return cls()
    hints = get_type_hints(cls)
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name not in d:
            continue
        val = d[f.name]
        ftype = hints.get(f.name)
        type_name = getattr(ftype, "__name__", "")
        if type_name in _DATACLASS_MAP and isinstance(val, dict):
            kwargs[f.name] = _from_dict(_DATACLASS_MAP[type_name], val)
        elif get_origin(ftype) is dict and isinstance(val, dict):
            args = get_args(ftype)
            if len(args) == 2:
                val_type_name = getattr(args[1], "__name__", "")
                if val_type_name in _DATACLASS_MAP:
                    kwargs[f.name] = {
                        k: _from_dict(_DATACLASS_MAP[val_type_name], v)
                        if isinstance(v, dict) else v
                        for k, v in val.items()
                    }
                else:
                    kwargs[f.name] = val
            else:
                kwargs[f.name] = val
        elif get_origin(ftype) is tuple and isinstance(val, list):
            kwargs[f.name] = tuple(val)
        elif _is_optional_tuple(ftype):
            kwargs[f.name] = tuple(val) if isinstance(val, list) else val
        elif _is_optional_list(ftype):
            kwargs[f.name] = val
        else:
            kwargs[f.name] = val
    return cls(**kwargs)


def _is_optional_tuple(ftype) -> bool:
    origin = get_origin(ftype)
    if origin is not None:
        for a in get_args(ftype):
            if get_origin(a) is tuple:
                return True
    return False


def _is_optional_list(ftype) -> bool:
    origin = get_origin(ftype)
    if origin is not None:
        for a in get_args(ftype):
            if get_origin(a) is list:
                return True
    return False


# ── Public API ────────────────────────────────────────────────

def settings_to_dict(settings: ReportStudioSettings) -> dict:
    d = _to_dict(settings)
    d["_config_version"] = CONFIG_VERSION
    return d


def settings_from_dict(d: dict) -> ReportStudioSettings:
    d.pop("_config_version", None)
    return _from_dict(ReportStudioSettings, d)


def save_render_config(project_dir: str, config_name: str,
                       settings: ReportStudioSettings) -> str:
    """Save settings as ``{project_dir}/render/{config_name}.json``.

    Returns the path to the saved file.
    """
    render_dir = os.path.join(project_dir, RENDER_DIR)
    os.makedirs(render_dir, exist_ok=True)
    safe_name = _sanitize_name(config_name)
    filepath = os.path.join(render_dir, f"{safe_name}.json")
    data = settings_to_dict(settings)
    data["_config_name"] = config_name
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return filepath


def load_render_config(filepath: str) -> ReportStudioSettings:
    """Load settings from a JSON config file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("_config_name", None)
    return settings_from_dict(data)


def list_render_configs(project_dir: str) -> list:
    """Return ``[(display_name, filepath), ...]`` for saved configs."""
    render_dir = os.path.join(project_dir, RENDER_DIR)
    if not os.path.isdir(render_dir):
        return []
    configs = []
    for fname in sorted(os.listdir(render_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(render_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            display_name = data.get("_config_name", fname[:-5])
        except Exception:
            display_name = fname[:-5]
        configs.append((display_name, fpath))
    return configs


def _sanitize_name(name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*]', '_', name).strip()
    return safe or "config"
