from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional, Tuple

try:
    import scipy.io  # optional
except Exception:
    scipy = None  # type: ignore


def load_klimits(*, mat_path: Optional[str] = None, csv_path: Optional[str] = None) -> Tuple[float, float]:
    if mat_path:
        if scipy is None:
            raise ImportError("SciPy is required to read MAT files.")
        mat = scipy.io.loadmat(mat_path)
        if 'klimits' not in mat:
            raise ValueError(f"MAT-file {mat_path!r} does not contain 'klimits'")
        arr = np.array(mat['klimits']).squeeze()
        if arr.size != 2:
            raise ValueError("'klimits' must have two elements [kmin, kmax]")
        return float(arr[0]), float(arr[1])
    if csv_path:
        with open(csv_path, 'r') as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                parts = [p for p in s.replace(',', ' ').split() if p]
                if len(parts) >= 2:
                    return float(parts[0]), float(parts[1])
        raise ValueError(f"CSV {csv_path!r} does not contain two numbers")
    raise ValueError("Provide mat_path or csv_path for klimits")


def parse_max_file(path: str) -> pd.DataFrame:
    """Parse Geopsy FK .max with robustness to separators and header lines."""
    cols = ['time', 'freq', 'slow', 'az', 'phi', 'semblance', 'beampow']
    try:
        df = pd.read_csv(
            path,
            comment='#',
            header=None,
            sep=r"[\s\|]+",
            usecols=list(range(7)),
            names=cols,
            engine='python',
            on_bad_lines='skip',
        )
    except TypeError:
        df = pd.read_csv(
            path,
            comment='#',
            header=None,
            sep=r"[\s\|]+",
            usecols=list(range(7)),
            names=cols,
            engine='python',
        )
    df = df.dropna(subset=['freq', 'slow'])
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['freq', 'slow'])
    return df










