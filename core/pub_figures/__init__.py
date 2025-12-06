"""Publication-quality figure generation package.

This package provides modular, extensible tools for generating
publication-ready dispersion curve figures.

Usage:
    from dc_cut.core.pub_figures import PublicationFigureGenerator, PlotConfig
    
    # From controller
    gen = PublicationFigureGenerator.from_controller(controller)
    gen.generate_aggregated_plot(output_path='figure.pdf')
    
    # With custom config
    config = PlotConfig(figsize=(10, 8), dpi=300, color_palette='muted')
    gen.generate_per_offset_plot(output_path='offsets.pdf', config=config)
"""

from .config import PlotConfig, COLORBLIND_PALETTE
from .generator import PublicationFigureGenerator

__all__ = [
    'PlotConfig',
    'PublicationFigureGenerator',
    'COLORBLIND_PALETTE',
]
