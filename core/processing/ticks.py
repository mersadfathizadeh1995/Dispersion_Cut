from __future__ import annotations

from typing import List, Tuple
import numpy as np


def make_freq_ticks(style: str, xmin: float, xmax: float, custom: List[float] | None = None) -> Tuple[List[float], List[str]]:
    """Return (ticks, labels) for a log-scaled frequency axis.

    style: 'decades' | 'one-two-five' | 'custom' | 'ruler'
    xmin/xmax: current axis bounds (positive)
    custom: optional list of tick values for 'custom'
    """
    xmin = max(xmin, 1e-3)
    ticks: List[float] = []
    if style == 'one-two-five':
        decades = np.arange(np.floor(np.log10(xmin)), np.ceil(np.log10(xmax)) + 1)
        for d in decades:
            base = 10.0 ** d
            for m in (1.0, 2.0, 5.0):
                val = m * base
                if val >= xmin and val <= xmax:
                    ticks.append(float(val))
    elif style == 'custom':
        if not custom:
            custom = []
        ticks = [float(v) for v in custom if v >= xmin and v <= xmax]
    elif style == 'ruler':
        majors = [1,2,3,4,5,6,7,8,9,10,15,20,30,40,50,60,80,100]
        ticks = [float(v) for v in majors if v >= xmin and v <= xmax]
    else:  # 'decades'
        decades = np.arange(np.floor(np.log10(xmin)), np.ceil(np.log10(xmax)) + 1)
        ticks = [float(10.0 ** d) for d in decades]

    def _fmt(v: float) -> str:
        if v >= 10:
            return f"{int(v):d}"
        if v >= 1:
            s = f"{v:.1f}"
            return s.rstrip('0').rstrip('.')
        s = f"{v:.3f}"
        return s.rstrip('0').rstrip('.')

    return ticks, [_fmt(v) for v in ticks]










