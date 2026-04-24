"""Unified figure-bundle registry for DC Cut → Report Studio.

Each figure type that Report Studio renders from a *standalone file*
(NACD-Only, NACD Zones, future types) registers a
:class:`FigureBundleSpec` here. The spec describes:

- ``type_id`` — matches the figure-type plugin (``"nacd_only"`` /
  ``"nacd_zones"`` / …).
- ``kind_tag`` — the ``_kind`` string embedded at the top of every
  bundle dict, used by :func:`detect_bundle_kind` to auto-route a
  bundle file to the right reader without the UI having to guess.
- ``display_name`` — what the "Save Figure …" menu entry reads.
- ``default_suffix`` — appended to the session-state stem when
  generating the default filename (e.g. ``_nacd_zones``).
- ``writer_fn`` / ``reader_fn`` — the per-format IO callables.
- ``summary_fn`` — returns a dict with ``figure_type``, ``saved_at``,
  ``n_offsets``, ``offsets`` (list of ``{label, x_bar, lambda_max,
  n_contaminated}``), and ``source`` (``{state_pkl, spectrum_npz}``)
  for the Add Data dialog's metadata preview card.

The registry is populated at module import time by the individual
bundle IO modules (:mod:`nacd_zone_pkl`, :mod:`nacd_only_pkl`). The
Add Data dialog + NF Eval dock consume the registry instead of
hard-coding one-off "Export Foo…" menu items.
"""
from __future__ import annotations

import os
import pickle
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class FigureBundleSpec:
    """Metadata + IO callables for a single figure-bundle format."""

    type_id: str
    kind_tag: str
    display_name: str
    default_suffix: str
    writer_fn: Callable[[str, Dict[str, Any]], None]
    reader_fn: Callable[[str], Optional[Dict[str, Any]]]
    summary_fn: Callable[[Dict[str, Any]], Dict[str, Any]]
    builder_fn: Optional[Callable[..., Dict[str, Any]]] = None


# Public registry (populated at import time by bundle modules).
FIGURE_BUNDLE_REGISTRY: Dict[str, FigureBundleSpec] = {}
# Secondary index: kind_tag → type_id.
_KIND_TO_TYPE_ID: Dict[str, str] = {}


def register_bundle_spec(spec: FigureBundleSpec) -> None:
    """Add or replace a bundle spec in the registry."""
    FIGURE_BUNDLE_REGISTRY[spec.type_id] = spec
    _KIND_TO_TYPE_ID[spec.kind_tag] = spec.type_id


def get_spec(type_id: str) -> Optional[FigureBundleSpec]:
    _ensure_builtins_registered()
    return FIGURE_BUNDLE_REGISTRY.get(type_id)


def all_specs() -> List[FigureBundleSpec]:
    _ensure_builtins_registered()
    return list(FIGURE_BUNDLE_REGISTRY.values())


def _ensure_builtins_registered() -> None:
    """Import every built-in bundle module once so they register.

    Called lazily from the public helpers because the bundle modules
    themselves import from this module — doing the imports at
    module-top would create a cycle on first use.
    """
    try:
        from . import nacd_zone_pkl as _nz  # noqa: F401
    except ImportError:
        pass
    try:
        from . import nacd_only_pkl as _no  # noqa: F401
    except ImportError:
        pass


def detect_bundle_kind(path: str) -> Optional[str]:
    """Peek at ``path`` and return the registered ``type_id``.

    Returns ``None`` when the file is missing, not a pickle, or the
    ``_kind`` tag isn't registered. Never raises.
    """
    _ensure_builtins_registered()
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as fh:
            data = pickle.load(fh)
    except (OSError, pickle.UnpicklingError, EOFError, AttributeError):
        return None
    if not isinstance(data, dict):
        return None
    kind = data.get("_kind")
    if not isinstance(kind, str):
        return None
    return _KIND_TO_TYPE_ID.get(kind)


def read_any_bundle(path: str) -> Optional[Dict[str, Any]]:
    """Read ``path`` using whichever registered reader matches.

    Returns the validated bundle dict on success, ``None`` otherwise.
    """
    _ensure_builtins_registered()
    type_id = detect_bundle_kind(path)
    if type_id is None:
        return None
    spec = FIGURE_BUNDLE_REGISTRY.get(type_id)
    if spec is None:
        return None
    return spec.reader_fn(path)


def bundle_summary(path: str) -> Optional[Dict[str, Any]]:
    """Return a lightweight preview dict for the Add Data dialog.

    The shape is::

        {
            "type_id": str,
            "figure_type": str,     # display_name
            "saved_at": str,        # formatted local time or ""
            "n_offsets": int,
            "offsets": [
                {"label": str, "x_bar": float, "lambda_max": float,
                 "n_contaminated": int},
                ...
            ],
            "source": {"state_pkl": str, "spectrum_npz": str},
            "path": str,
        }

    ``None`` when the path isn't a recognised bundle. Safe to call
    repeatedly; the caller doesn't have to pre-validate.
    """
    _ensure_builtins_registered()
    type_id = detect_bundle_kind(path)
    if type_id is None:
        return None
    spec = FIGURE_BUNDLE_REGISTRY.get(type_id)
    if spec is None:
        return None
    data = spec.reader_fn(path)
    if data is None:
        return None
    try:
        summary = spec.summary_fn(data)
    except Exception:
        return None
    summary.setdefault("type_id", spec.type_id)
    summary.setdefault("figure_type", spec.display_name)
    summary["path"] = path
    return summary


def format_saved_at(ts: Any) -> str:
    """Format a POSIX timestamp as ``YYYY-MM-DD HH:MM``; empty on error."""
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return ""


def default_bundle_path(state_pkl: str, suffix: str) -> str:
    """Produce ``<stem><suffix>.pkl`` next to ``state_pkl``."""
    if not state_pkl:
        return ""
    base, _ext = os.path.splitext(state_pkl)
    return f"{base}{suffix}.pkl"


__all__ = [
    "FigureBundleSpec",
    "FIGURE_BUNDLE_REGISTRY",
    "register_bundle_spec",
    "get_spec",
    "all_specs",
    "detect_bundle_kind",
    "read_any_bundle",
    "bundle_summary",
    "format_saved_at",
    "default_bundle_path",
]
