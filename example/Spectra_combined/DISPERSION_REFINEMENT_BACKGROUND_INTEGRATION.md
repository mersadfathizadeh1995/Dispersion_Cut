# Dispersion Curve Refinement: Power Spectrum Background Integration

## Overview

This guide explains how to integrate the exported power spectrum `.npz` files from SW_Transform as semi-transparent background overlays in a dispersion curve cutting/refinement application. The background provides visual context from the original 2D frequency-velocity power spectrum while editing dispersion curves.

---

## File Format Reference

### Power Spectrum Files (.npz)

**Filename Format**: `<base>_<method>_spectrum.npz`

Example: `survey01_fk_spectrum.npz`, `survey01_fdbf_p66_spectrum.npz`

**Contents** (NumPy compressed archive):
```python
import numpy as np
data = np.load('survey01_fk_spectrum.npz')

# Core data arrays
frequencies = data['frequencies']      # 1D array, shape (M,), units: Hz
velocities = data['velocities']        # 1D array, shape (N,), units: m/s
power = data['power']                  # 2D array, shape (N, M), normalized 0-1
picked_velocities = data['picked_velocities']  # 1D array, shape (M,), units: m/s

# Metadata
method = str(data['method'])           # 'fk', 'fdbf', 'ps', or 'ss'
offset = str(data['offset'])           # e.g., '+0', '+66m', '-12m'
export_date = str(data['export_date']) # ISO timestamp
version = str(data['version'])         # Format version (currently '1.0')

# Method-specific metadata (when available)
wavenumbers = data['wavenumbers']      # FK/FDBF only: 1D array
vibrosis_mode = bool(data['vibrosis_mode'])  # All methods
vspace = str(data['vspace'])           # PS only: 'log' or 'linear'
weight_mode = str(data['weight_mode']) # FDBF only: weighting mode
```

### Dispersion Curve Files (.csv)

**Filename Format**: `<base>_<method>_<offset_tag>.csv`

Example: `survey01_fk_p0.csv`, `survey01_fdbf_p66.csv`

**Contents** (CSV with header):
```csv
frequency(Hz),velocity(m/s),wavelength(m)
5.2,245.3,47.17
5.6,258.1,46.09
...
```

---

## Coordinate System and Data Structure

### Understanding the 2D Power Spectrum

The `power` array has shape `(N_velocities, N_frequencies)`:
- **X-axis (horizontal)**: Frequency (Hz) - from `frequencies[0]` to `frequencies[-1]`
- **Y-axis (vertical)**: Velocity (m/s) - from `velocities[0]` to `velocities[-1]`
- **Values**: Normalized power (0.0 to 1.0), where 1.0 = maximum energy

**Coordinate mapping**:
```python
power[i, j] corresponds to:
  - Velocity: velocities[i]
  - Frequency: frequencies[j]
  - Power level: power[i, j]
```

### Velocity Grid Details by Method

**FK and FDBF**:
- Always interpolated to uniform velocity grid
- 400 velocity points by default
- Range: `max(1.0, pick_vmin)` to `pick_vmax`
- Linear spacing

**PS and SS**:
- Native velocity grid from processing
- Grid size determined by `grid_n` parameter (typically 1200)
- Spacing: controlled by `vspace` ('log' or 'linear')

---

## Implementation Guide

### Step 1: Loading Power Spectrum Data

```python
import numpy as np
from pathlib import Path

def load_spectrum(npz_path):
    """
    Load power spectrum from .npz file.

    Returns:
        dict with keys: frequencies, velocities, power, method, offset, metadata
    """
    data = np.load(npz_path)

    return {
        'frequencies': data['frequencies'],
        'velocities': data['velocities'],
        'power': data['power'],
        'picked_velocities': data['picked_velocities'],
        'method': str(data['method']),
        'offset': str(data['offset']),
        'export_date': str(data['export_date']),
        'version': str(data['version']),
        # Optional metadata
        'wavenumbers': data.get('wavenumbers', None),
        'vibrosis_mode': bool(data.get('vibrosis_mode', False)),
        'vspace': data.get('vspace', None),
    }
```

### Step 2: Loading Dispersion Curve Data

```python
import csv

def load_dispersion_csv(csv_path):
    """
    Load dispersion curve from CSV.

    Returns:
        tuple of (frequencies, velocities, wavelengths) as numpy arrays
    """
    frequencies = []
    velocities = []
    wavelengths = []

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            frequencies.append(float(row['frequency(Hz)']))
            velocities.append(float(row['velocity(m/s)']))
            wavelengths.append(float(row['wavelength(m)']))

    return (np.array(frequencies),
            np.array(velocities),
            np.array(wavelengths))
```

### Step 3: Preparing Image for Canvas

Convert the 2D power array to an image with proper orientation and colormap:

```python
from PIL import Image
import numpy as np

def spectrum_to_image(power, alpha=0.5, colormap='viridis'):
    """
    Convert power spectrum to RGBA image for canvas overlay.

    Args:
        power: 2D array shape (N_vel, N_freq), values 0.0-1.0
        alpha: Opacity (0.0=transparent, 1.0=opaque)
        colormap: Color scheme ('viridis', 'plasma', 'hot', 'jet')

    Returns:
        PIL.Image in RGBA mode, shape (N_freq, N_vel) - note the transpose!
    """
    import matplotlib.cm as cm

    # Transpose: Canvas expects (width=frequency, height=velocity)
    # Original power is (velocity, frequency) so we need .T
    power_T = power.T  # Shape: (N_freq, N_vel)

    # Apply colormap
    cmap = cm.get_cmap(colormap)
    rgba = cmap(power_T)  # Shape: (N_freq, N_vel, 4)

    # Override alpha channel
    rgba[:, :, 3] = alpha

    # Convert to uint8 and create PIL Image
    rgba_uint8 = (rgba * 255).astype(np.uint8)

    # Flip vertically - canvas origin is top-left, velocity increases upward
    rgba_uint8 = np.flipud(rgba_uint8)

    img = Image.fromarray(rgba_uint8, mode='RGBA')

    return img
```

### Step 4: Canvas Integration with Proper Scaling

#### Tkinter Canvas Example

```python
import tkinter as tk
from PIL import Image, ImageTk

class DispersionRefinementCanvas:
    def __init__(self, parent):
        self.canvas = tk.Canvas(parent, bg='white')
        self.canvas.pack(fill='both', expand=True)

        # Data bounds (user coordinate system)
        self.freq_min = 0.0
        self.freq_max = 100.0
        self.vel_min = 0.0
        self.vel_max = 1000.0

        # Spectrum backgrounds (dictionary keyed by offset)
        self.spectrum_backgrounds = {}  # offset -> {'data': ..., 'image_id': ..., 'visible': True}

        # Canvas size
        self.canvas_width = 800
        self.canvas_height = 600

        # Zoom/pan state
        self.zoom_factor = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0

        # Bind resize event
        self.canvas.bind('<Configure>', self._on_resize)

    def _on_resize(self, event):
        """Update canvas size and redraw."""
        self.canvas_width = event.width
        self.canvas_height = event.height
        self.redraw_all()

    def data_to_canvas(self, freq, vel):
        """Convert data coordinates (Hz, m/s) to canvas pixels (x, y)."""
        # Apply zoom and pan
        x_norm = (freq - self.freq_min) / (self.freq_max - self.freq_min)
        y_norm = (vel - self.vel_min) / (self.vel_max - self.vel_min)

        # Apply zoom
        x_norm = (x_norm - 0.5) * self.zoom_factor + 0.5 + self.pan_x
        y_norm = (y_norm - 0.5) * self.zoom_factor + 0.5 + self.pan_y

        # Convert to canvas pixels
        x_canvas = x_norm * self.canvas_width
        y_canvas = (1.0 - y_norm) * self.canvas_height  # Flip Y

        return x_canvas, y_canvas

    def canvas_to_data(self, x_canvas, y_canvas):
        """Convert canvas pixels (x, y) to data coordinates (Hz, m/s)."""
        x_norm = x_canvas / self.canvas_width
        y_norm = 1.0 - (y_canvas / self.canvas_height)  # Flip Y

        # Reverse zoom
        x_norm = (x_norm - self.pan_x - 0.5) / self.zoom_factor + 0.5
        y_norm = (y_norm - self.pan_y - 0.5) / self.zoom_factor + 0.5

        freq = self.freq_min + x_norm * (self.freq_max - self.freq_min)
        vel = self.vel_min + y_norm * (self.vel_max - self.vel_min)

        return freq, vel

    def add_spectrum_background(self, offset, spectrum_data, alpha=0.5, colormap='viridis'):
        """
        Add a power spectrum as background for a specific offset.

        Args:
            offset: Source offset identifier (e.g., '+0', '+66m')
            spectrum_data: Dict from load_spectrum()
            alpha: Opacity 0.0-1.0
            colormap: Matplotlib colormap name
        """
        # Convert to image
        img = spectrum_to_image(spectrum_data['power'], alpha=alpha, colormap=colormap)

        # Store data
        self.spectrum_backgrounds[offset] = {
            'data': spectrum_data,
            'image': img,
            'image_tk': None,  # Will be set during draw
            'image_id': None,  # Canvas item ID
            'visible': True,
            'alpha': alpha,
            'colormap': colormap,
        }

        # Update display
        self.redraw_all()

    def toggle_spectrum_visibility(self, offset, visible=None):
        """Toggle or set visibility of a spectrum background."""
        if offset not in self.spectrum_backgrounds:
            return

        if visible is None:
            visible = not self.spectrum_backgrounds[offset]['visible']

        self.spectrum_backgrounds[offset]['visible'] = visible
        self.redraw_all()

    def set_spectrum_alpha(self, offset, alpha):
        """Change opacity of a spectrum background."""
        if offset not in self.spectrum_backgrounds:
            return

        bg = self.spectrum_backgrounds[offset]
        bg['alpha'] = alpha

        # Regenerate image with new alpha
        bg['image'] = spectrum_to_image(
            bg['data']['power'],
            alpha=alpha,
            colormap=bg['colormap']
        )

        self.redraw_all()

    def remove_spectrum_background(self, offset):
        """Remove a spectrum background."""
        if offset in self.spectrum_backgrounds:
            del self.spectrum_backgrounds[offset]
            self.redraw_all()

    def redraw_all(self):
        """Redraw all canvas elements."""
        self.canvas.delete('all')  # Clear canvas

        # Draw visible spectrum backgrounds
        for offset in sorted(self.spectrum_backgrounds.keys()):
            bg = self.spectrum_backgrounds[offset]
            if not bg['visible']:
                continue

            self._draw_spectrum_background(offset)

        # Draw dispersion curve points, selection handles, etc.
        # ... (your existing drawing code)

    def _draw_spectrum_background(self, offset):
        """Draw a single spectrum background on canvas."""
        bg = self.spectrum_backgrounds[offset]
        data = bg['data']

        # Get data bounds
        freq_data = data['frequencies']
        vel_data = data['velocities']
        freq_min_data = freq_data[0]
        freq_max_data = freq_data[-1]
        vel_min_data = vel_data[0]
        vel_max_data = vel_data[-1]

        # Convert corners to canvas coordinates
        x0, y1 = self.data_to_canvas(freq_min_data, vel_min_data)  # Bottom-left
        x1, y0 = self.data_to_canvas(freq_max_data, vel_max_data)  # Top-right

        # Calculate required image size on canvas
        width_canvas = abs(x1 - x0)
        height_canvas = abs(y1 - y0)

        if width_canvas < 1 or height_canvas < 1:
            return  # Too small to draw

        # Resize image to fit canvas area
        img_resized = bg['image'].resize(
            (int(width_canvas), int(height_canvas)),
            Image.Resampling.BILINEAR
        )

        # Convert to Tkinter PhotoImage
        bg['image_tk'] = ImageTk.PhotoImage(img_resized)

        # Draw on canvas at correct position
        # Use min coordinates as anchor point
        x_anchor = min(x0, x1)
        y_anchor = min(y0, y1)

        bg['image_id'] = self.canvas.create_image(
            x_anchor, y_anchor,
            image=bg['image_tk'],
            anchor='nw',
            tags=('spectrum_background', f'spectrum_{offset}')
        )

        # Send to back (so dispersion points draw on top)
        self.canvas.tag_lower('spectrum_background')

    def set_view_bounds(self, freq_min, freq_max, vel_min, vel_max):
        """Set data coordinate bounds for the view."""
        self.freq_min = freq_min
        self.freq_max = freq_max
        self.vel_min = vel_min
        self.vel_max = vel_max
        self.redraw_all()

    def zoom(self, factor, center_x=None, center_y=None):
        """Zoom in/out around a center point."""
        if center_x is None:
            center_x = self.canvas_width / 2
        if center_y is None:
            center_y = self.canvas_height / 2

        # Convert center to data coordinates
        freq_center, vel_center = self.canvas_to_data(center_x, center_y)

        # Update zoom
        self.zoom_factor *= factor
        self.zoom_factor = max(0.1, min(10.0, self.zoom_factor))  # Clamp

        # Adjust pan to keep center point fixed
        # ... (implement based on your pan system)

        self.redraw_all()
```

### Step 5: UI Controls for Background Management

#### Example Control Panel

```python
class BackgroundControlPanel(tk.Frame):
    def __init__(self, parent, canvas):
        super().__init__(parent)
        self.canvas = canvas

        # Master toggle
        self.master_enabled = tk.BooleanVar(value=True)
        tk.Checkbutton(
            self,
            text="Enable Spectrum Backgrounds",
            variable=self.master_enabled,
            command=self._toggle_master
        ).pack(anchor='w')

        tk.Label(self, text="Background Layers:").pack(anchor='w', pady=(10, 0))

        # Individual offset controls (dynamically populated)
        self.offset_frame = tk.Frame(self)
        self.offset_frame.pack(fill='both', expand=True)

        self.offset_controls = {}  # offset -> {'visible': BooleanVar, 'alpha': DoubleVar}

    def add_offset_control(self, offset):
        """Add UI controls for a specific offset's spectrum background."""
        frame = tk.Frame(self.offset_frame)
        frame.pack(fill='x', pady=2)

        # Visibility checkbox
        visible_var = tk.BooleanVar(value=True)
        cb = tk.Checkbutton(
            frame,
            text=f"Offset {offset}",
            variable=visible_var,
            command=lambda: self._toggle_offset(offset)
        )
        cb.pack(side='left')

        # Opacity slider
        tk.Label(frame, text="Opacity:").pack(side='left', padx=(10, 2))
        alpha_var = tk.DoubleVar(value=0.5)
        slider = tk.Scale(
            frame,
            from_=0.0, to=1.0,
            resolution=0.05,
            orient='horizontal',
            variable=alpha_var,
            command=lambda v: self._change_alpha(offset, float(v)),
            length=100
        )
        slider.pack(side='left')

        # Store references
        self.offset_controls[offset] = {
            'visible': visible_var,
            'alpha': alpha_var,
            'frame': frame
        }

    def remove_offset_control(self, offset):
        """Remove UI controls for an offset."""
        if offset in self.offset_controls:
            self.offset_controls[offset]['frame'].destroy()
            del self.offset_controls[offset]

    def _toggle_master(self):
        """Toggle all backgrounds on/off."""
        enabled = self.master_enabled.get()
        for offset in self.offset_controls:
            self.canvas.toggle_spectrum_visibility(offset, enabled)

    def _toggle_offset(self, offset):
        """Toggle visibility of a specific offset."""
        visible = self.offset_controls[offset]['visible'].get()
        self.canvas.toggle_spectrum_visibility(offset, visible)

    def _change_alpha(self, offset, alpha):
        """Change opacity of a specific offset."""
        self.canvas.set_spectrum_alpha(offset, alpha)
```

---

## Multi-Offset Handling Strategy

### File Discovery and Loading

```python
import glob
from pathlib import Path

def discover_spectrum_files(output_dir, base_name, method):
    """
    Find all spectrum files for a given base and method.

    Returns:
        dict mapping offset -> file path
    """
    pattern = f"{base_name}_{method}_*_spectrum.npz"
    matches = glob.glob(str(Path(output_dir) / pattern))

    offset_map = {}
    for fpath in matches:
        # Load to get offset metadata
        data = np.load(fpath)
        offset = str(data['offset'])
        offset_map[offset] = fpath

    return offset_map

def load_all_spectra(output_dir, base_name, method):
    """
    Load all spectrum backgrounds for a survey.

    Returns:
        dict mapping offset -> spectrum_data
    """
    files = discover_spectrum_files(output_dir, base_name, method)

    spectra = {}
    for offset, fpath in files.items():
        spectra[offset] = load_spectrum(fpath)

    return spectra
```

### Initialization in Refinement App

```python
# In your dispersion refinement app initialization:

def load_survey_with_backgrounds(survey_name, method='fk'):
    """Load dispersion curve and corresponding spectrum backgrounds."""

    # Load main dispersion CSV
    csv_path = f"output/{survey_name}_{method}_p0.csv"
    freq, vel, wav = load_dispersion_csv(csv_path)

    # Load all spectrum backgrounds for this survey
    spectra = load_all_spectra("output", survey_name, method)

    # Set up canvas
    canvas = DispersionRefinementCanvas(parent)

    # Determine view bounds from dispersion curve
    freq_min = max(0, freq.min() - 5)
    freq_max = freq.max() + 5
    vel_min = max(0, vel.min() - 50)
    vel_max = vel.max() + 100
    canvas.set_view_bounds(freq_min, freq_max, vel_min, vel_max)

    # Add each spectrum as background layer
    for offset, spectrum_data in spectra.items():
        canvas.add_spectrum_background(
            offset=offset,
            spectrum_data=spectrum_data,
            alpha=0.5,
            colormap='viridis'
        )

    # Set up control panel
    controls = BackgroundControlPanel(parent, canvas)
    for offset in spectra.keys():
        controls.add_offset_control(offset)

    return canvas, controls
```

---

## Important Implementation Notes

### 1. Coordinate System Alignment

**Critical**: The power spectrum coordinates MUST match the dispersion curve coordinates exactly.

- Both use frequency (Hz) on X-axis
- Both use velocity (m/s) on Y-axis
- The spectrum `frequencies` and `velocities` arrays define the data grid
- The dispersion CSV points should overlay the spectrum when coordinates match

**Test alignment**:
```python
# Load spectrum and CSV
spectrum = load_spectrum('survey01_fk_spectrum.npz')
freq_csv, vel_csv, _ = load_dispersion_csv('survey01_fk_p0.csv')

# Check that CSV points are within spectrum bounds
assert freq_csv.min() >= spectrum['frequencies'].min()
assert freq_csv.max() <= spectrum['frequencies'].max()
assert vel_csv.min() >= spectrum['velocities'].min()
assert vel_csv.max() <= spectrum['velocities'].max()
```

### 2. Canvas Refresh Strategy

When to redraw backgrounds:
- On zoom/pan operations
- On window resize
- On visibility toggle
- On opacity change
- When loading new survey

**Performance tip**: If zoom/pan is laggy, consider:
- Pre-render backgrounds at multiple zoom levels (mipmaps)
- Only redraw changed layers
- Use canvas layers/groups to avoid full redraws

### 3. Z-Order Management

Drawing order (back to front):
1. Canvas background (white/grid)
2. Spectrum backgrounds (oldest offset to newest)
3. Dispersion curve lines
4. Dispersion curve points
5. Selected points (highlight)
6. Editing handles/cursors

Use canvas tags to manage layers:
```python
self.canvas.tag_lower('spectrum_background')  # Send to back
self.canvas.tag_raise('dispersion_points')    # Bring to front
```

### 4. Colormap Recommendations

Suggested colormaps by use case:
- **Default**: `'viridis'` - perceptually uniform, colorblind-friendly
- **High contrast**: `'plasma'` or `'hot'`
- **Classic**: `'jet'` (not recommended - poor perceptual uniformity)
- **Grayscale**: `'gray'` - for printing
- **Diverging**: `'RdYlBu'` - if you need to show positive/negative

### 5. Opacity Guidelines

Recommended alpha values:
- **Light reference**: 0.3-0.4 (subtle background)
- **Balanced**: 0.5-0.6 (visible but not distracting)
- **Heavy**: 0.7-0.8 (when spectrum is primary focus)

Default: **0.5** provides good balance between visibility and overlay clarity.

### 6. Memory Management

For large surveys with many offsets:
- Load spectrum images on-demand (lazy loading)
- Unload invisible backgrounds from memory
- Use lower resolution images when zoomed out
- Consider caching rendered images at common zoom levels

```python
def _draw_spectrum_background_optimized(self, offset):
    """Optimized version with LOD (Level of Detail)."""
    bg = self.spectrum_backgrounds[offset]

    # Determine required resolution based on zoom
    if self.zoom_factor < 0.5:
        # Zoomed way out - use low-res version
        downsample = 4
    elif self.zoom_factor > 2.0:
        # Zoomed in - use full resolution
        downsample = 1
    else:
        # Normal zoom
        downsample = 2

    # Downsample power array if needed
    if downsample > 1:
        power_downsampled = bg['data']['power'][::downsample, ::downsample]
    else:
        power_downsampled = bg['data']['power']

    # Continue with rendering...
```

---

## Testing Checklist

Before integration:

- [ ] Load .npz file successfully
- [ ] Load corresponding .csv file
- [ ] Verify coordinates align (CSV points overlay spectrum peaks)
- [ ] Test image rendering with different colormaps
- [ ] Test opacity changes (0.0 to 1.0)
- [ ] Test visibility toggle (on/off)
- [ ] Test zoom in/out - background scales correctly
- [ ] Test pan - background moves with data points
- [ ] Test window resize - background rescales properly
- [ ] Test multiple offsets - all render correctly
- [ ] Test z-order - backgrounds behind curve points
- [ ] Test master enable/disable toggle
- [ ] Test performance with 5+ spectrum layers

---

## Example Workflow

### Typical User Workflow

1. **Load survey**: Select base survey and method (FK/FDBF/PS/SS)
2. **Auto-load backgrounds**: App discovers all spectrum .npz files for that survey
3. **Default state**: All backgrounds visible at 50% opacity
4. **Refinement mode**: User adjusts dispersion curve points while viewing spectrum
5. **Toggle references**: Turn on/off specific source offsets to reduce clutter
6. **Adjust opacity**: Increase/decrease to balance visibility
7. **Zoom analysis**: Zoom into specific frequency range - spectrum scales accordingly
8. **Export refined curve**: Save updated CSV with refined points

### Example Code: Complete Integration

```python
# Main application setup
class DispersionRefinementApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Dispersion Curve Refinement")

        # Create canvas
        canvas_frame = tk.Frame(self.root)
        canvas_frame.pack(side='left', fill='both', expand=True)
        self.canvas = DispersionRefinementCanvas(canvas_frame)

        # Create control panel
        control_frame = tk.Frame(self.root, width=250)
        control_frame.pack(side='right', fill='y')
        self.controls = BackgroundControlPanel(control_frame, self.canvas)

        # Load survey
        self.load_survey("survey01", method="fk")

    def load_survey(self, base_name, method):
        """Load survey with all backgrounds."""
        # Load dispersion curve
        csv_path = f"output/{base_name}_{method}_p0.csv"
        self.freq, self.vel, self.wav = load_dispersion_csv(csv_path)

        # Set canvas bounds
        freq_min = max(0, self.freq.min() - 5)
        freq_max = self.freq.max() + 5
        vel_min = max(0, self.vel.min() - 50)
        vel_max = self.vel.max() + 100
        self.canvas.set_view_bounds(freq_min, freq_max, vel_min, vel_max)

        # Load all spectrum backgrounds
        spectra = load_all_spectra("output", base_name, method)

        # Add to canvas and controls
        for offset in sorted(spectra.keys()):
            self.canvas.add_spectrum_background(
                offset=offset,
                spectrum_data=spectra[offset],
                alpha=0.5,
                colormap='viridis'
            )
            self.controls.add_offset_control(offset)

        # Initial draw
        self.canvas.redraw_all()

# Run app
if __name__ == '__main__':
    app = DispersionRefinementApp()
    app.root.mainloop()
```

---

## Troubleshooting

### Issue: Spectrum and dispersion points don't align

**Cause**: Coordinate system mismatch or incorrect data bounds.

**Solution**:
```python
# Verify bounds match
print(f"Spectrum freq range: {spectrum['frequencies'][0]:.1f} - {spectrum['frequencies'][-1]:.1f} Hz")
print(f"CSV freq range: {freq_csv.min():.1f} - {freq_csv.max():.1f} Hz")

# Check for coordinate system flip
# Velocity should increase upward (positive Y direction)
```

### Issue: Background doesn't scale with zoom

**Cause**: Image position/size not recalculated during zoom.

**Solution**: Ensure `redraw_all()` is called after any zoom/pan operation, and that `data_to_canvas()` correctly applies zoom factor.

### Issue: Performance degrades with multiple backgrounds

**Cause**: Too many high-resolution images being redrawn on every frame.

**Solution**:
- Implement layer caching
- Use lower resolution when zoomed out
- Only redraw changed layers
- Consider using GPU-accelerated canvas (OpenGL/Vulkan)

### Issue: Colors look washed out

**Cause**: Opacity too low or poor colormap choice.

**Solution**: Try alpha=0.6 and switch to 'plasma' or 'hot' colormap for higher contrast.

---

## Advanced Features

### Feature: Difference Highlighting

Show differences between multiple source offsets:

```python
def create_difference_overlay(spectrum1, spectrum2, threshold=0.2):
    """
    Create overlay showing where two spectra differ significantly.

    Highlights regions where power differs by more than threshold.
    """
    diff = np.abs(spectrum1['power'] - spectrum2['power'])
    mask = diff > threshold

    # Create colored overlay (red for differences)
    rgba = np.zeros((*diff.shape, 4), dtype=np.float32)
    rgba[mask, 0] = 1.0  # Red channel
    rgba[mask, 3] = 0.6  # Alpha

    return rgba
```

### Feature: Automatic Peak Highlighting

Overlay extracted peaks from the spectrum:

```python
def highlight_spectrum_peaks(spectrum_data, num_peaks=3):
    """
    Find and mark local maxima in the spectrum for each frequency.

    Returns peak locations as (frequency, velocity) pairs.
    """
    from scipy.signal import find_peaks

    peaks = []
    for j, freq in enumerate(spectrum_data['frequencies']):
        # Find peaks in this frequency column
        power_column = spectrum_data['power'][:, j]
        peak_indices, _ = find_peaks(power_column, height=0.5, distance=10)

        # Take top N peaks
        peak_indices = peak_indices[np.argsort(power_column[peak_indices])[-num_peaks:]]

        for i in peak_indices:
            peaks.append((freq, spectrum_data['velocities'][i]))

    return peaks
```

### Feature: Animation Between Offsets

Create smooth transitions when switching between source offset backgrounds:

```python
def animate_offset_transition(canvas, from_offset, to_offset, duration=0.5):
    """Animate fade between two spectrum backgrounds."""
    import time

    steps = 20
    dt = duration / steps

    for i in range(steps + 1):
        alpha_from = 1.0 - (i / steps)
        alpha_to = i / steps

        canvas.set_spectrum_alpha(from_offset, alpha_from)
        canvas.set_spectrum_alpha(to_offset, alpha_to)
        canvas.redraw_all()
        canvas.update()

        time.sleep(dt)
```

---

## Summary

This integration allows your dispersion curve refinement tool to display power spectra as semi-transparent, scalable background images that:

1. **Align perfectly** with dispersion curve coordinates (frequency vs. velocity)
2. **Scale correctly** during zoom/pan operations
3. **Support multiple source offsets** with individual visibility/opacity controls
4. **Maintain proper z-order** (backgrounds behind editable curve points)
5. **Provide visual context** from the original 2D transform data

The key technical requirements are:
- Proper coordinate mapping between data space and canvas pixels
- Image transformation with correct orientation (transpose + vertical flip)
- Recalculation of image size/position on every zoom/pan/resize
- Efficient rendering with optional LOD (Level of Detail) optimization

All necessary data is contained in the `.npz` files - no need to re-run the transforms.
