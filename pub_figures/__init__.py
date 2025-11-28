"""Publication-quality figure generation package for DC_Cut.

This package provides modular, extensible tools for generating
publication-ready dispersion curve figures.

Modules:
    config: PlotConfig dataclass and constants
    generator: Base PublicationFigureGenerator class
    basic: Basic plot types (aggregated, per-offset, dual-domain)
    uncertainty: Statistical uncertainty visualizations
    modal: Modal analysis figures (future)
    nearfield: Near-field analysis figures (future)
    qc: Quality control figures (future)
    comparison: Comparison figures (future)
    utils: Shared utilities

Usage:
    from dc_cut.pub_figures import PublicationFigureGenerator, PlotConfig
    
    # From controller
    gen = PublicationFigureGenerator.from_controller(controller)
    gen.generate_aggregated_plot(output_path='figure.pdf')
    
    # With custom config
    config = PlotConfig(figsize=(10, 8), dpi=300, color_palette='muted')
    gen.generate_per_offset_plot(output_path='offsets.pdf', config=config)
"""

from dc_cut.pub_figures.config import PlotConfig, COLORBLIND_PALETTES
from dc_cut.pub_figures.generator import PublicationFigureGenerator

__all__ = [
    'PlotConfig',
    'PublicationFigureGenerator',
    'COLORBLIND_PALETTES',
]

__version__ = '2.0.0'
