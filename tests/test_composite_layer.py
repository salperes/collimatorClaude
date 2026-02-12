"""Tests for composite layer (İç/Dış zon) support.

Validates:
- CollimatorLayer.is_composite property
- GeometryController composite methods (toggle, inner material, inner width)
- Signal emissions for composite changes
- Edge cases (invalid indices, width bounds)
"""

import pytest
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication
import sys

from app.models.geometry import (
    CollimatorLayer,
    CollimatorStage,
    CollimatorGeometry,
    LayerPurpose,
)
from app.ui.canvas.geometry_controller import GeometryController
from app.constants import MATERIAL_IDS

# QApplication instance needed for QObject / signals
_app = QApplication.instance() or QApplication(sys.argv)


# ------------------------------------------------------------------
# Model tests
# ------------------------------------------------------------------

class TestCompositeLayerModel:
    """CollimatorLayer composite fields and is_composite property."""

    def test_default_not_composite(self):
        layer = CollimatorLayer(material_id="Pb", thickness=10.0)
        assert layer.inner_material_id is None
        assert layer.inner_width == 0.0
        assert not layer.is_composite

    def test_composite_with_inner_material_and_width(self):
        layer = CollimatorLayer(
            material_id="Pb", thickness=20.0,
            inner_material_id="W", inner_width=5.0,
        )
        assert layer.is_composite
        assert layer.inner_material_id == "W"
        assert layer.inner_width == 5.0

    def test_not_composite_when_inner_width_zero(self):
        layer = CollimatorLayer(
            material_id="Pb", thickness=20.0,
            inner_material_id="W", inner_width=0.0,
        )
        assert not layer.is_composite

    def test_not_composite_when_inner_material_none(self):
        layer = CollimatorLayer(
            material_id="Pb", thickness=20.0,
            inner_material_id=None, inner_width=5.0,
        )
        assert not layer.is_composite


# ------------------------------------------------------------------
# Controller tests
# ------------------------------------------------------------------

class TestCompositeController:
    """GeometryController composite layer methods."""

    def setup_method(self):
        self.ctrl = GeometryController()
        # Ensure at least one stage with one layer
        if not self.ctrl.geometry.stages[0].layers:
            self.ctrl.add_layer(0)

    def test_enable_composite(self):
        self.ctrl.set_layer_composite(0, 0, True)
        layer = self.ctrl.geometry.stages[0].layers[0]
        assert layer.is_composite
        assert layer.inner_material_id is not None
        assert layer.inner_width > 0

    def test_disable_composite(self):
        self.ctrl.set_layer_composite(0, 0, True)
        self.ctrl.set_layer_composite(0, 0, False)
        layer = self.ctrl.geometry.stages[0].layers[0]
        assert not layer.is_composite
        assert layer.inner_material_id is None
        assert layer.inner_width == 0.0

    def test_set_inner_material(self):
        self.ctrl.set_layer_composite(0, 0, True)
        self.ctrl.set_layer_inner_material(0, 0, "Cu")
        layer = self.ctrl.geometry.stages[0].layers[0]
        assert layer.inner_material_id == "Cu"

    def test_set_inner_material_invalid_ignored(self):
        self.ctrl.set_layer_composite(0, 0, True)
        original = self.ctrl.geometry.stages[0].layers[0].inner_material_id
        self.ctrl.set_layer_inner_material(0, 0, "InvalidMaterial")
        assert self.ctrl.geometry.stages[0].layers[0].inner_material_id == original

    def test_set_inner_width(self):
        self.ctrl.set_layer_composite(0, 0, True)
        self.ctrl.set_layer_inner_width(0, 0, 3.0)
        layer = self.ctrl.geometry.stages[0].layers[0]
        assert layer.inner_width == 3.0

    def test_set_inner_width_clamped_to_thickness(self):
        self.ctrl.set_layer_composite(0, 0, True)
        thickness = self.ctrl.geometry.stages[0].layers[0].thickness
        self.ctrl.set_layer_inner_width(0, 0, thickness + 10.0)
        layer = self.ctrl.geometry.stages[0].layers[0]
        assert layer.inner_width < thickness

    def test_set_inner_width_negative_ignored(self):
        self.ctrl.set_layer_composite(0, 0, True)
        original = self.ctrl.geometry.stages[0].layers[0].inner_width
        self.ctrl.set_layer_inner_width(0, 0, -5.0)
        assert self.ctrl.geometry.stages[0].layers[0].inner_width == original


class TestCompositeSignals:
    """Verify layer_changed signal is emitted on composite mutations."""

    def setup_method(self):
        self.ctrl = GeometryController()
        if not self.ctrl.geometry.stages[0].layers:
            self.ctrl.add_layer(0)
        self.spy = MagicMock()
        self.ctrl.layer_changed.connect(self.spy)

    def test_enable_composite_emits_signal(self):
        self.ctrl.set_layer_composite(0, 0, True)
        self.spy.assert_called_with(0, 0)

    def test_set_inner_material_emits_signal(self):
        self.ctrl.set_layer_composite(0, 0, True)
        self.spy.reset_mock()
        self.ctrl.set_layer_inner_material(0, 0, "Cu")
        self.spy.assert_called_with(0, 0)

    def test_set_inner_width_emits_signal(self):
        self.ctrl.set_layer_composite(0, 0, True)
        self.spy.reset_mock()
        self.ctrl.set_layer_inner_width(0, 0, 2.0)
        self.spy.assert_called_with(0, 0)


class TestCompositeEdgeCases:
    """Invalid indices and boundary conditions."""

    def setup_method(self):
        self.ctrl = GeometryController()
        if not self.ctrl.geometry.stages[0].layers:
            self.ctrl.add_layer(0)

    def test_invalid_stage_index_no_crash(self):
        self.ctrl.set_layer_composite(99, 0, True)  # should not crash

    def test_invalid_layer_index_no_crash(self):
        self.ctrl.set_layer_composite(0, 99, True)  # should not crash

    def test_inner_material_on_non_composite_no_crash(self):
        self.ctrl.set_layer_inner_material(0, 0, "W")  # should not crash

    def test_inner_width_on_non_composite_no_crash(self):
        self.ctrl.set_layer_inner_width(0, 0, 3.0)  # should not crash

    def test_toggle_composite_twice(self):
        self.ctrl.set_layer_composite(0, 0, True)
        self.ctrl.set_layer_composite(0, 0, True)
        assert self.ctrl.geometry.stages[0].layers[0].is_composite


class TestBlankGeometry:
    """Test create_blank_geometry for 'Ozel (Bos)' template."""

    def setup_method(self):
        self.ctrl = GeometryController()

    def test_blank_geometry_creates_single_stage(self):
        self.ctrl.create_blank_geometry()
        assert self.ctrl.geometry.stage_count == 1

    def test_blank_geometry_has_one_layer(self):
        self.ctrl.create_blank_geometry()
        assert len(self.ctrl.geometry.stages[0].layers) == 1

    def test_blank_geometry_resets_active_stage(self):
        self.ctrl.create_blank_geometry()
        assert self.ctrl.active_stage_index == 0
