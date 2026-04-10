"""Publication-quality figure generation for DC Cut.

This is the canonical location. Backward-compat shims exist at
dc_cut.core.pub_figures and dc_cut.pub_figures.
"""
from dc_cut.visualization.pub_figures.config import PlotConfig, COLORBLIND_PALETTE
from dc_cut.visualization.pub_figures.generator import PublicationFigureGenerator

__all__ = [
    'PlotConfig',
    'PublicationFigureGenerator',
    'COLORBLIND_PALETTE',
]
