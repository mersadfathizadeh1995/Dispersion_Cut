"""Wrapper for generating theoretical curves from Geopsy report files."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Callable

from dc_cut.packages.theoretical_curves.config import GenerationConfig, TheoreticalCurve
from dc_cut.packages.theoretical_curves.io import load_theoretical_csv


class TheoreticalCurveGenerator:
    """Generates theoretical dispersion curves using the extraction script.
    
    Wraps the extract_theoretical_curves.py script for programmatic use.
    """
    
    def __init__(self, config: GenerationConfig) -> None:
        """Initialize generator with configuration.
        
        Parameters
        ----------
        config : GenerationConfig
            Generation configuration
        """
        self.config = config
    
    def generate(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[TheoreticalCurve]:
        """Generate theoretical curves from the configured report file.
        
        Parameters
        ----------
        progress_callback : callable, optional
            Function to call with progress messages
        
        Returns
        -------
        List[TheoreticalCurve]
            Generated curves loaded from output CSV files
        
        Raises
        ------
        FileNotFoundError
            If report file doesn't exist
        RuntimeError
            If generation fails
        """
        config = self.config
        
        if not Path(config.report_file).exists():
            raise FileNotFoundError(f"Report file not found: {config.report_file}")
        
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        script_path = Path(__file__).parent / "extract_theoretical_curves.py"
        if not script_path.exists():
            raise FileNotFoundError(f"Extraction script not found: {script_path}")
        
        cmd = [
            sys.executable,
            str(script_path),
            "--report", str(config.report_file),
            "--output", str(config.output_dir),
            "--geopsy-bin", str(config.geopsy_bin),
            "--git-bash", str(config.git_bash),
            "--mode", config.selection_mode,
            "--curve-type", config.curve_type,
            "--freq-min", str(config.freq_min),
            "--freq-max", str(config.freq_max),
            "--freq-points", str(config.freq_points),
            "--site-name", config.site_name,
            "--lower-pct", str(config.lower_percentile),
            "--upper-pct", str(config.upper_percentile),
        ]
        
        if config.selection_mode == "best":
            cmd.extend(["--n-profiles", str(config.n_best_profiles)])
        else:
            cmd.extend(["--misfit-max", str(config.misfit_max)])
            cmd.extend(["--max-profiles", str(config.max_profiles)])
        
        if config.curve_type in ("Rayleigh", "Both"):
            cmd.extend(["--ray-modes", str(config.num_modes)])
        if config.curve_type in ("Love", "Both"):
            cmd.extend(["--love-modes", str(config.num_modes)])
        
        if config.num_modes > 1:
            cmd.append("--separate-modes")
        
        if progress_callback:
            progress_callback(f"Running extraction: {config.curve_type}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,
            )
            
            if result.returncode != 0:
                error_msg = result.stderr[:500] if result.stderr else "Unknown error"
                raise RuntimeError(f"Extraction failed: {error_msg}")
            
            if progress_callback:
                progress_callback("Loading generated curves...")
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Extraction timed out (30 minutes)")
        
        curves = self._load_output_files(output_dir, config.site_name, config.curve_type)
        
        if progress_callback:
            progress_callback(f"Loaded {len(curves)} curves")
        
        return curves
    
    def _load_output_files(
        self,
        output_dir: Path,
        site_name: str,
        curve_type: str,
    ) -> List[TheoreticalCurve]:
        """Load generated CSV files from output directory.
        
        When separate_modes is enabled, loads only the mode-specific files
        to avoid duplicates with the combined statistics file.
        """
        curves = []
        config = self.config
        
        wave_types = []
        if curve_type in ("Rayleigh", "Both"):
            wave_types.append("Rayleigh")
        if curve_type in ("Love", "Both"):
            wave_types.append("Love")
        
        for wave_type in wave_types:
            if config.num_modes > 1:
                # Load mode-specific files only (avoid duplicates from combined file)
                for mode in range(config.num_modes):
                    mode_file = output_dir / f"{site_name}_{wave_type}_mode{mode}_statistics.csv"
                    if mode_file.exists():
                        try:
                            loaded = load_theoretical_csv(str(mode_file))
                            curves.extend(loaded)
                        except Exception as e:
                            print(f"Warning: Failed to load {mode_file}: {e}")
            else:
                # Single mode - load combined statistics file
                stats_file = output_dir / f"{site_name}_{wave_type}_statistics.csv"
                if stats_file.exists():
                    try:
                        loaded = load_theoretical_csv(str(stats_file))
                        curves.extend(loaded)
                    except Exception as e:
                        print(f"Warning: Failed to load {stats_file}: {e}")
        
        return curves


def validate_geopsy_installation(geopsy_bin: str) -> bool:
    """Check if Geopsy tools are available.
    
    Parameters
    ----------
    geopsy_bin : str
        Path to Geopsy bin directory
    
    Returns
    -------
    bool
        True if gpdc and gpdcreport executables exist
    """
    bin_path = Path(geopsy_bin)
    
    gpdc = bin_path / "gpdc.exe"
    gpdcreport = bin_path / "gpdcreport.exe"
    
    if not gpdc.exists():
        gpdc = bin_path / "gpdc"
    if not gpdcreport.exists():
        gpdcreport = bin_path / "gpdcreport"
    
    return gpdc.exists() and gpdcreport.exists()
