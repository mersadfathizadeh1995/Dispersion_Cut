from __future__ import annotations

import os
import numpy as np
from typing import List, Tuple


def load_combined_csv(csv_path: str) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray], List[str]]:
    """Load combined CSV of freq/vel(/wave) per offset.

    Returns (velocity_arrays, frequency_arrays, wavelength_arrays, set_leg)
    """
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with open(csv_path, 'r') as f:
        header_line = f.readline().strip()
        headers = [h.strip() for h in header_line.split(',') if h.strip()]
        total_cols = len(headers)
        headers_lower = [h.lower() for h in headers]

        has_wave = any("wave(" in h or "wavelength(" in h for h in headers_lower)
        columns_per_offset = 3 if (has_wave or total_cols % 3 == 0) else 2
        offset_count = total_cols // columns_per_offset

        def _extract_label(freq_label: str, index: int) -> str:
            lp = freq_label.find('(')
            rp = freq_label.find(')')
            if lp != -1 and rp != -1 and rp > lp + 1:
                inner = freq_label[lp+1:rp].strip()
                inner_low = inner.lower()
                # Avoid unit tokens like Hz/kHz and generic units
                unit_tokens = {"hz", "khz", "mhz", "ghz", "m/s", "m", "s"}
                if inner_low not in unit_tokens and "/" not in inner_low:
                    return inner
            return f"Offset {index+1}"

        set_leg: List[str] = []
        for i in range(offset_count):
            freq_label = headers[i*columns_per_offset] if i*columns_per_offset < len(headers) else "Freq"
            set_leg.append(_extract_label(freq_label, i))

        rows = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(',')]
            # Coerce non-numeric tokens to NaN, then drop incomplete rows later
            vec = []
            for p in parts:
                try:
                    vec.append(float(p))
                except Exception:
                    vec.append(float('nan'))
            rows.append(vec)
    mat = np.array(rows, float)

    frequency_arrays: List[np.ndarray] = []
    velocity_arrays: List[np.ndarray] = []
    wavelength_arrays: List[np.ndarray] = []
    for i in range(offset_count):
        start = i * columns_per_offset
        fcol = mat[:, start]
        vcol = mat[:, start+1]
        if columns_per_offset == 3:
            wcol = mat[:, start+2]
        else:
            with np.errstate(divide='ignore', invalid='ignore'):
                wcol = vcol / fcol
        # Filter invalid rows per offset
        mask = np.isfinite(fcol) & np.isfinite(vcol) & np.isfinite(wcol) & (fcol > 0) & (wcol > 0)
        frequency_arrays.append(fcol[mask])
        velocity_arrays.append(vcol[mask])
        wavelength_arrays.append(wcol[mask])

    return velocity_arrays, frequency_arrays, wavelength_arrays, set_leg
