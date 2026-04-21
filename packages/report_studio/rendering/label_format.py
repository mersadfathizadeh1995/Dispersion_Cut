"""Centralized number formatting for frequency / wavelength labels.

The renderer and a few label-building sites used ``f"{v:g}"`` previously,
which gave inconsistent precision (``8.66`` vs ``43``) and hard-coded the
choice. Routing everything through these helpers means the user can pick
the precision once in the Global panel (``typography.freq_decimals`` /
``typography.lambda_decimals``) and every label updates.
"""

from __future__ import annotations


def _clamp_decimals(decimals) -> int:
    try:
        d = int(decimals)
    except (TypeError, ValueError):
        return 1
    if d < 0:
        return 0
    if d > 6:
        return 6
    return d


def fmt_freq(value: float, decimals=1) -> str:
    """Format a frequency value with the given number of decimals."""
    d = _clamp_decimals(decimals)
    try:
        return f"{float(value):.{d}f}"
    except (TypeError, ValueError):
        return str(value)


def fmt_lambda(value: float, decimals=1) -> str:
    """Format a wavelength value with the given number of decimals."""
    d = _clamp_decimals(decimals)
    try:
        return f"{float(value):.{d}f}"
    except (TypeError, ValueError):
        return str(value)


__all__ = ["fmt_freq", "fmt_lambda"]
