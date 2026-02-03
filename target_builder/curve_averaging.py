"""
Curve Averaging Module
======================

Implements Geopsy-compatible dispersion curve averaging.

Algorithm:
1. Collect union of all frequencies from input curves
2. For each frequency, interpolate slowness from curves that span it
3. Average the interpolated slowness values
4. Set stddev = original_stddev * sqrt(N) where N is number of contributing curves
5. Set weight = N
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
import tempfile
import os


@dataclass
class AveragedPoint:
    """Single point in averaged curve."""
    frequency: float
    slowness: float
    stddev: float
    weight: int
    

@dataclass  
class CurveForAveraging:
    """Curve data prepared for averaging."""
    frequencies: np.ndarray
    slowness: np.ndarray
    stddev: float  # Single stddev value (log-normalized)
    name: str
    
    @property
    def freq_min(self) -> float:
        return float(self.frequencies.min())
    
    @property
    def freq_max(self) -> float:
        return float(self.frequencies.max())
    
    def interpolate_slowness(self, freq: float) -> Optional[float]:
        """
        Interpolate slowness at given frequency using linear interpolation.
        Returns None if frequency is outside curve range.
        """
        if freq < self.freq_min or freq > self.freq_max:
            return None
        return float(np.interp(freq, self.frequencies, self.slowness))


def load_curve_for_averaging(filepath: str, stddev: float = 1.08, name: str = "") -> CurveForAveraging:
    """
    Load a dispersion curve file for averaging.
    
    Args:
        filepath: Path to dispersion curve file (freq, slowness, stddev, weight)
        stddev: Fixed stddev value to use (overrides file values)
        name: Name for the curve
        
    Returns:
        CurveForAveraging object
    """
    data = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                freq = float(parts[0])
                slowness = float(parts[1])
                data.append((freq, slowness))
    
    if not data:
        raise ValueError(f"No data found in {filepath}")
    
    data = sorted(data, key=lambda x: x[0])
    frequencies = np.array([d[0] for d in data])
    slowness = np.array([d[1] for d in data])
    
    return CurveForAveraging(
        frequencies=frequencies,
        slowness=slowness,
        stddev=stddev,
        name=name or os.path.basename(filepath)
    )


def average_curves_geopsy(
    curves: List[CurveForAveraging],
    output_stddev: Optional[float] = None
) -> List[AveragedPoint]:
    """
    Average dispersion curves using Geopsy methodology.
    
    Algorithm:
    1. Collect union of all frequencies
    2. For each frequency:
       - Find curves that span this frequency (freq_min <= f <= freq_max)
       - Interpolate slowness from each spanning curve
       - Average the slowness values
       - Set stddev = base_stddev * sqrt(N)
       - Set weight = N
    
    Args:
        curves: List of curves to average
        output_stddev: Base stddev for output (default: use first curve's stddev)
        
    Returns:
        List of AveragedPoint objects
    """
    if not curves:
        raise ValueError("No curves to average")
    
    if len(curves) == 1:
        # Single curve - just return as-is
        curve = curves[0]
        return [
            AveragedPoint(
                frequency=float(f),
                slowness=float(s),
                stddev=curve.stddev,
                weight=1
            )
            for f, s in zip(curve.frequencies, curve.slowness)
        ]
    
    # Use first curve's stddev as base if not specified
    base_stddev = output_stddev if output_stddev is not None else curves[0].stddev
    
    # Collect all unique frequencies from all curves
    all_freqs = set()
    for curve in curves:
        all_freqs.update(curve.frequencies.tolist())
    all_freqs = sorted(all_freqs)
    
    # Average at each frequency
    averaged_points = []
    for freq in all_freqs:
        slowness_values = []
        
        for curve in curves:
            # Check if this curve spans this frequency
            if curve.freq_min <= freq <= curve.freq_max:
                interpolated = curve.interpolate_slowness(freq)
                if interpolated is not None:
                    slowness_values.append(interpolated)
        
        if slowness_values:
            n = len(slowness_values)
            avg_slowness = np.mean(slowness_values)
            # Geopsy formula: stddev increases by sqrt(N)
            avg_stddev = base_stddev * np.sqrt(n)
            
            averaged_points.append(AveragedPoint(
                frequency=freq,
                slowness=avg_slowness,
                stddev=avg_stddev,
                weight=n
            ))
    
    return averaged_points


def save_averaged_curve(
    points: List[AveragedPoint],
    output_path: str,
    curve_names: Optional[List[str]] = None
) -> str:
    """
    Save averaged curve to file.
    
    Args:
        points: List of AveragedPoint objects
        output_path: Path to save file
        curve_names: Optional list of source curve names for header
        
    Returns:
        Path to saved file
    """
    with open(output_path, 'w') as f:
        f.write("# Averaged dispersion curve (Geopsy-compatible)\n")
        if curve_names:
            f.write(f"# Source curves: {', '.join(curve_names)}\n")
        f.write("# Frequency(Hz)  Slowness(s/m)  LogStd  Weight\n")
        
        for pt in points:
            f.write(f"{pt.frequency:.10f}  {pt.slowness:.16f}  {pt.stddev:.16f}  {pt.weight}\n")
    
    return output_path


def compare_with_geopsy(
    our_points: List[AveragedPoint],
    geopsy_file: str,
    tolerance: float = 1e-10
) -> Tuple[bool, str]:
    """
    Compare our averaged result with Geopsy output.
    
    Args:
        our_points: Our averaged points
        geopsy_file: Path to Geopsy averaged curve (from target file)
        tolerance: Tolerance for floating point comparison
        
    Returns:
        Tuple of (match_success, report_string)
    """
    # Load Geopsy curve
    geopsy_data = []
    with open(geopsy_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 3:
                freq = float(parts[0])
                slowness = float(parts[1])
                stddev = float(parts[2])
                weight = int(float(parts[3])) if len(parts) >= 4 else 1
                geopsy_data.append((freq, slowness, stddev, weight))
    
    report_lines = []
    report_lines.append(f"Comparing {len(our_points)} our points vs {len(geopsy_data)} Geopsy points")
    report_lines.append("")
    
    if len(our_points) != len(geopsy_data):
        report_lines.append(f"MISMATCH: Different number of points!")
        return False, "\n".join(report_lines)
    
    all_match = True
    mismatches = []
    
    for i, (our_pt, geopsy_pt) in enumerate(zip(our_points, geopsy_data)):
        g_freq, g_slow, g_std, g_weight = geopsy_pt
        
        freq_match = np.isclose(our_pt.frequency, g_freq, rtol=tolerance, atol=tolerance)
        slow_match = np.isclose(our_pt.slowness, g_slow, rtol=tolerance, atol=tolerance)
        std_match = np.isclose(our_pt.stddev, g_std, rtol=tolerance, atol=tolerance)
        weight_match = our_pt.weight == g_weight
        
        if not (freq_match and slow_match and std_match and weight_match):
            all_match = False
            mismatches.append({
                'index': i,
                'our': our_pt,
                'geopsy': geopsy_pt,
                'freq_match': freq_match,
                'slow_match': slow_match,
                'std_match': std_match,
                'weight_match': weight_match
            })
    
    if all_match:
        report_lines.append("✓ ALL POINTS MATCH 100%!")
        report_lines.append(f"  Frequency: MATCH")
        report_lines.append(f"  Slowness:  MATCH")
        report_lines.append(f"  StdDev:    MATCH")
        report_lines.append(f"  Weight:    MATCH")
    else:
        report_lines.append(f"✗ MISMATCHES FOUND: {len(mismatches)} points differ")
        for mm in mismatches[:10]:  # Show first 10 mismatches
            report_lines.append(f"\n  Point {mm['index']}:")
            report_lines.append(f"    Freq:   ours={mm['our'].frequency:.10f} vs geopsy={mm['geopsy'][0]:.10f} {'✓' if mm['freq_match'] else '✗'}")
            report_lines.append(f"    Slow:   ours={mm['our'].slowness:.16f} vs geopsy={mm['geopsy'][1]:.16f} {'✓' if mm['slow_match'] else '✗'}")
            report_lines.append(f"    StdDev: ours={mm['our'].stddev:.16f} vs geopsy={mm['geopsy'][2]:.16f} {'✓' if mm['std_match'] else '✗'}")
            report_lines.append(f"    Weight: ours={mm['our'].weight} vs geopsy={mm['geopsy'][3]} {'✓' if mm['weight_match'] else '✗'}")
    
    return all_match, "\n".join(report_lines)


def extract_averaged_curve_from_target(target_path: str) -> Tuple[List[Tuple], str]:
    """
    Extract the averaged curve from a Geopsy target file.
    
    Args:
        target_path: Path to .target file
        
    Returns:
        Tuple of (list of (freq, slowness, stddev, weight), curve_name)
    """
    from sw_dcml.dinver.target.reader import _read_target_xml
    import xml.etree.ElementTree as ET
    
    xml_content = _read_target_xml(target_path)
    root = ET.fromstring(xml_content)
    
    # Find the averaged curve (enabled=true and name contains "average")
    for modal_curve in root.findall('.//ModalCurve'):
        enabled_elem = modal_curve.find('enabled')
        name_elem = modal_curve.find('name')
        
        if enabled_elem is not None and enabled_elem.text == 'true':
            name = name_elem.text if name_elem is not None else "average"
            
            points = []
            for pt in modal_curve.findall('RealStatisticalPoint'):
                freq = float(pt.find('x').text)
                slowness = float(pt.find('mean').text)
                stddev = float(pt.find('stddev').text)
                weight = int(float(pt.find('weight').text))
                points.append((freq, slowness, stddev, weight))
            
            return points, name
    
    raise ValueError("No averaged curve found in target file")
