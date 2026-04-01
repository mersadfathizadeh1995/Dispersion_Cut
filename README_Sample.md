<div align="center">

# HVSR Pro

### Professional HVSR Analysis Suite

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-41CD52.svg)](https://www.riverbankcomputing.com/software/pyqt/)

A modern, integrated **Horizontal-to-Vertical Spectral Ratio (HVSR)** analysis suite for seismic site characterization — featuring project-based workflows, multi-station batch processing, bedrock depth mapping, HVSR inversion, and publication-quality visualization.

**Author:** Mersad Fathizadeh — Ph.D. Candidate, University of Arkansas  
📧 mersadf@uark.edu · GitHub: [@mersadfathizadeh1995](https://github.com/mersadfathizadeh1995)

</div>

---

## Overview

HVSR Pro provides a complete pipeline for HVSR analysis of ambient vibration (microtremor) recordings. From raw seismic data import through spectral ratio computation to bedrock depth estimation and Google Earth export — everything is accessible through an interactive GUI, command-line interface, or Python API.

### Key Capabilities

| Module | Description |
|--------|-------------|
| **Standard Analysis** | Single-station HVSR with interactive windowing, multi-algorithm rejection, and azimuthal processing |
| **Batch Processing** | Multi-station automated analysis with configurable sensor routing and time-window assignment |
| **Bedrock Mapping** | Spatial interpolation of bedrock depth from HVSR peak frequencies, with KMZ export to Google Earth |
| **HV Strip** | Progressive time-frequency analysis with multiple processing engines and a figure studio |
| **HVSR Invert** | Forward-model inversion of HVSR curves to recover subsurface velocity structure |
| **Project Manager** | Unified project workflow connecting all modules with persistent state |

---

## Visual Tour

### 🗂️ Project Manager

Create and manage analysis projects. Define stations, assign sensors, and navigate between modules — all state is saved and restored automatically.

<p align="center">
  <img src="Pictures/1_project_define.jpg" width="65%" alt="Project creation dialog"/>
</p>

<p align="center">
  <img src="Pictures/2_main_window.jpg" width="80%" alt="Main application window"/>
</p>

---

### 📊 Standard HVSR Analysis

Load seismic data in multiple formats, configure processing settings, and compute HVSR interactively. Supports real-time window rejection, azimuthal processing, and layer-based visualization.

<p align="center">
  <img src="Pictures/3_standard_analysis_data_loading.jpg" width="80%" alt="Data loading"/>
</p>

<p align="center">
  <img src="Pictures/4_standard.jpg" width="80%" alt="HVSR analysis view"/>
</p>

<p align="center">
  <img src="Pictures/5_processing_settings.jpg" width="60%" alt="Processing settings panel"/>
</p>

<p align="center">
  <img src="Pictures/Standard_Analyze_Azimuthal_processing.jpg" width="80%" alt="Azimuthal HVSR processing"/>
</p>

<details>
<summary><strong>📈 Analysis Output Figures (click to expand)</strong></summary>
<br>

HVSR Pro generates a comprehensive set of publication-quality figures for each analysis:

<p align="center">
  <img src="Pictures/HVSR_Analysis_outputs/HVSR_STN01_FullDuration_waveform_3c.png" width="70%" alt="3-component waveform"/>
  <br><em>Three-component waveform display</em>
</p>

<p align="center">
  <img src="Pictures/HVSR_Analysis_outputs/HVSR_STN01_FullDuration_window_spectrogram.png" width="70%" alt="Window spectrogram"/>
  <br><em>Window spectrogram with time-frequency content</em>
</p>

<p align="center">
  <img src="Pictures/HVSR_Analysis_outputs/HVSR_STN01_FullDuration_pre_post_rejection.png" width="70%" alt="Pre/post rejection"/>
  <br><em>Pre- and post-rejection HVSR comparison</em>
</p>

<p align="center">
  <img src="Pictures/HVSR_Analysis_outputs/HVSR_STN01_FullDuration_raw_vs_adjusted.png" width="70%" alt="Raw vs adjusted HVSR"/>
  <br><em>Raw vs. adjusted HVSR curves</em>
</p>

<p align="center">
  <img src="Pictures/HVSR_Analysis_outputs/HVSR_STN01_FullDuration_hvsr_curve.png" width="70%" alt="Final HVSR curve"/>
  <br><em>Final HVSR curve with peak identification</em>
</p>

<p align="center">
  <img src="Pictures/HVSR_Analysis_outputs/HVSR_STN01_FullDuration_statistics.png" width="70%" alt="Statistics panel"/>
  <br><em>Statistical summary — mean/median, variability, and quality metrics</em>
</p>

</details>

<p align="center">
  <img src="Pictures/7_export%20option.jpg" width="40%" alt="Export options"/>
  <img src="Pictures/8_layers.jpg" width="55%" alt="Layer management"/>
</p>
<p align="center"><em>Export dialog (left) and layer management panel (right)</em></p>

---

### ⚡ Batch Processing

Process multiple stations at once with automatic sensor routing, per-station time-window configuration, and comprehensive statistics. Results are saved to the project and can be reloaded at any time.

<p align="center">
  <img src="Pictures/9_Batch_Processing.jpg" width="80%" alt="Batch processing window"/>
</p>

<p align="center">
  <img src="Pictures/HVSR_STN02_T_01_statistics.png" width="70%" alt="Batch statistics output"/>
  <br><em>Per-station statistics: H/V curve with uncertainty, mean vs. median comparison, variability, and summary</em>
</p>

---

### 🗺️ Bedrock Mapping

Compute bedrock depth from HVSR peak frequencies and Vs profiles. Perform spatial interpolation (IDW, Kriging, RBF), generate surface and bedrock contours, and export everything to Google Earth as KMZ.

<p align="center">
  <img src="Pictures/10_bedrock_Mapping.jpg" width="80%" alt="Bedrock mapping — map view"/>
</p>

<p align="center">
  <img src="Pictures/11_bedrock_Mapping_table.jpg" width="80%" alt="Bedrock mapping — station table"/>
  <br><em>Station registry with coordinates, Vs average, f0, depth, and bedrock elevation</em>
</p>

<p align="center">
  <img src="Pictures/12_bedrock_Interpolation.jpg" width="55%" alt="Interpolation settings"/>
  <br><em>Interpolation configuration panel</em>
</p>

<p align="center">
  <img src="Pictures/13_bedrodk_contour.jpg" width="80%" alt="Bedrock contour on map"/>
</p>

<p align="center">
  <img src="Pictures/14_Surface_contour.jpg" width="80%" alt="Surface elevation contour"/>
</p>

<p align="center">
  <img src="Pictures/15_Google_earth_export.jpg" width="60%" alt="Google Earth export settings"/>
</p>

<p align="center">
  <img src="Pictures/Google_Earth_output.jpg" width="80%" alt="KMZ output in Google Earth"/>
  <br><em>Contour layers and station markers exported to Google Earth</em>
</p>

#### 2D & 3D Visualization

<p align="center">
  <img src="Pictures/2D_plot.jpg" width="45%" alt="2D visualization"/>
  <img src="Pictures/3d_Plot.jpg" width="45%" alt="3D visualization"/>
</p>
<p align="center"><em>2D cross-section and interactive 3D subsurface model</em></p>

---

### 📐 HV Strip — Progressive Analysis

Time-frequency progressive HVSR analysis with multiple processing engines, side-by-side engine comparison, and a dedicated figure studio for creating custom visualizations.

<p align="center">
  <img src="Pictures/HV_Strip_App.jpg" width="80%" alt="HV Strip main window"/>
</p>

<p align="center">
  <img src="Pictures/HV_Strip_Progressive.jpg" width="45%" alt="Progressive analysis"/>
  <img src="Pictures/HV_Strip_Different_Engins.jpg" width="45%" alt="Engine comparison"/>
</p>
<p align="center"><em>Progressive analysis (left) and multi-engine comparison (right)</em></p>

<p align="center">
  <img src="Pictures/HV_Strip_Figure_Studio.jpg" width="70%" alt="Figure studio"/>
  <br><em>Figure Studio — customize and export publication-ready plots</em>
</p>

---

### 🔬 HVSR Invert — Subsurface Inversion

Forward-model inversion of HVSR curves to estimate subsurface shear-wave velocity profiles. Define layer bounds, run the inversion, and visualize the recovered Vs structure.

<p align="center">
  <img src="Pictures/HVSR_Invert.jpg" width="80%" alt="HVSR Invert main window"/>
</p>

<p align="center">
  <img src="Pictures/HVSR_Invert_bound_Generation.jpg" width="45%" alt="Bound generation"/>
  <img src="Pictures/HVSR_Invert_inversion_process.jpg" width="45%" alt="Inversion process"/>
</p>
<p align="center"><em>Layer bound generation (left) and inversion progress (right)</em></p>

---

## Installation

### Prerequisites

- **Python 3.8** or newer
- **pip** (included with Python)

### 1. Clone the Repository

```bash
git clone --recurse-submodules https://github.com/mersadfathizadeh1995/HV_Pro.git
cd HV_Pro/HV_Analyze_Pro
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
pip install -r requirements.txt
```

Or install the package in editable mode:

```bash
pip install -e .
```

<details>
<summary><strong>Core Dependencies</strong></summary>

| Package | Purpose |
| ------- | ------- |
| NumPy | Array operations and numerical computation |
| SciPy | Signal processing, spectral analysis |
| Matplotlib | Plotting and visualization |
| Pandas | Tabular data handling |
| ObsPy | Seismic data I/O (MiniSEED, SAC, etc.) |
| PyQt5 | GUI framework |
| PyQtWebEngine | Interactive map display |
| Folium | Leaflet-based station maps |
| Plotly | Interactive 3D visualizations |
| pyproj | Coordinate system transformations |
| scikit-learn | ML-based window rejection |
| PyYAML | Settings persistence |

</details>

<details>
<summary><strong>Optional — 3D Bedrock Mapping</strong></summary>

| Package | Purpose |
| ------- | ------- |
| PyKrige | Kriging interpolation |
| Shapely | Boundary geometry operations |
| PyVista | 3D mesh visualization and export |
| Pillow | Contour image generation |

</details>

### 4. Launch the Application

```bash
# GUI launcher
python launch_gui.py

# Project Manager (project-based workflow)
python -m hvsr_pro.packages.project_manager.main

# CLI
python -m hvsr_pro.cli --help
```

---

## Usage

### GUI Workflow

```bash
python launch_gui.py
```

1. **Load Data** — Import seismic recordings (MiniSEED, SAC, GCF, TXT, and more)
2. **Configure** — Adjust window length, overlap, smoothing, and rejection settings
3. **Process** — Compute HVSR spectral ratios
4. **Reject** — Toggle individual windows on/off interactively
5. **Analyze** — View mean HVSR, peak frequency, amplitude, and quality metrics
6. **Export** — Save results, plots, and full session files

### CLI

```bash
# Process a single file
python -m hvsr_pro.cli process data.txt --output results/

# Batch process a directory
python -m hvsr_pro.cli batch input_dir/ --output results/

# Show help
python -m hvsr_pro.cli --help
```

### Python API

```python
from hvsr_pro import HVSRDataHandler, HVSRProcessor, HVSRAnalysis

# Quick analysis
analysis = HVSRAnalysis()
results = analysis.run("data.txt", output_dir="results/")
print(f"Peak frequency: {results.peak_frequency:.2f} Hz")

# Step-by-step
handler = HVSRDataHandler()
data = handler.load_data("data.txt")

processor = HVSRProcessor()
results = processor.process(data)
```

---

## Project Structure

```
HV_Pro/
└── HV_Analyze_Pro/
    ├── launch_gui.py               # GUI launcher
    ├── setup.py                    # Package setup
    ├── requirements.txt            # Dependencies
    │
    └── hvsr_pro/                   # Main package
        ├── core/                   # Data structures & handling
        ├── processing/             # HVSR computation engine
        │   ├── hvsr/               #   Spectral ratio algorithms
        │   ├── windows/            #   Window management
        │   ├── rejection/          #   Multi-algorithm rejection
        │   ├── smoothing/          #   Konno-Ohmachi, Parzen, etc.
        │   └── azimuthal/          #   Directional HVSR
        ├── visualization/          # Matplotlib plotting tools
        ├── gui/                    # PyQt5 application
        │   ├── main_window.py      #   Main window
        │   ├── tabs/               #   Analysis tab widgets
        │   ├── panels/             #   Side panels
        │   ├── docks/              #   Dockable widgets
        │   ├── dialogs/            #   Dialog windows
        │   └── workers/            #   Background threads
        ├── loaders/                # Format-specific readers
        ├── config/                 # Settings & session persistence
        ├── cli/                    # Command-line interface
        ├── api/                    # Programmatic API
        │
        └── packages/               # Integrated sub-packages
            ├── project_manager/     #   Project workflow manager
            ├── batch_processing/    #   Multi-station batch analysis
            ├── bedrock_mapping/     #   Bedrock depth mapping (submodule)
            ├── hvstrip-progressive/ #   HV strip analysis (submodule)
            └── invert_hvsr/         #   HVSR inversion (submodule)
```

---

## Architecture

HVSR Pro follows a **layered, modular architecture**:

| Layer | Location | Role |
|-------|----------|------|
| **Core** | `core/` | Data structures, unified data handler, caching |
| **Processing** | `processing/` | Windowing, rejection, smoothing, HVSR computation |
| **Visualization** | `visualization/` | Matplotlib-based plotting engine |
| **Loaders** | `loaders/` | Format-specific readers (MiniSEED, SAC, GCF, TXT, ...) |
| **Config** | `config/` | Settings management, validation, session persistence |
| **GUI** | `gui/` | PyQt5 application with tabs, docks, and background workers |
| **CLI / API** | `cli/`, `api/` | Non-GUI access to the full pipeline |
| **Packages** | `packages/` | Self-contained modules (batch, bedrock, invert, HV strip) connected via the project manager |

---

## Supported Seismic Formats

| Format | Extension | Description |
| ------ | --------- | ----------- |
| MiniSEED | `.mseed`, `.miniseed` | Standard seismological format (via ObsPy) |
| SAC | `.sac` | Seismic Analysis Code format |
| GCF | `.gcf` | Guralp Compressed Format |
| ASCII/TXT | `.txt`, `.dat` | Column-based time series |
| SAF | `.saf` | Seismic Analysis Format |
| PEER | `.at2`, `.peer` | PEER ground motion database |
| MiniShark | various | MiniShark portable recorder |

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m "Add my feature"`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## Acknowledgments

This work was developed under the guidance of **Dr. Clinton Wood** at the University of Arkansas. Parts of the azimuthal analysis workflow and certain data-input format handling drew inspiration from [hvsrpy](https://github.com/jpvantassel/hvsrpy).

---

## Citation

If you use HVSR Pro in your research, please cite:

> Rahimi, M., Wood, C., Fathizadeh, M., & Rahimi, S. (2025). A Multi-method Geophysical Approach for Complex Shallow Landslide Characterization. *Annals of Geophysics*, 68(3), NS336. https://doi.org/10.4401/ag-9203

---

## License

Copyright (C) 2025 Mersad Fathizadeh

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License v3.0** as published by the Free Software Foundation.

See the [LICENSE](LICENSE) file for details.