"""
Curve History Management
========================

Undo/Redo system for curve processing operations.
"""

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class CurveState:
    """Represents a single state in the curve history."""
    filepath: str  # Path to the file representing this state
    description: str  # Description of the operation that created this state
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata


class CurveHistoryManager:
    """Manages undo/redo history for curve processing."""
    
    MAX_HISTORY = 20
    
    def __init__(self, temp_dir: Optional[str] = None):
        """Initialize the history manager.
        
        Args:
            temp_dir: Optional custom temp directory. If None, uses system temp.
        """
        if temp_dir:
            self._temp_dir = Path(temp_dir)
            self._temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            self._temp_dir = Path(tempfile.mkdtemp(prefix="target_builder_"))
        
        # History per curve (keyed by curve UID)
        self._histories: Dict[str, List[CurveState]] = {}
        self._current_indices: Dict[str, int] = {}  # Current position in history
    
    @property
    def temp_dir(self) -> Path:
        """Get the temp directory path."""
        return self._temp_dir
    
    def set_temp_dir(self, path: str):
        """Set a new temp directory."""
        new_dir = Path(path)
        new_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dir = new_dir
    
    def initialize_curve(self, uid: str, original_filepath: str, description: str = "Original") -> str:
        """Initialize history for a new curve.
        
        Args:
            uid: Unique identifier for the curve
            original_filepath: Path to the original file
            description: Description of initial state
            
        Returns:
            Path to the working copy
        """
        # Create working copy in temp directory
        working_path = self._create_working_copy(uid, original_filepath, "v0")
        
        # Initialize history with original state
        initial_state = CurveState(
            filepath=working_path,
            description=description,
            metadata={"original": original_filepath}
        )
        
        self._histories[uid] = [initial_state]
        self._current_indices[uid] = 0
        
        return working_path
    
    def push_state(self, uid: str, filepath: str, description: str, 
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """Push a new state to the history.
        
        Args:
            uid: Curve UID
            filepath: Path to file with new state data
            description: Description of the operation
            metadata: Optional additional metadata
            
        Returns:
            Path to the new working copy
        """
        if uid not in self._histories:
            raise ValueError(f"Curve {uid} not initialized in history")
        
        current_idx = self._current_indices[uid]
        history = self._histories[uid]
        
        # Remove any states after current position (discard redo history)
        while len(history) > current_idx + 1:
            old_state = history.pop()
            self._cleanup_file(old_state.filepath)
        
        # Create new version
        version = len(history)
        working_path = self._create_working_copy(uid, filepath, f"v{version}")
        
        new_state = CurveState(
            filepath=working_path,
            description=description,
            metadata=metadata or {}
        )
        
        history.append(new_state)
        self._current_indices[uid] = len(history) - 1
        
        # Trim history if too long
        while len(history) > self.MAX_HISTORY:
            old_state = history.pop(0)
            self._cleanup_file(old_state.filepath)
            self._current_indices[uid] -= 1
        
        return working_path
    
    def undo(self, uid: str) -> Optional[CurveState]:
        """Undo the last operation.
        
        Args:
            uid: Curve UID
            
        Returns:
            The previous state, or None if at beginning
        """
        if uid not in self._histories:
            return None
        
        current_idx = self._current_indices[uid]
        if current_idx <= 0:
            return None  # Already at beginning
        
        self._current_indices[uid] = current_idx - 1
        return self._histories[uid][current_idx - 1]
    
    def redo(self, uid: str) -> Optional[CurveState]:
        """Redo the last undone operation.
        
        Args:
            uid: Curve UID
            
        Returns:
            The next state, or None if at end
        """
        if uid not in self._histories:
            return None
        
        current_idx = self._current_indices[uid]
        history = self._histories[uid]
        
        if current_idx >= len(history) - 1:
            return None  # Already at end
        
        self._current_indices[uid] = current_idx + 1
        return history[current_idx + 1]
    
    def get_current_state(self, uid: str) -> Optional[CurveState]:
        """Get the current state for a curve.
        
        Args:
            uid: Curve UID
            
        Returns:
            Current state, or None if not found
        """
        if uid not in self._histories:
            return None
        
        idx = self._current_indices[uid]
        return self._histories[uid][idx]
    
    def get_current_filepath(self, uid: str) -> Optional[str]:
        """Get the current working filepath for a curve.
        
        Args:
            uid: Curve UID
            
        Returns:
            Current working filepath, or None if not found
        """
        state = self.get_current_state(uid)
        return state.filepath if state else None
    
    def can_undo(self, uid: str) -> bool:
        """Check if undo is available."""
        if uid not in self._current_indices:
            return False
        return self._current_indices[uid] > 0
    
    def can_redo(self, uid: str) -> bool:
        """Check if redo is available."""
        if uid not in self._histories:
            return False
        return self._current_indices[uid] < len(self._histories[uid]) - 1
    
    def get_history(self, uid: str) -> List[CurveState]:
        """Get full history for a curve."""
        return self._histories.get(uid, [])
    
    def get_history_position(self, uid: str) -> tuple:
        """Get current position in history.
        
        Returns:
            (current_index, total_count)
        """
        if uid not in self._histories:
            return (0, 0)
        return (self._current_indices[uid], len(self._histories[uid]))
    
    def remove_curve(self, uid: str):
        """Remove all history for a curve."""
        if uid in self._histories:
            for state in self._histories[uid]:
                self._cleanup_file(state.filepath)
            del self._histories[uid]
            del self._current_indices[uid]
    
    def cleanup(self):
        """Clean up all temp files."""
        for uid in list(self._histories.keys()):
            self.remove_curve(uid)
        
        # Try to remove temp directory if empty
        try:
            if self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)
        except Exception:
            pass
    
    def _create_working_copy(self, uid: str, source_path: str, version: str) -> str:
        """Create a working copy of a file.
        
        Args:
            uid: Curve UID
            source_path: Source file path
            version: Version string
            
        Returns:
            Path to the working copy
        """
        # Create subdirectory for this curve
        curve_dir = self._temp_dir / uid
        curve_dir.mkdir(parents=True, exist_ok=True)
        
        # Create unique filename
        source_name = Path(source_path).stem
        ext = Path(source_path).suffix or ".txt"
        working_path = curve_dir / f"{source_name}_{version}{ext}"
        
        # Copy file
        shutil.copy2(source_path, working_path)
        
        return str(working_path)
    
    def _cleanup_file(self, filepath: str):
        """Safely remove a file."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass


# Global history manager instance
_history_manager: Optional[CurveHistoryManager] = None


def get_history_manager() -> CurveHistoryManager:
    """Get the global history manager instance."""
    global _history_manager
    if _history_manager is None:
        _history_manager = CurveHistoryManager()
    return _history_manager


def set_history_temp_dir(path: str):
    """Set the temp directory for history manager."""
    get_history_manager().set_temp_dir(path)
