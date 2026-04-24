"""Standalone NACD-zone figure bundle (.pkl) IO.

This module owns the persistence format for the multi-zone NACD figure
that Report Studio loads as a *third* file (alongside the dispersion
PKL and spectrum NPZ). The bundle is fully self-contained: every
selected source offset's curve, NACD array, contamination mask, zone
indices, and DerivedLimitSet are baked in so Report Studio needs no
recomputation.

Schema v1::

    {
        "_kind": "dc_cut.nacd_zone_figure",
        "_version": 1,
        "saved_at": <float>,
        "source": {"state_pkl": <str>, "spectrum_npz": <str>},
        "zone_spec": <NACDZoneSpec.to_dict()>,
        "settings": {<NF settings copy>},
        "offsets": [
            {
                "label": "+66 m",
                "source_offset": 66.0,
                "x_bar": 30.0,
                "frequency": [...], "velocity": [...], "wavelength": [...],
                "nacd": [...],
                "mask_contaminated": [...],
                "zone_idx": [...],     # may be []
                "derived_lines": [...] # DerivedLimitSet line dicts
            },
            ...
        ],
        "limit_lines_ui": {...}        # optional, JSON-safe
    }

The bundle uses ``pickle`` (binary) so numpy lists stay compact. The
schema is validated on read; bad payloads return ``None`` so the
caller can warn the user without crashing.
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


BUNDLE_KIND = "dc_cut.nacd_zone_figure"
BUNDLE_VERSION = 2

# Version history
# ----------------
# v1 — initial multi-zone bundle (bands, labels, per-offset curves +
#      derived lines).
# v2 — per-zone ``arrow`` sub-spec (double-headed arrows pointing at
#      each zone's extent; see :class:`ZoneArrow`).  Reader accepts
#      v1 bundles unchanged; missing ``arrow`` fields default to
#      ``enabled=False``.


def build_nacd_zone_bundle(
    *,
    nf_results: Optional[Dict[str, Any]],
    nf_settings: Optional[Dict[str, Any]],
    zone_spec: Optional[Dict[str, Any]],
    state_pkl: str = "",
    spectrum_npz: str = "",
    limit_lines_ui: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble a v1 bundle dict from a finished NACD run.

    ``nf_results`` is the payload published by
    :meth:`NfDock._publish_nf_results` (already JSON-safe lists). It
    must contain ``per_offset`` and ideally ``per_offset_derived``;
    when the latter is missing, every offset gets an empty
    ``derived_lines`` list.
    """
    nf_results = nf_results or {}
    per_offset = list(nf_results.get("per_offset") or [])
    per_off_derived = {
        str(d.get("label", "")): d
        for d in (nf_results.get("per_offset_derived") or [])
    }

    def _to_list(value: Any) -> list:
        """Normalise array-like values to plain Python lists.

        ``list(None)`` blows up and ``arr or []`` raises numpy's
        ambiguity error, so funnel everything through here.
        """
        if value is None:
            return []
        try:
            return list(value)
        except TypeError:
            return []

    offsets: List[Dict[str, Any]] = []
    for entry in per_offset:
        lbl = str(entry.get("label", ""))
        derived_record = per_off_derived.get(lbl, {})
        offsets.append({
            "label": lbl,
            "source_offset": entry.get("source_offset"),
            "x_bar": float(entry.get("x_bar", 0.0)),
            "frequency": _to_list(entry.get("f")),
            "velocity": _to_list(entry.get("v")),
            "wavelength": _to_list(entry.get("w")),
            "nacd": _to_list(entry.get("nacd")),
            "mask_contaminated": _to_list(entry.get("mask")),
            "zone_idx": _to_list(entry.get("zone_idx")),
            "derived_lines": list(derived_record.get("derived_lines", []) or []),
        })

    return {
        "_kind": BUNDLE_KIND,
        "_version": BUNDLE_VERSION,
        "saved_at": time.time(),
        "source": {
            "state_pkl": str(state_pkl or ""),
            "spectrum_npz": str(spectrum_npz or ""),
        },
        "zone_spec": zone_spec or None,
        "settings": dict(nf_settings or {}),
        "offsets": offsets,
        "limit_lines_ui": dict(limit_lines_ui or {}),
    }


def write_bundle(path: str, bundle: Dict[str, Any]) -> None:
    """Pickle ``bundle`` to ``path`` (binary)."""
    with open(path, "wb") as fh:
        pickle.dump(bundle, fh, protocol=pickle.HIGHEST_PROTOCOL)


def read_bundle(path: str) -> Optional[Dict[str, Any]]:
    """Read and validate a NACD-zone bundle.

    Returns the bundle dict on success, ``None`` when the path is
    empty/missing or the file is not a recognised v1 bundle.
    """
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
    """Default filename for a bundle next to ``state_pkl``."""
    return default_bundle_path(state_pkl, "_nacd_zones")


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
        # λ_max isn't stored on zone bundles directly — pick it out of
        # the derived-lines list (kind="lambda", role="max") as a
        # best-effort for the preview card.
        lam_max = 0.0
        for ln in (o.get("derived_lines") or []):
            if (
                str(ln.get("kind")) == "lambda"
                and str(ln.get("role")) == "max"
            ):
                try:
                    lam_max = max(lam_max, float(ln.get("value", 0.0)))
                except (TypeError, ValueError):
                    continue
        offsets_out.append({
            "label": str(o.get("label", "")),
            "x_bar": float(o.get("x_bar", 0.0) or 0.0),
            "lambda_max": float(lam_max),
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
    type_id="nacd_zones",
    kind_tag=BUNDLE_KIND,
    display_name="NACD Zones Figure",
    default_suffix="_nacd_zones",
    writer_fn=write_bundle,
    reader_fn=read_bundle,
    summary_fn=summarise_bundle,
    builder_fn=build_nacd_zone_bundle,
))


__all__ = [
    "BUNDLE_KIND",
    "BUNDLE_VERSION",
    "build_nacd_zone_bundle",
    "write_bundle",
    "read_bundle",
    "default_bundle_path_for",
    "summarise_bundle",
]
