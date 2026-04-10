from __future__ import annotations

from typing import List, Tuple, Optional


def visible_wave_handles_labels(lines_wave: List[object], labels: List[str]) -> Tuple[List[object], List[str]]:
    handles: List[object] = []
    out_labels: List[str] = []
    for idx, line in enumerate(lines_wave):
        try:
            if line.get_visible():
                handles.append(line)
                out_labels.append(labels[idx])
        except Exception:
            # If a line is malformed, skip it rather than breaking the legend
            continue
    return handles, out_labels


def assemble_legend(
    lines_wave: List[object],
    labels: List[str],
    *,
    show_average: bool,
    avg_handle: Optional[object],
    avg_label: str,
    show_average_wave: bool,
    avg_wave_handle: Optional[object],
    avg_wave_label: str,
    k_guides_legend: Optional[List[object]] = None,
) -> Tuple[List[object], List[str]]:
    """Assemble legend handles and labels in a backend-agnostic way.

    Returns a tuple (handles, labels).
    """
    handles, out_labels = visible_wave_handles_labels(lines_wave, labels)
    if show_average and avg_handle is not None:
        handles.append(avg_handle)
        out_labels.append(avg_label)
    if show_average_wave and avg_wave_handle is not None:
        handles.append(avg_wave_handle)
        out_labels.append(avg_wave_label)
    if k_guides_legend:
        try:
            for d in k_guides_legend:
                handles.append(d)
                out_labels.append(d.get_label())
        except Exception:
            pass
    return handles, out_labels


def create_offset_lines(ax_freq, ax_wave, f_arr, v_arr, w_arr, *, marker: str, color, label: str):
    """Create left/right lines for an offset with consistent styling."""
    lf = ax_freq.semilogx(
        f_arr, v_arr,
        marker=marker, linestyle='',
        markerfacecolor='none', markeredgecolor=color,
        markeredgewidth=1.5
    )[0]
    lw = ax_wave.semilogx(
        w_arr, v_arr,
        marker=marker, linestyle='',
        markerfacecolor='none', markeredgecolor=color,
        markeredgewidth=1.5, label=label
    )[0]
    return lf, lw


def set_line_xy(line, x, y) -> None:
    """Set line data with small safety wrapper."""
    try:
        line.set_xdata(x)
        line.set_ydata(y)
    except Exception:
        # Some older mpl versions might require set_data
        try:
            line.set_data(x, y)
        except Exception:
            pass
