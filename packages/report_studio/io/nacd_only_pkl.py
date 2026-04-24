"""Standalone NACD-Only figure bundle (.pkl) IO.

Counterpart to :mod:`nacd_zone_pkl` for the **NACD-Only (NF severity)**
figure type. A single file ships every selected offset's dispersion
curve + NACD array + contamination mask + derived λ / freq limit
lines, plus the session-state paths so Report Studio can auto-fill
the Linked Data rows.

Schema v1::

    {
        "_kind": "dc_cut.nacd_only_figure",
        "_version": 1,
        "saved_at": <float>,
        "source": {"state_pkl": <str>, "spectrum_npz": <str>},
        "settings": {<NF settings copy>},
        "offsets": [
            {
                "label": "+66 m",
                "source_offset": 66.0,
                "x_bar": 30.0,
                "lambda_max": 43.0,
                "frequency": [...], "velocity": [...], "wavelength": [...],
                "nacd": [...],
                "mask_contaminated": [...],
                "derived_lines": [...]     # DerivedLimitSet line dicts
            },
            ...
        ],
        "limit_lines_ui": {...}            # optional, JSON-safe
    }

This format *replaces* the legacy ``nf_sidecar.json`` workflow.  The
sidecar reader remains in :mod:`nf_sidecar` so older projects load
without error, but no new code writes sidecars.
"""
from __future__ import annotations

import os
import pickle
import time
from typing import Any, Dict, List, Optional

from .figure_bundle import (
    FigureBundleSpec,
    default_bundle_path,
    format_saved_at,
    register_bundle_spec,
)


BUNDLE_KIND = "dc_cut.nacd_only_figure"
BUNDLE_VERSION = 1


def _to_list(value: Any) -> list:
    """Normalise array-like values to plain Python lists.

    ``list(None)`` raises and numpy's boolean check raises on arrays,
    so centralise the logic here (same helper lives in
    :mod:`nacd_zone_pkl`).
    """
    if value is None:
        return []
    try:
        return list(value)
    except TypeError:
        return []


def build_nacd_only_bundle(
    *,
    nf_results: Optional[Dict[str, Any]],
    nf_settings: Optional[Dict[str, Any]],
    state_pkl: str = "",
    spectrum_npz: str = "",
    limit_lines_ui: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble a v1 NACD-Only bundle dict from a finished NACD run.

    ``nf_results`` is the payload published by
    :meth:`NfDock._publish_nf_results` (JSON-safe lists). It must
    contain ``per_offset`` and ideally ``derived_lines`` /
    ``per_offset_derived``; when no per-offset derived records exist
    the single-zone ``derived_lines`` list is replicated onto every
    offset (classic NACD-Only behaviour).
    """
    nf_results = nf_results or {}
    per_offset = list(nf_results.get("per_offset") or [])
    shared_derived = list(nf_results.get("derived_lines") or [])
    per_off_derived = {
        str(d.get("label", "")): list(d.get("derived_lines") or [])
        for d in (nf_results.get("per_offset_derived") or [])
    }

    offsets: List[Dict[str, Any]] = []
    for entry in per_offset:
        lbl = str(entry.get("label", ""))
        derived = per_off_derived.get(lbl)
        if derived is None:
            derived = list(shared_derived)
        lam_max = 0.0
        for ln in derived:
            if (
                str(ln.get("kind")) == "lambda"
                and str(ln.get("role")) == "max"
            ):
                try:
                    lam_max = max(lam_max, float(ln.get("value", 0.0)))
                except (TypeError, ValueError):
                    continue
        offsets.append({
            "label": lbl,
            "source_offset": entry.get("source_offset"),
            "x_bar": float(entry.get("x_bar", 0.0) or 0.0),
            "lambda_max": float(lam_max),
            "frequency": _to_list(entry.get("f")),
            "velocity": _to_list(entry.get("v")),
            "wavelength": _to_list(entry.get("w")),
            "nacd": _to_list(entry.get("nacd")),
            "mask_contaminated": _to_list(entry.get("mask")),
            "derived_lines": derived,
        })

    return {
        "_kind": BUNDLE_KIND,
        "_version": BUNDLE_VERSION,
        "saved_at": time.time(),
        "source": {
            "state_pkl": str(state_pkl or ""),
            "spectrum_npz": str(spectrum_npz or ""),
        },
        "settings": dict(nf_settings or {}),
        "offsets": offsets,
        "limit_lines_ui": dict(limit_lines_ui or {}),
    }


def write_bundle(path: str, bundle: Dict[str, Any]) -> None:
    """Pickle ``bundle`` to ``path``."""
    with open(path, "wb") as fh:
        pickle.dump(bundle, fh, protocol=pickle.HIGHEST_PROTOCOL)


def read_bundle(path: str) -> Optional[Dict[str, Any]]:
    """Read + validate a NACD-Only bundle; return ``None`` on any error."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as fh:
            data = pickle.load(fh)
    except (OSError, pickle.UnpicklingError, EOFError, AttributeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("_kind") != BUNDLE_KIND:
        return None
    try:
        version = int(data.get("_version", 0))
    except (TypeError, ValueError):
        return None
    if version < 1 or version > BUNDLE_VERSION:
        return None
    if not isinstance(data.get("offsets", []), list):
        return None
    return data


def default_bundle_path_for(state_pkl: str) -> str:
    """Default filename for an NACD-Only bundle next to ``state_pkl``."""
    return default_bundle_path(state_pkl, "_nacd_only")


def summarise_bundle(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a :mod:`figure_bundle.bundle_summary` payload."""
    offsets_in = list(data.get("offsets") or [])
    offsets_out: List[Dict[str, Any]] = []
    for o in offsets_in:
        try:
            mask = list(o.get("mask_contaminated") or [])
            n_contam = sum(1 for m in mask if m)
        except TypeError:
            n_contam = 0
        offsets_out.append({
            "label": str(o.get("label", "")),
            "x_bar": float(o.get("x_bar", 0.0) or 0.0),
            "lambda_max": float(o.get("lambda_max", 0.0) or 0.0),
            "n_contaminated": int(n_contam),
        })
    src = data.get("source") or {}
    return {
        "saved_at": format_saved_at(data.get("saved_at")),
        "n_offsets": len(offsets_out),
        "offsets": offsets_out,
        "source": {
            "state_pkl": str(src.get("state_pkl", "") or ""),
            "spectrum_npz": str(src.get("spectrum_npz", "") or ""),
        },
    }


# ── Registry hook ────────────────────────────────────────────────────
register_bundle_spec(FigureBundleSpec(
    type_id="nacd_only",
    kind_tag=BUNDLE_KIND,
    display_name="NACD-Only Figure",
    default_suffix="_nacd_only",
    writer_fn=write_bundle,
    reader_fn=read_bundle,
    summary_fn=summarise_bundle,
    builder_fn=build_nacd_only_bundle,
))


__all__ = [
    "BUNDLE_KIND",
    "BUNDLE_VERSION",
    "build_nacd_only_bundle",
    "write_bundle",
    "read_bundle",
    "default_bundle_path_for",
    "summarise_bundle",
]
