"""Near-field report export helpers.

Exports the NF diagnostic report in multiple formats:
- CSV (one row per offset, summary columns)
- JSON (full structured report with arrays)
- ASCII table (console-friendly)
- NPZ (scatter plot arrays for external tools)

No framework imports, no controller references.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np


# ---------------------------------------------------------------------------
# ASCII table
# ---------------------------------------------------------------------------

def format_nearfield_report_table(
    report: List[Dict],
    *,
    show_nacd_stats: bool = True,
) -> str:
    """Format NF diagnostic report as an ASCII table for console output.

    Parameters
    ----------
    report : list of dict
        Output of ``compute_nearfield_report()``.
    show_nacd_stats : bool
        Include min/median/max NACD columns.

    Returns
    -------
    str
        Formatted table string.
    """
    lines: List[str] = []
    header_parts = [
        f"{'#':>3}",
        f"{'Offset':>8}",
        f"{'x_bar':>8}",
        f"{'λ_max':>8}",
    ]
    if show_nacd_stats:
        header_parts += [f"{'NACD_min':>9}", f"{'NACD_med':>9}", f"{'NACD_max':>9}"]
    header_parts += [
        f"{'Clean%':>8}",
        f"{'Marg%':>8}",
        f"{'Cont%':>8}",
        f"{'f_onset':>8}",
        f"{'Ref':>4}",
    ]
    header = " | ".join(header_parts)
    sep = "-" * len(header)
    lines.append(sep)
    lines.append(header)
    lines.append(sep)

    for entry in report:
        nacd = np.asarray(entry.get("nacd", []), float)
        valid_nacd = nacd[np.isfinite(nacd)]
        row = [
            f"{entry['index']:>3}",
            f"{entry['source_offset']:>+8.1f}",
            f"{entry['x_bar']:>8.2f}",
            f"{entry['lambda_max']:>8.2f}",
        ]
        if show_nacd_stats:
            if len(valid_nacd) > 0:
                row += [
                    f"{np.min(valid_nacd):>9.3f}",
                    f"{np.median(valid_nacd):>9.3f}",
                    f"{np.max(valid_nacd):>9.3f}",
                ]
            else:
                row += [f"{'N/A':>9}"] * 3
        row += [
            f"{entry.get('clean_pct', 0):>8.1f}",
            f"{entry.get('marginal_pct', 0):>8.1f}",
            f"{entry.get('contaminated_pct', 0):>8.1f}",
            f"{entry.get('onset_freq', float('nan')):>8.2f}" if entry.get("onset_freq") else f"{'N/A':>8}",
            f"{'*' if entry.get('is_reference') else '':>4}",
        ]
        lines.append(" | ".join(row))

    lines.append(sep)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def save_nearfield_report_csv(
    report: List[Dict],
    output_path: Union[str, Path],
    *,
    include_arrays: bool = False,
) -> str:
    """Export one-row-per-offset summary to CSV.

    Parameters
    ----------
    report : list of dict
        Output of ``compute_nearfield_report()``.
    output_path : str or Path
        Destination file path.
    include_arrays : bool
        If True, add columns for the full NACD and V_R arrays
        (semicolon-delimited within cells).

    Returns
    -------
    str
        The absolute path of the saved file.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    scalar_cols = [
        "index", "source_offset", "x_bar", "lambda_max",
        "clean_pct", "marginal_pct", "contaminated_pct",
        "onset_freq", "onset_wavelength", "is_reference",
    ]
    fieldnames = list(scalar_cols)
    if include_arrays:
        fieldnames += ["nacd_array", "vr_array", "severity_array"]

    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for entry in report:
            row = {k: entry.get(k, "") for k in scalar_cols}
            if include_arrays:
                row["nacd_array"] = _array_to_str(entry.get("nacd"))
                row["vr_array"] = _array_to_str(entry.get("vr"))
                row["severity_array"] = _array_to_str(entry.get("severity"))
            writer.writerow(row)

    return str(out.resolve())


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def save_nearfield_report_json(
    report: List[Dict],
    output_path: Union[str, Path],
    *,
    indent: int = 2,
) -> str:
    """Export full structured report to JSON.

    Numpy arrays are converted to lists.

    Returns
    -------
    str
        The absolute path of the saved file.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    serialisable = [_dict_to_serialisable(entry) for entry in report]
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(serialisable, fh, indent=indent)

    return str(out.resolve())


# ---------------------------------------------------------------------------
# NPZ export (scatter data)
# ---------------------------------------------------------------------------

def save_nacd_vr_scatter_npz(
    scatter_data: Dict[str, Any],
    output_path: Union[str, Path],
) -> str:
    """Export scatter plot data as a compressed NumPy archive.

    Parameters
    ----------
    scatter_data : dict
        Output of ``prepare_nacd_vr_scatter()``.
    output_path : str or Path
        Destination ``.npz`` file path.

    Returns
    -------
    str
        The absolute path of the saved file.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    arrays = {}
    for k, v in scatter_data.items():
        if isinstance(v, np.ndarray):
            arrays[k] = v
        elif isinstance(v, list):
            try:
                arrays[k] = np.array(v)
            except (ValueError, TypeError):
                arrays[k] = np.array(v, dtype=object)

    np.savez_compressed(str(out), **arrays)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _array_to_str(arr: Any, sep: str = ";") -> str:
    """Convert array-like to a semicolon-delimited string."""
    if arr is None:
        return ""
    a = np.asarray(arr)
    if a.ndim == 0:
        return str(a.item())
    return sep.join(str(x) for x in a.flat)


def _dict_to_serialisable(d: Dict) -> Dict:
    """Recursively convert numpy types to Python builtins for JSON."""
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, np.ndarray):
            out[k] = v.tolist()
        elif isinstance(v, (np.integer,)):
            out[k] = int(v)
        elif isinstance(v, (np.floating,)):
            out[k] = float(v)
        elif isinstance(v, (np.bool_,)):
            out[k] = bool(v)
        elif isinstance(v, dict):
            out[k] = _dict_to_serialisable(v)
        else:
            out[k] = v
    return out
