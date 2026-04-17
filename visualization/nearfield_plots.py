"""Publication-quality near-field diagnostic plots.

All functions are pure Matplotlib (no Qt).  They accept optional
``ax`` parameters so callers can embed them in any figure layout.

Key figure: NACD-vs-V_R scatter — the canonical diagnostic plot from
Rahimi et al. (2021) Figs. 5, 10, 13, 15, 17.

No framework imports, no controller references.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from matplotlib.axes import Axes
    from matplotlib.patches import Rectangle
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ── colour palette ─────────────────────────────────────────────────
ZONE_COLORS = {
    "clean": "#b2dfb2",       # light green
    "marginal": "#ffe0b2",    # light orange
    "contaminated": "#ffccbc", # light red
}
OFFSET_CMAP = "tab10"


def generate_nacd_vs_vr_scatter(
    scatter_data: Dict[str, Any],
    *,
    ax: Optional[Any] = None,
    show_zones: bool = True,
    show_site_cutoff: bool = False,
    site_nacd_cutoff: Optional[float] = None,
    nacd_thresholds: Optional[Dict[str, float]] = None,
    source_type: str = "sledgehammer",
    clean_threshold: float = 0.95,
    marginal_threshold: float = 0.85,
    figsize: Tuple[float, float] = (8, 6),
    dpi: int = 300,
    title: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Any:
    """Generate the NACD-vs-V_R scatter plot.

    Parameters
    ----------
    scatter_data : dict
        Output of ``prepare_nacd_vr_scatter()`` with keys:
        ``nacd_all``, ``vr_all``, ``offset_ids``, ``offsets``, ``labels``.
    ax : matplotlib Axes, optional
        If provided, plot on this axes instead of creating a new figure.
    show_zones : bool
        Shade clean / marginal / contaminated zones.
    show_site_cutoff : bool
        Show a site-calibrated NACD cutoff line.
    site_nacd_cutoff : float, optional
        The site-specific NACD cutoff value.
    nacd_thresholds : dict, optional
        Custom NACD thresholds ``{"5pct": ..., "10_15pct": ...}``.
        If None, uses defaults from criteria module.
    source_type : str
        Source type for default thresholds.
    clean_threshold, marginal_threshold : float
        V_R thresholds for zone shading.
    figsize, dpi : tuple, int
        Figure dimensions and resolution.
    title : str, optional
        Figure title override.
    output_path : str, optional
        If provided, save figure to this path.

    Returns
    -------
    matplotlib.figure.Figure
    """
    if not HAS_MPL:
        raise ImportError("matplotlib is required for plotting")

    nacd = np.asarray(scatter_data.get("nacd_all", []))
    vr = np.asarray(scatter_data.get("vr_all", []))
    ids = np.asarray(scatter_data.get("offset_ids", []))
    labels = scatter_data.get("labels", [])

    created_fig = ax is None
    if created_fig:
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    else:
        fig = ax.get_figure()

    # ── zone shading ───────────────────────────────────────────
    if show_zones and len(nacd) > 0:
        xlim = (max(nacd[nacd > 0].min() * 0.5, 0.01) if np.any(nacd > 0) else 0.01,
                nacd.max() * 2.0 if len(nacd) else 10)
        # Green = clean (V_R >= clean_threshold)
        ax.axhspan(clean_threshold, 1.3, color=ZONE_COLORS["clean"], alpha=0.25, zorder=0)
        # Orange = marginal
        ax.axhspan(marginal_threshold, clean_threshold, color=ZONE_COLORS["marginal"], alpha=0.25, zorder=0)
        # Red = contaminated
        ax.axhspan(0.3, marginal_threshold, color=ZONE_COLORS["contaminated"], alpha=0.25, zorder=0)

    # ── horizontal reference lines ─────────────────────────────
    ax.axhline(1.0, color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
    ax.axhline(clean_threshold, color="green", linestyle="--", linewidth=0.8, alpha=0.7,
               label=f"V_R = {clean_threshold}")
    ax.axhline(marginal_threshold, color="orange", linestyle="--", linewidth=0.8, alpha=0.7,
               label=f"V_R = {marginal_threshold}")

    # ── NACD threshold lines ───────────────────────────────────
    if nacd_thresholds is None:
        try:
            from dc_cut.core.processing.nearfield.criteria import NACD_CRITERIA
            nacd_thresholds = NACD_CRITERIA.get(source_type.lower(), NACD_CRITERIA["sledgehammer"])
        except ImportError:
            nacd_thresholds = {"10_15pct": 1.0, "5pct": 1.5}

    t_10 = nacd_thresholds.get("10_15pct", 1.0)
    t_5 = nacd_thresholds.get("5pct", 1.5)
    ax.axvline(t_10, color="blue", linestyle=":", linewidth=1.0, alpha=0.8,
               label=f"NACD = {t_10:.1f} (10–15%)")
    ax.axvline(t_5, color="blue", linestyle="-.", linewidth=1.0, alpha=0.6,
               label=f"NACD = {t_5:.1f} (5%)")

    # ── site-specific cutoff ───────────────────────────────────
    if show_site_cutoff and site_nacd_cutoff is not None:
        ax.axvline(site_nacd_cutoff, color="red", linestyle="-", linewidth=1.5,
                   label=f"Site NACD = {site_nacd_cutoff:.2f}")

    # ── scatter per offset ─────────────────────────────────────
    cmap = plt.get_cmap(OFFSET_CMAP)
    unique_ids = np.unique(ids) if len(ids) > 0 else []
    for gid in unique_ids:
        mask = ids == gid
        color = cmap(gid % 10)
        lbl = labels[gid] if gid < len(labels) else f"Offset {gid}"
        ax.scatter(nacd[mask], vr[mask], s=12, alpha=0.6, color=color,
                   label=lbl, edgecolors="none", zorder=3)

    # ── axes formatting ────────────────────────────────────────
    ax.set_xscale("log")
    ax.set_xlabel("NACD (x̄ / λ)", fontsize=11)
    ax.set_ylabel("Normalized Phase Velocity, V_R", fontsize=11)
    ax.set_ylim(0.4, 1.2)
    if len(nacd) > 0 and np.any(nacd > 0):
        xmin = max(nacd[nacd > 0].min() * 0.5, 0.01)
        xmax = nacd.max() * 2.0
        ax.set_xlim(xmin, xmax)

    if title:
        ax.set_title(title, fontsize=13, fontweight="bold")
    else:
        ax.set_title(f"NACD vs V_R — {source_type.title()}", fontsize=13, fontweight="bold")

    ax.legend(loc="lower right", fontsize=8, framealpha=0.9,
              ncol=1 if len(unique_ids) <= 6 else 2)
    ax.grid(True, which="both", alpha=0.3)

    if created_fig:
        fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")

    return fig


def generate_severity_bar_chart(
    report: List[Dict],
    *,
    ax: Optional[Any] = None,
    figsize: Tuple[float, float] = (10, 4),
    dpi: int = 150,
    output_path: Optional[str] = None,
) -> Any:
    """Generate a stacked bar chart of severity percentages per offset.

    Parameters
    ----------
    report : list of dict
        Output of ``compute_nearfield_report()``.
    """
    if not HAS_MPL:
        raise ImportError("matplotlib is required for plotting")

    created_fig = ax is None
    if created_fig:
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    else:
        fig = ax.get_figure()

    labels_list = [f"{e['source_offset']:+g} m" for e in report]
    clean = [e.get("clean_pct", 0) for e in report]
    marginal = [e.get("marginal_pct", 0) for e in report]
    contam = [e.get("contaminated_pct", 0) for e in report]
    x = np.arange(len(report))

    ax.bar(x, clean, color="#66bb6a", label="Clean")
    ax.bar(x, marginal, bottom=clean, color="#ffa726", label="Marginal")
    ax.bar(x, contam, bottom=np.array(clean) + np.array(marginal),
           color="#ef5350", label="Contaminated")

    ax.set_xticks(x)
    ax.set_xticklabels(labels_list, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("% of Data Points")
    ax.set_title("Near-Field Severity by Source Offset")
    ax.legend(loc="upper right")
    ax.set_ylim(0, 105)

    if created_fig:
        fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")

    return fig


def generate_nacd_profile(
    report: List[Dict],
    *,
    nacd_threshold: float = 1.0,
    ax: Optional[Any] = None,
    figsize: Tuple[float, float] = (10, 5),
    dpi: int = 150,
    output_path: Optional[str] = None,
) -> Any:
    """Generate NACD profiles (min, median, max) for each offset.

    Parameters
    ----------
    report : list of dict
        Output of ``compute_nearfield_report()``.
    """
    if not HAS_MPL:
        raise ImportError("matplotlib is required for plotting")

    created_fig = ax is None
    if created_fig:
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    else:
        fig = ax.get_figure()

    for entry in report:
        if entry.get("is_reference"):
            continue
        nacd = np.asarray(entry.get("nacd", []), float)
        f = np.asarray(entry.get("frequency", []), float) if "frequency" in entry else np.arange(len(nacd))
        valid = np.isfinite(nacd) & (nacd > 0)
        if not np.any(valid):
            continue
        lbl = f"{entry['source_offset']:+g} m"
        ax.semilogy(f[valid] if len(f) == len(nacd) else np.arange(np.sum(valid)),
                     nacd[valid], linewidth=1.2, alpha=0.7, label=lbl)

    ax.axhline(nacd_threshold, color="red", linestyle="--", linewidth=1.0,
               label=f"Threshold = {nacd_threshold:.1f}")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("NACD")
    ax.set_title("NACD Profile by Source Offset")
    ax.legend(fontsize=8, loc="best")
    ax.grid(True, alpha=0.3)

    if created_fig:
        fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")

    return fig
