"""Configuration dataclass and constants for publication figures.

This module provides:
    - PlotConfig: Comprehensive configuration dataclass
    - COLORBLIND_PALETTES: Accessibility-compliant color schemes
    - DEFAULT_FONT_SIZES: Standard typography settings
    - JOURNAL_PRESETS: Presets for common publication formats
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
import numpy as np

# ============================================================================
# Colorblind-Friendly Palettes
# ============================================================================

COLORBLIND_PALETTES = {
    'vibrant': [
        '#EE7733',  # Orange
        '#0077BB',  # Blue
        '#33BBEE',  # Cyan
        '#EE3377',  # Magenta
        '#CC3311',  # Red
        '#009988',  # Teal
        '#BBBBBB',  # Grey
    ],
    'muted': [
        '#CC6677',  # Rose
        '#332288',  # Indigo
        '#DDCC77',  # Sand
        '#117733',  # Green
        '#88CCEE',  # Cyan
        '#882255',  # Wine
        '#44AA99',  # Teal
        '#999933',  # Olive
    ],
    'bright': [
        '#4477AA',  # Blue
        '#EE6677',  # Red
        '#228833',  # Green
        '#CCBB44',  # Yellow
        '#66CCEE',  # Cyan
        '#AA3377',  # Purple
        '#BBBBBB',  # Grey
    ],
    'high_contrast': [
        '#000000',  # Black
        '#0077BB',  # Blue
        '#33BBEE',  # Cyan
        '#009988',  # Teal
        '#EE7733',  # Orange
        '#CC3311',  # Red
        '#EE3377',  # Magenta
    ],
}

# ============================================================================
# Default Font Sizes
# ============================================================================

DEFAULT_FONT_SIZES = {
    'title': 14,
    'axis_label': 12,
    'tick_label': 10,
    'legend': 10,
    'annotation': 9,
}

# ============================================================================
# Journal Presets
# ============================================================================

JOURNAL_PRESETS = {
    'nature': {
        'figsize': (89/25.4, 89/25.4),  # 89mm single column
        'dpi': 300,
        'font_family': 'Arial',
        'font_sizes': {'title': 8, 'axis_label': 7, 'tick_label': 6, 'legend': 6},
    },
    'agu': {
        'figsize': (95/25.4, 115/25.4),  # AGU single column
        'dpi': 300,
        'font_family': 'Helvetica',
        'font_sizes': {'title': 10, 'axis_label': 9, 'tick_label': 8, 'legend': 8},
    },
    'geophysics': {
        'figsize': (3.5, 4.0),  # Geophysics column width
        'dpi': 600,
        'font_family': 'Arial',
        'font_sizes': {'title': 10, 'axis_label': 9, 'tick_label': 8, 'legend': 8},
    },
    'presentation': {
        'figsize': (10, 7.5),
        'dpi': 150,
        'font_family': 'Arial',
        'font_sizes': {'title': 16, 'axis_label': 14, 'tick_label': 12, 'legend': 12},
    },
    'poster': {
        'figsize': (12, 9),
        'dpi': 150,
        'font_family': 'Arial',
        'font_sizes': {'title': 20, 'axis_label': 18, 'tick_label': 16, 'legend': 14},
    },
}


# ============================================================================
# PlotConfig Dataclass
# ============================================================================

@dataclass
class PlotConfig:
    """Comprehensive configuration for publication-quality figures.
    
    Attributes:
        figsize: Figure dimensions (width, height) in inches
        dpi: Resolution in dots per inch
        color_palette: Name of colorblind-friendly palette or custom list
        font_family: Font family for text elements
        font_sizes: Dictionary of font sizes for different elements
        line_width: Default line width for curves
        marker_size: Default marker size
        grid_style: Grid line style ('major', 'minor', 'both', 'none')
        grid_alpha: Grid transparency
        spine_width: Axis spine width
        tick_direction: Tick direction ('in', 'out', 'inout')
        legend_position: Legend location
        legend_frameon: Whether legend has frame
        colorbar_label: Label for colorbar (if applicable)
        title: Figure title (optional)
        x_label: X-axis label
        y_label: Y-axis label
        x_limits: X-axis limits (min, max) or None for auto
        y_limits: Y-axis limits (min, max) or None for auto
        invert_y: Whether to invert Y-axis (common for wavelength)
        log_x: Logarithmic X-axis
        log_y: Logarithmic Y-axis
        tight_layout: Apply tight layout
        pad_inches: Padding when saving
        transparent: Transparent background
        journal_preset: Apply a journal preset (overrides other settings)
    """
    
    # Figure dimensions
    figsize: Tuple[float, float] = (8, 6)
    dpi: int = 300
    
    # Colors
    color_palette: str = 'vibrant'
    custom_colors: Optional[List[str]] = None
    
    # Typography
    font_family: str = 'sans-serif'
    font_sizes: Dict[str, int] = field(default_factory=lambda: DEFAULT_FONT_SIZES.copy())
    
    # Lines and markers
    line_width: float = 1.5
    marker_size: float = 6.0
    marker_style: str = 'o'
    
    # Grid
    grid_style: str = 'major'  # 'major', 'minor', 'both', 'none'
    grid_alpha: float = 0.3
    grid_color: str = '#808080'
    
    # Axes
    spine_width: float = 1.0
    tick_direction: str = 'out'
    tick_width: float = 1.0
    tick_length: float = 4.0
    
    # Legend
    legend_position: str = 'best'
    legend_frameon: bool = False
    legend_ncol: int = 1
    
    # Labels
    title: Optional[str] = None
    x_label: str = 'Velocity (m/s)'
    y_label: str = 'Wavelength (m)'
    colorbar_label: str = 'Offset (m)'
    
    # Limits
    x_limits: Optional[Tuple[float, float]] = None
    y_limits: Optional[Tuple[float, float]] = None
    
    # Axis options
    invert_y: bool = True  # Standard for wavelength plots
    log_x: bool = False
    log_y: bool = False
    
    # Output options
    tight_layout: bool = True
    pad_inches: float = 0.1
    transparent: bool = False
    
    # Preset
    journal_preset: Optional[str] = None
    
    def __post_init__(self):
        """Apply journal preset if specified."""
        if self.journal_preset and self.journal_preset in JOURNAL_PRESETS:
            preset = JOURNAL_PRESETS[self.journal_preset]
            self.figsize = preset.get('figsize', self.figsize)
            self.dpi = preset.get('dpi', self.dpi)
            self.font_family = preset.get('font_family', self.font_family)
            if 'font_sizes' in preset:
                self.font_sizes.update(preset['font_sizes'])
    
    def get_colors(self, n: int = None) -> List[str]:
        """Get color list from palette.
        
        Args:
            n: Number of colors needed. If None, returns all.
            
        Returns:
            List of hex color strings
        """
        if self.custom_colors:
            colors = self.custom_colors
        elif self.color_palette in COLORBLIND_PALETTES:
            colors = COLORBLIND_PALETTES[self.color_palette]
        else:
            colors = COLORBLIND_PALETTES['vibrant']
        
        if n is None:
            return colors
        
        # Cycle colors if needed
        if n <= len(colors):
            return colors[:n]
        else:
            return [colors[i % len(colors)] for i in range(n)]
    
    def apply_to_axes(self, ax, include_labels: bool = True):
        """Apply configuration to matplotlib Axes.
        
        Args:
            ax: Matplotlib Axes object
            include_labels: Whether to apply title and axis labels
        """
        import matplotlib.pyplot as plt
        
        # Grid
        if self.grid_style == 'none':
            ax.grid(False)
        else:
            ax.grid(True, which=self.grid_style if self.grid_style in ['major', 'minor', 'both'] else 'major',
                   alpha=self.grid_alpha, color=self.grid_color)
        
        # Spines
        for spine in ax.spines.values():
            spine.set_linewidth(self.spine_width)
        
        # Ticks
        ax.tick_params(direction=self.tick_direction, 
                      width=self.tick_width,
                      length=self.tick_length,
                      labelsize=self.font_sizes.get('tick_label', 10))
        
        # Labels
        if include_labels:
            if self.title:
                ax.set_title(self.title, fontsize=self.font_sizes.get('title', 14),
                           fontfamily=self.font_family)
            ax.set_xlabel(self.x_label, fontsize=self.font_sizes.get('axis_label', 12),
                         fontfamily=self.font_family)
            ax.set_ylabel(self.y_label, fontsize=self.font_sizes.get('axis_label', 12),
                         fontfamily=self.font_family)
        
        # Limits
        if self.x_limits:
            ax.set_xlim(self.x_limits)
        if self.y_limits:
            ax.set_ylim(self.y_limits)
        
        # Axis options
        if self.invert_y and not ax.yaxis_inverted():
            ax.invert_yaxis()
        if self.log_x:
            ax.set_xscale('log')
        if self.log_y:
            ax.set_yscale('log')
    
    def create_figure(self):
        """Create a new figure with this configuration.
        
        Returns:
            Tuple of (fig, ax) matplotlib objects
        """
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        
        # Apply font settings globally for this figure
        plt.rcParams['font.family'] = self.font_family
        
        return fig, ax
    
    def save_figure(self, fig, output_path: str):
        """Save figure with configuration settings.
        
        Args:
            fig: Matplotlib figure
            output_path: Output file path
        """
        if self.tight_layout:
            fig.tight_layout()
        
        fig.savefig(output_path, 
                   dpi=self.dpi,
                   bbox_inches='tight',
                   pad_inches=self.pad_inches,
                   transparent=self.transparent)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            'figsize': self.figsize,
            'dpi': self.dpi,
            'color_palette': self.color_palette,
            'font_family': self.font_family,
            'font_sizes': self.font_sizes,
            'line_width': self.line_width,
            'marker_size': self.marker_size,
            'grid_style': self.grid_style,
            'invert_y': self.invert_y,
            'journal_preset': self.journal_preset,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlotConfig':
        """Create config from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def for_journal(cls, journal: str) -> 'PlotConfig':
        """Create config for a specific journal.
        
        Args:
            journal: Journal name ('nature', 'agu', 'geophysics', etc.)
            
        Returns:
            PlotConfig with journal-appropriate settings
        """
        if journal not in JOURNAL_PRESETS:
            raise ValueError(f"Unknown journal: {journal}. "
                           f"Available: {list(JOURNAL_PRESETS.keys())}")
        return cls(journal_preset=journal)
