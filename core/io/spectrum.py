"""Utility functions for loading and managing power spectrum backgrounds.

This module provides tolerant readers for the various ``.npz`` spectrum
layouts DC-cut has to deal with in the wild:

* Legacy SW-Transform single-offset files (8 core keys plus optional
  extras such as ``wavenumbers``).
* MASW 2D "slim" single-offset files (exactly 13 keys).
* MASW 2D "rich" single-offset files (13 slim keys plus workflow
  metadata like ``wavelengths`` / ``midpoint`` / ``subarray_config``).
* Combined multi-offset files whose keys carry a ``_<suffix>`` tag
  (e.g. ``frequencies_p66`` for ``+66m``).
* Files produced by third-party pipelines that forward only the
  canonical arrays (``frequencies`` / ``velocities`` / ``power``) with
  no metadata whatsoever.

Every reader in this module returns the same canonical dict shape used
by :class:`dc_cut.gui.controller.handlers.spectrum_handler.SpectrumHandler`,
so adding new schemas here does not ripple into the rest of the app.

The legacy public API (``load_spectrum_npz``, ``find_matching_spectrum``,
``load_combined_spectrum_npz`` …) keeps its original signature. Two new
entry points have been added for mapper-aware flows:

* :class:`SpectrumRecord` — canonical dataclass.
* :func:`detect_npz_format` — returns ``"single"`` / ``"combined"`` /
  ``"unknown"``.
* :func:`enumerate_spectra` — yields one :class:`SpectrumRecord` per
  offset regardless of single/combined layout.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np

from dc_cut.core.io.offset_label import (
    extract_method_from_filename,
    extract_offset_from_filename,
    from_suffix,
    normalize_offset,
    to_suffix,
)


# ---------------------------------------------------------------------------
# Canonical container
# ---------------------------------------------------------------------------


@dataclass
class SpectrumRecord:
    """Canonical representation of a single-offset spectrum.

    Every tolerant loader returns a ``SpectrumRecord`` (or a list of
    them). Call :meth:`to_dict` for the legacy dict shape the rest of
    DC-cut still consumes directly.
    """

    frequencies: np.ndarray
    velocities: np.ndarray
    power: np.ndarray
    picked_velocities: Optional[np.ndarray] = None
    method: str = "unknown"
    offset: str = ""
    export_date: str = ""
    version: str = "1.0"
    wavenumbers: Optional[np.ndarray] = None
    vibrosis_mode: bool = False
    vspace: Optional[str] = None
    weight_mode: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Legacy dict shape used by :mod:`spectrum_handler`."""
        d = {
            "frequencies": self.frequencies,
            "velocities": self.velocities,
            "power": self.power,
            "picked_velocities": self.picked_velocities,
            "method": self.method,
            "offset": self.offset,
            "export_date": self.export_date,
            "version": self.version,
            "wavenumbers": self.wavenumbers,
            "vibrosis_mode": bool(self.vibrosis_mode),
            "vspace": self.vspace,
            "weight_mode": self.weight_mode,
        }
        if self.extras:
            d["extras"] = dict(self.extras)
        return d


# Keys we never surface via ``extras`` because they are either core or
# per-offset aliases already consumed by :func:`enumerate_spectra`.
_CORE_KEYS = {
    "frequencies",
    "velocities",
    "power",
    "picked_velocities",
    "method",
    "offset",
    "export_date",
    "version",
    "wavenumbers",
    "vibrosis_mode",
    "vspace",
    "weight_mode",
    "offsets",
    "num_offsets",
}


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


_SUFFIXED_FREQ_RE = re.compile(r"^frequencies_([mpn]\d+(?:\.\d+)?)$", re.IGNORECASE)


def detect_npz_format(npz_path: str) -> str:
    """Inspect an NPZ and classify its layout.

    Returns
    -------
    str
        ``"single"`` if the file exposes top-level ``frequencies`` /
        ``velocities`` / ``power``, ``"combined"`` if it exposes
        per-offset ``frequencies_<suffix>`` keys (with or without the
        ``offsets`` metadata array), and ``"unknown"`` otherwise.
    """
    p = Path(npz_path)
    if not p.exists():
        raise FileNotFoundError(f"Spectrum file not found: {p}")

    try:
        with np.load(str(p), allow_pickle=True) as data:
            keys = set(data.files)
    except Exception as exc:  # pragma: no cover - I/O edge case
        raise ValueError(f"Unable to open NPZ {p.name}: {exc}") from exc

    # Combined takes precedence: if per-offset keys exist, it is
    # combined even when a stray top-level ``frequencies`` is present
    # (MASW 2D's combined writer occasionally emits both).
    if "offsets" in keys and any(k.startswith("frequencies_") for k in keys):
        return "combined"
    if any(_SUFFIXED_FREQ_RE.match(k) for k in keys):
        return "combined"

    if {"frequencies", "velocities", "power"}.issubset(keys):
        return "single"

    return "unknown"


# ---------------------------------------------------------------------------
# Tolerant single-file loader
# ---------------------------------------------------------------------------


def load_spectrum_npz(npz_path: str) -> Dict[str, Any]:
    """Load a single-offset spectrum from an ``.npz`` file.

    The loader is **tolerant**: it only requires ``frequencies``,
    ``velocities`` and ``power``. Every other field is filled with a
    sensible default (e.g. ``method`` falls back to what
    :func:`extract_method_from_filename` finds in the basename).

    Parameters
    ----------
    npz_path : str
        Path to a spectrum NPZ file.

    Returns
    -------
    dict
        Legacy dict shape identical to the pre-rewrite version of this
        function. An ``extras`` key preserves unknown arrays so callers
        that understand additional schemas (e.g. Report Studio) can
        still consume them.

    Raises
    ------
    FileNotFoundError
        If ``npz_path`` does not exist.
    ValueError
        If the file lacks the minimum ``frequencies`` / ``velocities``
        / ``power`` arrays needed to render a spectrum.
    """
    return _load_single_record(npz_path).to_dict()


def _load_single_record(npz_path: str) -> SpectrumRecord:
    p = Path(npz_path)
    if not p.exists():
        raise FileNotFoundError(f"Spectrum file not found: {p}")

    with np.load(str(p), allow_pickle=True) as data:
        keys = set(data.files)
        required = {"frequencies", "velocities", "power"}
        missing = required - keys
        if missing:
            raise ValueError(
                f"{p.name} is not a recognisable spectrum NPZ — missing "
                f"required arrays {sorted(missing)}. Use 'Map NPZ…' to "
                f"assign columns manually."
            )

        record = _build_record(
            data=data,
            key_map={
                "frequencies": "frequencies",
                "velocities": "velocities",
                "power": "power",
                "picked_velocities": "picked_velocities",
                "wavenumbers": "wavenumbers",
            },
            method=_scalar(data, "method", default=extract_method_from_filename(str(p)) or "unknown"),
            offset=_scalar(data, "offset", default=extract_offset_from_filename(str(p)) or ""),
            export_date=_scalar(data, "export_date", default=""),
            version=_scalar(data, "version", default="1.0"),
            vibrosis_mode=bool(_scalar(data, "vibrosis_mode", default=False)),
            vspace=_scalar(data, "vspace", default=None),
            weight_mode=_scalar(data, "weight_mode", default=None),
        )

    return record


# ---------------------------------------------------------------------------
# Tolerant combined-file loader
# ---------------------------------------------------------------------------


def load_combined_spectrum_npz(npz_path: str) -> Dict[str, Dict[str, Any]]:
    """Load a multi-offset spectrum from a combined ``.npz`` file.

    Works with three generator conventions:

    * Files written by DC-cut's original combined writer: rely on the
      ``offsets`` metadata array.
    * Files written by MASW 2D's combined writer: same metadata plus
      the per-offset suffixed keys.
    * Files that only expose the suffixed keys (no ``offsets`` array);
      the loader recovers the offset list by scanning the key names.

    Returns
    -------
    dict
        Mapping of canonical offset label (``"+66m"``, ``"-10m"``…) to
        the single-spectrum dict shape returned by
        :func:`load_spectrum_npz`.

    Raises
    ------
    FileNotFoundError
        If ``npz_path`` does not exist.
    ValueError
        If the file has no recognisable combined layout.
    """
    records = _load_combined_records(npz_path)
    return {r.offset: r.to_dict() for r in records if r.offset}


def _load_combined_records(npz_path: str) -> List[SpectrumRecord]:
    p = Path(npz_path)
    if not p.exists():
        raise FileNotFoundError(f"Spectrum file not found: {p}")

    with np.load(str(p), allow_pickle=True) as data:
        keys = set(data.files)

        # Discover offsets. Prefer the declared ``offsets`` array so we
        # honour the original ordering; otherwise scan suffixed keys.
        declared: List[str] = []
        if "offsets" in keys:
            try:
                declared = [str(x) for x in np.atleast_1d(data["offsets"])]
            except Exception:
                declared = []

        suffixes_by_key = {k: m.group(1).lower() for k in keys for m in (_SUFFIXED_FREQ_RE.match(k),) if m}
        scanned = list(dict.fromkeys(suffixes_by_key.values()))

        if not declared and not scanned:
            raise ValueError(
                f"{p.name} is not a recognisable combined spectrum NPZ — "
                f"found no 'offsets' array or 'frequencies_<suffix>' keys."
            )

        method = _scalar(
            data,
            "method",
            default=extract_method_from_filename(str(p)) or "unknown",
        )
        export_date = _scalar(data, "export_date", default="")
        version = _scalar(data, "version", default="1.0")

        records: List[SpectrumRecord] = []
        offset_iter = declared if declared else [from_suffix(s) for s in scanned]

        for raw_offset in offset_iter:
            label = normalize_offset(raw_offset) or str(raw_offset)
            suffix = to_suffix(raw_offset)
            if not suffix:
                continue

            freq_key = f"frequencies_{suffix}"
            vel_key = f"velocities_{suffix}"
            power_key = f"power_{suffix}"
            if freq_key not in keys or vel_key not in keys or power_key not in keys:
                # Try case variants (MASW 2D emits lowercase, but some
                # legacy pipelines uppercase the prefix).
                alt_suffix = suffix.upper()
                if (
                    f"frequencies_{alt_suffix}" in keys
                    and f"velocities_{alt_suffix}" in keys
                    and f"power_{alt_suffix}" in keys
                ):
                    suffix = alt_suffix
                    freq_key = f"frequencies_{alt_suffix}"
                    vel_key = f"velocities_{alt_suffix}"
                    power_key = f"power_{alt_suffix}"
                else:
                    continue

            try:
                records.append(
                    _build_record(
                        data=data,
                        key_map={
                            "frequencies": freq_key,
                            "velocities": vel_key,
                            "power": power_key,
                            "picked_velocities": f"picked_velocities_{suffix}",
                            "wavenumbers": f"wavenumbers_{suffix}",
                        },
                        method=method,
                        offset=label,
                        export_date=export_date,
                        version=version,
                        vibrosis_mode=bool(_scalar(data, f"vibrosis_mode_{suffix}", default=False)),
                        vspace=_scalar(data, f"vspace_{suffix}", default=None),
                        weight_mode=_scalar(data, f"weight_mode_{suffix}", default=None),
                    )
                )
            except Exception:
                continue

    return records


# ---------------------------------------------------------------------------
# Unified enumeration over both layouts
# ---------------------------------------------------------------------------


def enumerate_spectra(npz_path: str) -> List[SpectrumRecord]:
    """Yield one :class:`SpectrumRecord` per offset for any NPZ layout.

    Single-offset files yield a one-element list. Combined files yield
    one record per discovered offset. Callers no longer need to branch
    on the layout themselves.

    Raises
    ------
    FileNotFoundError
        If ``npz_path`` does not exist.
    ValueError
        If the file is neither a valid single nor combined spectrum.
    """
    fmt = detect_npz_format(npz_path)
    if fmt == "single":
        return [_load_single_record(npz_path)]
    if fmt == "combined":
        records = _load_combined_records(npz_path)
        if not records:
            raise ValueError(
                f"{Path(npz_path).name} looked like a combined NPZ but "
                "no individual offsets could be loaded."
            )
        return records
    raise ValueError(
        f"{Path(npz_path).name} has no recognisable spectrum layout. "
        "Use 'Map NPZ…' to tell DC-cut which arrays to use."
    )


# ---------------------------------------------------------------------------
# Legacy helpers (unchanged signatures)
# ---------------------------------------------------------------------------


def find_matching_spectrum(csv_path: str) -> Optional[str]:
    """Auto-detect spectrum ``.npz`` file matching a dispersion CSV.

    Supports both the legacy SW-Transform convention
    (``<base>_<method>_<offset>_spectrum.npz``) and MASW 2D's
    descriptive filenames (``DC_…_src-10.0m(off10m)_…_ss_tdom.npz``),
    so newly-generated companion NPZs are found without the user
    having to rename anything.
    """
    csv = Path(csv_path)
    base_dir = csv.parent
    if not base_dir.exists():
        return None

    stem = csv.stem

    # 1. Legacy exact match: ``<csv_stem>_spectrum.npz``.
    exact = base_dir / f"{stem}_spectrum.npz"
    if exact.exists():
        return str(exact)

    # 2. Same stem, no ``_spectrum`` suffix (MASW 2D rich NPZ).
    plain = base_dir / f"{stem}.npz"
    if plain.exists():
        return str(plain)

    # 3. Drop the trailing token (assumed offset) and retry.
    parts = stem.split("_")
    if len(parts) >= 2:
        base_name = "_".join(parts[:-1])
        for candidate in (
            base_dir / f"{base_name}_spectrum.npz",
            base_dir / f"{base_name}.npz",
        ):
            if candidate.exists():
                return str(candidate)

    # 4. MASW 2D layout: match by midpoint + offset tags embedded in
    # the CSV stem. We look for any NPZ in the folder that carries the
    # same offset label as the CSV.
    csv_offset = extract_offset_from_filename(str(csv))
    csv_method = extract_method_from_filename(str(csv))
    if csv_offset or csv_method:
        best: Optional[Tuple[int, Path]] = None
        for candidate in base_dir.glob("*.npz"):
            score = 0
            cand_offset = extract_offset_from_filename(str(candidate))
            cand_method = extract_method_from_filename(str(candidate))
            if csv_offset and cand_offset == csv_offset:
                score += 2
            if csv_method and cand_method == csv_method:
                score += 1
            if score and (best is None or score > best[0]):
                best = (score, candidate)
        if best is not None and best[0] > 0:
            return str(best[1])

    return None


def find_all_spectra(
    directory: str,
    base_name: Optional[str] = None,
    method: Optional[str] = None,
) -> Dict[str, str]:
    """Find every spectrum file in ``directory`` keyed by offset label.

    Scans both the legacy ``*_spectrum.npz`` files and MASW 2D's
    descriptive ``*.npz`` files. Offsets are read from the file
    itself when possible, with a fallback to the filename parser.
    """
    d = Path(directory)
    if not d.exists():
        return {}

    patterns: List[str] = []
    if base_name and method:
        patterns += [f"{base_name}_{method}*_spectrum.npz", f"{base_name}_{method}*.npz"]
    elif base_name:
        patterns += [f"{base_name}_*_spectrum.npz", f"{base_name}_*.npz"]
    elif method:
        patterns += [f"*_{method}*_spectrum.npz", f"*_{method}*.npz"]
    else:
        patterns += ["*_spectrum.npz", "*.npz"]

    offset_map: Dict[str, str] = {}
    seen: set = set()
    for pattern in patterns:
        for npz_file in d.glob(pattern):
            if npz_file in seen:
                continue
            seen.add(npz_file)

            offset_label = ""
            try:
                with np.load(str(npz_file), allow_pickle=True) as data:
                    if "offset" in data.files:
                        offset_label = normalize_offset(str(data["offset"]))
            except Exception:
                offset_label = ""

            if not offset_label:
                offset_label = extract_offset_from_filename(str(npz_file)) or ""

            if not offset_label:
                continue

            # Prefer ``*_spectrum.npz`` over plain ``.npz`` when both
            # exist for the same offset.
            existing = offset_map.get(offset_label)
            if existing and existing.endswith("_spectrum.npz"):
                continue
            offset_map[offset_label] = str(npz_file)

    return offset_map


def get_spectrum_bounds(spectrum_data: Mapping[str, Any]) -> Tuple[float, float, float, float]:
    """Return ``(freq_min, freq_max, vel_min, vel_max)`` for a spectrum."""
    freqs = np.asarray(spectrum_data["frequencies"], dtype=float)
    vels = np.asarray(spectrum_data["velocities"], dtype=float)
    return (
        float(np.nanmin(freqs)),
        float(np.nanmax(freqs)),
        float(np.nanmin(vels)),
        float(np.nanmax(vels)),
    )


def validate_spectrum_alignment(
    spectrum_data: Mapping[str, Any],
    csv_frequencies: np.ndarray,
    csv_velocities: np.ndarray,
) -> bool:
    """Return ``True`` if CSV samples fit inside the spectrum bounds."""
    freq_min, freq_max, vel_min, vel_max = get_spectrum_bounds(spectrum_data)

    csv_freq_min = float(np.nanmin(csv_frequencies))
    csv_freq_max = float(np.nanmax(csv_frequencies))
    csv_vel_min = float(np.nanmin(csv_velocities))
    csv_vel_max = float(np.nanmax(csv_velocities))

    freq_ok = (csv_freq_min >= freq_min - 1.0) and (csv_freq_max <= freq_max + 1.0)
    vel_ok = (csv_vel_min >= vel_min - 10.0) and (csv_vel_max <= vel_max + 10.0)
    return freq_ok and vel_ok


def match_csv_labels_to_spectrum(
    csv_labels: list,
    spectrum_offsets: Dict[str, Any],
) -> Dict[int, str]:
    """Map CSV layer labels to the best-matching spectrum offset key."""
    if not spectrum_offsets:
        return {}

    matches: Dict[int, str] = {}
    # Pre-normalise spectrum keys for cheap lookup.
    norm_index = {normalize_offset(k): k for k in spectrum_offsets.keys()}

    for i, raw_label in enumerate(csv_labels):
        label = str(raw_label).strip()
        if not label:
            continue

        # Pattern: method_offset (e.g., 'fk_+66', 'Rayleigh/fdbf_p66').
        candidate = label.split("/")[-1]
        if "_" in candidate:
            candidate = candidate.split("_")[-1]

        normalized = normalize_offset(candidate) or normalize_offset(label)
        if not normalized:
            continue

        if normalized in norm_index:
            matches[i] = norm_index[normalized]

    return matches


def load_combined_spectrum_for_csv(
    csv_path: str,
    npz_path: Optional[str] = None,
) -> Optional[Dict[int, Dict[str, Any]]]:
    """Load a combined spectrum and align its offsets to a CSV's layers."""
    csv = Path(csv_path)

    if npz_path is None:
        stem = csv.stem
        candidates = [
            csv.parent / f"{stem}_spectrum.npz",
            csv.parent / f"{stem.replace('_', '-')}_spectrum.npz",
            csv.parent / f"{stem}.npz",
        ]
        for candidate in candidates:
            if candidate.exists():
                npz_path = str(candidate)
                break

    if npz_path is None:
        return None

    try:
        spectrum_offsets = load_combined_spectrum_npz(npz_path)
    except Exception:
        return None

    if not spectrum_offsets:
        return None

    try:
        import pandas as pd

        df = pd.read_csv(csv, nrows=0)
        columns = list(df.columns)

        labels: List[str] = []
        seen: set = set()
        for col in columns:
            if "(" in col and ")" in col:
                label = col[col.index("(") + 1 : col.index(")")]
                if label not in seen:
                    seen.add(label)
                    labels.append(label)
    except Exception:
        return None

    matches = match_csv_labels_to_spectrum(labels, spectrum_offsets)
    if not matches:
        return None

    return {layer_idx: spectrum_offsets[key] for layer_idx, key in matches.items()}


# ---------------------------------------------------------------------------
# Backward-compatible private helpers
# ---------------------------------------------------------------------------


def _offset_to_suffix(offset: str) -> str:
    """Deprecated shim — use :func:`dc_cut.core.io.offset_label.to_suffix`."""
    return to_suffix(offset)


def _normalize_offset_label(offset: str) -> str:
    """Deprecated shim — use :func:`dc_cut.core.io.offset_label.normalize_offset`."""
    return normalize_offset(offset)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _scalar(data: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """Return a scalar metadata value from a loaded NPZ, honouring defaults."""
    if key not in getattr(data, "files", data):
        return default
    try:
        value = data[key]
    except Exception:
        return default
    try:
        arr = np.asarray(value)
    except Exception:
        return value
    if arr.shape == ():
        scalar = arr.item()
        if isinstance(scalar, bytes):
            try:
                return scalar.decode("utf-8")
            except Exception:
                return scalar
        return scalar
    if arr.size == 1:
        return arr.reshape(-1)[0]
    return value


def _coerce_power(power: np.ndarray, n_vel: int, n_freq: int) -> np.ndarray:
    """Return ``power`` with shape ``(n_vel, n_freq)`` when that is unambiguous.

    MASW 2D and SW-Transform both emit ``(n_vel, n_freq)``. Some
    downstream consumers transpose it — this helper rescues that
    case as long as the shape permits an unambiguous decision.
    """
    arr = np.asarray(power)
    if arr.ndim != 2:
        return arr
    if arr.shape == (n_vel, n_freq):
        return arr
    if arr.shape == (n_freq, n_vel) and n_vel != n_freq:
        return arr.T
    return arr


def _is_uniform(axis: np.ndarray, rtol: float = 1e-3) -> bool:
    """Return True if ``axis`` is (near-)uniformly spaced.

    The renderer plots spectra with ``imshow(extent=...)`` which assumes
    equal-width cells. SW-Transform can emit a log-spaced velocity axis
    (``vspace='log'``) — that case fails this check and triggers
    resampling in :func:`_resample_to_uniform`.
    """
    if axis.ndim != 1 or axis.size < 3:
        return True
    diffs = np.diff(axis.astype(np.float64))
    span = float(axis[-1] - axis[0])
    if span == 0:
        return True
    tol = rtol * abs(span) / max(1, axis.size - 1)
    return bool(np.max(np.abs(diffs - diffs.mean())) <= tol)


def _resample_to_uniform(
    freqs: np.ndarray,
    vels: np.ndarray,
    power: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Resample a spectrum onto uniformly spaced axes.

    DC_Cut renders the power array with ``imshow(extent=[f0, f1, v0, v1])``,
    which implicitly places each row/column at a uniform fraction of the
    span. When the NPZ was produced with ``vspace='log'`` (or any other
    non-uniform axis), the raw grid does not match that assumption and
    bright dispersion ridges end up shifted relative to the picked
    velocities in ``combined_*_fdbf.csv``. This helper linearly
    interpolates the power grid onto uniform axes of the same length and
    span so the extent-based renderer produces correct geometry.
    """
    freqs = np.asarray(freqs)
    vels = np.asarray(vels)
    power = np.asarray(power)
    if power.ndim != 2 or power.shape != (vels.size, freqs.size):
        return freqs, vels, power

    freqs_uniform = _is_uniform(freqs)
    vels_uniform = _is_uniform(vels)
    if freqs_uniform and vels_uniform:
        return freqs, vels, power

    out_freqs = freqs
    out_vels = vels
    out_power = power.astype(np.float32, copy=False)

    if not vels_uniform and vels.size >= 2:
        new_vels = np.linspace(float(vels[0]), float(vels[-1]), vels.size, dtype=np.float64)
        # Interpolate each frequency column along the velocity axis.
        # np.interp requires the x-coordinates to be increasing.
        vx = vels.astype(np.float64)
        if vx[0] > vx[-1]:
            vx = vx[::-1]
            out_power = out_power[::-1, :]
        resampled = np.empty((new_vels.size, out_power.shape[1]), dtype=np.float32)
        for j in range(out_power.shape[1]):
            resampled[:, j] = np.interp(new_vels, vx, out_power[:, j])
        out_power = resampled
        out_vels = new_vels.astype(vels.dtype, copy=False)

    if not freqs_uniform and freqs.size >= 2:
        new_freqs = np.linspace(float(freqs[0]), float(freqs[-1]), freqs.size, dtype=np.float64)
        fx = freqs.astype(np.float64)
        if fx[0] > fx[-1]:
            fx = fx[::-1]
            out_power = out_power[:, ::-1]
        resampled = np.empty((out_power.shape[0], new_freqs.size), dtype=np.float32)
        for i in range(out_power.shape[0]):
            resampled[i, :] = np.interp(new_freqs, fx, out_power[i, :])
        out_power = resampled
        out_freqs = new_freqs.astype(freqs.dtype, copy=False)

    return out_freqs, out_vels, out_power


def _build_record(
    *,
    data: Mapping[str, Any],
    key_map: Dict[str, str],
    method: str,
    offset: str,
    export_date: str,
    version: str,
    vibrosis_mode: bool,
    vspace: Optional[str],
    weight_mode: Optional[str],
) -> SpectrumRecord:
    freqs = np.asarray(data[key_map["frequencies"]])
    vels = np.asarray(data[key_map["velocities"]])
    power = _coerce_power(np.asarray(data[key_map["power"]]), len(vels), len(freqs))

    # SW-Transform may emit log-spaced velocity axes (vspace='log'). The
    # renderer plots with imshow(extent=...) which assumes uniform
    # spacing, so resample onto a linear grid of the same span/length.
    freqs, vels, power = _resample_to_uniform(freqs, vels, power)

    picked: Optional[np.ndarray] = None
    picked_key = key_map.get("picked_velocities")
    if picked_key and picked_key in getattr(data, "files", data):
        try:
            picked = np.asarray(data[picked_key])
        except Exception:
            picked = None

    wavenumbers: Optional[np.ndarray] = None
    wk_key = key_map.get("wavenumbers")
    if wk_key and wk_key in getattr(data, "files", data):
        try:
            wavenumbers = np.asarray(data[wk_key])
        except Exception:
            wavenumbers = None

    extras: Dict[str, Any] = {}
    for name in getattr(data, "files", ()):  # type: ignore[attr-defined]
        if name in _CORE_KEYS:
            continue
        if _SUFFIXED_FREQ_RE.match(name):
            continue
        if name in key_map.values():
            continue
        try:
            extras[name] = data[name]
        except Exception:
            continue

    # Normalise the offset for downstream matching.
    canonical_offset = normalize_offset(offset) or str(offset or "")

    return SpectrumRecord(
        frequencies=freqs,
        velocities=vels,
        power=power,
        picked_velocities=picked,
        method=str(method) if method is not None else "unknown",
        offset=canonical_offset,
        export_date=str(export_date or ""),
        version=str(version or "1.0"),
        wavenumbers=wavenumbers,
        vibrosis_mode=bool(vibrosis_mode),
        vspace=None if vspace is None else str(vspace),
        weight_mode=None if weight_mode is None else str(weight_mode),
        extras=extras,
    )


__all__ = [
    "SpectrumRecord",
    "detect_npz_format",
    "enumerate_spectra",
    "load_spectrum_npz",
    "load_combined_spectrum_npz",
    "find_matching_spectrum",
    "find_all_spectra",
    "get_spectrum_bounds",
    "validate_spectrum_alignment",
    "match_csv_labels_to_spectrum",
    "load_combined_spectrum_for_csv",
]
