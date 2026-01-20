"""Tests for circular_array subpackage - Phase 1 components."""
from __future__ import annotations

import tempfile
from pathlib import Path
import numpy as np
import pytest

from dc_cut.circular_array.config import Stage, ArrayConfig, WorkflowConfig
from dc_cut.circular_array.io import (
    load_multi_array_klimits,
    export_stage_to_mat,
    export_dinver_txt,
)


class TestStage:
    """Tests for Stage enum."""

    def test_stage_next_initial(self):
        assert Stage.INITIAL.next() == Stage.INTERMEDIATE

    def test_stage_next_intermediate(self):
        assert Stage.INTERMEDIATE.next() == Stage.REFINED

    def test_stage_next_refined_is_none(self):
        assert Stage.REFINED.next() is None

    def test_stage_prev_initial_is_none(self):
        assert Stage.INITIAL.prev() is None

    def test_stage_prev_intermediate(self):
        assert Stage.INTERMEDIATE.prev() == Stage.INITIAL

    def test_stage_prev_refined(self):
        assert Stage.REFINED.prev() == Stage.INTERMEDIATE

    def test_stage_display_name(self):
        assert Stage.INITIAL.display_name == "Initial"
        assert Stage.INTERMEDIATE.display_name == "Intermediate"
        assert Stage.REFINED.display_name == "Refined"


class TestArrayConfig:
    """Tests for ArrayConfig dataclass."""

    def test_array_config_creation(self):
        cfg = ArrayConfig(
            diameter=500,
            max_file_path=Path("/test/500m.max"),
            kmin=0.002,
            kmax=0.02,
        )
        assert cfg.diameter == 500
        assert cfg.kmin == 0.002
        assert cfg.kmax == 0.02

    def test_array_config_path_conversion(self):
        cfg = ArrayConfig(
            diameter=200,
            max_file_path="/test/200m.max",
            kmin=0.005,
            kmax=0.05,
        )
        assert isinstance(cfg.max_file_path, Path)

    def test_array_config_invalid_klimits(self):
        with pytest.raises(ValueError, match="kmin.*must be less than kmax"):
            ArrayConfig(diameter=50, max_file_path="/test.max", kmin=0.1, kmax=0.01)


class TestWorkflowConfig:
    """Tests for WorkflowConfig dataclass."""

    @pytest.fixture
    def sample_config(self, tmp_path):
        return WorkflowConfig(
            site_name="TestSite",
            output_dir=tmp_path,
            arrays=[
                ArrayConfig(500, tmp_path / "500m.max", 0.002, 0.02),
                ArrayConfig(200, tmp_path / "200m.max", 0.005, 0.05),
                ArrayConfig(50, tmp_path / "50m.max", 0.02, 0.2),
            ],
        )

    def test_config_creation(self, sample_config):
        assert sample_config.site_name == "TestSite"
        assert len(sample_config.arrays) == 3
        assert sample_config.current_stage == Stage.INITIAL

    def test_config_empty_site_name_raises(self, tmp_path):
        with pytest.raises(ValueError, match="site_name cannot be empty"):
            WorkflowConfig(site_name="", output_dir=tmp_path, arrays=[])

    def test_get_klimits_for_array(self, sample_config):
        kmin, kmax = sample_config.get_klimits_for_array(500)
        assert kmin == 0.002
        assert kmax == 0.02

    def test_get_klimits_for_invalid_array(self, sample_config):
        with pytest.raises(ValueError, match="No array with diameter"):
            sample_config.get_klimits_for_array(100)

    def test_get_array_diameters(self, sample_config):
        diameters = sample_config.get_array_diameters()
        assert diameters == [500, 200, 50]

    def test_get_state_path(self, sample_config, tmp_path):
        path = sample_config.get_state_path(Stage.INITIAL)
        assert path == tmp_path / "TestSite_Initial.pkl"

    def test_get_mat_path(self, sample_config, tmp_path):
        path = sample_config.get_mat_path(Stage.INTERMEDIATE)
        assert path == tmp_path / "TestSite_Intermediate.mat"

    def test_get_dinver_path(self, sample_config, tmp_path):
        path = sample_config.get_dinver_path()
        assert path == tmp_path / "TestSite_dinver.txt"

    def test_to_dict_and_from_dict(self, sample_config):
        data = sample_config.to_dict()
        restored = WorkflowConfig.from_dict(data)

        assert restored.site_name == sample_config.site_name
        assert restored.wave_type == sample_config.wave_type
        assert len(restored.arrays) == len(sample_config.arrays)
        assert restored.arrays[0].diameter == 500


class TestLoadKlimits:
    """Tests for load_multi_array_klimits function."""

    def test_load_klimits_csv(self, tmp_path):
        csv_path = tmp_path / "klimits.csv"
        csv_path.write_text(
            "# k-limits for circular arrays\n"
            "500, 0.002, 0.02\n"
            "200, 0.005, 0.05\n"
            "50, 0.02, 0.2\n"
        )

        result = load_multi_array_klimits(csv_path)

        assert result[500] == (0.002, 0.02)
        assert result[200] == (0.005, 0.05)
        assert result[50] == (0.02, 0.2)

    def test_load_klimits_csv_space_separated(self, tmp_path):
        csv_path = tmp_path / "klimits.csv"
        csv_path.write_text("500 0.002 0.02\n200 0.005 0.05\n")

        result = load_multi_array_klimits(csv_path)

        assert result[500] == (0.002, 0.02)
        assert result[200] == (0.005, 0.05)

    def test_load_klimits_mat(self, tmp_path):
        pytest.importorskip("scipy")
        from scipy.io import savemat

        mat_path = tmp_path / "klimits.mat"
        savemat(str(mat_path), {
            'klimits': np.array([
                [500, 0.002, 0.02],
                [200, 0.005, 0.05],
                [50, 0.02, 0.2],
            ])
        })

        result = load_multi_array_klimits(mat_path)

        assert result[500] == (0.002, 0.02)
        assert result[200] == (0.005, 0.05)
        assert result[50] == (0.02, 0.2)

    def test_load_klimits_invalid_format(self, tmp_path):
        txt_path = tmp_path / "klimits.txt"
        txt_path.write_text("invalid")

        with pytest.raises(ValueError, match="Unsupported klimits file format"):
            load_multi_array_klimits(txt_path)

    def test_load_klimits_empty_csv(self, tmp_path):
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("# only comments\n")

        with pytest.raises(ValueError, match="No valid klimits rows"):
            load_multi_array_klimits(csv_path)


class TestExportStageMat:
    """Tests for export_stage_to_mat function."""

    def test_export_stage_to_mat(self, tmp_path):
        pytest.importorskip("scipy")
        from scipy.io import loadmat

        vel = [np.array([100.0, 200.0, 300.0]), np.array([150.0, 250.0])]
        freq = [np.array([1.0, 2.0, 3.0]), np.array([2.0, 3.0])]
        wlen = [np.array([100.0, 100.0, 100.0]), np.array([75.0, 83.3])]
        labels = ["500m Array", "200m Array"]

        out_path = tmp_path / "test_stage.mat"
        export_stage_to_mat(vel, freq, wlen, labels, out_path, "TestSite", "Initial")

        assert out_path.exists()

        data = loadmat(str(out_path))
        assert data['site_name'][0] == "TestSite"
        assert data['stage'][0] == "Initial"
        assert data['num_layers'][0, 0] == 2
        assert len(data['velocity_1'].flatten()) == 3
        assert len(data['velocity_2'].flatten()) == 2
        assert len(data['velocity_all'].flatten()) == 5


class TestExportDinverTxt:
    """Tests for export_dinver_txt function."""

    def test_export_dinver_txt(self, tmp_path):
        freq = np.array([1.0, 2.0, 3.0])
        slow_mean = np.array([0.005, 0.004, 0.003])
        slow_std = np.array([0.001, 0.001, 0.001])
        num_points = np.array([10, 20, 30])

        out_path = tmp_path / "test_dinver.txt"
        export_dinver_txt(freq, slow_mean, slow_std, num_points, out_path)

        assert out_path.exists()

        content = out_path.read_text()
        lines = [l for l in content.split('\n') if l and not l.startswith('#')]
        assert len(lines) == 3

        parts = lines[0].split()
        assert float(parts[0]) == pytest.approx(1.0)
        assert float(parts[1]) == pytest.approx(0.005)

    def test_export_dinver_txt_skips_nan(self, tmp_path):
        freq = np.array([1.0, 2.0, 3.0])
        slow_mean = np.array([0.005, np.nan, 0.003])
        slow_std = np.array([0.001, 0.001, 0.001])
        num_points = np.array([10, 20, 30])

        out_path = tmp_path / "test_dinver_nan.txt"
        export_dinver_txt(freq, slow_mean, slow_std, num_points, out_path)

        content = out_path.read_text()
        lines = [l for l in content.split('\n') if l and not l.startswith('#')]
        assert len(lines) == 2


class TestPackageImports:
    """Test that package imports work correctly."""

    def test_import_from_package(self):
        from dc_cut.circular_array import (
            WorkflowConfig,
            Stage,
            ArrayConfig,
            load_multi_array_klimits,
            export_stage_to_mat,
            export_dinver_txt,
        )

        assert WorkflowConfig is not None
        assert Stage is not None
        assert ArrayConfig is not None


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for all tests in module."""
    try:
        from matplotlib.backends import qt_compat
        QtWidgets = qt_compat.QtWidgets
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])
        yield app
    except Exception:
        pytest.skip("Qt not available")


class TestCircularArrayTab:
    """Tests for CircularArrayTab widget - Phase 2."""

    def test_tab_get_config_new_workflow(self, tmp_path, qapp):
        """Test config generation for new workflow."""
        from dc_cut.gui.open_data import CircularArrayTab

        tab = CircularArrayTab()
        tab.site_name.setText("TestSite")
        tab.output_dir.setText(str(tmp_path))
        tab.path_500m.setText(str(tmp_path / "500m.max"))
        tab.klimits_path.setText(str(tmp_path / "klimits.csv"))

        config = tab.get_config()

        assert config['mode'] == 'circular_array_new'
        assert config['site_name'] == "TestSite"
        assert config['output_dir'] == str(tmp_path)
        assert config['arrays'][500] == str(tmp_path / "500m.max")
        assert config['arrays'][200] is None
        assert config['wave_type'] == 'Rayleigh_Vertical'

    def test_tab_get_config_continue(self, tmp_path, qapp):
        """Test config generation for continue mode."""
        from dc_cut.gui.open_data import CircularArrayTab

        session_file = tmp_path / "test.pkl"
        session_file.write_bytes(b"test")

        tab = CircularArrayTab()
        tab.continue_path.setText(str(session_file))

        config = tab.get_config()

        assert config['mode'] == 'circular_array_continue'
        assert config['session_path'] == str(session_file)

    def test_tab_validate_missing_site_name(self, tmp_path, qapp):
        """Test validation fails without site name."""
        from dc_cut.gui.open_data import CircularArrayTab

        tab = CircularArrayTab()
        tab.output_dir.setText(str(tmp_path))
        tab.path_500m.setText(str(tmp_path / "500m.max"))
        tab.klimits_path.setText(str(tmp_path / "klimits.csv"))

        is_valid, error = tab.validate()
        assert not is_valid
        assert "site name" in error.lower()

    def test_tab_validate_missing_output_dir(self, tmp_path, qapp):
        """Test validation fails without output directory."""
        from dc_cut.gui.open_data import CircularArrayTab

        tab = CircularArrayTab()
        tab.site_name.setText("TestSite")
        tab.path_500m.setText(str(tmp_path / "500m.max"))
        tab.klimits_path.setText(str(tmp_path / "klimits.csv"))

        is_valid, error = tab.validate()
        assert not is_valid
        assert "output directory" in error.lower()

    def test_tab_validate_no_arrays(self, tmp_path, qapp):
        """Test validation fails without any array files."""
        from dc_cut.gui.open_data import CircularArrayTab

        tab = CircularArrayTab()
        tab.site_name.setText("TestSite")
        tab.output_dir.setText(str(tmp_path))
        tab.klimits_path.setText(str(tmp_path / "klimits.csv"))

        is_valid, error = tab.validate()
        assert not is_valid
        assert "array" in error.lower()

    def test_tab_validate_missing_klimits(self, tmp_path, qapp):
        """Test validation fails without klimits file."""
        from dc_cut.gui.open_data import CircularArrayTab

        max_file = tmp_path / "500m.max"
        max_file.write_text("test")

        tab = CircularArrayTab()
        tab.site_name.setText("TestSite")
        tab.output_dir.setText(str(tmp_path))
        tab.path_500m.setText(str(max_file))

        is_valid, error = tab.validate()
        assert not is_valid
        assert "k-limits" in error.lower()

    def test_tab_validate_success(self, tmp_path, qapp):
        """Test validation passes with all required fields."""
        from dc_cut.gui.open_data import CircularArrayTab

        max_file = tmp_path / "500m.max"
        max_file.write_text("test")
        klimits_file = tmp_path / "klimits.csv"
        klimits_file.write_text("500,0.002,0.02")

        tab = CircularArrayTab()
        tab.site_name.setText("TestSite")
        tab.output_dir.setText(str(tmp_path))
        tab.path_500m.setText(str(max_file))
        tab.klimits_path.setText(str(klimits_file))

        is_valid, error = tab.validate()
        assert is_valid
        assert error == ""

    def test_tab_wave_type_selection(self, tmp_path, qapp):
        """Test wave type radio button selection."""
        from dc_cut.gui.open_data import CircularArrayTab

        tab = CircularArrayTab()
        tab.site_name.setText("TestSite")
        tab.output_dir.setText(str(tmp_path))

        assert tab._get_wave_type() == "Rayleigh_Vertical"

        tab.wave_radial.setChecked(True)
        assert tab._get_wave_type() == "Rayleigh_Radial"

        tab.wave_transverse.setChecked(True)
        assert tab._get_wave_type() == "Love_Transverse"


class TestCircularArrayOrchestrator:
    """Tests for CircularArrayOrchestrator - Phase 3."""

    def test_orchestrator_creation(self, tmp_path):
        """Test orchestrator creation with config."""
        from dc_cut.circular_array.orchestrator import CircularArrayOrchestrator
        from dc_cut.circular_array.config import WorkflowConfig, ArrayConfig, Stage

        config = WorkflowConfig(
            site_name="TestSite",
            output_dir=tmp_path,
            arrays=[
                ArrayConfig(diameter=500, max_file_path=tmp_path / "500.max", kmin=0.002, kmax=0.02),
            ],
        )
        orch = CircularArrayOrchestrator(config)

        assert orch.current_stage == Stage.INITIAL
        assert orch.stage_number == 1
        assert orch.total_stages == 3
        assert orch.is_first_stage
        assert not orch.is_last_stage

    def test_orchestrator_stage_navigation(self, tmp_path):
        """Test stage advancement and retreat."""
        from dc_cut.circular_array.orchestrator import CircularArrayOrchestrator
        from dc_cut.circular_array.config import WorkflowConfig, ArrayConfig, Stage

        config = WorkflowConfig(
            site_name="TestSite",
            output_dir=tmp_path,
            arrays=[ArrayConfig(diameter=500, max_file_path=tmp_path / "500.max", kmin=0.002, kmax=0.02)],
        )
        orch = CircularArrayOrchestrator(config)

        assert orch.can_advance()
        assert not orch.can_go_back()

        next_stage = orch.advance_stage()
        assert next_stage == Stage.INTERMEDIATE
        assert orch.current_stage == Stage.INTERMEDIATE
        assert orch.stage_number == 2

        assert orch.can_advance()
        assert orch.can_go_back()

        next_stage = orch.advance_stage()
        assert next_stage == Stage.REFINED
        assert orch.is_last_stage
        assert not orch.can_advance()

        prev_stage = orch.retreat_stage()
        assert prev_stage == Stage.INTERMEDIATE
        assert orch.current_stage == Stage.INTERMEDIATE

    def test_orchestrator_array_focus(self, tmp_path):
        """Test array focus selection."""
        from dc_cut.circular_array.orchestrator import CircularArrayOrchestrator
        from dc_cut.circular_array.config import WorkflowConfig, ArrayConfig

        config = WorkflowConfig(
            site_name="TestSite",
            output_dir=tmp_path,
            arrays=[
                ArrayConfig(diameter=500, max_file_path=tmp_path / "500.max", kmin=0.002, kmax=0.02),
                ArrayConfig(diameter=200, max_file_path=tmp_path / "200.max", kmin=0.005, kmax=0.05),
            ],
        )
        orch = CircularArrayOrchestrator(config)

        assert orch.focused_array == 500

        orch.set_array_focus(200)
        assert orch.focused_array == 200

        with pytest.raises(ValueError):
            orch.set_array_focus(50)

    def test_orchestrator_path_generation(self, tmp_path):
        """Test state and mat path generation."""
        from dc_cut.circular_array.orchestrator import CircularArrayOrchestrator
        from dc_cut.circular_array.config import WorkflowConfig, ArrayConfig, Stage

        config = WorkflowConfig(
            site_name="TestSite",
            output_dir=tmp_path,
            arrays=[ArrayConfig(diameter=500, max_file_path=tmp_path / "500.max", kmin=0.002, kmax=0.02)],
        )
        orch = CircularArrayOrchestrator(config)

        assert orch.get_previous_stage_path() is None

        orch.advance_stage()
        prev_path = orch.get_previous_stage_path()
        assert prev_path is not None
        assert "Initial" in str(prev_path)

    def test_orchestrator_status_summary(self, tmp_path):
        """Test status summary generation."""
        from dc_cut.circular_array.orchestrator import CircularArrayOrchestrator
        from dc_cut.circular_array.config import WorkflowConfig, ArrayConfig

        config = WorkflowConfig(
            site_name="MySite",
            output_dir=tmp_path,
            arrays=[ArrayConfig(diameter=500, max_file_path=tmp_path / "500.max", kmin=0.002, kmax=0.02)],
            wave_type="Love_Transverse",
        )
        orch = CircularArrayOrchestrator(config)

        summary = orch.get_status_summary()
        assert "MySite" in summary
        assert "Initial" in summary
        assert "Love_Transverse" in summary


@pytest.fixture
def workflow_dock_setup(tmp_path, qapp):
    """Set up orchestrator and dock for workflow dock tests."""
    try:
        from dc_cut.circular_array.workflow_dock import CircularArrayWorkflowDock
        from dc_cut.circular_array.orchestrator import CircularArrayOrchestrator
        from dc_cut.circular_array.config import WorkflowConfig, ArrayConfig

        config = WorkflowConfig(
            site_name="TestSite",
            output_dir=tmp_path,
            arrays=[ArrayConfig(diameter=500, max_file_path=tmp_path / "500.max", kmin=0.002, kmax=0.02)],
        )
        orch = CircularArrayOrchestrator(config)
        dock = CircularArrayWorkflowDock(orch)
        return orch, dock
    except Exception as e:
        pytest.skip(f"WorkflowDock setup failed: {e}")


@pytest.mark.skipif(
    not hasattr(__import__('sys'), 'stdin') or not __import__('sys').stdin.isatty(),
    reason="Skip Qt dock tests in non-interactive environment"
)
class TestCircularArrayWorkflowDock:
    """Tests for CircularArrayWorkflowDock - Phase 3."""

    def test_workflow_dock_creation(self, workflow_dock_setup):
        """Test workflow dock creation."""
        orch, dock = workflow_dock_setup
        assert dock is not None
        assert dock.orchestrator is orch

    def test_workflow_dock_button_states(self, workflow_dock_setup):
        """Test button enabled states based on stage."""
        orch, dock = workflow_dock_setup

        assert not dock._btn_back.isEnabled()
        assert dock._btn_next.isEnabled()

        orch.advance_stage()
        dock.refresh()

        assert dock._btn_back.isEnabled()
        assert dock._btn_next.isEnabled()

    def test_workflow_dock_array_group_visibility(self, workflow_dock_setup):
        """Test array focus group visibility per stage."""
        orch, dock = workflow_dock_setup

        assert dock._array_group.isVisible()

        orch.advance_stage()
        dock.refresh()

        assert not dock._array_group.isVisible()


class TestPackageImportsPhase3:
    """Test Phase 3 package imports."""

    def test_import_orchestrator(self):
        """Test importing orchestrator from package."""
        from dc_cut.circular_array import CircularArrayOrchestrator
        assert CircularArrayOrchestrator is not None

    def test_import_workflow_dock(self):
        """Test importing workflow dock from package."""
        pytest.importorskip("matplotlib")
        from dc_cut.circular_array import CircularArrayWorkflowDock
        assert CircularArrayWorkflowDock is not None


class TestExportToMat:
    """Tests for export_to_mat function - Phase 4."""

    def test_export_to_mat_creates_file(self, tmp_path):
        """Test that export_to_mat creates a valid MAT file."""
        from dc_cut.io.export import export_to_mat
        import scipy.io as sio

        vel = [np.array([100, 200, 300]), np.array([150, 250])]
        freq = [np.array([1.0, 2.0, 3.0]), np.array([1.5, 2.5])]
        wave = [np.array([100, 100, 100]), np.array([100, 100])]
        labels = ["Layer1", "Layer2"]

        out_path = tmp_path / "test_export.mat"
        export_to_mat(vel, freq, wave, labels, str(out_path), site_name="TestSite", stage_name="Initial")

        assert out_path.exists()

        data = sio.loadmat(str(out_path))
        assert data['site_name'][0] == "TestSite"
        assert data['stage'][0] == "Initial"
        assert data['num_layers'] == 2
        assert 'velocity_1' in data
        assert 'velocity_2' in data
        assert 'velocity_all' in data

    def test_export_to_mat_with_wave_type(self, tmp_path):
        """Test export_to_mat includes wave_type metadata."""
        from dc_cut.io.export import export_to_mat
        import scipy.io as sio

        vel = [np.array([100, 200])]
        freq = [np.array([1.0, 2.0])]
        wave = [np.array([100, 100])]
        labels = ["Layer1"]

        out_path = tmp_path / "test_wave.mat"
        export_to_mat(vel, freq, wave, labels, str(out_path), wave_type="Love_Transverse")

        data = sio.loadmat(str(out_path))
        assert data['wave_type'][0] == "Love_Transverse"

    def test_export_to_mat_slowness_calculation(self, tmp_path):
        """Test slowness is correctly calculated from velocity."""
        from dc_cut.io.export import export_to_mat
        import scipy.io as sio

        vel = [np.array([1000.0, 2000.0])]
        freq = [np.array([1.0, 2.0])]
        wave = [np.array([1000.0, 1000.0])]
        labels = ["Test"]

        out_path = tmp_path / "test_slow.mat"
        export_to_mat(vel, freq, wave, labels, str(out_path))

        data = sio.loadmat(str(out_path))
        slow = data['slowness_1'].flatten()
        np.testing.assert_array_almost_equal(slow, [1.0, 0.5])

    def test_export_to_mat_empty_arrays(self, tmp_path):
        """Test export_to_mat handles empty arrays."""
        from dc_cut.io.export import export_to_mat

        out_path = tmp_path / "test_empty.mat"
        export_to_mat([], [], [], [], str(out_path))

        assert out_path.exists()


class TestDinverExport:
    """Tests for dinver export format - Phase 4."""

    def test_dinver_txt_format(self, tmp_path):
        """Test dinver txt export has correct format."""
        from dc_cut.circular_array.io import export_dinver_txt

        freq = np.array([1.0, 2.0, 3.0])
        slow_mean = np.array([0.5, 0.4, 0.3])
        slow_std = np.array([0.01, 0.02, 0.03])
        num_pts = np.array([10, 20, 30])

        out_path = tmp_path / "test_dinver.txt"
        export_dinver_txt(freq, slow_mean, slow_std, num_pts, out_path)

        content = out_path.read_text()
        lines = [l for l in content.strip().split('\n') if not l.startswith('#')]

        assert len(lines) == 3
        parts = lines[0].split()
        assert len(parts) == 4
        assert float(parts[0]) == pytest.approx(1.0)
        assert float(parts[1]) == pytest.approx(0.5)


class TestMainWindowIntegration:
    """Tests for main_window circular array integration - Phase 4."""

    def test_import_main_window(self):
        """Test main_window imports successfully."""
        pytest.importorskip("matplotlib")
        from dc_cut.gui.main_window import MainWindow, show_shell
        assert MainWindow is not None
        assert show_shell is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
