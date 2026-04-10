"""Figure type definitions and constants for pub_figures_dialog."""

from __future__ import annotations

from typing import Dict, List, Tuple

# Each entry: (display_name, internal_key, description, is_implemented)
FIGURE_TYPES: Dict[str, List[Tuple[str, str, str, bool]]] = {
    "Basic Plots - Frequency Domain": [
        (
            "Aggregated Dispersion Curve",
            "aggregated",
            "Shows binned average velocity with +/-1 sigma uncertainty envelope.\n"
            "Suitable for final dispersion curves in publications.",
            True
        ),
        (
            "Per-Offset Curves",
            "per_offset",
            "Shows individual curves for each active offset/layer.\n"
            "Useful for comparing multiple offsets or showing data diversity.",
            True
        ),
        (
            "Uncertainty Visualization",
            "uncertainty",
            "Shows coefficient of variation (CV = sigma/mu) as a function of frequency.\n"
            "Highlights regions with high uncertainty.",
            True
        ),
    ],
    "Basic Plots - Wavelength Domain": [
        (
            "Aggregated Wavelength",
            "aggregated_wavelength",
            "Same as aggregated but in wavelength domain.\n"
            "Better for depth-related interpretations (lambda/2 or lambda/3 rules).",
            True
        ),
        (
            "Per-Offset Wavelength",
            "per_offset_wavelength",
            "Per-offset curves in wavelength domain.\n"
            "Shows aperture-wavelength relationships clearly.",
            True
        ),
        (
            "Dual-Domain Comparison",
            "dual_domain",
            "Side-by-side frequency and wavelength plots.\n"
            "Very common in MASW publications for comprehensive presentation.",
            True
        ),
    ],
    "Modal Analysis": [
        (
            "Multi-Mode Overlay",
            "multi_mode_overlay",
            "Overlays multiple modes (fundamental + higher) on the same plot.\n"
            "Useful for showing mode identification results.",
            False
        ),
        (
            "Modal Energy Distribution",
            "modal_energy",
            "Shows relative energy distribution between modes.\n"
            "Helps identify dominant modes at different frequencies.",
            False
        ),
        (
            "Mode Confidence Map",
            "mode_confidence",
            "Color-coded confidence levels for mode identification.\n"
            "Indicates reliability of mode separation.",
            False
        ),
        (
            "Apparent vs. Fundamental",
            "apparent_vs_fundamental",
            "Compares apparent (picked) curve with theoretical fundamental mode.\n"
            "Useful for validating mode identification.",
            False
        ),
        (
            "Modal Separation Quality",
            "modal_separation",
            "Visualizes the quality of separation between modes.\n"
            "Shows spectral gaps and overlapping regions.",
            False
        ),
        (
            "Cross-Component (Z vs. R)",
            "cross_component",
            "Compares vertical and radial component dispersion curves.\n"
            "Useful for multi-component MASW analysis.",
            False
        ),
    ],
    "Uncertainty & Statistics": [
        (
            "Data Density Heatmap",
            "density_heatmap",
            "2D histogram showing data point density in frequency-velocity space.\n"
            "Reveals data concentration and sparse regions.",
            False
        ),
        (
            "Percentile Bands (5th-95th)",
            "percentile_bands",
            "Shows multiple percentile bands instead of just standard deviation.\n"
            "Provides more robust uncertainty visualization.",
            False
        ),
        (
            "Bootstrap Confidence Intervals",
            "bootstrap_ci",
            "Confidence intervals computed via bootstrap resampling.\n"
            "More robust for non-normal distributions.",
            False
        ),
        (
            "Per-Offset CV Comparison",
            "cv_comparison",
            "Compares CV values across different offsets.\n"
            "Identifies which offsets contribute most uncertainty.",
            False
        ),
        (
            "Heterogeneity Map",
            "heterogeneity_map",
            "Spatial map of velocity heterogeneity along the survey line.\n"
            "Shows lateral variations in dispersion properties.",
            False
        ),
    ],
    "Near-Field & Array": [
        (
            "NACD-Wavelength Analysis",
            "nacd_wavelength",
            "Normalized Array Center Distance vs. wavelength analysis.\n"
            "Standard near-field assessment visualization.",
            False
        ),
        (
            "Array Response Overlay",
            "array_response",
            "Shows theoretical array response function with picked data.\n"
            "Helps identify spatial aliasing effects.",
            False
        ),
        (
            "Offset-Dependent Comparison",
            "offset_dependent",
            "Systematic comparison of how curves change with offset.\n"
            "Reveals near-field contamination patterns.",
            False
        ),
    ],
    "Advanced Comparison": [
        (
            "Forward Model vs. Observed",
            "forward_vs_observed",
            "Compares picked dispersion with forward-modeled theoretical curve.\n"
            "Standard validation figure for inversion results.",
            False
        ),
        (
            "Multi-Transform Comparison",
            "multi_transform",
            "Compares results from different transform methods (F-K, FDBF, etc.).\n"
            "Shows method-dependent differences.",
            False
        ),
        (
            "Active vs. Passive Merge",
            "active_passive",
            "Visualizes the merge zone between active and passive data.\n"
            "Shows frequency overlap and weighting.",
            False
        ),
        (
            "Temporal Change Detection",
            "temporal_change",
            "Compares dispersion curves from different time periods.\n"
            "For monitoring applications.",
            False
        ),
        (
            "Reference Curve Overlay",
            "reference_overlay",
            "Overlays user-provided reference curves for comparison.\n"
            "Useful for benchmarking against published results.",
            False
        ),
    ],
    "Quality Control": [
        (
            "SNR vs. Frequency",
            "snr_frequency",
            "Signal-to-noise ratio as a function of frequency.\n"
            "Helps identify reliable frequency bands.",
            False
        ),
        (
            "Spatial Aliasing Diagnostic",
            "aliasing_diagnostic",
            "Shows theoretical aliasing limits with picked data.\n"
            "Warns about potentially aliased picks.",
            False
        ),
        (
            "Picking Consistency Check",
            "picking_consistency",
            "Visualizes picking consistency across offsets.\n"
            "Identifies outliers and inconsistent picks.",
            False
        ),
    ],
    "Canvas Export": [
        (
            "Current View (Frequency)",
            "canvas_frequency",
            "Export current canvas exactly as displayed in frequency domain.\n"
            "Includes all visible layers, current zoom/pan, and styling.",
            True
        ),
        (
            "Current View (Wavelength)",
            "canvas_wavelength",
            "Export current canvas converted to wavelength domain.\n"
            "Uses wavelength = velocity / frequency transformation.",
            True
        ),
        (
            "Current View (Dual Domain)",
            "canvas_dual",
            "Side-by-side frequency and wavelength views of current canvas.\n"
            "Creates a two-panel figure for comprehensive presentation.",
            True
        ),
    ],
    "Source Offset Analysis": [
        (
            "Individual Offset - Curve Only",
            "offset_curve_only",
            "Clean dispersion curve for a single offset without spectrum.\n"
            "Select the offset from the dropdown below.",
            True
        ),
        (
            "Individual Offset - With Spectrum",
            "offset_with_spectrum",
            "Dispersion curve overlaid on spectrum background.\n"
            "Requires spectrum data (.npz) to be loaded.",
            True
        ),
        (
            "Individual Offset - Spectrum Only",
            "offset_spectrum_only",
            "Pure spectrum visualization for selected offset.\n"
            "Shows the frequency-velocity power spectrum.",
            True
        ),
        (
            "Comparison Grid",
            "offset_grid",
            "Multi-panel grid comparing selected offsets.\n"
            "Select which offsets to include and configure shared colorbar.",
            True
        ),
    ],
    "Near-Field Analysis": [
        (
            "NACD Curve - Single Offset",
            "nacd_curve",
            "Dispersion curve with NACD-based coloring for selected offset.\n"
            "Blue = far-field (good), Red = near-field (contaminated).",
            True
        ),
        (
            "NACD Grid - All Offsets",
            "nacd_grid",
            "Multi-panel grid showing NACD-colored curves for each offset.\n"
            "Blue = far-field, Red = near-field. Shows NF% per offset.",
            True
        ),
        (
            "NACD Combined Overlay",
            "nacd_combined",
            "All curves overlaid on single plot with original colors.\n"
            "Near-field points from ALL offsets shown in red.",
            True
        ),
        (
            "NACD Comparison Plot",
            "nacd_comparison",
            "Overlaid NACD curves for all offsets on single plot.\n"
            "Shows how near-field region varies with source offset.",
            True
        ),
        (
            "Near-Field Summary",
            "nacd_summary",
            "Summary statistics of near-field contamination across offsets.\n"
            "Shows percentage of data in near-field per offset.",
            True
        ),
    ],
}


