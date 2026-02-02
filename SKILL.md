# Refactoring Skill

## Purpose
Safely refactor a Python script into modular components using the parallel build approach. Never modify the original until refactoring is complete and verified.

---

## Phase 1: Analyze

Before writing any code:

- **Map the script structure:** List all functions, classes, and their responsibilities
- **Identify dependencies:** Document imports and external calls
- **Trace data flow:** What inputs/outputs exist for each component
- **Spot code smells:** Duplication, long functions, mixed responsibilities
- **Find extraction candidates:** Group related functionality that can become modules

Output: Mental model of script architecture and extraction order (least-coupled first)

---

## Phase 2: Plan

Create folder structure:

```
project/
├── original_script.py              # DO NOT TOUCH
├── {script_name}_modules/          # e.g., controller_modules/
│   ├── __init__.py
│   ├── {module_a}.py
│   ├── {module_b}.py
│   └── _old_code/                  # archive location
└── {script_name}_new.py            # built incrementally
```

Rules:
- Name module folder: `{original_script_name}_modules`
- Each module = single responsibility
- Plan extraction order before starting

---

## Phase 3: Execute

For each extraction, follow this cycle:

### 3.1 Extract
- Copy one logical piece from original into a new module file
- Keep it focused (one purpose per module)

### 3.2 Test
- Write basic tests verifying the extracted module works correctly
- Test edge cases and expected inputs/outputs
- Do not proceed until tests pass

### 3.3 Integrate
- Import the new module into `{script_name}_new.py`
- Wire it up to work with other completed modules
- Verify integrated behavior matches original

### 3.4 Repeat
- Move to next extraction candidate
- Continue until all functionality is migrated to `{script_name}_new.py`

---

## Phase 4: Finalize

Only after full verification:

1. **Run complete test suite** - all modules + integration
2. **Compare outputs** - new script must match original behavior exactly
3. **Archive original:**
   - Move `original_script.py` → `{script_name}_modules/_old_code/`
4. **Rename new script:**
   - Rename `{script_name}_new.py` → `original_script.py`

---

## Rules (Never Break)

| Rule | Reason |
|------|--------|
| Never delete/modify original during refactor | Safety net |
| One extraction per cycle | Reduces debugging complexity |
| Test before integrating | Catch issues early |
| Keep original until 100% verified | Rollback capability |
| Each module = single responsibility | Clean architecture |

---

## Module Naming Convention

- Folder: `{script_name}_modules/`
- Modules: descriptive, lowercase, underscores (e.g., `data_parser.py`, `api_handler.py`)
- Archive: `_old_code/` (underscore prefix = internal/private)

---

## Quick Reference

```
1. ANALYZE  →  Understand everything first
2. PLAN     →  Create folder structure + extraction order
3. EXECUTE  →  Extract → Test → Integrate → Repeat
4. FINALIZE →  Verify all → Archive original → Rename new
```
