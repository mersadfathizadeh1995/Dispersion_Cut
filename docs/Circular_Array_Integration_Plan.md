# Circular Array Workflow Integration Plan

## Architecture Overview

```
dc_cut/
├── circular_array/          # NEW SUBPACKAGE
│   ├── __init__.py
│   ├── config.py           # WorkflowConfig, Stage enum
│   ├── io.py               # Multi-array I/O, MAT export
│   ├── orchestrator.py     # Workflow state machine
│   └── workflow_dock.py    # UI dock widget
├── gui/
│   ├── open_data.py        # MODIFY: Add Circular Array tab
│   └── main_window.py      # MODIFY: Conditionally add workflow dock
├── io/
│   └── export.py           # MODIFY: Add export_to_mat()
└── app.py                  # MODIFY: Add dispatcher
```

## Workflow State Machine

```
LOAD DIALOG → Select .max files (3), klimits (3 rows), output directory
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  INITIAL STAGE                                      │
│  - Per-array editing with array-specific k-limits   │
│  - Array focus selector switches k-guides           │
│  Outputs: {site}_Initial.pkl, {site}_Initial.mat    │
└─────────────────────────────────────────────────────┘
      │ [Save & Next]
      ▼
┌─────────────────────────────────────────────────────┐
│  INTERMEDIATE STAGE                                 │
│  - Cross-array refinement, all arrays overlaid      │
│  - [Back] reloads Initial.pkl (full undo history)   │
│  Outputs: {site}_Intermediate.pkl/.mat              │
└─────────────────────────────────────────────────────┘
      │ [Save & Next]
      ▼
┌─────────────────────────────────────────────────────┐
│  REFINED STAGE                                      │
│  - Mode extraction and final cleanup                │
│  - [Back] reloads Intermediate.pkl                  │
│  - [Complete] exports dinver.txt                    │
│  Outputs: {site}_Refined.pkl/.mat, {site}_dinver.txt│
└─────────────────────────────────────────────────────┘
```

## K-Limits File Format

3-row CSV or MAT:
```
diameter, kmin, kmax
500, 0.002, 0.02
200, 0.005, 0.05
50, 0.02, 0.2
```

---

## Phase 1: Foundation (Days 1-2)

### Objective
Create `circular_array` subpackage with config and I/O.

### Files to Create

**1. `dc_cut/circular_array/__init__.py`**
```python
from .config import WorkflowConfig, Stage, ArrayConfig
from .orchestrator import CircularArrayOrchestrator
__all__ = ['WorkflowConfig', 'Stage', 'ArrayConfig', 'CircularArrayOrchestrator']
```

**2. `dc_cut/circular_array/config.py`**
- `Stage` enum: INITIAL, INTERMEDIATE, REFINED with next()/prev() methods
- `ArrayConfig` dataclass: diameter, max_file_path, kmin, kmax
- `WorkflowConfig` dataclass: site_name, output_dir, arrays, wave_type, current_stage
  - Methods: `get_klimits_for_array()`, `get_state_path()`, `get_mat_path()`, `get_dinver_path()`

**3. `dc_cut/circular_array/io.py`**
- `load_multi_array_klimits(path)` → Dict[int, Tuple[kmin, kmax]]
- `export_stage_to_mat(...)` → saves velocity/freq/wavelength per array
- `export_dinver_txt(...)` → frequency, slowness mean/std, count

### Phase 1 Tests
- Stage navigation (next/prev)
- Config path generation
- K-limits loading from CSV and MAT

### Acceptance Criteria
- [ ] Can import `from dc_cut.circular_array import WorkflowConfig, Stage`
- [ ] K-limits parser handles both .csv and .mat
- [ ] All Phase 1 tests pass

---

## Phase 2: Open Dialog & Loading (Days 3-4)

### Objective
Add "Circular Array" tab to OpenDataDialog and implement loading.

### Files to Modify

**1. `dc_cut/gui/open_data.py`** - Add `CircularArrayTab`
- Site name input
- Output directory browser (REQUIRED)
- 3x array file browsers (500m, 200m, 50m .max files)
- K-limits file browser
- Wave type radio buttons
- "Continue existing session" option (.pkl file)
- Validation method

**2. `dc_cut/app.py`** - Add `_load_circular_array(spec)`
- Handle 'circular_array_new' mode: parse .max files, create orchestrator
- Handle 'circular_array_continue' mode: load from .pkl

### Phase 2 Tests
- Tab validation (required fields)
- Config dict generation
- Load dispatcher routing

### Acceptance Criteria
- [ ] Circular Array tab appears in dialog
- [ ] Required field validation works
- [ ] Can browse for all files
- [ ] App launches orchestrator on accept

---

## Phase 3: Orchestrator & Workflow Dock (Days 5-7)

### Objective
Implement workflow orchestrator and control dock.

### Files to Create

**1. `dc_cut/circular_array/orchestrator.py`** - `CircularArrayOrchestrator`
- `__init__(config)` - stores config, prepares for launch
- `from_session(path)` - class method to load from .pkl
- `launch()` - creates controller, opens main window, adds dock
- `set_array_focus(diameter)` - updates k-limits for selected array
- `save_current_stage()` - saves .pkl and .mat
- `complete_stage()` - save only
- `save_and_next()` - save, advance stage, reload app
- `go_back()` - load previous stage .pkl, reload app
- `_reload_app()` - close window, relaunch with new state
- `_export_final()` - dinver export at end

**2. `dc_cut/circular_array/workflow_dock.py`** - `CircularArrayWorkflowDock`
- Stage indicator label with styling
- Progress bar (1-3)
- Array focus radio buttons (visible only in INITIAL)
- Output info display
- Buttons: [Complete], [Save & Next], [Back]

### Phase 3 Tests
- Orchestrator stage management
- Save/load state files
- Stage transition (reload)
- Back navigation

### Acceptance Criteria
- [ ] Workflow dock shows current stage
- [ ] Array focus selector changes k-limits
- [ ] Save creates both .pkl and .mat
- [ ] Next stage reloads app quickly (<2 sec)
- [ ] Back loads previous .pkl with undo history

---

## Phase 4: Export & Integration (Days 8-9)

### Objective
Complete MAT export and integrate with main window.

### Files to Modify

**1. `dc_cut/io/export.py`** - Add `export_to_mat()`
- Per-array: velocity, frequency, wavelength, slowness
- Combined arrays for convenience
- Metadata (site_name, stage, etc.)

**2. `dc_cut/gui/main_window.py`**
- In `adopt_controller()`: check for `_circular_orchestrator` attribute
- If present, add `CircularArrayWorkflowDock`

### Phase 4 Tests
- MAT export produces valid file
- MAT loadable in MATLAB/scipy
- Dinver txt format correct
- Dock only appears in circular array mode

### Acceptance Criteria
- [ ] .mat files work in MATLAB
- [ ] Normal passive/active modes unchanged
- [ ] Dinver export correct format

---

## Phase 5: Testing & Polish (Days 10-12)

### Objective
Integration testing, edge cases, documentation.

### Integration Tests
1. Full workflow from new .max files through all 3 stages
2. Continue from saved intermediate session
3. Back navigation preserves undo history
4. Error handling for missing/invalid files

### Edge Cases
| Case | Behavior |
|------|----------|
| Missing .max file | Error dialog, don't crash |
| Invalid klimits | Show expected format |
| Output dir not writable | Permission error |
| Corrupted session | Suggest starting fresh |
| Back at first stage | Button disabled |

### Acceptance Criteria
- [ ] All integration tests pass
- [ ] Edge cases handled gracefully
- [ ] Reload < 2 seconds
- [ ] No memory leaks

---

## Summary

| Phase | Days | Key Deliverable |
|-------|------|-----------------|
| 1 | 2 | Config + I/O subpackage |
| 2 | 2 | Open dialog tab + loading |
| 3 | 3 | Orchestrator + workflow dock |
| 4 | 2 | MAT export + integration |
| 5 | 3 | Testing + polish |
| **Total** | **12** | **Complete workflow** |

**Files: 5 new, 4 modified**

---

## Approval Checklist

Before Phase 1, confirm:
- [ ] Architecture acceptable
- [ ] 3-stage workflow correct
- [ ] K-limits 3-row format correct
- [ ] Output naming convention acceptable
- [ ] Phase order acceptable

**Reply to confirm or request changes.**
