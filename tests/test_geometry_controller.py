"""Tests for GeometryController — data model mediator.

Tests mutation methods, signal emissions, re-entrancy guard,
and edge cases (min stages, invalid indices).
"""

import pytest
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication
import sys

from app.models.geometry import (
    CollimatorType, FocalSpotDistribution, StagePurpose,
    ApertureConfig,
)
from app.ui.canvas.geometry_controller import GeometryController

# QApplication instance needed for QObject / signals
_app = QApplication.instance() or QApplication(sys.argv)


class TestControllerDefaults:
    """Default state after construction."""

    def setup_method(self):
        self.ctrl = GeometryController()

    def test_default_geometry_is_slit(self):
        assert self.ctrl.geometry.type == CollimatorType.SLIT

    def test_default_active_stage_is_0(self):
        assert self.ctrl.active_stage_index == 0

    def test_default_has_stages(self):
        assert self.ctrl.geometry.stage_count >= 1

    def test_active_stage_returns_first(self):
        assert self.ctrl.active_stage is not None
        assert self.ctrl.active_stage is self.ctrl.geometry.stages[0]


class TestLoadTemplate:
    """Template loading and type switching."""

    def setup_method(self):
        self.ctrl = GeometryController()

    def test_load_pencil_beam(self):
        self.ctrl.load_template(CollimatorType.PENCIL_BEAM)
        assert self.ctrl.geometry.type == CollimatorType.PENCIL_BEAM
        assert self.ctrl.geometry.stage_count == 1

    def test_load_slit(self):
        self.ctrl.load_template(CollimatorType.SLIT)
        assert self.ctrl.geometry.type == CollimatorType.SLIT
        assert self.ctrl.geometry.stage_count == 1

    def test_load_fan_beam(self):
        self.ctrl.load_template(CollimatorType.FAN_BEAM)
        assert self.ctrl.geometry.type == CollimatorType.FAN_BEAM
        assert self.ctrl.geometry.stage_count == 3

    def test_load_template_emits_geometry_changed(self):
        spy = MagicMock()
        self.ctrl.geometry_changed.connect(spy)
        self.ctrl.load_template(CollimatorType.SLIT)
        spy.assert_called_once()

    def test_set_collimator_type_emits_type_signal(self):
        spy = MagicMock()
        self.ctrl.collimator_type_changed.connect(spy)
        self.ctrl.set_collimator_type(CollimatorType.PENCIL_BEAM)
        spy.assert_called_once_with(CollimatorType.PENCIL_BEAM)

    def test_load_resets_active_stage_to_0(self):
        self.ctrl.select_stage(2)  # fan beam has 3 stages
        self.ctrl.load_template(CollimatorType.PENCIL_BEAM)
        assert self.ctrl.active_stage_index == 0


class TestStageMutations:
    """Stage add / remove / select / move / edit."""

    def setup_method(self):
        self.ctrl = GeometryController()
        # Load fan-beam (3 stages) for multi-stage tests
        self.ctrl.load_template(CollimatorType.FAN_BEAM)

    def test_add_stage_increases_count(self):
        before = self.ctrl.geometry.stage_count
        self.ctrl.add_stage()
        assert self.ctrl.geometry.stage_count == before + 1

    def test_add_stage_emits_signal(self):
        spy = MagicMock()
        self.ctrl.stage_added.connect(spy)
        self.ctrl.add_stage()
        spy.assert_called_once()

    def test_remove_stage_decreases_count(self):
        before = self.ctrl.geometry.stage_count
        self.ctrl.remove_stage(1)
        assert self.ctrl.geometry.stage_count == before - 1

    def test_remove_stage_emits_signal(self):
        spy = MagicMock()
        self.ctrl.stage_removed.connect(spy)
        self.ctrl.remove_stage(0)
        spy.assert_called_once_with(0)

    def test_cannot_remove_last_stage(self):
        self.ctrl.load_template(CollimatorType.PENCIL_BEAM)  # 1 stage
        self.ctrl.remove_stage(0)
        assert self.ctrl.geometry.stage_count == 1  # unchanged

    def test_cannot_exceed_max_stages(self):
        from app.constants import MAX_STAGES
        # Add until max
        while self.ctrl.geometry.stage_count < MAX_STAGES:
            self.ctrl.add_stage()
        before = self.ctrl.geometry.stage_count
        self.ctrl.add_stage()
        assert self.ctrl.geometry.stage_count == before  # unchanged

    def test_select_stage(self):
        spy = MagicMock()
        self.ctrl.stage_selected.connect(spy)
        self.ctrl.select_stage(2)
        assert self.ctrl.active_stage_index == 2
        spy.assert_called_once_with(2)

    def test_select_invalid_stage_ignored(self):
        self.ctrl.select_stage(99)
        assert self.ctrl.active_stage_index == 0  # unchanged

    def test_move_stage(self):
        names_before = [s.name for s in self.ctrl.geometry.stages]
        self.ctrl.move_stage(0, 2)
        assert self.ctrl.geometry.stages[2].name == names_before[0]

    def test_set_stage_dimensions(self):
        spy = MagicMock()
        self.ctrl.stage_changed.connect(spy)
        self.ctrl.set_stage_dimensions(0, width=200.0, height=150.0)
        assert self.ctrl.geometry.stages[0].outer_width == 200.0
        assert self.ctrl.geometry.stages[0].outer_height == 150.0
        spy.assert_called_once_with(0)

    def test_set_stage_dimensions_rejects_zero(self):
        old_w = self.ctrl.geometry.stages[0].outer_width
        self.ctrl.set_stage_dimensions(0, width=0.0)
        assert self.ctrl.geometry.stages[0].outer_width == old_w

    def test_set_stage_name(self):
        self.ctrl.set_stage_name(0, "Test Name")
        assert self.ctrl.geometry.stages[0].name == "Test Name"

    def test_set_stage_purpose(self):
        self.ctrl.set_stage_purpose(0, StagePurpose.FILTER)
        assert self.ctrl.geometry.stages[0].purpose == StagePurpose.FILTER

    def test_set_stage_y_position(self):
        spy = MagicMock()
        self.ctrl.stage_changed.connect(spy)
        self.ctrl.set_stage_y_position(0, 75.0)
        assert self.ctrl.geometry.stages[0].y_position == 75.0
        spy.assert_called_once_with(0)

    def test_set_stage_x_offset(self):
        spy = MagicMock()
        self.ctrl.stage_changed.connect(spy)
        self.ctrl.set_stage_x_offset(1, 15.0)
        assert self.ctrl.geometry.stages[1].x_offset == 15.0
        spy.assert_called_once_with(1)

    def test_set_stage_x_offset_invalid_index_ignored(self):
        old_x = self.ctrl.geometry.stages[0].x_offset
        self.ctrl.set_stage_x_offset(99, 10.0)
        assert self.ctrl.geometry.stages[0].x_offset == old_x

    def test_set_stage_y_position_invalid_index_ignored(self):
        old_y = self.ctrl.geometry.stages[0].y_position
        self.ctrl.set_stage_y_position(99, 10.0)
        assert self.ctrl.geometry.stages[0].y_position == old_y

    def test_set_stage_aperture(self):
        new_aperture = ApertureConfig(fan_angle=45.0, fan_slit_width=5.0)
        self.ctrl.set_stage_aperture(0, new_aperture)
        assert self.ctrl.geometry.stages[0].aperture.fan_angle == 45.0

    def test_stage_order_maintained_after_add_remove(self):
        self.ctrl.add_stage(after_index=1)
        orders = [s.order for s in self.ctrl.geometry.stages]
        assert orders == list(range(len(self.ctrl.geometry.stages)))


class TestStageMaterial:
    """Stage material and wall thickness mutations."""

    def setup_method(self):
        self.ctrl = GeometryController()
        self.ctrl.load_template(CollimatorType.FAN_BEAM)

    def test_set_stage_material(self):
        self.ctrl.set_stage_material(0, "W")
        assert self.ctrl.geometry.stages[0].material_id == "W"

    def test_set_stage_material_emits_signal(self):
        spy = MagicMock()
        self.ctrl.stage_changed.connect(spy)
        self.ctrl.set_stage_material(0, "W")
        spy.assert_called_once_with(0)

    def test_set_stage_material_invalid_rejected(self):
        old = self.ctrl.geometry.stages[0].material_id
        self.ctrl.set_stage_material(0, "Unobtanium")
        assert self.ctrl.geometry.stages[0].material_id == old

    def test_set_stage_material_invalid_index_ignored(self):
        old = self.ctrl.geometry.stages[0].material_id
        self.ctrl.set_stage_material(99, "W")
        assert self.ctrl.geometry.stages[0].material_id == old

    def test_set_stage_material_different_stages(self):
        self.ctrl.set_stage_material(0, "W")
        self.ctrl.set_stage_material(1, "Cu")
        assert self.ctrl.geometry.stages[0].material_id == "W"
        assert self.ctrl.geometry.stages[1].material_id == "Cu"

    def test_set_stage_y_position(self):
        self.ctrl.set_stage_y_position(0, 50.0)
        assert self.ctrl.geometry.stages[0].y_position == 50.0

    def test_set_stage_y_position_emits_signal(self):
        spy = MagicMock()
        self.ctrl.stage_changed.connect(spy)
        self.ctrl.set_stage_y_position(0, 50.0)
        spy.assert_called_once_with(0)

    def test_set_stage_y_position_invalid_index_ignored(self):
        old = self.ctrl.geometry.stages[0].y_position
        self.ctrl.set_stage_y_position(99, 50.0)
        assert self.ctrl.geometry.stages[0].y_position == old

    def test_set_stage_x_offset(self):
        self.ctrl.set_stage_x_offset(0, 15.0)
        assert self.ctrl.geometry.stages[0].x_offset == 15.0

    def test_set_stage_x_offset_emits_signal(self):
        spy = MagicMock()
        self.ctrl.stage_changed.connect(spy)
        self.ctrl.set_stage_x_offset(0, 10.0)
        spy.assert_called_once_with(0)

    def test_set_stage_x_offset_invalid_index_ignored(self):
        old = self.ctrl.geometry.stages[0].x_offset
        self.ctrl.set_stage_x_offset(99, 10.0)
        assert self.ctrl.geometry.stages[0].x_offset == old

    def test_update_stage_position_from_canvas(self):
        spy = MagicMock()
        self.ctrl.stage_position_changed.connect(spy)
        self.ctrl.update_stage_position_from_canvas(0, 5.0, 100.0)
        assert self.ctrl.geometry.stages[0].x_offset == 5.0
        assert self.ctrl.geometry.stages[0].y_position == 100.0
        spy.assert_called_once_with(0)


class TestSourceDetector:
    """Source and detector mutations."""

    def setup_method(self):
        self.ctrl = GeometryController()

    def test_set_source_position(self):
        spy = MagicMock()
        self.ctrl.source_changed.connect(spy)
        self.ctrl.set_source_position(10.0, -200.0)
        assert self.ctrl.geometry.source.position.x == 10.0
        assert self.ctrl.geometry.source.position.y == -200.0
        spy.assert_called_once()

    def test_set_source_focal_spot(self):
        self.ctrl.set_source_focal_spot(2.5)
        assert self.ctrl.geometry.source.focal_spot_size == 2.5

    def test_set_source_focal_spot_zero_rejected(self):
        old = self.ctrl.geometry.source.focal_spot_size
        self.ctrl.set_source_focal_spot(0.0)
        assert self.ctrl.geometry.source.focal_spot_size == old

    def test_default_focal_spot_distribution_is_uniform(self):
        assert (
            self.ctrl.geometry.source.focal_spot_distribution
            == FocalSpotDistribution.UNIFORM
        )

    def test_set_focal_spot_distribution_gaussian(self):
        spy = MagicMock()
        self.ctrl.source_changed.connect(spy)
        self.ctrl.set_source_focal_spot_distribution(
            FocalSpotDistribution.GAUSSIAN
        )
        assert (
            self.ctrl.geometry.source.focal_spot_distribution
            == FocalSpotDistribution.GAUSSIAN
        )
        spy.assert_called_once()

    def test_set_focal_spot_distribution_back_to_uniform(self):
        self.ctrl.set_source_focal_spot_distribution(
            FocalSpotDistribution.GAUSSIAN
        )
        self.ctrl.set_source_focal_spot_distribution(
            FocalSpotDistribution.UNIFORM
        )
        assert (
            self.ctrl.geometry.source.focal_spot_distribution
            == FocalSpotDistribution.UNIFORM
        )

    def test_set_detector_position(self):
        spy = MagicMock()
        self.ctrl.detector_changed.connect(spy)
        self.ctrl.set_detector_position(0.0, 400.0)
        assert self.ctrl.geometry.detector.position.y == 400.0
        spy.assert_called_once()

    def test_set_detector_updates_sdd(self):
        self.ctrl.set_source_position(0.0, -100.0)
        self.ctrl.set_detector_position(0.0, 400.0)
        assert self.ctrl.geometry.detector.distance_from_source == pytest.approx(500.0)

    def test_set_detector_width(self):
        self.ctrl.set_detector_width(600.0)
        assert self.ctrl.geometry.detector.width == 600.0


class TestReentrancyGuard:
    """Verify _updating flag prevents circular signal loops."""

    def test_mutation_during_updating_is_ignored(self):
        ctrl = GeometryController()
        ctrl._updating = True
        old_width = ctrl.geometry.stages[0].outer_width
        ctrl.set_stage_dimensions(0, width=999.0)
        assert ctrl.geometry.stages[0].outer_width == old_width
        ctrl._updating = False  # cleanup
