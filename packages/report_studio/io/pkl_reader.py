"""
Read DC Cut .pkl state files → list of OffsetCurve.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from ..core.models import OffsetCurve, CURVE_COLORS


def read_pkl(path: str | Path) -> List[OffsetCurve]:
    """
    Load a DC Cut state file and return a list of OffsetCurve objects.

    The PKL file contains:
      velocity_arrays, frequency_arrays, wavelength_arrays, offset_labels,
      set_leg, layer_spectrum_settings, ...
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PKL file not found: {path}")

    with open(path, "rb") as fh:
        state = pickle.load(fh)

    velocity_arrays = state.get("velocity_arrays", [])
    frequency_arrays = state.get("frequency_arrays", [])
    wavelength_arrays = state.get("wavelength_arrays", [])
    labels = state.get("offset_labels", [])

    # Fallback for older state format
    if not labels:
        labels = state.get("set_leg", [])
    if isinstance(labels, set):
        labels = sorted(labels)

    n = min(len(velocity_arrays), len(frequency_arrays))
    while len(labels) < n:
        labels.append(f"Offset {len(labels)+1}")

    # Build wavelength if missing
    if not wavelength_arrays or len(wavelength_arrays) < n:
        wavelength_arrays = []
        for i in range(n):
            freq = frequency_arrays[i]
            vel = velocity_arrays[i]
            with np.errstate(divide="ignore", invalid="ignore"):
                wl = np.where(freq > 0, vel / freq, 0.0)
            wavelength_arrays.append(wl)

    curves: List[OffsetCurve] = []
    for i in range(n):
        freq = np.asarray(frequency_arrays[i], dtype=float)
        vel = np.asarray(velocity_arrays[i], dtype=float)
        wl = np.asarray(wavelength_arrays[i], dtype=float)
        label = str(labels[i]) if i < len(labels) else f"Offset {i+1}"

        curve = OffsetCurve(
            name=label,
            frequency=freq,
            velocity=vel,
            wavelength=wl,
            color=CURVE_COLORS[i % len(CURVE_COLORS)],
            subplot_key="main",
        )
        curves.append(curve)

    return curves


def read_pkl_metadata(path: str | Path) -> dict:
    """Read just metadata from PKL without full array loading."""
    path = Path(path)
    with open(path, "rb") as fh:
        state = pickle.load(fh)

    labels = state.get("offset_labels", state.get("set_leg", []))
    if isinstance(labels, set):
        labels = sorted(labels)

    n = len(state.get("velocity_arrays", []))
    return {
        "n_offsets": n,
        "labels": list(labels)[:n],
        "has_spectrum_settings": "layer_spectrum_settings" in state,
        "kmin": state.get("kmin"),
        "kmax": state.get("kmax"),
    }
