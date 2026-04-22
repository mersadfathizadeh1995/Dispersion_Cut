"""NF evaluation sidecar JSON (optional 3rd file in Report Studio loads).

Report Studio normally loads a dispersion PKL plus an optional spectrum
NPZ. DC Cut also embeds ``nf_results`` / ``nf_settings`` inside the PKL
so the NACD-Only figure works out-of-the-box. The sidecar format lets
the user **also** export an explicit "NF evaluation" bundle — the same
``nf_results`` / ``nf_settings`` plus per-line UI state (visibility,
colors) that the PKL currently drops — and load it as a third file. A
sidecar, when provided, **overrides** the embedded PKL NF blocks for
that load so the Report Studio figure matches the exact DC Cut session.

The schema is versioned and JSON-safe so projects can survive future
refactors (sidecars produced by v1 DC Cut still work with later
Report Studio releases as long as the reader respects ``_version``).
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import numpy as np


SIDECAR_KIND = "dc_cut.nf_eval_sidecar"
SIDECAR_VERSION = 1


def _jsonify(obj: Any) -> Any:
    """Recursively convert numpy/bool arrays into JSON-safe primitives."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, dict):
        return {str(k): _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    return obj


def build_sidecar(
    *,
    nf_results: Optional[Dict[str, Any]],
    nf_settings: Optional[Dict[str, Any]],
    limit_lines_ui: Optional[Dict[str, Any]] = None,
    pkl_path: str = "",
    ui_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the sidecar dict ready to be written with :func:`write_sidecar`.

    Parameters
    ----------
    nf_results, nf_settings:
        Mirrors of ``controller._nf_results`` / ``controller._nf_settings``.
    limit_lines_ui:
        Optional UI state from the Limit Lines tab (visibility/colors
        keyed by ``"band_index/kind/role"``). Stored verbatim.
    pkl_path:
        Source PKL absolute path (human-debug breadcrumb only; not a
        security boundary — Report Studio never validates it).
    ui_state:
        Optional dict of cross-panel UI state.  Currently carries
        ``nacd_zone_spec`` (serialised :class:`NACDZoneSpec`) but the
        key is kept open-ended so future viewer settings can be added
        without another schema bump.  When absent, the sidecar still
        contains an effectively empty ``ui_state`` block and readers
        fall back to ``nf_settings.nacd_zone_spec`` for backward
        compatibility.
    """
    # Derive ``nacd_zone_spec`` from ``nf_settings`` if the caller did
    # not pass an explicit ``ui_state``.  Keeps current callers working
    # without requiring them to duplicate the spec.
    if ui_state is None:
        ui_state = {}
        if nf_settings and isinstance(nf_settings, dict):
            spec = nf_settings.get("nacd_zone_spec")
            if spec:
                ui_state["nacd_zone_spec"] = spec

    return {
        "_version": SIDECAR_VERSION,
        "kind": SIDECAR_KIND,
        "source": {
            "pkl_path": str(pkl_path) if pkl_path else "",
            "saved_at": time.time(),
        },
        "nf_results": _jsonify(nf_results) if nf_results else None,
        "nf_settings": _jsonify(nf_settings) if nf_settings else None,
        "limit_lines_ui": _jsonify(limit_lines_ui) if limit_lines_ui else None,
        "ui_state": _jsonify(ui_state) if ui_state else {},
    }


def write_sidecar(path: str, payload: Dict[str, Any]) -> None:
    """Write ``payload`` to ``path`` as pretty-printed UTF-8 JSON."""
    data = _jsonify(payload)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def read_sidecar(path: str) -> Optional[Dict[str, Any]]:
    """Read a sidecar file; return ``None`` when the path is empty/missing."""
    if not path:
        return None
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def default_sidecar_path_for(pkl_path: str) -> str:
    """Default filename for a sidecar living next to ``pkl_path``.

    Returns an empty string when ``pkl_path`` is empty so callers can
    fall through to the raw file dialog default.
    """
    if not pkl_path:
        return ""
    base, _ext = os.path.splitext(pkl_path)
    return f"{base}_nf_eval.json"


_VALID_ZONE_STYLES = ("classic", "multi_zone", "multi_group")
_VALID_LABEL_POSITIONS = ("top", "bottom", "left", "right")


def _validate_nacd_zone_spec(spec: Any) -> List[str]:
    """Return issues with a ``nacd_zone_spec`` payload; empty = OK.

    Accepts both the current shape (each group has ``thresholds`` +
    ``zones``) and the legacy shape (each group has ``levels``) so
    older sidecars continue to load.
    """
    issues: List[str] = []
    if spec is None:
        return issues
    if not isinstance(spec, dict):
        issues.append("'nacd_zone_spec' is not an object.")
        return issues
    style = spec.get("style", "classic")
    if style not in _VALID_ZONE_STYLES:
        issues.append(f"nacd_zone_spec: unknown style {style!r}.")
    groups = spec.get("groups", [])
    if not isinstance(groups, list):
        issues.append("nacd_zone_spec: 'groups' must be a list.")
        return issues
    for gi, g in enumerate(groups):
        if not isinstance(g, dict):
            issues.append(f"nacd_zone_spec.groups[{gi}] is not an object.")
            continue
        pos = g.get("label_position", "top")
        if pos not in _VALID_LABEL_POSITIONS:
            issues.append(
                f"nacd_zone_spec.groups[{gi}]: invalid label_position "
                f"{pos!r}."
            )

        # ── Preferred shape: "thresholds" + "zones" ───────────────
        if "thresholds" in g or "zones" in g:
            thresholds = g.get("thresholds", [])
            zones = g.get("zones", [])
            if not isinstance(thresholds, list):
                issues.append(
                    f"nacd_zone_spec.groups[{gi}].thresholds must be a list."
                )
                continue
            if not isinstance(zones, list):
                issues.append(
                    f"nacd_zone_spec.groups[{gi}].zones must be a list."
                )
                continue
            nacds: List[float] = []
            for ti, t in enumerate(thresholds):
                if not isinstance(t, dict):
                    issues.append(
                        f"nacd_zone_spec.groups[{gi}].thresholds[{ti}] "
                        "is not an object."
                    )
                    continue
                try:
                    nacds.append(float(t.get("nacd", 0.0)))
                except (TypeError, ValueError):
                    issues.append(
                        f"nacd_zone_spec.groups[{gi}].thresholds[{ti}]: "
                        "non-numeric 'nacd'."
                    )
            if nacds and nacds != sorted(nacds):
                issues.append(
                    f"nacd_zone_spec.groups[{gi}]: thresholds must be "
                    "ascending by NACD."
                )
            # Zones must match N+1 (warn but do not reject — the
            # loader normalises via ZoneGroup.normalised()).
            if zones and thresholds and len(zones) != len(thresholds) + 1:
                issues.append(
                    f"nacd_zone_spec.groups[{gi}]: expected "
                    f"{len(thresholds) + 1} zones for "
                    f"{len(thresholds)} thresholds, got {len(zones)}."
                )
            continue

        # ── Legacy shape: "levels" ────────────────────────────────
        levels = g.get("levels", [])
        if not isinstance(levels, list):
            issues.append(
                f"nacd_zone_spec.groups[{gi}].levels must be a list."
            )
            continue
        nacds = []
        for li, lv in enumerate(levels):
            if not isinstance(lv, dict):
                issues.append(
                    f"nacd_zone_spec.groups[{gi}].levels[{li}] is "
                    "not an object."
                )
                continue
            try:
                nacds.append(float(lv.get("nacd", 0.0)))
            except (TypeError, ValueError):
                issues.append(
                    f"nacd_zone_spec.groups[{gi}].levels[{li}]: "
                    "non-numeric 'nacd'."
                )
        if nacds and nacds != sorted(nacds):
            issues.append(
                f"nacd_zone_spec.groups[{gi}]: NACD levels must be "
                "ascending."
            )
    return issues


def validate(payload: Dict[str, Any]) -> List[str]:
    """Return a list of human-readable issues; empty list = OK."""
    issues: List[str] = []
    if not isinstance(payload, dict):
        issues.append("Sidecar root is not a dict.")
        return issues
    if payload.get("kind") != SIDECAR_KIND:
        issues.append(f"Unexpected 'kind': {payload.get('kind')!r}.")
    version = payload.get("_version")
    if not isinstance(version, int) or version < 1 or version > SIDECAR_VERSION:
        issues.append(f"Unsupported sidecar version: {version!r}.")
    if payload.get("nf_results") is None:
        issues.append("Sidecar has no 'nf_results' block.")
    # Optional ui_state validation.
    ui_state = payload.get("ui_state")
    if ui_state is not None:
        if not isinstance(ui_state, dict):
            issues.append("'ui_state' must be an object.")
        else:
            issues.extend(
                _validate_nacd_zone_spec(ui_state.get("nacd_zone_spec"))
            )
    return issues


def merge_into_state(state: Dict[str, Any], sidecar: Dict[str, Any]) -> Dict[str, Any]:
    """Return a new state dict with sidecar ``nf_results`` / ``nf_settings``.

    The sidecar wins over whatever the PKL embeds. Unrelated state keys
    are kept intact so curves / spectra still load from the PKL. When
    the sidecar only carries one of the blocks, the other is left
    untouched.
    """
    merged = dict(state) if state else {}
    if not isinstance(sidecar, dict):
        return merged
    nf_res = sidecar.get("nf_results")
    nf_set = sidecar.get("nf_settings")
    if nf_res is not None:
        merged["nf_results"] = nf_res
    if nf_set is not None:
        merged["nf_settings"] = nf_set
    # Surface the zone spec explicitly so consumers can treat it as a
    # first-class field without peeking inside ``nf_settings``.  Falls
    # back to ``nf_settings.nacd_zone_spec`` for sidecars written by
    # older DC Cut versions that didn't populate ``ui_state``.
    ui_state = sidecar.get("ui_state") or {}
    spec = ui_state.get("nacd_zone_spec") if isinstance(ui_state, dict) else None
    if not spec and isinstance(nf_set, dict):
        spec = nf_set.get("nacd_zone_spec")
    if spec:
        merged["nacd_zone_spec"] = spec
    return merged
