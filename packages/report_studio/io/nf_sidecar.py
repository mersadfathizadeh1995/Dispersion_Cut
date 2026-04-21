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
    """
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
    return merged
