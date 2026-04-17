from __future__ import annotations

import numpy as np
from typing import Dict, List


def compute_k_guides(kmin: float, kmax: float, fmin: float, fmax: float) -> Dict[str, object]:
    if kmin <= 0 or kmax <= 0:
        raise ValueError("k-limits must be positive")
    fmin = max(1e-3, float(fmin))
    fmax = max(float(fmax), fmin * 1.1)
    f_curve = np.logspace(np.log10(fmin), np.log10(fmax), 300)
    v_ap   = (2*np.pi*f_curve)/float(kmin)
    v_ap2  = (2*np.pi*f_curve)/(float(kmin)/2.0)
    v_al   = (2*np.pi*f_curve)/float(kmax)
    v_al2  = (2*np.pi*f_curve)/(float(kmax)/2.0)
    w_ap   = 2*np.pi/float(kmin)
    w_ap2  = 2*np.pi/(float(kmin)/2.0)
    w_al   = 2*np.pi/float(kmax)
    w_al2  = 2*np.pi/(float(kmax)/2.0)
    return {
        'f_curve': f_curve,
        'v_ap':  v_ap,
        'v_ap2': v_ap2,
        'v_al':  v_al,
        'v_al2': v_al2,
        'w_ap':  w_ap,
        'w_ap2': w_ap2,
        'w_al':  w_al,
        'w_al2': w_al2,
    }










