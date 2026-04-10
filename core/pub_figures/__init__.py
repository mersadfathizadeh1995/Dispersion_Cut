"""Backward-compatibility shim -- real package is dc_cut.visualization.pub_figures."""
from dc_cut.visualization.pub_figures import (  # noqa: F401
    PlotConfig,
    PublicationFigureGenerator,
    COLORBLIND_PALETTE,
)

__all__ = [
    'PlotConfig',
    'PublicationFigureGenerator',
    'COLORBLIND_PALETTE',
]
