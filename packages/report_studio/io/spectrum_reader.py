"""Report Studio spectrum reader — thin adapter over :mod:`dc_cut.core.io.spectrum`.

This module used to carry its own NPZ parsing and offset-label helpers.
The implementation has moved to :mod:`dc_cut.core.io.spectrum` so the
main DC-cut app and Report Studio share a single, tolerant loader.

The original public surface is preserved exactly:

* :func:`read_spectrum_npz` — returns ``List[SpectrumData]`` regardless
  of whether the file is single-offset or combined.
* :func:`normalize_offset` — extracts a canonical ``+66`` / ``-20``
  offset label from any free-form input.

A few legacy helpers (``_label_to_suffix``, ``_suffix_to_label``) are
kept as thin re-exports for the small number of callers outside this
package that still import them, but new code should use the helpers in
:mod:`dc_cut.core.io.offset_label` directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np

from dc_cut.core.io.offset_label import (
    from_suffix as _from_suffix_core,
    normalize_offset as _normalize_offset_core,
    to_suffix as _to_suffix_core,
)
from dc_cut.core.io.spectrum import enumerate_spectra

from ..core.models import SpectrumData


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_spectrum_npz(path: str | Path) -> List[SpectrumData]:
    """Load spectra from an NPZ file and return one :class:`SpectrumData` per offset.

    Delegates all schema handling to :func:`dc_cut.core.io.spectrum.enumerate_spectra`,
    which tolerates every known single/combined layout plus a few
    permissive variants. If the loader fails, the exception is
    propagated so upstream callers can surface it to the user.
    """
    records = enumerate_spectra(str(path))
    results: List[SpectrumData] = []
    for record in records:
        results.append(
            SpectrumData(
                offset_name=record.offset or "",
                frequencies=np.asarray(record.frequencies, dtype=float),
                velocities=np.asarray(record.velocities, dtype=float),
                power=np.asarray(record.power, dtype=float),
                method=record.method or "unknown",
            )
        )
    return results


def normalize_offset(name: str) -> str:
    """Return the signed-integer offset label (``"+66"`` / ``"-20"``).

    The Report Studio convention is the human label *without* a trailing
    ``m``. The core helper returns ``"+66m"`` / ``"-20m"``; we strip the
    unit here so every existing caller keeps working against project
    files that stored the old form.
    """
    canonical = _normalize_offset_core(name)
    if canonical.endswith("m"):
        canonical = canonical[:-1]
    return canonical or name


# ---------------------------------------------------------------------------
# Legacy re-exports
# ---------------------------------------------------------------------------


def _label_to_suffix(label: str) -> str:
    """Backward-compat shim over :func:`dc_cut.core.io.offset_label.to_suffix`."""
    return _to_suffix_core(label)


def _suffix_to_label(suffix: str) -> str:
    """Backward-compat shim over :func:`dc_cut.core.io.offset_label.from_suffix`.

    Historically this returned the label *without* a trailing ``m``
    (``'p66'`` → ``'+66'``). Match that convention for stored callers.
    """
    label = _from_suffix_core(suffix)
    if label.endswith("m"):
        label = label[:-1]
    return label or suffix


__all__ = [
    "read_spectrum_npz",
    "normalize_offset",
    "_label_to_suffix",
    "_suffix_to_label",
]
