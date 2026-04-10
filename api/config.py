"""Configuration dataclasses for DC Cut API operations.

All tunable parameters live here. Master config composes sub-configs.
JSON serialization via dataclasses.asdict() / config_from_dict().
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple, Dict, Any


@dataclass
class DataLoadConfig:
    """Configuration for loading dispersion data files."""
    file_path: str = ""
    file_type: str = "auto"  # "auto", "matlab", "csv", "state", "max"
    freq_column: Optional[str] = None
    velocity_column: Optional[str] = None
    wavelength_column: Optional[str] = None
    slowness_column: Optional[str] = None
    receiver_dx: float = 2.0
    n_phones: int = 24


@dataclass
class FilterConfig:
    """Configuration for data filtering operations."""
    velocity_min: Optional[float] = None
    velocity_max: Optional[float] = None
    frequency_min: Optional[float] = None
    frequency_max: Optional[float] = None
    wavelength_min: Optional[float] = None
    wavelength_max: Optional[float] = None
    nacd_threshold: Optional[float] = None


@dataclass
class AverageConfig:
    """Configuration for computing averages."""
    num_bins: int = 50
    log_bias: float = 0.7
    domain: str = "frequency"  # "frequency" or "wavelength"


@dataclass
class NearFieldConfig:
    """Configuration for near-field analysis."""
    threshold: float = 1.0
    n_phones: int = 24
    receiver_dx: float = 2.0


@dataclass
class ExportConfig:
    """Configuration for exporting data."""
    output_path: str = ""
    format: str = "geopsy_txt"  # "geopsy_txt", "csv_stats", "matlab"
    include_stats: bool = True


@dataclass
class ViewConfig:
    """Configuration for display/visualization."""
    view_mode: str = "both"  # "freq", "wave", "both"
    show_average: bool = True
    show_average_wave: bool = False
    show_k_guides: bool = False
    freq_tick_style: str = "decades"
    freq_custom_ticks: List[float] = field(default_factory=list)
    robust_lower_pct: float = 0.5
    robust_upper_pct: float = 99.5
    theme: str = "light"


@dataclass
class SessionConfig:
    """Master configuration composing all sub-configs."""
    data_load: DataLoadConfig = field(default_factory=DataLoadConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    average: AverageConfig = field(default_factory=AverageConfig)
    nearfield: NearFieldConfig = field(default_factory=NearFieldConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    view: ViewConfig = field(default_factory=ViewConfig)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionConfig:
        return cls(
            data_load=DataLoadConfig(**data.get("data_load", {})),
            filter=FilterConfig(**data.get("filter", {})),
            average=AverageConfig(**data.get("average", {})),
            nearfield=NearFieldConfig(**data.get("nearfield", {})),
            export=ExportConfig(**data.get("export", {})),
            view=ViewConfig(**data.get("view", {})),
        )
