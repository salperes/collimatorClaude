"""Phantom controller tests — add/remove/modify phantoms via GeometryController.

Tests phantom CRUD operations, signal emission, and validation.
"""

import pytest
from unittest.mock import MagicMock

from app.ui.canvas.geometry_controller import GeometryController
from app.models.phantom import (
    GridPhantom,
    LinePairPhantom,
    PhantomType,
    WirePhantom,
)
from app.constants import MAX_PHANTOMS


@pytest.fixture
def ctrl() -> GeometryController:
    return GeometryController()


# -----------------------------------------------------------------------
# Add / remove
# -----------------------------------------------------------------------

class TestPhantomAddRemove:
    """Test add/remove phantom operations."""

    def test_add_wire_phantom(self, ctrl: GeometryController):
        sig = MagicMock()
        ctrl.phantom_added.connect(sig)

        ctrl.add_phantom(PhantomType.WIRE)

        assert len(ctrl.geometry.phantoms) == 1
        assert isinstance(ctrl.geometry.phantoms[0], WirePhantom)
        sig.assert_called_once_with(0)

    def test_add_line_pair_phantom(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.LINE_PAIR)

        assert len(ctrl.geometry.phantoms) == 1
        assert isinstance(ctrl.geometry.phantoms[0], LinePairPhantom)

    def test_add_grid_phantom(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.GRID)

        assert len(ctrl.geometry.phantoms) == 1
        assert isinstance(ctrl.geometry.phantoms[0], GridPhantom)

    def test_add_sets_active_phantom(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        assert ctrl.active_phantom_index == 0

        ctrl.add_phantom(PhantomType.LINE_PAIR)
        assert ctrl.active_phantom_index == 1

    def test_remove_phantom(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl.add_phantom(PhantomType.LINE_PAIR)

        sig = MagicMock()
        ctrl.phantom_removed.connect(sig)

        ctrl.remove_phantom(0)
        assert len(ctrl.geometry.phantoms) == 1
        assert isinstance(ctrl.geometry.phantoms[0], LinePairPhantom)
        sig.assert_called_once_with(0)

    def test_remove_invalid_index(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl.remove_phantom(5)
        assert len(ctrl.geometry.phantoms) == 1

    def test_remove_negative_index(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl.remove_phantom(-1)
        assert len(ctrl.geometry.phantoms) == 1

    def test_max_phantoms_enforced(self, ctrl: GeometryController):
        for _ in range(MAX_PHANTOMS):
            ctrl.add_phantom(PhantomType.WIRE)
        assert len(ctrl.geometry.phantoms) == MAX_PHANTOMS

        # Adding one more should be ignored
        ctrl.add_phantom(PhantomType.WIRE)
        assert len(ctrl.geometry.phantoms) == MAX_PHANTOMS

    def test_auto_position(self, ctrl: GeometryController):
        """Added phantom should be positioned between stages and detector."""
        ctrl.add_phantom(PhantomType.WIRE)
        phantom = ctrl.geometry.phantoms[0]
        src_y = ctrl.geometry.source.position.y
        det_y = ctrl.geometry.detector.position.y
        # Position should be between the collimator bottom and detector
        assert phantom.config.position_y > 0
        assert phantom.config.position_y < det_y

    def test_explicit_position(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE, position_y=250.0)
        assert ctrl.geometry.phantoms[0].config.position_y == 250.0


# -----------------------------------------------------------------------
# Select
# -----------------------------------------------------------------------

class TestPhantomSelect:
    """Test phantom selection."""

    def test_select_phantom(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl.add_phantom(PhantomType.LINE_PAIR)

        sig = MagicMock()
        ctrl.phantom_selected.connect(sig)

        ctrl.select_phantom(1)
        assert ctrl.active_phantom_index == 1
        sig.assert_called_once_with(1)

    def test_select_invalid(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl.select_phantom(5)
        # Should not change
        assert ctrl.active_phantom_index == 0

    def test_active_phantom_property(self, ctrl: GeometryController):
        assert ctrl.active_phantom is None
        ctrl.add_phantom(PhantomType.WIRE)
        assert ctrl.active_phantom is not None
        assert isinstance(ctrl.active_phantom, WirePhantom)


# -----------------------------------------------------------------------
# Modify phantom properties
# -----------------------------------------------------------------------

class TestPhantomModify:
    """Test phantom property modifications."""

    def test_set_position(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        sig = MagicMock()
        ctrl.phantom_changed.connect(sig)

        ctrl.set_phantom_position(0, 350.0)
        assert ctrl.geometry.phantoms[0].config.position_y == 350.0
        sig.assert_called_once_with(0)

    def test_set_material(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl.set_phantom_material(0, "Pb")
        assert ctrl.geometry.phantoms[0].config.material_id == "Pb"

    def test_set_invalid_material(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl.set_phantom_material(0, "Unobtanium")
        assert ctrl.geometry.phantoms[0].config.material_id == "W"  # unchanged

    def test_set_enabled(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl.set_phantom_enabled(0, False)
        assert ctrl.geometry.phantoms[0].config.enabled is False

    def test_set_name(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl.set_phantom_name(0, "Test Wire")
        assert ctrl.geometry.phantoms[0].config.name == "Test Wire"


# -----------------------------------------------------------------------
# Wire-specific
# -----------------------------------------------------------------------

class TestWirePhantomMethods:
    """Test wire-specific phantom modifications."""

    def test_set_wire_diameter(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl.set_wire_diameter(0, 1.5)
        phantom = ctrl.geometry.phantoms[0]
        assert isinstance(phantom, WirePhantom)
        assert phantom.diameter == 1.5

    def test_set_wire_diameter_negative(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl.set_wire_diameter(0, -1.0)
        phantom = ctrl.geometry.phantoms[0]
        assert isinstance(phantom, WirePhantom)
        assert phantom.diameter == 0.5  # default, unchanged

    def test_set_wire_diameter_wrong_type(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.LINE_PAIR)
        ctrl.set_wire_diameter(0, 1.5)
        # Should be ignored — not a wire phantom
        phantom = ctrl.geometry.phantoms[0]
        assert isinstance(phantom, LinePairPhantom)


# -----------------------------------------------------------------------
# Line-pair specific
# -----------------------------------------------------------------------

class TestLinePairPhantomMethods:
    """Test line-pair specific modifications."""

    def test_set_frequency(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.LINE_PAIR)
        ctrl.set_line_pair_frequency(0, 2.5)
        phantom = ctrl.geometry.phantoms[0]
        assert isinstance(phantom, LinePairPhantom)
        assert phantom.frequency == 2.5

    def test_set_thickness(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.LINE_PAIR)
        ctrl.set_line_pair_thickness(0, 3.0)
        phantom = ctrl.geometry.phantoms[0]
        assert isinstance(phantom, LinePairPhantom)
        assert phantom.bar_thickness == 3.0

    def test_set_num_cycles(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.LINE_PAIR)
        ctrl.set_line_pair_num_cycles(0, 10)
        phantom = ctrl.geometry.phantoms[0]
        assert isinstance(phantom, LinePairPhantom)
        assert phantom.num_cycles == 10


# -----------------------------------------------------------------------
# Grid specific
# -----------------------------------------------------------------------

class TestGridPhantomMethods:
    """Test grid-specific modifications."""

    def test_set_grid_pitch(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.GRID)
        ctrl.set_grid_pitch(0, 2.0)
        phantom = ctrl.geometry.phantoms[0]
        assert isinstance(phantom, GridPhantom)
        assert phantom.pitch == 2.0

    def test_set_grid_wire_diameter(self, ctrl: GeometryController):
        ctrl.add_phantom(PhantomType.GRID)
        ctrl.set_grid_wire_diameter(0, 0.3)
        phantom = ctrl.geometry.phantoms[0]
        assert isinstance(phantom, GridPhantom)
        assert phantom.wire_diameter == 0.3


# -----------------------------------------------------------------------
# Re-entrancy guard
# -----------------------------------------------------------------------

class TestPhantomReentrancy:
    """Test that re-entrancy guard prevents nested mutations."""

    def test_reentrancy_guard(self, ctrl: GeometryController):
        """Mutations during _updating=True should be ignored."""
        ctrl.add_phantom(PhantomType.WIRE)
        ctrl._updating = True
        ctrl.add_phantom(PhantomType.LINE_PAIR)
        ctrl._updating = False
        # Only the first phantom should exist
        assert len(ctrl.geometry.phantoms) == 1
