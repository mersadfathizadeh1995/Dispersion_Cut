# DC Cut — Interactive Dispersion Curve Editor

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

A **Qt-based desktop application** for interactive editing, visualization, and analysis of **surface wave dispersion curves** from **MASW (Multichannel Analysis of Surface Waves)** and **passive seismic array** data.

**Repository:** <https://github.com/mersadfathizadeh1995/Dispersion_Cut>

**Author:** Mersad Fathizadeh — Ph.D. Candidate, University of Arkansas
(email: mersadf@uark.edu · GitHub: [@mersadfathizadeh1995](https://github.com/mersadfathizadeh1995))

---

## Overview

DC Cut streamlines the workflow of cleaning, editing, and exporting dispersion curve picks commonly produced by MASW / passive FK / FDBF processing software (e.g., Geopsy, SurfSeis, MATLAB toolboxes). It replaces tedious manual editing in spreadsheets or MATLAB with a purpose-built interactive GUI.

### Key Features

- **Multi-format import** — MATLAB `.mat` (MASW), CSV, Geopsy `.max` (passive FK), and saved session files
- **Interactive box-select & delete** — Remove outlier picks with rubber-band selection on frequency or wavelength plots
- **Velocity / frequency / wavelength filtering** — Apply range-based filters to clean data
- **Near-field evaluation** — NACD (Normalized Array Center Distance) criteria for near-field effect assessment
- **Statistical averaging** — Frequency-binned and wavelength-binned averaging with uncertainty envelopes
- **Data appending** — Combine multiple files/arrays into a single session
- **Layer management** — Per-layer visibility, color, marker, and style customization via right-click context menu
- **Export Wizard** — Resample, smooth, and export cleaned curves to Geopsy-compatible TXT, CSV, or state files
- **Publication figures** — Generate camera-ready plots with uncertainty bands
- **Undo / Redo** — Full history stack for all editing operations

### Screenshots

> *Coming soon — screenshots of the main window, layer panel, and export wizard.*

---

## Domain

- **Geophysical Engineering / Near-Surface Geophysics**
- Seismic wave analysis for soil and rock characterization
- Surface wave methods: Active MASW, Passive FK/FDBF, Circular Array

---

## Installation

### Prerequisites

- **Python 3.10** or newer
- **pip** (included with Python)

### 1. Clone the Repository

```bash
git clone https://github.com/mersadfathizadeh1995/Dispersion_Cut.git
cd Dispersion_Cut/dc_cut
```

### 2. Create a Virtual Environment (recommended)

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install numpy pandas matplotlib scipy PyQt6
```

| Package | Purpose |
|---------|---------|
| **NumPy** | Array operations and data processing |
| **Pandas** | CSV / tabular data parsing |
| **Matplotlib** | Plotting with the Qt backend (`QtAgg`) |
| **SciPy** | `.mat` file loading |
| **PyQt6** | Qt GUI framework (PyQt5 also works) |

### 4. Run the Application

```bash
# Option A — as a Python module
python -m dc_cut

# Option B — runner script
python run_dc_cut.py
```

The **Launcher Window** will appear, letting you select a data file and processing mode (Active, Passive, Circular Array, or State).

---

## Quick Start

1. **Launch** — Run `python -m dc_cut`
2. **Select mode** — Choose *Active*, *Passive*, *Circular Array*, or load a saved *State*
3. **Browse file** — Select your `.mat`, `.csv`, `.max`, or state file
4. **Edit** — Use box-select (click-drag) to highlight outliers, then press `Delete`
5. **Filter** — Apply velocity / frequency / wavelength range filters from the Edit menu
6. **Average** — Toggle the average curve in the Layers panel
7. **Export** — Open the Export Wizard (`Ctrl+E`) to resample and save cleaned curves

### Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Open Data | `Ctrl+Shift+O` |
| Undo | `Ctrl+Z` |
| Redo | `Ctrl+Y` |
| Delete Selection | `Delete` |
| Cancel Selection | `Esc` |
| Add Point to Layer | `Ctrl+P` |
| Export Wizard | `Ctrl+E` |

---

## Supported File Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| MATLAB | `.mat` | MASW dispersion data (`FrequencyRaw`, `VelocityRaw`, `setLeg` keys) |
| CSV | `.csv` | Comma-separated frequency, velocity (, wavelength) columns |
| Geopsy Max | `.max` | Passive FK picks from Geopsy |
| Text | `.txt` | Tab/space-delimited dispersion data |
| State | `.dc_state` | Saved DC Cut session (JSON) |

---

## Project Structure

```
dc_cut/
├── app.py                  # Entry point, LauncherWindow, main()
├── run_dc_cut.py           # Simple runner script
├── __main__.py             # python -m dc_cut entry
├── __init__.py             # Package init
│
├── core/                   # Business logic
│   ├── controller.py       # Main controller (editing, undo/redo, state)
│   ├── base_controller.py  # Figure/axes, lines, selection tools
│   ├── model.py            # LayersModel, LayerData dataclasses
│   ├── selection.py        # Point selection & removal
│   ├── filters.py          # Velocity/frequency/wavelength filters
│   ├── averages.py         # Statistical binning & averaging
│   ├── plot.py             # Legend assembly helpers
│   └── controller_modules/ # Handler mix-ins (visualization, file I/O, etc.)
│
├── gui/                    # Qt widgets & dialogs
│   ├── main_window.py      # MainWindow with menus, toolbar, docks
│   ├── layer_tree_dock.py  # Layer tree with right-click settings
│   ├── layers_dock.py      # Simple layer visibility list
│   ├── open_data.py        # Open / Append data dialog
│   ├── add_point_dialog.py # Add point to layer dialog
│   └── layer_settings_dialog.py  # Per-layer color/marker settings
│
├── io/                     # File readers & writers
│   └── universal.py        # Unified parser for MAT, CSV, TXT, MAX
│
├── export_wizard/          # Export Wizard window
│   ├── wizard_main.py      # Main wizard window
│   ├── wizard_canvas.py    # Interactive resampling canvas
│   ├── wizard_table.py     # Editable data table
│   ├── data_model.py       # CurveDataModel
│   └── processing_panel.py # Smoothing & resampling controls
│
├── pub_figures/            # Publication-quality figure generator
├── services/               # Preferences, theming, logging, actions
├── circular_array/         # Circular array processing
├── theoretical_curves/     # Theoretical curve overlay support
│
└── example/                # Example data files for testing
    ├── Active_array/       # MASW .mat and .csv examples
    ├── LADC/               # Passive FK .max example
    ├── RTBF/               # Circular array example
    └── theoretical_curves/ # Inversion result overlays
```

---

## Architecture

DC Cut follows an **MVC-like pattern with an Action Registry**:

- **Model** — `core/model.py` (`LayersModel`, `LayerData`) holds per-layer arrays and visibility state
- **View** — `gui/` widgets display data via Matplotlib canvases embedded in Qt
- **Controller** — `core/controller.py` orchestrates editing, history, and plot updates
- **Services** — `services/` provides cross-cutting concerns (preferences, theming, logging)

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m "Add my feature"`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## Citation

If you use DC Cut in your research, please cite:

> Rahimi, M., Wood, C., Fathizadeh, M., & Rahimi, S. (2025). A Multi-method Geophysical Approach for Complex Shallow Landslide Characterization. *Annals of Geophysics*, 68(3), NS336. <https://doi.org/10.4401/ag-9203>

---

## License

Copyright (C) 2025 Mersad Fathizadeh

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License v3.0** as published by the Free Software Foundation.

See the [LICENSE](LICENSE) file for details.
