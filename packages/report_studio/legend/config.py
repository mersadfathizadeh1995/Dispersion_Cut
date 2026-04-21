"""Lightweight value types for the legend module.

The main config dataclass (:class:`SubplotLegendConfig`) lives in
:mod:`packages.report_studio.core.models` so it can be a default
field on :class:`SubplotState` without creating an import cycle.
This module only adds the auxiliary :class:`LegendItem` record
returned by extension collectors.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LegendItem:
    """One legend entry contributed by an extension collector.

    Renderers normally rely on Matplotlib's automatic
    handle/label discovery (``ax.get_legend_handles_labels()``).
    For overlays that want to add a custom symbol that does not
    correspond to a visible artist (e.g. a translucent NACD band
    swatch, or a "Theoretical bound" marker), a collector may emit
    one of these and the legend builder will append it.
    """

    handle: Any  # any Matplotlib artist that legend() understands
    label: str
