# Phase 5: Issues and Fixes Report

## Executive Summary

After exploring the codebase and analyzing the user-reported issues, I identified **5 critical bugs** and **2 design clarifications** needed for the circular array workflow to function correctly.

---

## Critical Bugs

### 1. Duplicate Workflow Dock (Two Docks Appearing)

**Symptom:** Two "Circular Array Workflow" dock widgets appear in the main window.

**Root Cause:** The workflow dock is created **twice**:
1. In `app.py` lines 602-612: Explicitly creates and adds `CircularArrayWorkflowDock`
2. In `main_window.py` line 164: `adopt_controller()` calls `_setup_circular_array_dock()` which creates another dock

**Location:**
- `dc_cut/app.py:602-612`
- `dc_cut/gui/main_window.py:164-191`

**Fix Required:**
Remove the dock creation from `app.py` (lines 602-614) since `main_window.py` already handles it automatically in `_setup_circular_array_dock()`.

---

### 2. AttributeError: 'velocity' not found on controller

**Symptom:** Error "InteractiveRemovalWithLayers object has no attribute 'velocity'" when clicking Save & Next.

**Root Cause:** The orchestrator's `get_state_dict()` and `export_current_stage_mat()` methods reference:
```python
c.velocity, c.frequency, c.wavelength
```
But the controller stores these as:
```python
c.velocity_arrays, c.frequency_arrays, c.wavelength_arrays
```

**Location:**
- `dc_cut/circular_array/orchestrator.py:113` - `get_state_dict()`
- `dc_cut/circular_array/orchestrator.py:157` - `export_current_stage_mat()`
- `dc_cut/circular_array/orchestrator.py:237` - `export_final_dinver()`

**Fix Required:**
Change all references from `c.velocity` to `c.velocity_arrays`, `c.frequency` to `c.frequency_arrays`, `c.wavelength` to `c.wavelength_arrays`.

---

### 3. Radio Buttons Not Mutually Exclusive

**Symptom:** Multiple array radio buttons appear "on" when clicking between them.

**Root Cause:** The radio buttons are created without being in a proper `QButtonGroup`. Qt radio buttons are only mutually exclusive if they share a parent or are in the same button group.

**Location:**
- `dc_cut/circular_array/workflow_dock.py:78-82`

**Fix Required:**
Add a `QButtonGroup` to manage the radio button exclusivity.

---

### 4. Array Focus Radio Buttons Should Be Hidden After INITIAL Stage

**Symptom:** The "Array Focus (k-limits)" section with 500m/200m/50m radio buttons should only appear during INITIAL stage, but may not be properly hidden.

**Root Cause:** The visibility logic at line 166 correctly sets visibility:
```python
self._array_group.setVisible(self.orchestrator.current_stage.name == 'INITIAL')
```
But this is only called in `_update_display()`, not when transitioning stages.

**Location:**
- `dc_cut/circular_array/workflow_dock.py:166`

**Fix Required:**
Ensure `_update_display()` is called after stage transitions.

---

### 5. Layers Model Not Used When Available

**Symptom:** The orchestrator checks for `layers_model` but falls back to the wrong attribute names.

**Root Cause:** The code at lines 106-117 and 150-161 checks:
```python
if hasattr(c, 'layers_model') and c.layers_model is not None:
    # Use layers_model
else:
    # Use c.velocity (WRONG - should be c.velocity_arrays)
```

**Location:**
- `dc_cut/circular_array/orchestrator.py:106-117`
- `dc_cut/circular_array/orchestrator.py:150-161`

**Fix Required:**
Fix the fallback path to use `velocity_arrays` instead of `velocity`.

---

## Design Clarifications

### 1. Stage Concept vs Array Concept

**User Confusion:** Expected 3 stages for 3 arrays (500m, 200m, 50m).

**Actual Design:** 
The 3 stages (INITIAL, INTERMEDIATE, REFINED) are **refinement passes** over the **same combined data**, not separate stages per array:

| Stage | Purpose |
|-------|---------|
| **INITIAL** | Per-array editing with array-specific k-limits. Use radio buttons to switch focus between 500m, 200m, 50m arrays. |
| **INTERMEDIATE** | Cross-array refinement with all arrays overlaid. No array focus needed. |
| **REFINED** | Final cleanup and mode extraction before export. |

**All 3 arrays are loaded together** and displayed as different colored layers. The radio buttons control which array's k-limits are shown as guides during INITIAL stage editing.

### 2. Radio Buttons Purpose

**User Confusion:** What do 500m/200m/50m radio buttons do?

**Actual Purpose:**
- These control which array's **k-limits** are displayed as vertical guide lines
- When you select "500m Array", the k-guides show the k-limits for the 500m array
- All 3 arrays are always visible; only the k-limit guides change
- This feature is only useful during INITIAL stage (should be hidden in later stages)

---

## Files Requiring Modification

| File | Issue # | Change Summary |
|------|---------|----------------|
| `dc_cut/app.py` | #1 | Remove duplicate dock creation (lines 602-614) |
| `dc_cut/circular_array/orchestrator.py` | #2, #5 | Fix `velocity` → `velocity_arrays` throughout |
| `dc_cut/circular_array/workflow_dock.py` | #3, #4 | Add QButtonGroup, ensure visibility update on stage change |

---

## Implementation Checklist for Phase 5

- [ ] **Bug #1:** Remove duplicate dock creation from `app.py`
- [ ] **Bug #2:** Fix `velocity` → `velocity_arrays` in orchestrator (3 locations)
- [ ] **Bug #3:** Add `QButtonGroup` to radio buttons in workflow_dock
- [ ] **Bug #4:** Call `refresh()` after stage transitions to update visibility
- [ ] **Bug #5:** Same as #2 - fix fallback attribute names
- [ ] **Test:** Verify only one dock appears
- [ ] **Test:** Verify Save & Next works without AttributeError
- [ ] **Test:** Verify radio buttons are mutually exclusive
- [ ] **Test:** Verify array focus section hides after INITIAL stage
- [ ] **Test:** Full workflow from INITIAL → INTERMEDIATE → REFINED → export

---

## Test Files for Verification

Use the provided test files:
- `D:\Runs\Readfield\Proccessed\Passive_HVSR\Processed\Processed_Passive\HRFK\Redfield_500mvertical.max`
- `D:\Runs\Readfield\Proccessed\Passive_HVSR\Processed\Processed_Passive\HRFK\Redfield_200mvertical.max`
- `D:\Runs\Readfield\Proccessed\Passive_HVSR\Processed\Processed_Passive\HRFK\Redfield_50mvertical.max`
- `D:\Runs\Readfield\Proccessed\Passive_HVSR\Processed\Processed_Passive\HRFK\klimits.mat`

Output directory: `D:\Runs\Readfield\Proccessed\Passive_HVSR\Processed\Processed_Passive\HRFK`
