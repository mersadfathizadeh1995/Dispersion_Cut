"""Backward-compatibility shim -- real module is dc_cut.core.io.spectrum."""
from dc_cut.core.io.spectrum import *  # noqa: F401,F403
from dc_cut.core.io.spectrum import (
    load_spectrum_npz,
    load_combined_spectrum_npz,
    find_matching_spectrum,
    find_all_spectra,
    get_spectrum_bounds,
    validate_spectrum_alignment,
    match_csv_labels_to_spectrum,
    load_combined_spectrum_for_csv,
)
