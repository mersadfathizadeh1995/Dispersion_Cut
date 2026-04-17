# Near-Field Analysis Sub-Package

> `dc_cut.core.processing.nearfield`

Comprehensive near-field effect evaluation for surface wave dispersion curves,
implementing the criteria and methods from:

- **Rahimi et al. (2021)** — *Near-field effects on surface wave measurements*
- **Rahimi et al. (2022)** — *Practical guidelines for mitigating near-field effects*

## Module Map

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `nacd.py` | NACD computation (x̄/λ) | `compute_nacd`, `compute_nacd_array`, `compute_nacd_for_all_data` |
| `criteria.py` | Source-type thresholds & transform multipliers | `resolve_nacd_threshold`, `parse_transform_from_label` |
| `normalized_vr.py` | V_R = V_measured / V_reference | `compute_normalized_vr`, `classify_nearfield_severity` |
| `reference.py` | Reference curve selection & composite | `select_reference_by_largest_xbar`, `compute_composite_reference` |
| `onset.py` | NF onset & roll-off detection | `detect_nearfield_onset`, `detect_rolloff_point` |
| `calibration.py` | Site-specific NACD threshold fitting | `fit_nacd_cutoff_from_scatter`, `recommend_site_nacd_threshold` |
| `composite_curve.py` | NF-clean dispersion curve for inversion | `build_nf_clean_composite_curve` |
| `far_field.py` | Far-field attenuation risk check | `assess_far_field_risk`, `assess_far_field_risk_batch` |
| `mode_detection.py` | Higher-mode & mode-kissing flags | `detect_mode_jump`, `detect_mode_kissing` |
| `uncertainty.py` | V_R error propagation | `compute_vr_with_uncertainty`, `classify_nearfield_severity_with_uncertainty` |
| `report.py` | Diagnostic report & scatter data | `compute_nearfield_report`, `prepare_nacd_vr_scatter` |
| `report_io.py` | Export to CSV / JSON / NPZ / ASCII | `save_nearfield_report_csv`, `save_nearfield_report_json` |
| `constants.py` | Shared constants (severity levels) | `SEVERITY_LEVELS` |

## Quick Start

```python
from dc_cut.core.processing.nearfield import (
    compute_nacd,
    resolve_nacd_threshold,
    compute_normalized_vr,
    classify_nearfield_severity,
    compute_nearfield_report,
)

# 1. Resolve threshold for your source type
threshold = resolve_nacd_threshold(
    source_type="sledgehammer",
    error_level="10_15pct",
    transform="fdbf_cylindrical",  # halves the threshold
)

# 2. Compute NACD for a single pick
nacd = compute_nacd(receiver_positions, freq=10.0, velocity=200.0, source_offset=-5.0)

# 3. Full diagnostic report across all offsets
report = compute_nearfield_report(
    velocity_arrays, frequency_arrays,
    receiver_positions=receiver_positions,
    source_offsets=source_offsets,
    nacd_threshold=threshold,
)
```

## Key Concepts

### NACD (Normalized Array-Center Distance)

```
NACD = x̄ / λ

x̄ = (1/M) Σ |xₘ − x_source|   (mean source-to-receiver distance)
λ = V / f                        (wavelength)
```

Points with NACD < threshold are near-field contaminated.

### Source-Type Thresholds (Rahimi et al. 2022, Table 2)

| Source Type | ≤ 10–15% error | ≤ 5% error |
|-------------|---------------|------------|
| Sledgehammer | NACD ≥ 1.0 | NACD ≥ 1.5 |
| Vibroseis | NACD ≥ 0.5 | NACD ≥ 0.6 |

### Transform Multipliers (Rahimi et al. 2021)

FDBF-cylindrical resolves ≈ 2× longer wavelengths than FK/τ-p, so its
effective NACD threshold is halved (multiplier = 0.5).

## Design Principles

- **Pure functions only** — no Qt/GUI imports, no controller references
- **Backward compatible** — `__init__.py` re-exports all public symbols
- **Paper-faithful** — every threshold cites the source paper and equation
- **API-first** — consumed via `dc_cut.api.analysis_ops` before GUI wiring
