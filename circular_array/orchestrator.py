"""Orchestrator for circular array workflow management."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict, Any, TYPE_CHECKING
import numpy as np

from dc_cut.circular_array.config import WorkflowConfig, Stage
from dc_cut.circular_array.io import export_stage_to_mat, export_dinver_txt
from dc_cut.core.io.state import save_session, load_session

if TYPE_CHECKING:
    from dc_cut.gui.controller.composed import InteractiveRemovalWithLayers


class CircularArrayOrchestrator:
    """Manages the circular array workflow lifecycle.
    
    Handles stage transitions, state persistence, and controller coordination.
    """

    def __init__(self, config: WorkflowConfig, controller: Optional[InteractiveRemovalWithLayers] = None):
        self.config = config
        self.controller = controller
        self._focused_array_idx: int = 0
        self._active_klimits: List[int] = []

    @classmethod
    def from_session(cls, session_path: Path) -> CircularArrayOrchestrator:
        """Load orchestrator from existing session file."""
        S = load_session(str(session_path))
        
        if 'workflow_config' not in S:
            raise ValueError("Session file does not contain workflow_config")
        
        config = WorkflowConfig.from_dict(S['workflow_config'])
        orchestrator = cls(config)
        orchestrator._session_data = S
        return orchestrator

    @property
    def current_stage(self) -> Stage:
        """Get current workflow stage."""
        return self.config.current_stage

    @property
    def stage_number(self) -> int:
        """Get 1-indexed stage number."""
        stages = list(Stage)
        return stages.index(self.current_stage) + 1

    @property
    def total_stages(self) -> int:
        """Get total number of stages."""
        return len(list(Stage))

    @property
    def is_first_stage(self) -> bool:
        """Check if at first stage."""
        return self.current_stage.prev() is None

    @property
    def is_last_stage(self) -> bool:
        """Check if at last stage."""
        return self.current_stage.next() is None

    @property
    def focused_array(self) -> Optional[int]:
        """Get currently focused array diameter."""
        diameters = self.config.get_array_diameters()
        if 0 <= self._focused_array_idx < len(diameters):
            return diameters[self._focused_array_idx]
        return None

    def set_array_focus(self, diameter: int) -> None:
        """Set focus to specific array, update k-limits on controller."""
        diameters = self.config.get_array_diameters()
        if diameter not in diameters:
            raise ValueError(f"Array {diameter}m not in config")
        
        self._focused_array_idx = diameters.index(diameter)
        
        if self.controller is not None:
            kmin, kmax = self.config.get_klimits_for_array(diameter)
            self.controller.kmin = kmin
            self.controller.kmax = kmax
            self.controller.show_k_guides = True
            try:
                self.controller._draw_k_guides()
                self.controller._update_legend()
                self.controller.fig.canvas.draw_idle()
            except Exception:
                pass

    def add_klimits_display(self, diameter: int) -> None:
        """Add k-limits display for specified array diameter."""
        diameters = self.config.get_array_diameters()
        if diameter not in diameters:
            raise ValueError(f"Array {diameter}m not in config")
        
        if diameter not in self._active_klimits:
            self._active_klimits.append(diameter)
        
        self._update_klimits_display()

    def remove_klimits_display(self, diameter: int) -> None:
        """Remove k-limits display for specified array diameter."""
        if diameter in self._active_klimits:
            self._active_klimits.remove(diameter)
        
        self._update_klimits_display()

    def _update_klimits_display(self) -> None:
        """Update controller to display all active k-limits."""
        if self.controller is None:
            return
        
        if not self._active_klimits:
            self.controller.show_k_guides = False
            self.controller._multi_klimits = []
        else:
            self.controller.show_k_guides = True
            klimits_list = []
            for diameter in self._active_klimits:
                kmin, kmax = self.config.get_klimits_for_array(diameter)
                klimits_list.append((diameter, kmin, kmax))
            self.controller._multi_klimits = klimits_list
            if klimits_list:
                self.controller.kmin = klimits_list[0][1]
                self.controller.kmax = klimits_list[0][2]
        
        try:
            self.controller._draw_k_guides()
            self.controller._update_legend()
            self.controller.fig.canvas.draw_idle()
        except Exception:
            pass

    def get_state_dict(self) -> Dict[str, Any]:
        """Build complete state dictionary for persistence."""
        if self.controller is None:
            raise RuntimeError("No controller attached")
        
        c = self.controller
        
        velocity_arrays = []
        frequency_arrays = []
        wavelength_arrays = []
        labels = []
        
        if hasattr(c, 'layers_model') and c.layers_model is not None:
            for layer in c.layers_model.layers:
                velocity_arrays.append(np.array(layer.velocity))
                frequency_arrays.append(np.array(layer.frequency))
                wavelength_arrays.append(np.array(layer.wavelength))
                labels.append(layer.label)
        else:
            for i, (vel, freq, wave) in enumerate(zip(c.velocity_arrays, c.frequency_arrays, c.wavelength_arrays)):
                velocity_arrays.append(np.array(vel))
                frequency_arrays.append(np.array(freq))
                wavelength_arrays.append(np.array(wave))
                labels.append(c.offset_labels[i] if i < len(c.offset_labels) else f"Layer {i+1}")
        
        return {
            'workflow_config': self.config.to_dict(),
            'velocity_arrays': velocity_arrays,
            'frequency_arrays': frequency_arrays,
            'wavelength_arrays': wavelength_arrays,
            'set_leg': labels,
            'focused_array_idx': self._focused_array_idx,
            'kmin': getattr(c, 'kmin', None),
            'kmax': getattr(c, 'kmax', None),
            'show_k_guides': getattr(c, 'show_k_guides', False),
        }

    def save_current_stage(self) -> Path:
        """Save current state to .pkl file for current stage."""
        state = self.get_state_dict()
        pkl_path = self.config.get_state_path(self.current_stage)
        save_session(state, str(pkl_path))
        return pkl_path

    def export_current_stage_mat(self) -> Path:
        """Export current stage data to .mat file."""
        if self.controller is None:
            raise RuntimeError("No controller attached")
        
        c = self.controller
        
        velocity_arrays = []
        frequency_arrays = []
        wavelength_arrays = []
        labels = []
        
        if hasattr(c, 'layers_model') and c.layers_model is not None:
            for layer in c.layers_model.layers:
                velocity_arrays.append(np.array(layer.velocity))
                frequency_arrays.append(np.array(layer.frequency))
                wavelength_arrays.append(np.array(layer.wavelength))
                labels.append(layer.label)
        else:
            for i, (vel, freq, wave) in enumerate(zip(c.velocity_arrays, c.frequency_arrays, c.wavelength_arrays)):
                velocity_arrays.append(np.array(vel))
                frequency_arrays.append(np.array(freq))
                wavelength_arrays.append(np.array(wave))
                labels.append(c.offset_labels[i] if i < len(c.offset_labels) else f"Layer {i+1}")
        
        mat_path = self.config.get_mat_path(self.current_stage)
        export_stage_to_mat(
            velocity_arrays,
            frequency_arrays,
            wavelength_arrays,
            labels,
            mat_path,
            self.config.site_name,
            self.current_stage.display_name,
            wave_type=self.config.wave_type,
        )
        return mat_path

    def complete_stage(self) -> tuple:
        """Save current stage (pkl + mat). Returns (pkl_path, mat_path)."""
        pkl_path = self.save_current_stage()
        mat_path = self.export_current_stage_mat()
        return pkl_path, mat_path

    def can_advance(self) -> bool:
        """Check if can advance to next stage."""
        return not self.is_last_stage

    def can_go_back(self) -> bool:
        """Check if can go back to previous stage."""
        return not self.is_first_stage

    def advance_stage(self) -> Optional[Stage]:
        """Advance to next stage. Returns new stage or None if at end."""
        next_stage = self.current_stage.next()
        if next_stage is None:
            return None
        
        self.config.current_stage = next_stage
        return next_stage

    def retreat_stage(self) -> Optional[Stage]:
        """Go back to previous stage. Returns previous stage or None if at start."""
        prev_stage = self.current_stage.prev()
        if prev_stage is None:
            return None
        
        self.config.current_stage = prev_stage
        return prev_stage

    def get_previous_stage_path(self) -> Optional[Path]:
        """Get path to previous stage's state file."""
        prev_stage = self.current_stage.prev()
        if prev_stage is None:
            return None
        return self.config.get_state_path(prev_stage)

    def get_next_stage_path(self) -> Optional[Path]:
        """Get path to next stage's state file (may not exist yet)."""
        next_stage = self.current_stage.next()
        if next_stage is None:
            return None
        return self.config.get_state_path(next_stage)

    def export_final_dinver(self) -> Path:
        """Export final dinver-compatible txt file from refined stage."""
        if self.controller is None:
            raise RuntimeError("No controller attached")
        
        c = self.controller
        
        all_freq = []
        all_vel = []
        
        if hasattr(c, 'layers_model') and c.layers_model is not None:
            for layer in c.layers_model.layers:
                all_freq.extend(layer.frequency)
                all_vel.extend(layer.velocity)
        else:
            for freq, vel in zip(c.frequency_arrays, c.velocity_arrays):
                all_freq.extend(freq)
                all_vel.extend(vel)
        
        freq_arr = np.array(all_freq)
        vel_arr = np.array(all_vel)
        slow_arr = 1000.0 / vel_arr
        
        mask = np.isfinite(freq_arr) & np.isfinite(slow_arr) & (freq_arr > 0)
        freq_arr = freq_arr[mask]
        slow_arr = slow_arr[mask]
        
        sort_idx = np.argsort(freq_arr)
        freq_sorted = freq_arr[sort_idx]
        slow_sorted = slow_arr[sort_idx]
        
        n_bins = min(100, len(freq_sorted) // 5) if len(freq_sorted) > 10 else len(freq_sorted)
        if n_bins < 2:
            n_bins = len(freq_sorted)
        
        if n_bins > 0 and len(freq_sorted) > n_bins:
            bins = np.linspace(freq_sorted.min(), freq_sorted.max(), n_bins + 1)
            bin_idx = np.digitize(freq_sorted, bins) - 1
            bin_idx = np.clip(bin_idx, 0, n_bins - 1)
            
            freq_mean = np.zeros(n_bins)
            slow_mean = np.zeros(n_bins)
            slow_std = np.zeros(n_bins)
            num_pts = np.zeros(n_bins, dtype=int)
            
            for i in range(n_bins):
                in_bin = bin_idx == i
                if np.any(in_bin):
                    freq_mean[i] = np.mean(freq_sorted[in_bin])
                    slow_mean[i] = np.mean(slow_sorted[in_bin])
                    slow_std[i] = np.std(slow_sorted[in_bin]) if np.sum(in_bin) > 1 else 0.0
                    num_pts[i] = np.sum(in_bin)
            
            valid = num_pts > 0
            freq_mean = freq_mean[valid]
            slow_mean = slow_mean[valid]
            slow_std = slow_std[valid]
            num_pts = num_pts[valid]
        else:
            freq_mean = freq_sorted
            slow_mean = slow_sorted
            slow_std = np.zeros_like(slow_sorted)
            num_pts = np.ones(len(freq_sorted), dtype=int)
        
        dinver_path = self.config.get_dinver_path()
        export_dinver_txt(freq_mean, slow_mean, slow_std, num_pts, dinver_path)
        return dinver_path

    def get_status_summary(self) -> str:
        """Get human-readable status summary."""
        return (
            f"Site: {self.config.site_name}\n"
            f"Stage: {self.current_stage.display_name} ({self.stage_number}/{self.total_stages})\n"
            f"Output: {self.config.output_dir}\n"
            f"Wave Type: {self.config.wave_type}"
        )
