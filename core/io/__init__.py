"""File format readers and writers for DC Cut.

Modules in this package handle loading and saving data files
(MATLAB, CSV, Geopsy .max, spectrum .npz, session state, exports).
"""
from __future__ import annotations

from dc_cut.core.io.universal import parse_any_file, parse_combined_csv
from dc_cut.core.io.matlab import load_matlab_data
from dc_cut.core.io.csv_io import load_combined_csv
from dc_cut.core.io.max_parser import load_klimits, load_klimits_multi, parse_max_file
from dc_cut.core.io.state import save_session, load_session
from dc_cut.core.io.export import write_geopsy_txt, write_passive_stats_csv, export_to_mat
from dc_cut.core.io.offset_label import (
    normalize_offset,
    to_suffix,
    from_suffix,
    extract_offset_from_filename,
    extract_method_from_filename,
)
from dc_cut.core.io.spectrum import (
    SpectrumRecord,
    detect_npz_format,
    enumerate_spectra,
    load_spectrum_npz,
    load_combined_spectrum_npz,
    find_matching_spectrum,
    find_all_spectra,
    get_spectrum_bounds,
    validate_spectrum_alignment,
    match_csv_labels_to_spectrum,
    load_combined_spectrum_for_csv,
)

__all__ = [
    "parse_any_file",
    "parse_combined_csv",
    "load_matlab_data",
    "load_combined_csv",
    "load_klimits",
    "load_klimits_multi",
    "parse_max_file",
    "save_session",
    "load_session",
    "write_geopsy_txt",
    "write_passive_stats_csv",
    "export_to_mat",
    # Offset label helpers
    "normalize_offset",
    "to_suffix",
    "from_suffix",
    "extract_offset_from_filename",
    "extract_method_from_filename",
    # Spectrum loading
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
