"""
Theoretical Dispersion Curve Extractor with Statistics

Standalone script to extract theoretical dispersion curves from a Geopsy .report file
and compute statistics (median, percentiles) for the gray shaded area in figures.

Usage:
    python extract_theoretical_curves.py --report path/to/run.report --output output_dir \\
        --geopsy-bin /path/to/Geopsy.org/bin --git-bash "C:/Program Files/Git/bin/bash.exe" \\
        --mode best --n-profiles 1000 --curve-type Rayleigh

Author: Figure Automation Project
"""

import argparse
import logging
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ExtractionConfig:
    """Configuration for theoretical curve extraction."""
    
    report_file: Path
    output_dir: Path
    geopsy_bin: Path
    git_bash_exe: Optional[Path]
    
    # Selection mode: "best" or "misfit"
    selection_mode: str = "best"
    
    # For "best" mode: number of best profiles to extract
    n_best_profiles: int = 1000
    
    # For "misfit" mode: maximum misfit value and max profiles
    misfit_max: float = 1.0
    n_max_profiles: int = 10000
    
    # Curve type: "Rayleigh", "Love", or "Both"
    curve_type: str = "Rayleigh"
    
    # Number of modes
    ray_num_modes: int = 1
    love_num_modes: int = 1
    
    # Frequency range
    freq_min: float = 1.0
    freq_max: float = 50.0
    n_freq_points: int = 200
    
    # Site name for output files
    site_name: str = "Site"
    
    # Percentiles for uncertainty band
    lower_percentile: float = 16.0
    upper_percentile: float = 84.0
    
    # Mode output options
    separate_modes: bool = False
    modes_to_include: Optional[List[int]] = None


# =============================================================================
# Geopsy Tools
# =============================================================================

class GeopsyRunner:
    """Runs Geopsy command-line tools."""
    
    def __init__(self, geopsy_bin: Path, git_bash_exe: Optional[Path] = None):
        self.geopsy_bin = geopsy_bin
        self.git_bash_exe = git_bash_exe
        self.is_windows = platform.system() == "Windows"
    
    def to_bash_path(self, win_path: Path) -> str:
        """Convert Windows path to Git Bash compatible path."""
        if not self.is_windows:
            return str(win_path)
        p = win_path.resolve()
        return f"/{p.drive[0].lower()}{p.as_posix()[2:]}"
    
    def build_env_prefix(self) -> str:
        """Build PATH environment prefix."""
        if self.is_windows:
            bash_path = self.to_bash_path(self.geopsy_bin)
            return f'export PATH="{bash_path}:$PATH" && '
        else:
            return f'export PATH="{self.geopsy_bin}:$PATH" && '
    
    def run_command(self, command: str, timeout: int = 600) -> subprocess.CompletedProcess:
        """Run a Geopsy command via bash."""
        env_prefix = self.build_env_prefix()
        
        if not self.is_windows:
            lib_path = self.geopsy_bin.parent / "lib"
            if lib_path.exists():
                env_prefix += f'export LD_LIBRARY_PATH="{lib_path}:$LD_LIBRARY_PATH" && '
        
        full_command = env_prefix + command
        logger.debug(f"Running: {command}")
        
        if self.is_windows and self.git_bash_exe:
            result = subprocess.run(
                [str(self.git_bash_exe), "-c", full_command],
                capture_output=True,
                text=True,
                timeout=timeout
            )
        else:
            result = subprocess.run(
                ["bash", "-c", full_command],
                capture_output=True,
                text=True,
                timeout=timeout
            )
        
        return result


# =============================================================================
# Curve Extraction
# =============================================================================

def extract_theoretical_curves(config: ExtractionConfig) -> Dict[str, Path]:
    """
    Extract theoretical dispersion curves from report file.
    
    Returns:
        Dict mapping curve type ("rayleigh", "love") to output file path.
    """
    runner = GeopsyRunner(config.geopsy_bin, config.git_bash_exe)
    
    if not config.report_file.exists():
        raise FileNotFoundError(f"Report file not found: {config.report_file}")
    
    config.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build gpdcreport command
    report_bash = runner.to_bash_path(config.report_file)
    
    if config.selection_mode == "best":
        gpdcreport_cmd = f"gpdcreport -best {config.n_best_profiles} {report_bash}"
        logger.info(f"Selection: {config.n_best_profiles} best profiles")
    elif config.selection_mode == "misfit":
        gpdcreport_cmd = f"gpdcreport -m {config.misfit_max} -n {config.n_max_profiles} {report_bash}"
        logger.info(f"Selection: misfit <= {config.misfit_max}, max {config.n_max_profiles} profiles")
    else:
        raise ValueError(f"Invalid selection_mode: {config.selection_mode}")
    
    # Determine curves to extract
    curve_specs = []
    if config.curve_type in ("Rayleigh", "Both"):
        curve_specs.append(("Ray", config.ray_num_modes, 0))
    if config.curve_type in ("Love", "Both"):
        curve_specs.append(("Love", 0, config.love_num_modes))
    
    output_files = {}
    
    for curve_name, ray_modes, love_modes in curve_specs:
        logger.info(f"Extracting {curve_name} dispersion curves...")
        
        # Build gpdc command
        gpdc_cmd = (
            f"gpdc -R {ray_modes} -L {love_modes} "
            f"-min {config.freq_min} -max {config.freq_max} -n {config.n_freq_points}"
        )
        
        output_file = config.output_dir / f"{config.site_name}_DC_{curve_name}.txt"
        output_bash = runner.to_bash_path(output_file)
        
        full_command = f"{gpdcreport_cmd} | {gpdc_cmd} > '{output_bash}'"
        
        result = runner.run_command(full_command, timeout=900)
        
        if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
            logger.info(f"  ✓ Created: {output_file.name}")
            output_files[curve_name.lower()] = output_file
        else:
            logger.error(f"  ✗ Failed to extract {curve_name}")
            if result.stderr:
                logger.error(f"    Error: {result.stderr[:500]}")
    
    return output_files


# =============================================================================
# Parsing
# =============================================================================

def parse_theoretical_file(filepath: Path, wave_type: str, site_name: str) -> pd.DataFrame:
    """
    Parse theoretical dispersion curve file.
    
    File format:
        # Mode 0
        freq   slowness
        ...
        # Mode 1
        freq   slowness
        ...
        # Mode 0  <- new profile starts
        ...
    
    Returns:
        DataFrame with columns: site, wave_type, profile, mode, freq_Hz, phase_velocity_mps
    """
    MODE_RE = re.compile(r"#\s*Mode\s+(\d+)", re.I)
    FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
    
    rows = []
    profile = -1
    mode = None
    
    with open(filepath, 'r', errors='ignore') as fh:
        for line in fh:
            line = line.strip()
            
            m_mode = MODE_RE.match(line)
            if m_mode:
                mode_tag = int(m_mode.group(1))
                if mode_tag == 0:
                    profile += 1
                mode = mode_tag
                continue
            
            nums = FLOAT_RE.findall(line)
            if len(nums) >= 2 and mode is not None and profile >= 0:
                f_Hz = float(nums[0])
                s_s_m = float(nums[1])
                v_mps = 1.0 / s_s_m
                
                rows.append({
                    'site': site_name,
                    'wave_type': wave_type,
                    'profile': profile,
                    'mode': mode,
                    'freq_Hz': f_Hz,
                    'phase_velocity_mps': v_mps,
                })
    
    if not rows:
        raise ValueError(f"No dispersion curves found in {filepath.name}")
    
    df = pd.DataFrame(rows)
    n_profiles = df['profile'].nunique()
    n_modes = df['mode'].nunique()
    logger.info(f"  Parsed: {n_profiles} profiles, {n_modes} modes, {len(df)} points")
    
    return df


# =============================================================================
# Statistics Computation
# =============================================================================

def compute_statistics(
    df: pd.DataFrame,
    lower_pct: float = 16.0,
    upper_pct: float = 84.0,
    freq_min: float = None,
    freq_max: float = None,
    min_count: int = 10
) -> pd.DataFrame:
    """
    Compute statistics (median, percentiles) for theoretical curves.
    
    Groups by frequency and mode, computes statistics across profiles.
    
    Args:
        df: Input DataFrame with freq_Hz, mode, phase_velocity_mps columns
        lower_pct: Lower percentile (default: 16)
        upper_pct: Upper percentile (default: 84)
        freq_min: Minimum frequency to include (filter out lower)
        freq_max: Maximum frequency to include (filter out higher)
        min_count: Minimum number of profiles at a frequency to include (default: 10)
    
    Returns:
        DataFrame with columns: freq_Hz, mode, median, lower, upper, std, count
    """
    df = df.copy()
    
    # Filter by frequency range if specified
    if freq_min is not None:
        df = df[df['freq_Hz'] >= freq_min]
    if freq_max is not None:
        df = df[df['freq_Hz'] <= freq_max]
    
    # Round frequency to handle floating point differences
    df['freq_rounded'] = df['freq_Hz'].round(6)
    
    stats_rows = []
    
    for mode in sorted(df['mode'].unique()):
        mode_df = df[df['mode'] == mode]
        
        for freq in sorted(mode_df['freq_rounded'].unique()):
            freq_df = mode_df[mode_df['freq_rounded'] == freq]
            velocities = freq_df['phase_velocity_mps'].values
            
            # Skip frequencies with too few data points (likely parsing artifacts)
            if len(velocities) >= min_count:
                stats_rows.append({
                    'freq_Hz': freq,
                    'mode': mode,
                    'median': np.median(velocities),
                    'mean': np.mean(velocities),
                    'lower': np.percentile(velocities, lower_pct),
                    'upper': np.percentile(velocities, upper_pct),
                    'std': np.std(velocities),
                    'min': np.min(velocities),
                    'max': np.max(velocities),
                    'count': len(velocities),
                })
    
    stats_df = pd.DataFrame(stats_rows)
    stats_df = stats_df.sort_values(['mode', 'freq_Hz']).reset_index(drop=True)
    
    return stats_df


# =============================================================================
# Main Workflow
# =============================================================================

def run_extraction(config: ExtractionConfig) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Complete workflow: extract curves, parse, and compute statistics.
    
    Returns:
        Dict mapping curve type to (raw_df, stats_df) tuple.
    """
    logger.info("=" * 60)
    logger.info("THEORETICAL CURVE EXTRACTION WITH STATISTICS")
    logger.info("=" * 60)
    logger.info(f"Report: {config.report_file.name}")
    logger.info(f"Output: {config.output_dir}")
    logger.info(f"Curve type: {config.curve_type}")
    logger.info(f"Percentiles: {config.lower_percentile}th - {config.upper_percentile}th")
    logger.info("")
    
    # Step 1: Extract curves
    logger.info("Step 1: Extracting theoretical curves...")
    curve_files = extract_theoretical_curves(config)
    
    if not curve_files:
        raise RuntimeError("No curves were extracted")
    
    results = {}
    
    for curve_type, filepath in curve_files.items():
        wave_type = "Rayleigh" if curve_type in ("ray", "rayleigh") else "Love"
        
        # Step 2: Parse
        logger.info(f"\nStep 2: Parsing {wave_type} curves...")
        raw_df = parse_theoretical_file(filepath, wave_type, config.site_name)
        
        # Filter modes if requested
        available_modes = sorted(raw_df['mode'].unique())
        logger.info(f"  Available modes: {available_modes}")
        
        if config.modes_to_include is not None:
            raw_df = raw_df[raw_df['mode'].isin(config.modes_to_include)]
            logger.info(f"  Filtered to modes: {config.modes_to_include}")
        
        # Step 3: Compute statistics
        logger.info(f"Step 3: Computing statistics for {wave_type}...")
        
        if config.separate_modes:
            # Create separate files for each mode
            for mode in sorted(raw_df['mode'].unique()):
                mode_df = raw_df[raw_df['mode'] == mode]
                mode_stats = compute_statistics(
                    mode_df,
                    lower_pct=config.lower_percentile,
                    upper_pct=config.upper_percentile,
                    freq_min=config.freq_min,
                    freq_max=config.freq_max
                )
                
                mode_label = f"mode{mode}"
                raw_csv = config.output_dir / f"{config.site_name}_{wave_type}_{mode_label}_profiles.csv"
                stats_csv = config.output_dir / f"{config.site_name}_{wave_type}_{mode_label}_statistics.csv"
                
                mode_df.to_csv(raw_csv, index=False)
                mode_stats.to_csv(stats_csv, index=False)
                
                logger.info(f"  ✓ Mode {mode}: {raw_csv.name}, {stats_csv.name}")
            
            # Also save combined
            stats_df = compute_statistics(
                raw_df,
                lower_pct=config.lower_percentile,
                upper_pct=config.upper_percentile,
                freq_min=config.freq_min,
                freq_max=config.freq_max
            )
        else:
            stats_df = compute_statistics(
                raw_df,
                lower_pct=config.lower_percentile,
                upper_pct=config.upper_percentile,
                freq_min=config.freq_min,
                freq_max=config.freq_max
            )
        
        # Step 4: Save combined CSV files
        raw_csv = config.output_dir / f"{config.site_name}_{wave_type}_all_profiles.csv"
        stats_csv = config.output_dir / f"{config.site_name}_{wave_type}_statistics.csv"
        
        raw_df.to_csv(raw_csv, index=False)
        stats_df.to_csv(stats_csv, index=False)
        
        logger.info(f"  ✓ Saved: {raw_csv.name}")
        logger.info(f"  ✓ Saved: {stats_csv.name}")
        
        results[curve_type] = (raw_df, stats_df)
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("EXTRACTION COMPLETE")
    logger.info("=" * 60)
    
    return results


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract theoretical dispersion curves from Geopsy .report file and compute statistics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract 1000 best profiles (Rayleigh)
  python extract_theoretical_curves.py \\
      --report run_24.report \\
      --output ./output \\
      --geopsy-bin "C:/Program Files/Geopsy.org/bin" \\
      --git-bash "C:/Program Files/Git/bin/bash.exe" \\
      --mode best --n-profiles 1000

  # Extract profiles with misfit <= 0.5 (Both Rayleigh and Love)
  python extract_theoretical_curves.py \\
      --report run_24.report \\
      --output ./output \\
      --geopsy-bin "/usr/local/Geopsy.org/bin" \\
      --mode misfit --misfit-max 0.5 --curve-type Both

Output Files:
  - Site_Rayleigh_all_profiles.csv  : All individual profiles (raw data)
  - Site_Rayleigh_statistics.csv    : Statistics (median, percentiles, etc.)
  - Site_DC_Ray.txt                 : Raw gpdc output (intermediate)
"""
    )
    
    # Required arguments
    parser.add_argument(
        "--report", "-r",
        type=Path,
        required=True,
        help="Path to Geopsy .report file"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output directory for CSV files"
    )
    parser.add_argument(
        "--geopsy-bin", "-g",
        type=Path,
        required=True,
        help="Path to Geopsy bin directory (containing gpdc, gpdcreport)"
    )
    
    # Optional: Git Bash (Windows only)
    parser.add_argument(
        "--git-bash",
        type=Path,
        default=None,
        help="Path to Git Bash executable (Windows only, e.g., 'C:/Program Files/Git/bin/bash.exe')"
    )
    
    # Selection mode
    parser.add_argument(
        "--mode", "-m",
        choices=["best", "misfit"],
        default="best",
        help="Profile selection mode: 'best' (N best profiles) or 'misfit' (profiles with misfit <= threshold)"
    )
    parser.add_argument(
        "--n-profiles", "-n",
        type=int,
        default=1000,
        help="Number of best profiles to extract (for 'best' mode, default: 1000)"
    )
    parser.add_argument(
        "--misfit-max",
        type=float,
        default=1.0,
        help="Maximum misfit value (for 'misfit' mode, default: 1.0)"
    )
    parser.add_argument(
        "--max-profiles",
        type=int,
        default=10000,
        help="Maximum profiles to extract (for 'misfit' mode, default: 10000)"
    )
    
    # Curve type
    parser.add_argument(
        "--curve-type", "-c",
        choices=["Rayleigh", "Love", "Both"],
        default="Rayleigh",
        help="Type of dispersion curve to extract (default: Rayleigh)"
    )
    
    # Frequency range
    parser.add_argument(
        "--freq-min",
        type=float,
        default=1.0,
        help="Minimum frequency in Hz (default: 1.0)"
    )
    parser.add_argument(
        "--freq-max",
        type=float,
        default=50.0,
        help="Maximum frequency in Hz (default: 50.0)"
    )
    parser.add_argument(
        "--freq-points",
        type=int,
        default=200,
        help="Number of frequency points (default: 200)"
    )
    
    # Modes
    parser.add_argument(
        "--ray-modes",
        type=int,
        default=1,
        help="Number of Rayleigh modes to extract (default: 1). Use 2 for fundamental + 1st higher, 3 for +2nd higher, etc."
    )
    parser.add_argument(
        "--love-modes",
        type=int,
        default=1,
        help="Number of Love modes to extract (default: 1)"
    )
    parser.add_argument(
        "--separate-modes",
        action="store_true",
        help="Create separate CSV files for each mode (default: all modes in one file)"
    )
    parser.add_argument(
        "--modes-to-include",
        type=str,
        default=None,
        help="Comma-separated list of mode numbers to include in output (e.g., '0,1,2'). Default: all extracted modes."
    )
    
    # Statistics
    parser.add_argument(
        "--lower-pct",
        type=float,
        default=16.0,
        help="Lower percentile for uncertainty band (default: 16.0)"
    )
    parser.add_argument(
        "--upper-pct",
        type=float,
        default=84.0,
        help="Upper percentile for uncertainty band (default: 84.0)"
    )
    
    # Site name
    parser.add_argument(
        "--site-name", "-s",
        type=str,
        default="Site",
        help="Site name for output files (default: Site)"
    )
    
    # Verbosity
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug output"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Parse modes_to_include
    modes_to_include = None
    if args.modes_to_include:
        modes_to_include = [int(m.strip()) for m in args.modes_to_include.split(',')]
    
    # Build config
    config = ExtractionConfig(
        report_file=args.report.resolve(),
        output_dir=args.output.resolve(),
        geopsy_bin=args.geopsy_bin.resolve(),
        git_bash_exe=args.git_bash.resolve() if args.git_bash else None,
        selection_mode=args.mode,
        n_best_profiles=args.n_profiles,
        misfit_max=args.misfit_max,
        n_max_profiles=args.max_profiles,
        curve_type=args.curve_type,
        ray_num_modes=args.ray_modes,
        love_num_modes=args.love_modes,
        freq_min=args.freq_min,
        freq_max=args.freq_max,
        n_freq_points=args.freq_points,
        site_name=args.site_name,
        lower_percentile=args.lower_pct,
        upper_percentile=args.upper_pct,
        separate_modes=args.separate_modes,
        modes_to_include=modes_to_include,
    )
    
    try:
        results = run_extraction(config)
        
        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        for curve_type, (raw_df, stats_df) in results.items():
            n_profiles = raw_df['profile'].nunique()
            n_freqs = stats_df['freq_Hz'].nunique()
            print(f"\n{curve_type.upper()}:")
            print(f"  - Profiles extracted: {n_profiles}")
            print(f"  - Frequency points: {n_freqs}")
            print(f"  - Median velocity range: {stats_df['median'].min():.1f} - {stats_df['median'].max():.1f} m/s")
        
        return 0
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
