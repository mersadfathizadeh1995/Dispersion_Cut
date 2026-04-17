# DC Cut -- Software Architecture

## Overview

DC Cut is a desktop application for interactive editing and analysis of surface-wave dispersion data. It is built with **Python 3.10+** and **PySide6** (Qt), following a **layered architecture** inspired by Clean Architecture and Hexagonal (Ports & Adapters) patterns.

The fundamental rule: **dependencies flow inward only**. Outer layers may import from inner layers, but inner layers never import from outer layers.

```
┌─────────────────────────────────────────────────────┐
│                   CONSUMERS (outermost)              │
│   gui/  ·  cli/  ·  future MCP server               │
├─────────────────────────────────────────────────────┤
│                   API (orchestration)                 │
│   api/config  ·  api/data_ops  ·  api/edit_ops  ... │
├─────────────────────────────────────────────────────┤
│                   CORE (innermost)                   │
│   core/models  ·  core/processing/  ·  core/io/     │
├─────────────────────────────────────────────────────┤
│   CROSS-CUTTING: services/  ·  visualization/        │
├─────────────────────────────────────────────────────┤
│   PACKAGES: packages/ (self-contained extensions)    │
└─────────────────────────────────────────────────────┘
```

---

## Layer Responsibilities

### `core/` -- Domain Logic (innermost, zero UI dependencies)

Pure Python. No Qt, no matplotlib figure management, no user preferences.

| Module | Purpose |
|--------|---------|
| `models.py` | Domain entities: `LayerData`, `LayerStyle`, `LayersModel` |
| `history.py` | Undo/redo snapshot stack |
| `processing/` | Stateless computation: selection, filters, averages, nearfield (NACD), limits, guides, ticks |
| `io/` | File readers/writers: universal parser, MATLAB, CSV, MAX, spectrum, state (session), export |

**Key constraint:** Every function in `core/processing/` is a pure function -- it takes arrays in, returns arrays out, with no side effects.

### `api/` -- Orchestration Layer

Sits between core and consumers. Provides:

- **Config dataclasses** (`SessionConfig`, `DataLoadConfig`, `FilterConfig`, etc.) that bundle parameters into typed, serializable objects.
- **Operation functions** (`data_ops.load_data`, `edit_ops.apply_filters`, `analysis_ops.compute_averages`, etc.) that validate inputs, call core functions, and return standardized `{"success": bool, "errors": [...], ...}` dicts.
- **Validation** (`validation.py`) for file paths, output paths, arrays, and numeric ranges.

The API layer is **consumer-agnostic** -- the same operations can be called from GUI, CLI, MCP server, or tests.

### `gui/` -- Qt Consumer (outermost)

The interactive desktop interface.

| Module | Purpose |
|--------|---------|
| `app.py` | Application entry point, `DataLoaderApp` (main data-loading orchestrator) |
| `main_window.py` | `MainWindow` -- Qt window, menus, toolbar, docks |
| `controller/` | Interactive editing logic: `composed.py` (main controller), `base.py`, tool handlers, NF inspector |
| `controller/handlers/` | 8 handler modules: spectrum, tools, dialogs, file I/O, state, edit, add, visualization |
| `views/` | Qt dock widgets: properties, layers, spectrum, NF eval, quick actions, etc. |
| `dialogs/` | Modal dialogs: open data, preferences, layer settings, add point, append data, pub figures |
| `widgets/` | Reusable Qt widget components |

### `visualization/` -- Plotting Utilities

| Module | Purpose |
|--------|---------|
| `plot_helpers.py` | Shared matplotlib helpers (legend assembly, line updates) |
| `pub_figures/` | Publication-quality figure generation: config, generator, plot types |

### `services/` -- Cross-cutting Concerns

| Module | Purpose |
|--------|---------|
| `prefs.py` | User preferences (load/save/get) |
| `theme.py` | Qt and matplotlib theming |
| `log.py` | Application logging |
| `actions.py` | Shared action definitions |
| `mpl_compat.py` | Matplotlib compatibility patches |

### `packages/` -- Self-contained Extension Packages

Feature modules that can be developed and added independently:

| Package | Purpose |
|---------|---------|
| `circular_array/` | Circular array workflow (multi-array k-limits, orchestration, workflow dock) |
| `theoretical_curves/` | Theoretical dispersion curve overlay (config, renderer, generator, dock) |
| `export_wizard/` | Advanced multi-step export wizard |

To add a new package, create a directory under `packages/` with its own `__init__.py`.

---

## Dependency Rules

```
gui/           -->  api/  -->  core/
gui/           -->  core/          (controller reads arrays directly)
gui/           -->  services/
gui/           -->  visualization/
gui/           -->  packages/
visualization/ -->  core/
api/           -->  core/
packages/      -->  core/, services/, gui/ (for docks)
core/          -->  (nothing -- only stdlib + numpy/scipy)
```

Arrows mean "may import from". A module must **never** import from a layer to its left.

---

## Entry Points

| Command | What it does |
|---------|-------------|
| `python -m dc_cut` | Runs `__main__.py` -> `gui.app.main()` |
| `python run_dc_cut.py` | Same, but adds parent directory to `sys.path` first |

---

## Current State and Future Direction

The **core** and **API** layers are fully separated. The GUI currently calls core functions both directly (through the controller) and will progressively migrate to calling API operation functions instead, which enables:

1. **CLI consumer** (`cli/`) -- headless batch processing using the same API
2. **MCP server** -- remote tool access for AI agents
3. **Testing** -- unit tests call API functions without any Qt dependency
