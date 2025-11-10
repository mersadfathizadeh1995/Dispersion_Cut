from __future__ import annotations

from typing import Dict


def snapshot_state(controller) -> Dict:
    """Get a deep snapshot of the current session state.

    Prefers controller.get_current_state(); falls back to legacy structure.
    """
    try:
        return controller.get_current_state()
    except Exception:
        # Minimal fallback; not expected in our current bridge
        return {
            'velocity_arrays':   getattr(controller, 'velocity_arrays', []),
            'frequency_arrays':  getattr(controller, 'frequency_arrays', []),
            'wavelength_arrays': getattr(controller, 'wavelength_arrays', []),
            'set_leg':           getattr(controller, 'offset_labels', []),
        }


def restore_state(controller, state: Dict) -> None:
    """Restore a session snapshot safely and refresh the view."""
    try:
        controller.apply_state(state)
    except Exception:
        # Best effort minimal restore
        try:
            controller.velocity_arrays   = state['velocity_arrays']
            controller.frequency_arrays  = state['frequency_arrays']
            controller.wavelength_arrays = state['wavelength_arrays']
        except Exception:
            pass
    # Always refresh
    try:
        controller._apply_axis_limits(); controller.fig.canvas.draw_idle()
    except Exception:
        pass


def push_undo(controller) -> None:
    """Push current state using the legacy controller's _save_state()."""
    try:
        controller._save_state()
    except Exception:
        # Fallback to best-effort snapshot
        try:
            snap = snapshot_state(controller)
            controller.history.append(snap)
            controller.redo_stack.clear()
        except Exception:
            pass


def perform_undo(controller) -> bool:
    """Undo to the last snapshot; returns True if applied."""
    try:
        if not controller.history:
            return False
        # Push current to redo, then pop and restore undo
        try:
            controller.redo_stack.append(snapshot_state(controller))
        except Exception:
            pass
        state = controller.history.pop()
        restore_state(controller, state)
        return True
    except Exception:
        return False


def perform_redo(controller) -> bool:
    """Redo from the redo stack; returns True if applied."""
    try:
        if not controller.redo_stack:
            return False
        # Push current to undo, then pop and restore redo
        controller.history.append(snapshot_state(controller))
        state = controller.redo_stack.pop()
        restore_state(controller, state)
        return True
    except Exception:
        return False


