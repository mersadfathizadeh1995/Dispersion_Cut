"""Canonical offset-label handling for spectrum NPZ files.

One place for every bit of logic that converts between the three offset
string conventions DC-cut has to deal with:

- Human label: ``"+66m"``, ``"-10m"``, ``"+66"``, ``"-10"``.
- NPZ key suffix: ``"p66"``, ``"m10"``, ``"n10"``.
- CSV column label: ``"fdbf_+66"``, ``"fdbf_p66"``, ``"Rayleigh/fdbf_-30"``.

Callers should work with the canonical human label (``"+66m"`` /
``"-10m"``) internally and only convert to a suffix when reading/writing
per-offset NPZ keys.
"""
from __future__ import annotations

import re
from typing import Optional

# Allow fractional tags like ``m10.5`` produced by MASW 2D when the
# source position is not an integer metre count.
_SUFFIX_RE = re.compile(r"^[mpnMPN]\d+(?:\.\d+)?$")
_HUMAN_RE = re.compile(r"([+-])\s*(\d+(?:\.\d+)?)")
_SUFFIX_NUM_RE = re.compile(r"(?<![A-Za-z])([mpnMPN])(\d+(?:\.\d+)?)")
_BARE_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")


def normalize_offset(raw: object) -> str:
    """Return the canonical ``+66m`` / ``-10m`` form for any known input.

    Returns an empty string for inputs that contain no recognisable
    offset. The function is deliberately liberal — it will strip
    surrounding context like ``"fdbf_+66"`` or ``"Rayleigh/fk_-30"`` and
    return just ``"+66m"`` / ``"-30m"``.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""

    # Suffix form: p66, m10, n10, m10.5 (possibly surrounded by junk).
    m = _SUFFIX_NUM_RE.search(s)
    if m:
        prefix = m.group(1).lower()
        num = m.group(2)
        sign = "-" if prefix in ("m", "n") else "+"
        return f"{sign}{_trim_num(num)}m"

    # Human form: +66, -10, +66m, -10m.
    m = _HUMAN_RE.search(s)
    if m:
        sign = m.group(1)
        num = m.group(2)
        return f"{sign}{_trim_num(num)}m"

    # Bare number assumed positive.
    m = _BARE_NUM_RE.search(s)
    if m:
        return f"+{_trim_num(m.group(1))}m"

    return ""


def to_suffix(raw: object) -> str:
    """Return the NPZ key suffix (``p66``, ``m10``, ``m10.5``) for an offset.

    Empty string for inputs that contain no recognisable offset.
    Already-suffix inputs pass through with casing normalised.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""

    # Already a suffix — lowercase and normalise ``n`` to ``m`` so writer
    # output is consistent regardless of which producer wrote the file.
    if _SUFFIX_RE.match(s):
        lowered = s.lower()
        if lowered.startswith("n"):
            return "m" + lowered[1:]
        return lowered

    norm = normalize_offset(s)
    if not norm:
        return ""

    # norm is always "<sign><num>m"
    sign = norm[0]
    body = norm[1:-1] if norm.endswith("m") else norm[1:]
    if sign == "-":
        return "m" + body
    return "p" + body


def from_suffix(suffix: object) -> str:
    """Inverse of :func:`to_suffix` — canonical human label for a suffix."""
    if suffix is None:
        return ""
    s = str(suffix).strip()
    if not s:
        return ""
    lowered = s.lower()
    if lowered.startswith("p"):
        return f"+{_trim_num(lowered[1:])}m"
    if lowered.startswith("m") or lowered.startswith("n"):
        return f"-{_trim_num(lowered[1:])}m"
    # Fall back to generic normalisation.
    return normalize_offset(s)


def extract_offset_from_filename(path: str) -> Optional[str]:
    """Best-effort extraction of the offset from a spectrum filename.

    Recognises both ``..._fdbf_p66_spectrum.npz`` and MASW 2D's
    ``DC_24ch_mid23.0m_src-10.0m(off10m)_fwd_ss.npz`` layout. Returns
    the canonical ``+66m`` / ``-10m`` label, or ``None`` if nothing
    recognisable is present.
    """
    if not path:
        return None
    import os

    name = os.path.basename(str(path))
    stem = name.rsplit(".", 1)[0]

    # MASW 2D ``src-10.0m`` / ``src+10.0m`` — grab the signed value.
    m = re.search(r"src([+-]?\d+(?:\.\d+)?)m", stem, flags=re.IGNORECASE)
    if m:
        return normalize_offset(m.group(1))

    # Legacy convention: suffix token (``p66``/``m10``) or an explicitly
    # signed value (``+66`` / ``-10m``) next to the method. Unsigned bare
    # numbers like a leading "1" in ``1_fdbf_p66_spectrum.npz`` are
    # explicitly skipped so we don't mistake a sequence index for an
    # offset.
    tokens = stem.split("_")
    for tok in tokens:
        if _SUFFIX_RE.match(tok) or _HUMAN_RE.match(tok):
            canon = normalize_offset(tok)
            if canon:
                return canon

    return None


def extract_method_from_filename(path: str) -> Optional[str]:
    """Best-effort extraction of the processing method from the filename.

    Recognises ``fk``, ``fdbf``, ``ps`` and ``ss`` (plus its MASW 2D
    ``ss_tdom`` / ``ss_fdom`` variants).
    """
    if not path:
        return None
    import os

    name = os.path.basename(str(path)).lower()
    for method in ("fdbf", "fk", "ps", "ss"):
        if re.search(rf"(?<![a-z]){method}(?![a-z])", name):
            return method
    return None


def _trim_num(raw: str) -> str:
    """Drop trailing ``.0`` so ``10.0`` becomes ``10`` while ``10.5`` stays."""
    if "." not in raw:
        return raw
    trimmed = raw.rstrip("0").rstrip(".")
    return trimmed or "0"


__all__ = [
    "normalize_offset",
    "to_suffix",
    "from_suffix",
    "extract_offset_from_filename",
    "extract_method_from_filename",
]
