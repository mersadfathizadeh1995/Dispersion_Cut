"""
Read .npz spectrum files → list of SpectrumData.

Supports both single-offset and combined (multi-offset) NPZ formats.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np

from ..core.models import SpectrumData


def read_spectrum_npz(path: str | Path) -> List[SpectrumData]:
    """
    Load spectrum data from an NPZ file.

    Returns one SpectrumData per offset found in the file.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"NPZ file not found: {path}")

    data = np.load(path, allow_pickle=True)
    keys = list(data.keys())

    # Detect combined vs single format
    if "offsets" in keys:
        return _read_combined(data)
    elif "power" in keys:
        return _read_single(data)
    else:
        return _read_combined_by_pattern(data, keys)


def _read_single(data) -> List[SpectrumData]:
    """Single-offset NPZ: frequencies, velocities, power."""
    freq = np.asarray(data["frequencies"], dtype=float)
    vel = np.asarray(data["velocities"], dtype=float)
    power = np.asarray(data["power"], dtype=float)
    method = str(data["method"]) if "method" in data else "unknown"
    offset = str(data["offset"]) if "offset" in data else ""

    return [SpectrumData(
        offset_name=offset,
        frequencies=freq,
        velocities=vel,
        power=power,
        method=method,
    )]


def _read_combined(data) -> List[SpectrumData]:
    """Combined NPZ with explicit 'offsets' array."""
    offsets = list(data["offsets"])
    method = str(data.get("method", "unknown"))
    results = []

    for offset_label in offsets:
        suffix = _label_to_suffix(str(offset_label))
        freq_key = f"frequencies_{suffix}"
        vel_key = f"velocities_{suffix}"
        power_key = f"power_{suffix}"

        if freq_key in data and vel_key in data and power_key in data:
            results.append(SpectrumData(
                offset_name=str(offset_label),
                frequencies=np.asarray(data[freq_key], dtype=float),
                velocities=np.asarray(data[vel_key], dtype=float),
                power=np.asarray(data[power_key], dtype=float),
                method=method,
            ))

    return results


def _read_combined_by_pattern(data, keys: list) -> List[SpectrumData]:
    """Detect combined format by looking for frequencies_* pattern."""
    freq_keys = sorted(k for k in keys if k.startswith("frequencies_"))
    method = str(data.get("method", "unknown")) if "method" in data else "unknown"
    results = []

    for fk in freq_keys:
        suffix = fk.replace("frequencies_", "")
        vel_key = f"velocities_{suffix}"
        power_key = f"power_{suffix}"

        if vel_key in keys and power_key in keys:
            offset_name = _suffix_to_label(suffix)
            results.append(SpectrumData(
                offset_name=offset_name,
                frequencies=np.asarray(data[fk], dtype=float),
                velocities=np.asarray(data[vel_key], dtype=float),
                power=np.asarray(data[power_key], dtype=float),
                method=method,
            ))

    return results


def _label_to_suffix(label: str) -> str:
    """Convert offset label like '+66m' to NPZ key suffix like 'p66'."""
    s = label.strip().lower()
    s = s.replace(" ", "").replace("m", "")
    s = s.replace("+", "p").replace("-", "n")
    return s


def _suffix_to_label(suffix: str) -> str:
    """Convert NPZ key suffix like 'p66' back to label like '+66m'."""
    s = suffix
    if s.startswith("p"):
        return f"+{s[1:]}m"
    elif s.startswith("n"):
        return f"-{s[1:]}m"
    return s
