"""
Comprehensive test suite for Report Studio v2.

Tests core models, IO readers, rendering pipeline, project persistence,
and GUI widgets in headless/offscreen mode.

Usage:
    python -m pytest tests/test_report_studio.py -v
"""

import os
import sys
import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

# Ensure dc_cut package is importable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Test data paths
PKL_PATH = ROOT / "Files" / "Test_Files" / "Rayleigh01.pkl"
NPZ_PATH = ROOT / "Files" / "Test_Files" / "combined_fdbf_spectrum.npz"


# ═══════════════════════════════════════════════════════════════════════
# 1. Core Models
# ═══════════════════════════════════════════════════════════════════════

class TestOffsetCurve:
    def test_creation_generates_uid(self):
        from packages.report_studio.core.models import OffsetCurve
        c = OffsetCurve(name="test")
        assert c.uid and len(c.uid) == 8

    def test_has_data(self):
        from packages.report_studio.core.models import OffsetCurve
        c1 = OffsetCurve()
        assert not c1.has_data

        c2 = OffsetCurve(frequency=np.array([1, 2, 3]), velocity=np.array([100, 200, 300]))
        assert c2.has_data
        assert c2.n_points == 3

    def test_point_mask_auto_created(self):
        from packages.report_studio.core.models import OffsetCurve
        c = OffsetCurve(frequency=np.array([1, 2]), velocity=np.array([10, 20]))
        assert c.point_mask is not None
        assert c.point_mask.sum() == 2

    def test_masked_arrays(self):
        from packages.report_studio.core.models import OffsetCurve
        c = OffsetCurve(
            frequency=np.array([1.0, 2.0, 3.0]),
            velocity=np.array([100.0, 200.0, 300.0]),
            wavelength=np.array([100.0, 100.0, 100.0]),
        )
        c.point_mask = np.array([True, False, True])
        x, y = c.masked_arrays("frequency")
        assert np.isnan(x[1])
        assert np.isnan(y[1])
        assert not np.isnan(x[0])

    def test_display_name_fallback(self):
        from packages.report_studio.core.models import OffsetCurve
        c = OffsetCurve()
        assert c.display_name == c.uid
        c.name = "My Curve"
        assert c.display_name == "My Curve"


class TestSheetState:
    def test_default_subplot(self):
        from packages.report_studio.core.models import SheetState
        s = SheetState()
        assert "main" in s.subplots

    def test_add_curve(self):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        s = SheetState()
        c = OffsetCurve(name="c1", frequency=np.array([1]), velocity=np.array([1]))
        s.add_curve(c)
        assert c.uid in s.curves
        assert c.uid in s.subplots["main"].curve_uids

    def test_remove_curve(self):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        s = SheetState()
        c = OffsetCurve(name="c1", frequency=np.array([1]), velocity=np.array([1]))
        s.add_curve(c)
        s.remove_curve(c.uid)
        assert c.uid not in s.curves
        assert c.uid not in s.subplots["main"].curve_uids

    def test_move_curve(self):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        s = SheetState()
        s.set_grid(1, 2)
        c = OffsetCurve(name="c1", frequency=np.array([1]), velocity=np.array([1]))
        s.add_curve(c, "cell_0_0")
        s.move_curve(c.uid, "cell_0_1")
        assert c.uid not in s.subplots["cell_0_0"].curve_uids
        assert c.uid in s.subplots["cell_0_1"].curve_uids

    def test_set_grid(self):
        from packages.report_studio.core.models import SheetState
        s = SheetState()
        s.set_grid(2, 3)
        assert s.grid_rows == 2
        assert s.grid_cols == 3
        assert len(s.col_ratios) == 3
        keys = s.subplot_keys_ordered()
        assert len(keys) == 6

    def test_get_curves_for_subplot(self):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        s = SheetState()
        c1 = OffsetCurve(name="a", frequency=np.array([1]), velocity=np.array([1]))
        c2 = OffsetCurve(name="b", frequency=np.array([2]), velocity=np.array([2]))
        s.add_curve(c1)
        s.add_curve(c2)
        curves = s.get_curves_for_subplot("main")
        assert len(curves) == 2


class TestSubplotTypes:
    def test_can_accept(self):
        from packages.report_studio.core.subplot_types import (
            can_accept, UNSET, DISPERSION, SPECTRUM, COMBINED,
            KIND_CURVE, KIND_SPECTRUM,
        )
        assert can_accept(UNSET, KIND_CURVE)
        assert can_accept(COMBINED, KIND_CURVE)
        assert can_accept(COMBINED, KIND_SPECTRUM)
        assert not can_accept(DISPERSION, KIND_SPECTRUM)
        assert not can_accept(SPECTRUM, KIND_CURVE)

    def test_auto_assign(self):
        from packages.report_studio.core.subplot_types import (
            auto_assign_type, UNSET, COMBINED, SPECTRUM, KIND_CURVE, KIND_SPECTRUM,
        )
        assert auto_assign_type(UNSET, KIND_CURVE) == COMBINED
        assert auto_assign_type(UNSET, KIND_SPECTRUM) == SPECTRUM
        assert auto_assign_type(COMBINED, KIND_CURVE) == COMBINED  # no change


# ═══════════════════════════════════════════════════════════════════════
# 2. IO Readers
# ═══════════════════════════════════════════════════════════════════════

class TestPklReader:
    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_read_pkl(self):
        from packages.report_studio.io.pkl_reader import read_pkl
        curves = read_pkl(PKL_PATH)
        assert len(curves) > 0
        for c in curves:
            assert c.has_data
            assert len(c.frequency) == len(c.velocity)
            assert c.name

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_read_pkl_metadata(self):
        from packages.report_studio.io.pkl_reader import read_pkl_metadata
        meta = read_pkl_metadata(PKL_PATH)
        assert meta["n_offsets"] > 0
        assert isinstance(meta["labels"], list)

    def test_read_nonexistent_raises(self):
        from packages.report_studio.io.pkl_reader import read_pkl
        with pytest.raises(FileNotFoundError):
            read_pkl("nonexistent.pkl")


class TestSpectrumReader:
    @pytest.mark.skipif(not NPZ_PATH.exists(), reason="Test NPZ not found")
    def test_read_spectrum(self):
        from packages.report_studio.io.spectrum_reader import read_spectrum_npz
        spectra = read_spectrum_npz(NPZ_PATH)
        assert len(spectra) > 0
        for s in spectra:
            assert s.has_data
            assert s.power.ndim == 2

    def test_read_nonexistent_raises(self):
        from packages.report_studio.io.spectrum_reader import read_spectrum_npz
        with pytest.raises(FileNotFoundError):
            read_spectrum_npz("nonexistent.npz")


# ═══════════════════════════════════════════════════════════════════════
# 3. Rendering Pipeline
# ═══════════════════════════════════════════════════════════════════════

class TestRendering:
    def test_style_config_defaults(self):
        from packages.report_studio.rendering.style import StyleConfig
        s = StyleConfig()
        assert s.dpi == 150
        assert s.legend_visible is True
        assert s.grid_visible is True

    def test_style_get_labels(self):
        from packages.report_studio.rendering.style import StyleConfig
        s = StyleConfig()
        assert "Frequency" in s.get_x_label("frequency")
        assert "Wavelength" in s.get_x_label("wavelength")
        assert "Velocity" in s.get_y_label()

    def test_layout_builder_single(self):
        from matplotlib.figure import Figure
        from packages.report_studio.core.models import SheetState
        from packages.report_studio.rendering.layout_builder import create_grid

        fig = Figure()
        state = SheetState()
        axes = create_grid(fig, state)
        assert "main" in axes

    def test_layout_builder_grid(self):
        from matplotlib.figure import Figure
        from packages.report_studio.core.models import SheetState
        from packages.report_studio.rendering.layout_builder import create_grid

        fig = Figure()
        state = SheetState()
        state.set_grid(2, 2)
        axes = create_grid(fig, state)
        assert len(axes) == 4

    def test_curve_drawer(self):
        from matplotlib.figure import Figure
        from packages.report_studio.core.models import OffsetCurve
        from packages.report_studio.rendering.curve_drawer import draw

        fig = Figure()
        ax = fig.add_subplot(111)
        curve = OffsetCurve(
            frequency=np.array([1.0, 2.0, 3.0]),
            velocity=np.array([100.0, 200.0, 300.0]),
        )
        draw(ax, curve)
        assert len(ax.lines) == 1

    def test_curve_drawer_invisible_skipped(self):
        from matplotlib.figure import Figure
        from packages.report_studio.core.models import OffsetCurve
        from packages.report_studio.rendering.curve_drawer import draw

        fig = Figure()
        ax = fig.add_subplot(111)
        curve = OffsetCurve(
            frequency=np.array([1.0]), velocity=np.array([100.0]), visible=False,
        )
        draw(ax, curve)
        assert len(ax.lines) == 0

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_render_sheet_full(self):
        from matplotlib.figure import Figure
        from packages.report_studio.core.models import SheetState
        from packages.report_studio.io.pkl_reader import read_pkl
        from packages.report_studio.rendering.renderer import render_sheet
        from packages.report_studio.rendering.style import StyleConfig

        curves = read_pkl(PKL_PATH)
        state = SheetState()
        for c in curves:
            state.add_curve(c)

        fig = Figure(figsize=(10, 7))
        style = StyleConfig()
        axes = render_sheet(fig, state, style)
        assert "main" in axes

    @pytest.mark.skipif(
        not PKL_PATH.exists() or not NPZ_PATH.exists(),
        reason="Test data not found"
    )
    def test_render_with_spectra(self):
        from matplotlib.figure import Figure
        from packages.report_studio.core.models import SheetState
        from packages.report_studio.io.pkl_reader import read_pkl
        from packages.report_studio.io.spectrum_reader import read_spectrum_npz
        from packages.report_studio.rendering.renderer import render_sheet
        from packages.report_studio.rendering.style import StyleConfig

        curves = read_pkl(PKL_PATH)
        spectra = read_spectrum_npz(NPZ_PATH)
        state = SheetState()
        for c in curves:
            state.add_curve(c)
        for s in spectra:
            state.spectra[s.uid] = s

        fig = Figure(figsize=(10, 7))
        axes = render_sheet(fig, state)
        assert len(axes) >= 1

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_render_multi_subplot(self):
        from matplotlib.figure import Figure
        from packages.report_studio.core.models import SheetState
        from packages.report_studio.io.pkl_reader import read_pkl
        from packages.report_studio.rendering.renderer import render_sheet

        curves = read_pkl(PKL_PATH)
        state = SheetState()
        state.set_grid(1, 2)
        keys = state.subplot_keys_ordered()
        # Put first half in subplot 0, second half in subplot 1
        for i, c in enumerate(curves):
            key = keys[0] if i < len(curves) // 2 else keys[1]
            state.add_curve(c, key)

        fig = Figure(figsize=(14, 7))
        axes = render_sheet(fig, state)
        assert len(axes) == 2

    def test_render_empty_sheet(self):
        from matplotlib.figure import Figure
        from packages.report_studio.core.models import SheetState
        from packages.report_studio.rendering.renderer import render_sheet

        state = SheetState()
        fig = Figure()
        axes = render_sheet(fig, state)
        assert "main" in axes


# ═══════════════════════════════════════════════════════════════════════
# 4. Project Persistence
# ═══════════════════════════════════════════════════════════════════════

class TestProjectPersistence:
    def test_save_load_roundtrip(self, tmp_path):
        from packages.report_studio.core.models import (
            SheetState, OffsetCurve, SpectrumData, LegendConfig,
        )
        from packages.report_studio.io.project import save_project, load_project

        # Create a sheet with data
        sheet = SheetState(name="Test Sheet")
        c = OffsetCurve(
            name="curve1",
            frequency=np.array([1.0, 2.0, 3.0]),
            velocity=np.array([100.0, 200.0, 300.0]),
            wavelength=np.array([100.0, 100.0, 100.0]),
            color="#FF0000",
            line_width=2.0,
        )
        sheet.add_curve(c)
        sheet.legend.position = "upper left"
        sheet.typography.title_size = 14

        path = tmp_path / "test_project.json"
        save_project([sheet], path)

        # Verify file was created
        assert path.exists()

        # Load it back
        loaded = load_project(path)
        assert len(loaded) == 1
        ls = loaded[0]
        assert ls.name == "Test Sheet"
        assert len(ls.curves) == 1

        lc = list(ls.curves.values())[0]
        assert lc.name == "curve1"
        assert lc.color == "#FF0000"
        assert lc.line_width == 2.0
        np.testing.assert_array_almost_equal(lc.frequency, [1.0, 2.0, 3.0])
        np.testing.assert_array_almost_equal(lc.velocity, [100.0, 200.0, 300.0])

        assert ls.legend.position == "upper left"
        assert ls.typography.title_size == 14

    def test_save_load_with_spectrum(self, tmp_path):
        from packages.report_studio.core.models import SheetState, SpectrumData
        from packages.report_studio.io.project import save_project, load_project

        sheet = SheetState()
        spec = SpectrumData(
            offset_name="+10m",
            frequencies=np.linspace(5, 50, 100),
            velocities=np.linspace(50, 500, 80),
            power=np.random.rand(80, 100),
        )
        sheet.spectra[spec.uid] = spec

        path = tmp_path / "spec_project.json"
        save_project([sheet], path)

        loaded = load_project(path)
        ls = loaded[0]
        assert len(ls.spectra) == 1
        loaded_spec = list(ls.spectra.values())[0]
        assert loaded_spec.offset_name == "+10m"
        assert loaded_spec.power.shape == (80, 100)

    def test_save_load_grid(self, tmp_path):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        from packages.report_studio.io.project import save_project, load_project

        sheet = SheetState()
        sheet.set_grid(2, 2)
        c = OffsetCurve(
            name="c1", frequency=np.array([1.0]), velocity=np.array([1.0])
        )
        sheet.add_curve(c, "cell_0_1")

        path = tmp_path / "grid_project.json"
        save_project([sheet], path)

        loaded = load_project(path)
        ls = loaded[0]
        assert ls.grid_rows == 2
        assert ls.grid_cols == 2
        lc = list(ls.curves.values())[0]
        assert lc.subplot_key == "cell_0_1"

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_save_load_real_data(self, tmp_path):
        from packages.report_studio.core.models import SheetState
        from packages.report_studio.io.pkl_reader import read_pkl
        from packages.report_studio.io.project import save_project, load_project

        curves = read_pkl(PKL_PATH)
        sheet = SheetState()
        for c in curves:
            sheet.add_curve(c)

        path = tmp_path / "real_data_project.json"
        save_project([sheet], path)

        loaded = load_project(path)
        assert len(loaded[0].curves) == len(curves)

    def test_load_nonexistent_raises(self):
        from packages.report_studio.io.project import load_project
        with pytest.raises(FileNotFoundError):
            load_project("nonexistent.json")


# ═══════════════════════════════════════════════════════════════════════
# 5. GUI Widget Tests (offscreen/headless)
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def qapp():
    """Create or reuse the global QApplication for offscreen testing."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from packages.report_studio.qt_compat import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["--platform", "offscreen"])
    yield app


class TestPlotCanvas:
    def test_construction(self, qapp):
        from packages.report_studio.gui.canvas.plot_canvas import PlotCanvas
        canvas = PlotCanvas()
        assert canvas.figure is not None
        qapp.processEvents()  # flush pending events

    def test_render_empty(self, qapp):
        from packages.report_studio.gui.canvas.plot_canvas import PlotCanvas
        from packages.report_studio.core.models import SheetState
        from packages.report_studio.rendering.style import StyleConfig

        canvas = PlotCanvas()
        sheet = SheetState()
        canvas.render(sheet, StyleConfig())
        assert "main" in canvas.axes
        qapp.processEvents()

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_render_with_data(self, qapp):
        from packages.report_studio.gui.canvas.plot_canvas import PlotCanvas
        from packages.report_studio.core.models import SheetState
        from packages.report_studio.io.pkl_reader import read_pkl
        from packages.report_studio.rendering.style import StyleConfig

        canvas = PlotCanvas()
        curves = read_pkl(PKL_PATH)
        sheet = SheetState()
        for c in curves:
            sheet.add_curve(c)

        canvas.render(sheet, StyleConfig())
        assert len(canvas.axes) >= 1
        qapp.processEvents()

    def test_export_image(self, qapp, tmp_path):
        from packages.report_studio.gui.canvas.plot_canvas import PlotCanvas
        from packages.report_studio.core.models import SheetState, OffsetCurve
        from packages.report_studio.rendering.style import StyleConfig

        canvas = PlotCanvas()
        sheet = SheetState()
        c = OffsetCurve(
            frequency=np.array([1.0, 2.0]), velocity=np.array([100.0, 200.0])
        )
        sheet.add_curve(c)
        canvas.render(sheet, StyleConfig())

        img_path = tmp_path / "test_export.png"
        canvas.export_image(str(img_path), dpi=100)
        assert img_path.exists()
        assert img_path.stat().st_size > 0
        qapp.processEvents()


class TestSheetTabs:
    def test_construction(self, qapp):
        from packages.report_studio.gui.canvas.sheet_tabs import SheetTabs
        tabs = SheetTabs()
        assert tabs.count() == 0

    def test_add_tab(self, qapp):
        from packages.report_studio.gui.canvas.sheet_tabs import SheetTabs
        from packages.report_studio.gui.canvas.plot_canvas import PlotCanvas
        tabs = SheetTabs()
        canvas = PlotCanvas()
        idx = tabs.add_tab(canvas, "Sheet 1")
        assert idx == 0
        assert tabs.count() == 1
        assert tabs.current_canvas() is canvas

    def test_close_keeps_minimum(self, qapp):
        from packages.report_studio.gui.canvas.sheet_tabs import SheetTabs
        from packages.report_studio.gui.canvas.plot_canvas import PlotCanvas
        tabs = SheetTabs()
        tabs.add_tab(PlotCanvas(), "S1")
        tabs._on_close_requested(0)  # Should not close — minimum 1
        assert tabs.count() == 1


class TestDataTree:
    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.data_tree import DataTreePanel
        tree = DataTreePanel()
        assert tree is not None

    def test_populate_empty(self, qapp):
        from packages.report_studio.gui.panels.data_tree import DataTreePanel
        from packages.report_studio.core.models import SheetState
        tree = DataTreePanel()
        tree.populate(SheetState())
        # Should have one top-level item for "main" subplot
        assert tree._tree.topLevelItemCount() == 1

    def test_populate_with_curves(self, qapp):
        from packages.report_studio.gui.panels.data_tree import DataTreePanel
        from packages.report_studio.core.models import SheetState, OffsetCurve
        tree = DataTreePanel()
        sheet = SheetState()
        c1 = OffsetCurve(name="A", frequency=np.array([1]), velocity=np.array([1]))
        c2 = OffsetCurve(name="B", frequency=np.array([2]), velocity=np.array([2]))
        sheet.add_curve(c1)
        sheet.add_curve(c2)
        tree.populate(sheet)

        main_item = tree._tree.topLevelItem(0)
        assert main_item.childCount() == 2

    def test_curve_has_data_sublayer(self, qapp):
        """Each curve should have a 'Data: N points' sub-item."""
        from packages.report_studio.gui.panels.data_tree import DataTreePanel
        from packages.report_studio.core.models import SheetState, OffsetCurve
        tree = DataTreePanel()
        sheet = SheetState()
        c = OffsetCurve(name="Test", frequency=np.array([1, 2, 3]),
                        velocity=np.array([10, 20, 30]))
        sheet.add_curve(c)
        tree.populate(sheet)

        main_item = tree._tree.topLevelItem(0)
        curve_item = main_item.child(0)
        assert curve_item.childCount() >= 1  # at least data info
        data_item = curve_item.child(0)
        assert "3" in data_item.text(0) and "points" in data_item.text(0)

    def test_curve_has_spectrum_sublayer(self, qapp):
        """Curve with linked spectrum should show spectrum sub-item."""
        from packages.report_studio.gui.panels.data_tree import DataTreePanel
        from packages.report_studio.core.models import (
            SheetState, OffsetCurve, SpectrumData
        )
        tree = DataTreePanel()
        sheet = SheetState()
        spec = SpectrumData(
            offset_name="test",
            frequencies=np.linspace(5, 50, 10),
            velocities=np.linspace(50, 500, 20),
            power=np.random.rand(20, 10),
            method="fdbf",
        )
        sheet.spectra[spec.uid] = spec
        c = OffsetCurve(name="Test", frequency=np.array([1, 2]),
                        velocity=np.array([10, 20]),
                        spectrum_uid=spec.uid, spectrum_visible=False)
        sheet.add_curve(c)
        tree.populate(sheet)

        main_item = tree._tree.topLevelItem(0)
        curve_item = main_item.child(0)
        assert curve_item.childCount() == 2  # data + spectrum
        spec_item = curve_item.child(1)
        assert "Spectrum" in spec_item.text(0)
        assert "fdbf" in spec_item.text(0)

    def test_spectrum_default_not_visible(self, qapp):
        """New OffsetCurve should have spectrum_visible=False by default."""
        from packages.report_studio.core.models import OffsetCurve
        c = OffsetCurve(name="X", frequency=np.array([1]), velocity=np.array([1]))
        assert c.spectrum_visible is False

    def test_spectrum_selected_signal(self, qapp, qtbot):
        """Clicking a spectrum sub-item should emit spectrum_selected, not curve_selected."""
        from packages.report_studio.gui.panels.data_tree import (
            DataTreePanel, _TYPE_SPECTRUM, _ITEM_TYPE_ROLE, _UID_ROLE,
        )
        from packages.report_studio.core.models import (
            SheetState, OffsetCurve, SpectrumData,
        )
        tree = DataTreePanel()
        sheet = SheetState()
        spec = SpectrumData(
            offset_name="test",
            frequencies=np.linspace(5, 50, 10),
            velocities=np.linspace(50, 500, 20),
            power=np.random.rand(20, 10),
            method="fdbf",
        )
        sheet.spectra[spec.uid] = spec
        c = OffsetCurve(name="Test", frequency=np.array([1, 2]),
                        velocity=np.array([10, 20]),
                        spectrum_uid=spec.uid, spectrum_visible=False)
        sheet.add_curve(c)
        tree.populate(sheet)

        # Find the spectrum item
        main_item = tree._tree.topLevelItem(0)
        curve_item = main_item.child(0)
        spec_item = curve_item.child(1)  # spectrum sub-item
        assert spec_item.data(0, _ITEM_TYPE_ROLE) == _TYPE_SPECTRUM

        # Connect signals
        with qtbot.waitSignal(tree.spectrum_selected, timeout=1000) as blocker:
            tree._on_item_clicked(spec_item, 0)

        assert blocker.args == [c.uid]


class TestPropertiesPanel:
    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.properties_panel import PropertiesPanel
        panel = PropertiesPanel()
        assert panel is not None
        # Curve group should be hidden initially
        assert panel._curve_group.isHidden()

    def test_show_curve(self, qapp):
        from packages.report_studio.gui.panels.properties_panel import PropertiesPanel
        from packages.report_studio.core.models import OffsetCurve
        panel = PropertiesPanel()
        c = OffsetCurve(
            name="Test",
            frequency=np.array([1.0, 2.0]),
            velocity=np.array([10.0, 20.0]),
            color="#FF0000",
            line_width=2.5,
            marker_size=6.0,
        )
        panel.show_curve(c)
        assert not panel._curve_group.isHidden()
        assert panel._lbl_name.text() == "Test"
        assert panel._spin_line_width.value() == 2.5
        assert panel._spin_marker.value() == 6.0

    def test_show_subplot(self, qapp):
        from packages.report_studio.gui.panels.properties_panel import PropertiesPanel
        from packages.report_studio.core.models import SubplotState
        panel = PropertiesPanel()
        sp = SubplotState(key="main", x_domain="wavelength", auto_x=False)
        panel.show_subplot(sp)
        assert panel._combo_domain.currentText() == "wavelength"
        assert not panel._chk_auto_x.isChecked()

    def test_clear_curve(self, qapp):
        from packages.report_studio.gui.panels.properties_panel import PropertiesPanel
        from packages.report_studio.core.models import OffsetCurve
        panel = PropertiesPanel()
        c = OffsetCurve(name="X", frequency=np.array([1]), velocity=np.array([1]))
        panel.show_curve(c)
        assert not panel._curve_group.isHidden()
        panel.clear_curve()
        assert panel._curve_group.isHidden()


class TestSheetPanel:
    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.sheet_panel import SheetPanel
        panel = SheetPanel()
        assert panel is not None

    def test_populate(self, qapp):
        from packages.report_studio.gui.panels.sheet_panel import SheetPanel
        from packages.report_studio.core.models import SheetState
        panel = SheetPanel()
        sheet = SheetState()
        sheet.set_grid(2, 3)
        sheet.legend.position = "upper left"
        sheet.typography.title_size = 14
        panel.populate(sheet)
        assert panel._spin_rows.value() == 2
        assert panel._spin_cols.value() == 3
        assert panel._combo_legend_pos.currentText() == "upper left"
        assert panel._spin_title_size.value() == 14


class TestExportDialog:
    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.export_dialog import ExportDialog
        dlg = ExportDialog()
        assert dlg is not None
        assert dlg.dpi == 300


class TestProjectDialog:
    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.project_dialog import ProjectDialog
        dlg = ProjectDialog()
        assert dlg is not None


# ═══════════════════════════════════════════════════════════════════════
# 6. Main Window Integration
# ═══════════════════════════════════════════════════════════════════════

class TestMainWindowIntegration:
    def test_window_construction(self, qapp):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        # Patch out the initial load dialog
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win.setWindowTitle("Test")
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        assert win.sheet_tabs.count() == 1
        assert hasattr(win, "data_tree")
        assert hasattr(win, "right_panel")

    def test_add_new_sheet(self, qapp):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        win._add_new_sheet("Sheet 2")
        assert len(win._sheets) == 2
        assert win.sheet_tabs.count() == 2

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_load_and_render(self, qapp):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        # Load data programmatically
        win._load_from_files(str(PKL_PATH), str(NPZ_PATH) if NPZ_PATH.exists() else "", show_dialog=False)

        sheet = win._current_sheet()
        assert sheet is not None
        assert len(sheet.curves) > 0

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_curve_selection(self, qapp):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        win._load_from_files(str(PKL_PATH), show_dialog=False)
        sheet = win._current_sheet()
        uid = list(sheet.curves.keys())[0]
        win._on_curve_selected(uid)
        assert win._selected_uid == uid

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_curve_visibility_toggle(self, qapp):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        win._load_from_files(str(PKL_PATH), show_dialog=False)
        sheet = win._current_sheet()
        uid = list(sheet.curves.keys())[0]
        win._on_curve_visibility_changed(uid, False)
        assert sheet.curves[uid].visible is False

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_grid_change(self, qapp):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        win._load_from_files(str(PKL_PATH), show_dialog=False)
        win._on_grid_changed(2, 2)
        sheet = win._current_sheet()
        assert sheet.grid_rows == 2
        assert sheet.grid_cols == 2

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_legend_change(self, qapp):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        win._load_from_files(str(PKL_PATH), show_dialog=False)
        win._on_legend_changed("position", "upper left")
        sheet = win._current_sheet()
        assert sheet.legend.position == "upper left"

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_style_change(self, qapp):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        win._load_from_files(str(PKL_PATH), show_dialog=False)
        sheet = win._current_sheet()
        uid = list(sheet.curves.keys())[0]
        win._on_style_changed(uid, "color", "#00FF00")
        assert sheet.curves[uid].color == "#00FF00"

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_export_image(self, qapp, tmp_path):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        win._load_from_files(str(PKL_PATH), show_dialog=False)

        # Direct export (bypassing dialog)
        canvas = win.sheet_tabs.current_canvas()
        img_path = tmp_path / "export_test.png"
        canvas.export_image(str(img_path), dpi=100)
        assert img_path.exists()

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_save_load_project_integration(self, qapp, tmp_path):
        """Full workflow: load data → save project → load project → verify."""
        from packages.report_studio.gui.main_window import ReportStudioWindow
        from packages.report_studio.io.project import save_project, load_project

        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        win._load_from_files(str(PKL_PATH), show_dialog=False)
        sheet = win._current_sheet()
        original_count = len(sheet.curves)

        # Modify something
        uid = list(sheet.curves.keys())[0]
        sheet.curves[uid].color = "#123456"

        # Save
        proj_path = tmp_path / "integration_test.json"
        save_project(win._sheets, proj_path)
        assert proj_path.exists()

        # Load into new "session"
        loaded_sheets = load_project(proj_path)
        assert len(loaded_sheets) == 1
        assert len(loaded_sheets[0].curves) == original_count

        # Verify the modification persisted
        loaded_curve = list(loaded_sheets[0].curves.values())[0]
        # The UIDs match so we should find the modified one
        for lc in loaded_sheets[0].curves.values():
            if lc.uid == uid:
                assert lc.color == "#123456"
                break


# ═══════════════════════════════════════════════════════════════════════
# 7. Full Workflow End-to-End
# ═══════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    @pytest.mark.skipif(
        not PKL_PATH.exists() or not NPZ_PATH.exists(),
        reason="Test data not found"
    )
    def test_full_workflow(self, qapp, tmp_path):
        """
        End-to-end: load PKL+NPZ → assign to subplots → change style
        → change grid → export PNG → save project → load project → verify.
        """
        from packages.report_studio.gui.main_window import ReportStudioWindow
        from packages.report_studio.io.project import save_project, load_project

        # 1. Create window and load data
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        win._load_from_files(str(PKL_PATH), str(NPZ_PATH), show_dialog=False)
        sheet = win._current_sheet()
        assert len(sheet.curves) >= 9

        # 2. Change grid to 2x1
        win._on_grid_changed(2, 1)
        assert sheet.grid_rows == 2
        keys = sheet.subplot_keys_ordered()
        assert len(keys) == 2

        # 3. Move some curves to second subplot
        curve_uids = list(sheet.curves.keys())
        for uid in curve_uids[5:]:
            win._on_curve_moved(uid, keys[1])

        # 4. Change style
        uid0 = curve_uids[0]
        win._on_style_changed(uid0, "color", "#FF0000")
        win._on_style_changed(uid0, "line_width", 3.0)
        assert sheet.curves[uid0].color == "#FF0000"
        assert sheet.curves[uid0].line_width == 3.0

        # 5. Change legend + typography
        win._on_legend_changed("position", "lower right")
        win._on_typography_changed("title_size", 14)
        assert sheet.legend.position == "lower right"
        assert sheet.typography.title_size == 14

        # 6. Export image
        img_path = tmp_path / "e2e_export.png"
        canvas = win.sheet_tabs.current_canvas()
        canvas.export_image(str(img_path), dpi=100)
        assert img_path.exists()
        assert img_path.stat().st_size > 1000  # Non-trivial image

        # 7. Save project
        proj_path = tmp_path / "e2e_project.json"
        save_project(win._sheets, proj_path)
        assert proj_path.exists()

        # 8. Load and verify
        loaded = load_project(proj_path)
        ls = loaded[0]
        assert ls.grid_rows == 2
        assert ls.legend.position == "lower right"
        assert ls.typography.title_size == 14
        assert len(ls.curves) >= 9

        for lc in ls.curves.values():
            if lc.uid == uid0:
                assert lc.color == "#FF0000"
                assert lc.line_width == 3.0
                break


# ═══════════════════════════════════════════════════════════════════════
# 8. Phase 6: Grid Migration, Multi-Select, Layout, Smoke Tests
# ═══════════════════════════════════════════════════════════════════════

class TestGridMigration:
    """Verify curves survive grid changes (1x1 ↔ NxM)."""

    def test_1x1_to_2x2_migrates_curves(self):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        s = SheetState()
        c1 = OffsetCurve(name="a", frequency=np.array([1]), velocity=np.array([1]))
        c2 = OffsetCurve(name="b", frequency=np.array([2]), velocity=np.array([2]))
        s.add_curve(c1)
        s.add_curve(c2)
        assert c1.uid in s.subplots["main"].curve_uids

        s.set_grid(2, 2)
        # Curves should migrate from "main" to "cell_0_0"
        assert "main" not in s.subplots
        assert "cell_0_0" in s.subplots
        assert c1.uid in s.subplots["cell_0_0"].curve_uids
        assert c2.uid in s.subplots["cell_0_0"].curve_uids

    def test_2x2_to_1x1_merges_back(self):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        s = SheetState()
        s.set_grid(2, 2)
        c1 = OffsetCurve(name="a", frequency=np.array([1]), velocity=np.array([1]))
        c2 = OffsetCurve(name="b", frequency=np.array([2]), velocity=np.array([2]))
        s.add_curve(c1, "cell_0_0")
        s.add_curve(c2, "cell_1_1")

        s.set_grid(1, 1)
        assert "main" in s.subplots
        assert c1.uid in s.subplots["main"].curve_uids
        assert c2.uid in s.subplots["main"].curve_uids

    def test_grid_change_preserves_curve_data(self):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        s = SheetState()
        freq = np.array([1.0, 2.0, 3.0])
        vel = np.array([100.0, 200.0, 300.0])
        c = OffsetCurve(name="x", frequency=freq, velocity=vel, color="#AA0000")
        s.add_curve(c)

        s.set_grid(3, 1)
        assert c.uid in s.curves
        assert np.array_equal(s.curves[c.uid].frequency, freq)
        assert s.curves[c.uid].color == "#AA0000"

        s.set_grid(1, 1)
        assert np.array_equal(s.curves[c.uid].velocity, vel)

    def test_multiple_grid_transitions(self):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        s = SheetState()
        curves = []
        for i in range(5):
            c = OffsetCurve(name=f"c{i}", frequency=np.array([i]),
                            velocity=np.array([i * 10]))
            s.add_curve(c)
            curves.append(c)

        # 1x1 → 2x2
        s.set_grid(2, 2)
        assert all(c.uid in s.curves for c in curves)
        # 2x2 → 3x1
        s.set_grid(3, 1)
        assert all(c.uid in s.curves for c in curves)
        # 3x1 → 1x1
        s.set_grid(1, 1)
        assert all(c.uid in s.curves for c in curves)
        assert all(c.uid in s.subplots["main"].curve_uids for c in curves)


class TestLayoutFields:
    """Test new layout fields on SheetState."""

    def test_default_layout_values(self):
        from packages.report_studio.core.models import SheetState
        s = SheetState()
        assert s.figure_width == 10.0
        assert s.figure_height == 7.0
        assert s.hspace == 0.3
        assert s.wspace == 0.3

    def test_layout_fields_persist(self, tmp_path):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        from packages.report_studio.io.project import save_project, load_project
        s = SheetState()
        s.figure_width = 14.0
        s.figure_height = 10.0
        s.hspace = 0.5
        s.wspace = 0.2
        c = OffsetCurve(name="t", frequency=np.array([1]), velocity=np.array([1]))
        s.add_curve(c)

        path = tmp_path / "layout_test.json"
        save_project([s], path)
        loaded = load_project(path)
        ls = loaded[0]
        assert ls.figure_width == 14.0
        assert ls.figure_height == 10.0
        assert ls.hspace == 0.5
        assert ls.wspace == 0.2


class TestMultiSelect:
    """Test multi-select in DataTreePanel."""

    def test_tree_has_extended_selection(self, qapp):
        from packages.report_studio.gui.panels.data_tree import DataTreePanel
        tree = DataTreePanel()
        from packages.report_studio.qt_compat import QtWidgets
        mode = tree._tree.selectionMode()
        try:
            expected = QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        except AttributeError:
            expected = QtWidgets.QAbstractItemView.ExtendedSelection
        assert mode == expected

    def test_curves_selected_signal_exists(self, qapp):
        from packages.report_studio.gui.panels.data_tree import DataTreePanel
        tree = DataTreePanel()
        assert hasattr(tree, 'curves_selected')


class TestBatchProperties:
    """Test batch properties editing for multiple curves."""

    def test_show_curves_batch(self, qapp):
        from packages.report_studio.gui.panels.properties_panel import PropertiesPanel
        from packages.report_studio.core.models import OffsetCurve
        panel = PropertiesPanel()

        c1 = OffsetCurve(name="A", frequency=np.array([1, 2]),
                         velocity=np.array([10, 20]), color="#FF0000")
        c2 = OffsetCurve(name="B", frequency=np.array([3, 4]),
                         velocity=np.array([30, 40]), color="#00FF00")

        panel.show_curves_batch([c1.uid, c2.uid], [c1, c2])
        assert not panel._curve_group.isHidden()
        assert "2 selected" in panel._curve_group.title()
        assert panel._batch_uids == [c1.uid, c2.uid]

    def test_batch_style_emits_for_all(self, qapp, qtbot):
        from packages.report_studio.gui.panels.properties_panel import PropertiesPanel
        from packages.report_studio.core.models import OffsetCurve
        panel = PropertiesPanel()

        c1 = OffsetCurve(name="A", frequency=np.array([1]),
                         velocity=np.array([10]))
        c2 = OffsetCurve(name="B", frequency=np.array([2]),
                         velocity=np.array([20]))

        panel.show_curves_batch([c1.uid, c2.uid], [c1, c2])

        emitted = []
        panel.style_changed.connect(lambda uid, attr, val: emitted.append(uid))

        # Simulate changing line width (triggers _emit_style)
        panel._updating = False
        panel._emit_style("line_width", 3.0)

        assert len(emitted) == 2
        assert c1.uid in emitted
        assert c2.uid in emitted

    def test_single_select_clears_batch(self, qapp):
        from packages.report_studio.gui.panels.properties_panel import PropertiesPanel
        from packages.report_studio.core.models import OffsetCurve
        panel = PropertiesPanel()

        c1 = OffsetCurve(name="A", frequency=np.array([1]),
                         velocity=np.array([10]))
        c2 = OffsetCurve(name="B", frequency=np.array([2]),
                         velocity=np.array([20]))

        # First show batch
        panel.show_curves_batch([c1.uid, c2.uid], [c1, c2])
        assert len(panel._batch_uids) == 2

        # Then select single — should clear batch
        panel.show_curve(c1)
        assert panel._batch_uids == []
        assert panel._current_uid == c1.uid


class TestAssignmentDialog:
    """Tests for the grid-first assignment dialog."""

    def test_dialog_construction(self, qapp):
        from packages.report_studio.gui.panels.assignment_dialog import AssignmentDialog
        from packages.report_studio.core.models import OffsetCurve

        curves = [
            OffsetCurve(name=f"C{i}", frequency=np.array([1]),
                        velocity=np.array([10]))
            for i in range(4)
        ]
        dlg = AssignmentDialog(curves)
        assert dlg._spin_rows.value() == 1
        assert dlg._spin_cols.value() == 1
        # Source list should have all 4 curves
        assert dlg._source_list.count() == 4
        # All curves assigned to "main" by default
        assert len(dlg.assignments.get("main", [])) == 4

    def test_grid_change_updates_slots(self, qapp):
        from packages.report_studio.gui.panels.assignment_dialog import AssignmentDialog
        from packages.report_studio.core.models import OffsetCurve

        curves = [
            OffsetCurve(name=f"C{i}", frequency=np.array([1]),
                        velocity=np.array([10]))
            for i in range(3)
        ]
        dlg = AssignmentDialog(curves)
        dlg._set_grid(2, 2)
        # Should have 4 top-level items (subplots)
        assert dlg._assign_tree.topLevelItemCount() == 4
        assert dlg.grid_rows == 2
        assert dlg.grid_cols == 2
        # All curves migrate to first subplot
        first_key = list(dlg.assignments.keys())[0]
        assert len(dlg.assignments[first_key]) == 3

    def test_assign_and_unassign(self, qapp):
        from packages.report_studio.gui.panels.assignment_dialog import AssignmentDialog
        from packages.report_studio.core.models import OffsetCurve

        curves = [
            OffsetCurve(name="X", frequency=np.array([1]),
                        velocity=np.array([10]))
        ]
        dlg = AssignmentDialog(curves)
        # Switch to 2x1 grid
        dlg._set_grid(2, 1)
        # All curves are in cell_0_0
        assert len(dlg.assignments.get("cell_0_0", [])) == 1
        assert len(dlg.assignments.get("cell_1_0", [])) == 0

        # Select the curve item in assign_tree (child of first top-level)
        top0 = dlg._assign_tree.topLevelItem(0)
        child = top0.child(0)
        dlg._assign_tree.setCurrentItem(child)

        # Unassign it
        dlg._on_unassign()
        assert len(dlg.assignments.get("cell_0_0", [])) == 0

        # Now assign it to the second subplot
        dlg._source_list.setCurrentRow(0)
        # Select target subplot cell_1_0
        top1 = dlg._assign_tree.topLevelItem(1)
        dlg._assign_tree.setCurrentItem(top1)
        dlg._on_assign()
        assert len(dlg.assignments.get("cell_1_0", [])) == 1
        assert dlg.assignments["cell_1_0"][0] == curves[0].uid

    def test_populate_sheet_direct(self, qapp):
        """Verify _populate_sheet_direct adds all curves without dialog."""
        from packages.report_studio.gui.main_window import ReportStudioWindow
        from packages.report_studio.core.models import OffsetCurve
        from packages.report_studio.qt_compat import QtWidgets

        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        curves = [
            OffsetCurve(name=f"T{i}", frequency=np.array([1.0, 2.0]),
                        velocity=np.array([100.0, 200.0]))
            for i in range(5)
        ]
        win._populate_sheet_direct(curves, [])
        sheet = win._current_sheet()
        assert len(sheet.curves) == 5


class TestSmokeEndToEnd:
    """End-to-end smoke test with real data covering all v2.1 features."""

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_full_v21_workflow(self, qapp, tmp_path):
        """
        Load → grid 2×2 → move curves → batch select → layout →
        export → save/load project → verify everything.
        """
        from packages.report_studio.gui.main_window import ReportStudioWindow
        from packages.report_studio.io.project import save_project, load_project

        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        # 1. Load data
        npz = str(NPZ_PATH) if NPZ_PATH.exists() else ""
        win._load_from_files(str(PKL_PATH), npz, show_dialog=False)
        sheet = win._current_sheet()
        n_curves = len(sheet.curves)
        assert n_curves >= 9

        # 2. Set grid 2×2 and verify migration
        win._on_grid_changed(2, 2)
        assert sheet.grid_rows == 2
        assert sheet.grid_cols == 2
        assert len(sheet.curves) == n_curves  # no curves lost

        # 3. Move some curves
        keys = sheet.subplot_keys_ordered()
        uids = list(sheet.curves.keys())
        if len(uids) > 3:
            win._on_curve_moved(uids[3], keys[1])
            assert uids[3] in sheet.subplots[keys[1]].curve_uids

        # 4. Batch select handler
        batch_uids = uids[:3]
        win._on_curves_selected(batch_uids)
        # Right panel should have switched to curve context
        assert win.right_panel is not None

        # 5. Change layout
        win._on_layout_changed("hspace", 0.4)
        win._on_layout_changed("figure_width", 12.0)
        assert sheet.hspace == 0.4
        assert sheet.figure_width == 12.0

        # 6. Change style
        win._on_style_changed(uids[0], "color", "#ABCDEF")
        assert sheet.curves[uids[0]].color == "#ABCDEF"

        # 7. Export image
        img_path = tmp_path / "smoke_v21.png"
        canvas = win.sheet_tabs.current_canvas()
        canvas.export_image(str(img_path), dpi=100)
        assert img_path.exists()
        assert img_path.stat().st_size > 500

        # 8. Save project with layout fields
        proj = tmp_path / "smoke_v21.json"
        save_project(win._sheets, proj)

        # 9. Load and verify
        loaded = load_project(proj)
        ls = loaded[0]
        assert ls.grid_rows == 2
        assert ls.grid_cols == 2
        assert ls.hspace == 0.4
        assert ls.figure_width == 12.0
        assert len(ls.curves) == n_curves
        for lc in ls.curves.values():
            if lc.uid == uids[0]:
                assert lc.color == "#ABCDEF"
                break


# ═══════════════════════════════════════════════════════════════════════
# v2.2 Tests — New panels, exporters, rendering features
# ═══════════════════════════════════════════════════════════════════════


class TestCollapsibleSection:
    """Test the arrow-based collapsible section widget."""

    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.collapsible import CollapsibleSection
        sec = CollapsibleSection("Test Group")
        assert sec is not None
        assert sec.content is not None
        assert sec.form is not None

    def test_collapse_toggle(self, qapp):
        from packages.report_studio.gui.panels.collapsible import CollapsibleSection
        sec = CollapsibleSection("Test", expanded=True)
        assert sec._toggle.isChecked()  # expanded
        # Collapse
        sec._toggle.setChecked(False)
        sec._on_toggle(False)
        assert not sec._toggle.isChecked()
        # Expand
        sec._toggle.setChecked(True)
        sec._on_toggle(True)
        assert sec._toggle.isChecked()

    def test_backward_compat_alias(self, qapp):
        from packages.report_studio.gui.panels.collapsible import CollapsibleGroupBox, CollapsibleSection
        assert CollapsibleGroupBox is CollapsibleSection


class TestSubplotSettingsPanel:
    """Test the new subplot settings panel."""

    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.subplot_settings import SubplotSettingsPanel
        panel = SubplotSettingsPanel()
        assert panel is not None

    def test_show_subplot(self, qapp):
        from packages.report_studio.gui.panels.subplot_settings import SubplotSettingsPanel
        from packages.report_studio.core.models import SubplotState
        panel = SubplotSettingsPanel()
        sp = SubplotState(key="main", name="Test Plot",
                          x_scale="log", y_scale="linear",
                          x_tick_format="sci")
        panel.show_subplot(sp)
        assert panel._edit_name.text() == "Test Plot"
        assert panel._combo_xscale.currentText() == "log"
        assert panel._combo_xtick.currentText() == "sci"

    def test_setting_emits_signal(self, qapp, qtbot):
        from packages.report_studio.gui.panels.subplot_settings import SubplotSettingsPanel
        from packages.report_studio.core.models import SubplotState
        panel = SubplotSettingsPanel()
        sp = SubplotState(key="main")
        panel.show_subplot(sp)

        emitted = []
        panel.setting_changed.connect(lambda k, a, v: emitted.append((k, a, v)))

        panel._combo_xscale.setCurrentText("log")
        assert any(a == "x_scale" and v == "log" for _, a, v in emitted)


class TestCurveSettingsPanel:
    """Test the new curve settings panel."""

    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.curve_settings import CurveSettingsPanel
        panel = CurveSettingsPanel()
        assert panel is not None

    def test_show_curve(self, qapp):
        from packages.report_studio.gui.panels.curve_settings import CurveSettingsPanel
        from packages.report_studio.core.models import OffsetCurve
        panel = CurveSettingsPanel()
        c = OffsetCurve(name="C1", frequency=np.array([1, 2]),
                        velocity=np.array([10, 20]),
                        line_width=2.0, marker_size=5.0)
        panel.show_curve(c)
        assert panel._lbl_name.text() == "C1"
        assert panel._spin_lw.value() == 2.0
        assert panel._spin_ms.value() == 5.0

    def test_batch_mode(self, qapp):
        from packages.report_studio.gui.panels.curve_settings import CurveSettingsPanel
        from packages.report_studio.core.models import OffsetCurve
        panel = CurveSettingsPanel()
        c1 = OffsetCurve(name="A", frequency=np.array([1]), velocity=np.array([10]))
        c2 = OffsetCurve(name="B", frequency=np.array([2]), velocity=np.array([20]))
        panel.show_curves_batch([c1.uid, c2.uid], [c1, c2])
        assert "2 curves" in panel._lbl_name.text()


class TestSpectrumSettingsPanel:
    """Test the new spectrum settings panel."""

    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.spectrum_settings import SpectrumSettingsPanel
        panel = SpectrumSettingsPanel()
        assert panel is not None

    def test_show_spectrum(self, qapp):
        from packages.report_studio.gui.panels.spectrum_settings import SpectrumSettingsPanel
        from packages.report_studio.core.models import OffsetCurve
        panel = SpectrumSettingsPanel()
        c = OffsetCurve(name="S1", frequency=np.array([1]), velocity=np.array([10]),
                        spectrum_cmap="viridis", spectrum_alpha=0.6)
        panel.show_spectrum(c)
        assert panel._combo_cmap.currentText() == "viridis"
        assert abs(panel._spin_alpha.value() - 0.6) < 0.01


class TestGlobalSettingsPanel:
    """Test the new global settings panel."""

    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.global_panel import GlobalSettingsPanel
        panel = GlobalSettingsPanel()
        assert panel is not None

    def test_populate(self, qapp):
        from packages.report_studio.gui.panels.global_panel import GlobalSettingsPanel
        from packages.report_studio.core.models import SheetState
        panel = GlobalSettingsPanel()
        sheet = SheetState()
        sheet.set_grid(2, 3)
        sheet.hspace = 0.4
        sheet.legend.position = "upper left"
        panel.populate(sheet)
        assert panel._spin_rows.value() == 2
        assert panel._spin_cols.value() == 3
        assert abs(panel._spin_hspace.value() - 0.4) < 0.01

    def test_grid_signal(self, qapp, qtbot):
        from packages.report_studio.gui.panels.global_panel import GlobalSettingsPanel
        panel = GlobalSettingsPanel()
        emitted = []
        panel.grid_changed.connect(lambda r, c: emitted.append((r, c)))
        panel._spin_rows.setValue(3)
        assert any(r == 3 for r, _ in emitted)


class TestExportPanel:
    """Test the export panel."""

    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.export_panel import ExportPanel
        panel = ExportPanel()
        assert panel is not None

    def test_update_subplots(self, qapp):
        from packages.report_studio.gui.panels.export_panel import ExportPanel
        panel = ExportPanel()
        panel.update_subplots(["R0C0", "R0C1", "R1C0"])
        assert len(panel._subplot_checks) == 3
        assert "R0C0" in panel._subplot_checks


class TestRightPanel:
    """Test the 3-tab right panel container."""

    def test_construction(self, qapp):
        from packages.report_studio.gui.panels.right_panel import RightPanel
        panel = RightPanel()
        assert panel._tabs.count() == 3

    def test_show_subplot_switches_context(self, qapp):
        from packages.report_studio.gui.panels.right_panel import RightPanel
        from packages.report_studio.core.models import SubplotState
        panel = RightPanel()
        sp = SubplotState(key="main")
        panel.show_subplot(sp)
        assert panel._context_stack.currentIndex() == RightPanel._IDX_SUBPLOT

    def test_show_curve_switches_context(self, qapp):
        from packages.report_studio.gui.panels.right_panel import RightPanel
        from packages.report_studio.core.models import OffsetCurve
        panel = RightPanel()
        c = OffsetCurve(name="C", frequency=np.array([1]), velocity=np.array([10]))
        panel.show_curve(c)
        assert panel._context_stack.currentIndex() == RightPanel._IDX_CURVE

    def test_show_spectrum_switches_context(self, qapp):
        from packages.report_studio.gui.panels.right_panel import RightPanel
        from packages.report_studio.core.models import OffsetCurve
        panel = RightPanel()
        c = OffsetCurve(name="S", frequency=np.array([1]), velocity=np.array([10]))
        panel.show_spectrum(c)
        assert panel._context_stack.currentIndex() == RightPanel._IDX_SPECTRUM

    def test_populate_global(self, qapp):
        from packages.report_studio.gui.panels.right_panel import RightPanel
        from packages.report_studio.core.models import SheetState
        panel = RightPanel()
        sheet = SheetState()
        sheet.set_grid(2, 2)
        panel.populate_global(sheet)
        assert panel.global_panel._spin_rows.value() == 2


class TestCurveExporter:
    """Test the modular curve data exporter."""

    def test_can_export_empty(self):
        from packages.report_studio.core.exporters.curve_exporter import CurveExporter
        from packages.report_studio.core.models import SheetState
        exp = CurveExporter()
        sheet = SheetState()
        assert not exp.can_export(sheet)

    def test_can_export_with_curves(self):
        from packages.report_studio.core.exporters.curve_exporter import CurveExporter
        from packages.report_studio.core.models import SheetState, OffsetCurve
        exp = CurveExporter()
        sheet = SheetState()
        c = OffsetCurve(name="T", frequency=np.array([1, 2]),
                        velocity=np.array([100, 200]))
        sheet.add_curve(c)
        assert exp.can_export(sheet)

    def test_export_csv(self, tmp_path):
        from packages.report_studio.core.exporters.curve_exporter import CurveExporter
        from packages.report_studio.core.models import SheetState, OffsetCurve
        exp = CurveExporter()
        sheet = SheetState()
        c = OffsetCurve(name="Test", frequency=np.array([1.0, 2.0, 3.0]),
                        velocity=np.array([100.0, 200.0, 300.0]))
        sheet.add_curve(c)
        msg = exp.export(sheet, str(tmp_path), {"format": "csv"})
        assert "1 curves" in msg
        csv_files = list(tmp_path.glob("*.csv"))
        assert len(csv_files) == 1


class TestDualDpiRendering:
    """Test the dual-quality rendering pipeline."""

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_draft_quality_render(self, qapp):
        from packages.report_studio.io.pkl_reader import read_pkl
        from packages.report_studio.core.models import SheetState
        from packages.report_studio.rendering.renderer import render_sheet
        from packages.report_studio.rendering.style import StyleConfig
        import matplotlib.pyplot as plt

        curves = read_pkl(str(PKL_PATH))
        sheet = SheetState()
        for c in curves[:3]:
            sheet.add_curve(c)

        style = StyleConfig()
        fig = plt.figure()
        render_sheet(fig, sheet, style, quality="draft")
        assert len(fig.axes) > 0
        plt.close(fig)

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_high_quality_render(self, qapp):
        from packages.report_studio.io.pkl_reader import read_pkl
        from packages.report_studio.core.models import SheetState
        from packages.report_studio.rendering.renderer import render_sheet
        from packages.report_studio.rendering.style import StyleConfig
        import matplotlib.pyplot as plt

        curves = read_pkl(str(PKL_PATH))
        sheet = SheetState()
        for c in curves[:3]:
            sheet.add_curve(c)

        style = StyleConfig()
        fig = plt.figure()
        render_sheet(fig, sheet, style, quality="high")
        assert len(fig.axes) > 0
        plt.close(fig)


class TestRendererScales:
    """Test log-scale and tick-format rendering."""

    def test_log_scale_x(self, qapp):
        from packages.report_studio.core.models import SheetState, OffsetCurve, SubplotState
        from packages.report_studio.rendering.renderer import render_sheet
        from packages.report_studio.rendering.style import StyleConfig
        import matplotlib.pyplot as plt

        sheet = SheetState()
        c = OffsetCurve(name="Log", frequency=np.array([1.0, 10.0, 100.0]),
                        velocity=np.array([100.0, 200.0, 300.0]))
        sheet.add_curve(c)
        # Set x_scale to log on first subplot
        key = sheet.subplot_keys_ordered()[0]
        sheet.subplots[key].x_scale = "log"

        style = StyleConfig()
        fig = plt.figure()
        render_sheet(fig, sheet, style)
        ax = fig.axes[0]
        assert ax.get_xscale() == "log"
        plt.close(fig)

    def test_tick_format_sci(self, qapp):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        from packages.report_studio.rendering.renderer import render_sheet
        from packages.report_studio.rendering.style import StyleConfig
        import matplotlib.pyplot as plt

        sheet = SheetState()
        c = OffsetCurve(name="Sci", frequency=np.array([1000.0, 2000.0, 3000.0]),
                        velocity=np.array([100.0, 200.0, 300.0]))
        sheet.add_curve(c)
        key = sheet.subplot_keys_ordered()[0]
        sheet.subplots[key].x_tick_format = "sci"

        style = StyleConfig()
        fig = plt.figure()
        render_sheet(fig, sheet, style)
        assert len(fig.axes) > 0
        plt.close(fig)


class TestPerSubplotFonts:
    """Test per-subplot font override rendering."""

    def test_subplot_font_override(self, qapp):
        from packages.report_studio.core.models import SheetState, OffsetCurve
        from packages.report_studio.rendering.renderer import render_sheet
        from packages.report_studio.rendering.style import StyleConfig
        import matplotlib.pyplot as plt

        sheet = SheetState()
        c = OffsetCurve(name="Font", frequency=np.array([1.0, 2.0]),
                        velocity=np.array([10.0, 20.0]))
        sheet.add_curve(c)
        key = sheet.subplot_keys_ordered()[0]
        sheet.subplots[key].title_font_size = 16
        sheet.subplots[key].name = "Custom Title"

        style = StyleConfig()
        fig = plt.figure()
        render_sheet(fig, sheet, style)
        ax = fig.axes[0]
        assert ax.get_title() == "Custom Title"
        plt.close(fig)


class TestV22MainWindowIntegration:
    """Integration tests for v2.2 right panel wiring."""

    def test_right_panel_exists(self, qapp):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        assert hasattr(win, "right_panel")
        assert win.right_panel._tabs.count() == 3

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_curve_select_shows_context(self, qapp):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        win._load_from_files(str(PKL_PATH), show_dialog=False)
        sheet = win._current_sheet()
        uid = list(sheet.curves.keys())[0]
        win._on_curve_selected(uid)

        from packages.report_studio.gui.panels.right_panel import RightPanel
        assert win.right_panel._context_stack.currentIndex() == RightPanel._IDX_CURVE

    @pytest.mark.skipif(not PKL_PATH.exists(), reason="Test PKL not found")
    def test_subplot_click_shows_context(self, qapp):
        from packages.report_studio.gui.main_window import ReportStudioWindow
        win = ReportStudioWindow.__new__(ReportStudioWindow)
        win._controller = None
        win._sheets = []
        win._selected_uid = None
        from packages.report_studio.qt_compat import QtWidgets
        QtWidgets.QMainWindow.__init__(win)
        win._build_ui()
        win._setup_menubar()
        win._connect_signals()

        win._load_from_files(str(PKL_PATH), show_dialog=False)
        sheet = win._current_sheet()
        key = sheet.subplot_keys_ordered()[0]
        win._on_subplot_clicked(key)

        from packages.report_studio.gui.panels.right_panel import RightPanel
        assert win.right_panel._context_stack.currentIndex() == RightPanel._IDX_SUBPLOT
