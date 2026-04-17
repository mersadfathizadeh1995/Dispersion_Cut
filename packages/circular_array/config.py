"""Configuration and enums for circular array workflow."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Tuple, Optional, List


class Stage(Enum):
    """Workflow stages for circular array processing."""
    INITIAL = auto()
    INTERMEDIATE = auto()
    REFINED = auto()

    def next(self) -> Optional[Stage]:
        """Get next stage or None if at end."""
        members = list(Stage)
        idx = members.index(self)
        return members[idx + 1] if idx < len(members) - 1 else None

    def prev(self) -> Optional[Stage]:
        """Get previous stage or None if at start."""
        members = list(Stage)
        idx = members.index(self)
        return members[idx - 1] if idx > 0 else None

    @property
    def display_name(self) -> str:
        """Human-readable stage name."""
        return self.name.capitalize()


@dataclass
class ArrayConfig:
    """Configuration for a single circular array."""
    diameter: int
    max_file_path: Path
    kmin: float
    kmax: float

    def __post_init__(self):
        self.max_file_path = Path(self.max_file_path)
        if self.kmin >= self.kmax:
            raise ValueError(f"kmin ({self.kmin}) must be less than kmax ({self.kmax})")


@dataclass
class WorkflowConfig:
    """Complete workflow configuration for circular array processing."""
    site_name: str
    output_dir: Path
    arrays: List[ArrayConfig]
    wave_type: str = "Rayleigh_Vertical"
    velocity_cutoff: float = 6000.0
    current_stage: Stage = field(default=Stage.INITIAL)

    def __post_init__(self):
        self.output_dir = Path(self.output_dir)
        if not self.site_name:
            raise ValueError("site_name cannot be empty")

    def get_klimits_for_array(self, diameter: int) -> Tuple[float, float]:
        """Get (kmin, kmax) for specific array diameter."""
        for arr in self.arrays:
            if arr.diameter == diameter:
                return (arr.kmin, arr.kmax)
        raise ValueError(f"No array with diameter {diameter}m")

    def get_array_diameters(self) -> List[int]:
        """Get list of array diameters in order."""
        return [arr.diameter for arr in self.arrays]

    def get_stage_filename(self, stage: Stage, extension: str) -> str:
        """Generate filename for a stage output."""
        stage_name = stage.display_name
        return f"{self.site_name}_{stage_name}.{extension}"

    def get_state_path(self, stage: Stage) -> Path:
        """Get full path for stage state file (.pkl)."""
        return self.output_dir / self.get_stage_filename(stage, "pkl")

    def get_mat_path(self, stage: Stage) -> Path:
        """Get full path for stage MAT file (.mat)."""
        return self.output_dir / self.get_stage_filename(stage, "mat")

    def get_dinver_path(self) -> Path:
        """Get path for final dinver export (.txt)."""
        return self.output_dir / f"{self.site_name}_dinver.txt"

    def to_dict(self) -> Dict:
        """Serialize config to dictionary for persistence."""
        return {
            'site_name': self.site_name,
            'output_dir': str(self.output_dir),
            'wave_type': self.wave_type,
            'velocity_cutoff': self.velocity_cutoff,
            'current_stage': self.current_stage.name,
            'arrays': [
                {
                    'diameter': arr.diameter,
                    'max_file_path': str(arr.max_file_path),
                    'kmin': arr.kmin,
                    'kmax': arr.kmax,
                }
                for arr in self.arrays
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> WorkflowConfig:
        """Deserialize config from dictionary."""
        arrays = [
            ArrayConfig(
                diameter=arr['diameter'],
                max_file_path=Path(arr['max_file_path']),
                kmin=arr['kmin'],
                kmax=arr['kmax'],
            )
            for arr in data['arrays']
        ]
        return cls(
            site_name=data['site_name'],
            output_dir=Path(data['output_dir']),
            arrays=arrays,
            wave_type=data.get('wave_type', 'Rayleigh_Vertical'),
            velocity_cutoff=data.get('velocity_cutoff', 6000.0),
            current_stage=Stage[data.get('current_stage', 'INITIAL')],
        )
