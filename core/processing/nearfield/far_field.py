"""Far-field attenuation sanity check.

Assesses whether a source offset is too large for reliable low-frequency
data.  Beyond a certain distance, geometric spreading and material
attenuation reduce signal-to-noise below useful levels, even though
NACD values would look "clean".

Rahimi et al. (2022) Section 4.2, Fig. 12:
  40 m offset at Aubrey → λ_max = 71 m (less than 20 m offset's 140 m)
  because far-field signal attenuation.

No framework imports, no controller references.
"""
from __future__ import annotations

from typing import Any, Dict
import numpy as np


def assess_far_field_risk(
    source_offset: float,
    receiver_positions: np.ndarray,
    v_phase_max: float,
    f_min: float,
    *,
    attenuation_qr: float = 20.0,
    geometric_power: float = 0.5,
    snr_threshold: float = 0.1,
    max_offset_wavelengths: float = 3.0,
) -> Dict[str, Any]:
    """Check if a source offset is too far for reliable low-frequency data.

    Parameters
    ----------
    source_offset : float
        Distance from source to array center (m).
    receiver_positions : array
        Receiver positions (m).
    v_phase_max : float
        Maximum expected phase velocity (m/s) at the site.
    f_min : float
        Lowest frequency of interest (Hz).
    attenuation_qr : float
        Quality factor for Rayleigh waves (lower = more attenuation).
        Typical range: 10–50 for shallow soils.
    geometric_power : float
        Geometric spreading exponent (0.5 for surface waves).
    snr_threshold : float
        Relative amplitude below which signal is considered lost.
    max_offset_wavelengths : float
        Maximum source-to-center distance in wavelengths before
        far-field attenuation becomes a concern.

    Returns
    -------
    dict
        ``at_risk`` — bool, whether far-field attenuation is likely.
        ``max_reliable_wavelength`` — largest wavelength with adequate SNR.
        ``attenuation_at_fmin`` — relative amplitude at f_min.
        ``offset_in_wavelengths`` — source offset / max wavelength.
        ``message`` — human-readable assessment.
    """
    recv = np.asarray(receiver_positions, float)
    x_bar = float(np.mean(np.abs(recv - source_offset)))
    lambda_max = v_phase_max / max(f_min, 1e-6)

    # Geometric spreading attenuation: A_geo = (r_ref / r)^p
    r_ref = float(np.min(np.abs(recv - source_offset)))
    r_ref = max(r_ref, 1.0)  # avoid zero
    a_geo = (r_ref / max(x_bar, 1.0)) ** geometric_power

    # Material attenuation: A_mat = exp(-π f r / (Q V))
    a_mat = float(np.exp(-np.pi * f_min * x_bar / (attenuation_qr * v_phase_max)))

    total_attenuation = a_geo * a_mat

    # Offset in wavelengths
    offset_wl = abs(source_offset) / max(lambda_max, 1e-6)

    at_risk = total_attenuation < snr_threshold or offset_wl > max_offset_wavelengths

    # Find max reliable wavelength (where attenuation >= threshold)
    test_freqs = np.geomspace(max(f_min, 0.1), 100.0, 200)
    max_reliable_wl = 0.0
    for freq in test_freqs:
        wl = v_phase_max / freq
        r = max(x_bar, 1.0)
        a = (r_ref / r) ** geometric_power * np.exp(-np.pi * freq * r / (attenuation_qr * v_phase_max))
        if a >= snr_threshold:
            max_reliable_wl = max(max_reliable_wl, wl)

    if at_risk:
        msg = (
            f"Far-field attenuation risk: source at {source_offset:.1f}m "
            f"(x̄ = {x_bar:.1f}m, {offset_wl:.1f}λ). "
            f"Signal amplitude at f_min = {total_attenuation:.2%} of reference. "
            f"Max reliable λ ≈ {max_reliable_wl:.1f}m."
        )
    else:
        msg = (
            f"Source at {source_offset:.1f}m OK: "
            f"amplitude at f_min = {total_attenuation:.2%}, "
            f"offset = {offset_wl:.1f}λ."
        )

    return {
        "at_risk": at_risk,
        "max_reliable_wavelength": max_reliable_wl,
        "attenuation_at_fmin": float(total_attenuation),
        "offset_in_wavelengths": float(offset_wl),
        "x_bar": x_bar,
        "message": msg,
    }


def assess_far_field_risk_batch(
    source_offsets: list[float],
    receiver_positions: np.ndarray,
    v_phase_max: float,
    f_min: float,
    **kwargs,
) -> list[Dict[str, Any]]:
    """Assess far-field risk for multiple source offsets."""
    return [
        assess_far_field_risk(so, receiver_positions, v_phase_max, f_min, **kwargs)
        for so in source_offsets
    ]
