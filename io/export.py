from __future__ import annotations

import csv
from typing import Sequence, Dict
import numpy as np


def write_geopsy_txt(stats: Dict[str, np.ndarray], out_filename: str) -> None:
    """Write Geopsy-compatible TXT from stats dict.

    Expects keys: 'FreqMean', 'SlowMean', 'DinverStd', 'NumPoints'.
    Format: freq slow DinverStd numPoints
    """
    freq = np.asarray(stats['FreqMean'])
    slow = np.asarray(stats['SlowMean'])
    dstd = np.asarray(stats['DinverStd'])
    npnts = np.asarray(stats['NumPoints'])

    with open(out_filename, "w", encoding="utf-8") as f:
        for i in range(len(freq)):
            if not np.isfinite(slow[i]):
                continue
            f.write(f"{float(freq[i]):16.6f} {float(slow[i]):12.10f} {float(dstd[i]):16.12f} {int(npnts[i]):16.0f}\n")


def write_passive_stats_csv(freq_mean: Sequence[float], slow_mean: Sequence[float], dinver_std: Sequence[float], num_points: Sequence[int], out_filename: str) -> None:
    """Write Passive Stats CSV with header.

    Columns: FreqMean, SlowMean, DinverStd, NumPoints
    """
    with open(out_filename, 'w', newline='', encoding='utf-8') as fw:
        w = csv.writer(fw)
        w.writerow(["FreqMean","SlowMean","DinverStd","NumPoints"])
        for i in range(len(freq_mean)):
            w.writerow([float(freq_mean[i]), float(slow_mean[i]), float(dinver_std[i]), int(num_points[i])])











