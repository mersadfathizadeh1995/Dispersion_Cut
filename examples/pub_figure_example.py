"""Examples for generating publication-quality dispersion curve figures.

This module demonstrates how to use the PublicationFigureGenerator class
to create high-quality figures for scientific publications.

The generator can be used in two ways:
1. From an interactive DC_Cut session (recommended)
2. From saved data arrays (for batch processing)

Author: DC_Cut Team
Date: 2025
"""

from __future__ import annotations

import numpy as np
from pathlib import Path


# ==============================================================================
# Example 1: Generate figure from interactive session
# ==============================================================================
def example_from_session(controller):
    """Generate publication figure from an interactive DC_Cut session.

    This is the recommended approach when you have an active session with
    data already loaded and processed.

    Args:
        controller: Instance of InteractiveRemovalWithLayers
    """
    from dc_cut.core.pub_figures import PublicationFigureGenerator, PlotConfig

    # Create generator from controller
    generator = PublicationFigureGenerator.from_controller(controller)

    # Option 1: Use default configuration
    generator.generate_aggregated_plot(output_path='dispersion_curve.pdf')

    # Option 2: Customize configuration
    config = PlotConfig(
        figsize=(10, 7),           # Figure size in inches
        dpi=300,                   # Resolution for raster outputs
        font_family='serif',       # Use serif fonts (Times-like)
        font_size=12,              # Base font size
        color_palette='vibrant',   # Colorblind-friendly palette
        mark_near_field=True,      # Mark near-field data
        near_field_style='faded',  # Fade near-field points
        nacd_threshold=1.0,        # NACD threshold
        show_grid=True,            # Show grid
        output_format='pdf',       # PDF (vector format)
    )

    generator.generate_aggregated_plot(
        output_path='custom_dispersion_curve.pdf',
        config=config
    )

    print("✓ Generated aggregated dispersion curve")


# ==============================================================================
# Example 2: Generate per-offset figure
# ==============================================================================
def example_per_offset(controller):
    """Generate per-offset dispersion curves.

    This plot shows individual curves for each active offset/layer,
    which is useful for comparing multiple offsets or showing data diversity.

    Args:
        controller: Instance of InteractiveRemovalWithLayers
    """
    from dc_cut.core.pub_figures import PublicationFigureGenerator, PlotConfig

    generator = PublicationFigureGenerator.from_controller(controller)

    config = PlotConfig(
        figsize=(8, 6),
        dpi=300,
        font_family='serif',
        font_size=11,
        color_palette='muted',      # Use muted color palette
        show_grid=True,
    )

    generator.generate_per_offset_plot(
        output_path='per_offset_curves.pdf',
        config=config,
        max_offsets=10  # Limit to 10 offsets to avoid clutter
    )

    print("✓ Generated per-offset dispersion curves")


# ==============================================================================
# Example 3: Generate uncertainty visualization
# ==============================================================================
def example_uncertainty(controller):
    """Generate uncertainty visualization plot.

    This plot shows the coefficient of variation (CV = σ/μ) as a function
    of frequency, highlighting regions with high uncertainty.

    Args:
        controller: Instance of InteractiveRemovalWithLayers
    """
    from dc_cut.core.pub_figures import PublicationFigureGenerator, PlotConfig

    generator = PublicationFigureGenerator.from_controller(controller)

    config = PlotConfig(
        figsize=(8, 5),
        dpi=300,
        font_family='serif',
        font_size=11,
        color_palette='vibrant',
        mark_near_field=True,
        near_field_style='faded',
        show_grid=True,
    )

    generator.generate_uncertainty_plot(
        output_path='uncertainty_plot.pdf',
        config=config
    )

    print("✓ Generated uncertainty visualization")


# ==============================================================================
# Example 4: Generate all three plot types
# ==============================================================================
def example_generate_all(controller, output_dir='publication_figures'):
    """Generate all three plot types with consistent styling.

    Args:
        controller: Instance of InteractiveRemovalWithLayers
        output_dir: Directory to save figures (created if doesn't exist)
    """
    from dc_cut.core.pub_figures import PublicationFigureGenerator, PlotConfig

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Create generator
    generator = PublicationFigureGenerator.from_controller(controller)

    # Shared configuration
    config = PlotConfig(
        figsize=(8, 6),
        dpi=300,
        font_family='serif',
        font_size=11,
        line_width=1.5,
        marker_size=4.0,
        color_palette='vibrant',
        uncertainty_alpha=0.3,
        near_field_alpha=0.4,
        mark_near_field=True,
        near_field_style='faded',
        nacd_threshold=1.0,
        show_grid=True,
        grid_alpha=0.3,
        output_format='pdf',
        tight_layout=True,
    )

    # Generate aggregated plot
    generator.generate_aggregated_plot(
        output_path=str(output_path / 'fig1_aggregated.pdf'),
        config=config
    )
    print(f"✓ Generated {output_path / 'fig1_aggregated.pdf'}")

    # Generate per-offset plot
    generator.generate_per_offset_plot(
        output_path=str(output_path / 'fig2_per_offset.pdf'),
        config=config,
        max_offsets=10
    )
    print(f"✓ Generated {output_path / 'fig2_per_offset.pdf'}")

    # Generate uncertainty plot
    generator.generate_uncertainty_plot(
        output_path=str(output_path / 'fig3_uncertainty.pdf'),
        config=config
    )
    print(f"✓ Generated {output_path / 'fig3_uncertainty.pdf'}")

    print(f"\n✓ All figures saved to: {output_path.absolute()}")


# ==============================================================================
# Example 5: Use different output formats
# ==============================================================================
def example_output_formats(controller):
    """Generate figures in different output formats.

    PDF is recommended for publications (vector format), but PNG and SVG
    are also supported.

    Args:
        controller: Instance of InteractiveRemovalWithLayers
    """
    from dc_cut.core.pub_figures import PublicationFigureGenerator, PlotConfig

    generator = PublicationFigureGenerator.from_controller(controller)

    # PDF (vector, recommended)
    config_pdf = PlotConfig(output_format='pdf', dpi=300)
    generator.generate_aggregated_plot(
        output_path='dispersion_curve.pdf',
        config=config_pdf
    )

    # PNG (raster, for presentations)
    config_png = PlotConfig(output_format='png', dpi=300)
    generator.generate_aggregated_plot(
        output_path='dispersion_curve.png',
        config=config_png
    )

    # SVG (vector, for web/editing)
    config_svg = PlotConfig(output_format='svg', dpi=300)
    generator.generate_aggregated_plot(
        output_path='dispersion_curve.svg',
        config=config_svg
    )

    # High-resolution PNG (for posters)
    config_highres = PlotConfig(output_format='png', dpi=600, figsize=(12, 9))
    generator.generate_aggregated_plot(
        output_path='dispersion_curve_highres.png',
        config=config_highres
    )

    print("✓ Generated figures in multiple formats")


# ==============================================================================
# Example 6: Customize near-field marking styles
# ==============================================================================
def example_near_field_styles(controller):
    """Compare different near-field marking styles.

    Args:
        controller: Instance of InteractiveRemovalWithLayers
    """
    from dc_cut.core.pub_figures import PublicationFigureGenerator, PlotConfig

    generator = PublicationFigureGenerator.from_controller(controller)

    # Style 1: Faded (default, recommended)
    config_faded = PlotConfig(
        near_field_style='faded',
        near_field_alpha=0.4,
        mark_near_field=True,
    )
    generator.generate_aggregated_plot(
        output_path='nf_style_faded.pdf',
        config=config_faded
    )

    # Style 2: Crossed (clear separation)
    config_crossed = PlotConfig(
        near_field_style='crossed',
        near_field_alpha=0.5,
        mark_near_field=True,
    )
    generator.generate_aggregated_plot(
        output_path='nf_style_crossed.pdf',
        config=config_crossed
    )

    # Style 3: No marking (treat all data equally)
    config_none = PlotConfig(
        near_field_style='none',
        mark_near_field=False,
    )
    generator.generate_aggregated_plot(
        output_path='nf_style_none.pdf',
        config=config_none
    )

    print("✓ Generated figures with different near-field styles")


# ==============================================================================
# Example 7: Generate from saved data arrays
# ==============================================================================
def example_from_arrays():
    """Generate figure from saved data arrays (without active session).

    This approach is useful for batch processing or when you have saved
    data arrays from previous sessions.
    """
    from dc_cut.core.pub_figures import PublicationFigureGenerator, PlotConfig

    # Example: Load data from saved files (numpy arrays)
    # In practice, you would load these from your saved session data
    velocity_arrays = [
        np.array([300, 350, 400, 450, 500]),  # Layer 1
        np.array([320, 370, 420, 470, 520]),  # Layer 2
        np.array([310, 360, 410, 460, 510]),  # Layer 3
    ]

    frequency_arrays = [
        np.array([5, 10, 15, 20, 25]),   # Layer 1
        np.array([5, 10, 15, 20, 25]),   # Layer 2
        np.array([5, 10, 15, 20, 25]),   # Layer 3
    ]

    wavelength_arrays = [
        np.array([60, 35, 26.7, 22.5, 20]),   # Layer 1 (λ = v/f)
        np.array([64, 37, 28, 23.5, 20.8]),   # Layer 2
        np.array([62, 36, 27.3, 23, 20.4]),   # Layer 3
    ]

    layer_labels = ['Offset 1', 'Offset 2', 'Offset 3']

    # Optional: provide array positions for NACD computation
    array_positions = np.arange(0, 48, 2.0)  # 24 receivers, 2m spacing

    # Create generator
    generator = PublicationFigureGenerator.from_arrays(
        velocity_arrays=velocity_arrays,
        frequency_arrays=frequency_arrays,
        wavelength_arrays=wavelength_arrays,
        layer_labels=layer_labels,
        array_positions=array_positions,
    )

    # Generate figure
    config = PlotConfig(
        figsize=(8, 6),
        dpi=300,
        font_family='serif',
        mark_near_field=True,
    )

    generator.generate_aggregated_plot(
        output_path='from_arrays.pdf',
        config=config
    )

    print("✓ Generated figure from saved arrays")


# ==============================================================================
# Example 8: Customize axis limits
# ==============================================================================
def example_custom_limits(controller):
    """Generate figure with custom axis limits.

    Args:
        controller: Instance of InteractiveRemovalWithLayers
    """
    from dc_cut.core.pub_figures import PublicationFigureGenerator, PlotConfig

    generator = PublicationFigureGenerator.from_controller(controller)

    config = PlotConfig(
        xlim=(5, 50),        # Frequency range: 5-50 Hz
        ylim=(200, 600),     # Velocity range: 200-600 m/s
        show_grid=True,
    )

    generator.generate_aggregated_plot(
        output_path='custom_limits.pdf',
        config=config
    )

    print("✓ Generated figure with custom axis limits")


# ==============================================================================
# Example 9: Use different color palettes
# ==============================================================================
def example_color_palettes(controller):
    """Compare different colorblind-friendly palettes.

    Args:
        controller: Instance of InteractiveRemovalWithLayers
    """
    from dc_cut.core.pub_figures import PublicationFigureGenerator, PlotConfig

    generator = PublicationFigureGenerator.from_controller(controller)

    palettes = ['vibrant', 'muted', 'bright']

    for palette in palettes:
        config = PlotConfig(color_palette=palette)
        generator.generate_per_offset_plot(
            output_path=f'palette_{palette}.pdf',
            config=config,
            max_offsets=5
        )
        print(f"✓ Generated figure with '{palette}' palette")


# ==============================================================================
# Main function for demonstration
# ==============================================================================
def main():
    """Main function to demonstrate usage.

    Note: This requires an active DC_Cut session with data loaded.
    In practice, you would call these functions from your analysis scripts.
    """
    print("=" * 70)
    print("DC_Cut Publication Figure Generator - Examples")
    print("=" * 70)
    print()
    print("These examples demonstrate how to generate publication-quality")
    print("dispersion curve figures using the PublicationFigureGenerator.")
    print()
    print("To use these examples:")
    print("  1. Load data in DC_Cut")
    print("  2. Process and clean your dispersion curves")
    print("  3. Call the example functions with your controller instance")
    print()
    print("Example usage:")
    print("  >>> from dc_cut.examples.pub_figure_example import example_generate_all")
    print("  >>> example_generate_all(controller)")
    print()
    print("Available examples:")
    print("  - example_from_session(controller)")
    print("  - example_per_offset(controller)")
    print("  - example_uncertainty(controller)")
    print("  - example_generate_all(controller)")
    print("  - example_output_formats(controller)")
    print("  - example_near_field_styles(controller)")
    print("  - example_from_arrays()")
    print("  - example_custom_limits(controller)")
    print("  - example_color_palettes(controller)")
    print()
    print("=" * 70)


if __name__ == '__main__':
    main()
