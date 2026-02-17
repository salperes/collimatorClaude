"""Tests for UndoManager and GeometryController undo/redo + clipboard.

Covers:
- UndoManager basic stack operations (push/undo/redo/clear/limits)
- GeometryController @undoable decorator integration
- Clipboard cut/copy/paste/delete for stages and phantoms
"""

import pytest
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication
import sys

from app.core.undo_manager import UndoManager, MAX_UNDO_LEVELS
from app.models.geometry import CollimatorType, ApertureConfig
from app.models.phantom import PhantomType
from app.ui.canvas.geometry_controller import GeometryController

# QApplication instance needed for QObject / signals
_app = QApplication.instance() or QApplication(sys.argv)


# ===================================================================
# UndoManager unit tests
# ===================================================================

class TestUndoManagerBasics:
    """Core stack operations."""

    def test_initial_state_empty(self):
        mgr = UndoManager()
        assert not mgr.can_undo
        assert not mgr.can_redo
        assert mgr.undo_count == 0
        assert mgr.redo_count == 0

    def test_push_enables_undo(self):
        mgr = UndoManager()
        mgr.push({"state": "A"})
        assert mgr.can_undo
        assert not mgr.can_redo

    def test_undo_returns_previous(self):
        mgr = UndoManager()
        mgr.push({"state": "A"})
        result = mgr.undo({"state": "B"})
        assert result == {"state": "A"}

    def test_undo_enables_redo(self):
        mgr = UndoManager()
        mgr.push({"state": "A"})
        mgr.undo({"state": "B"})
        assert mgr.can_redo
        assert not mgr.can_undo

    def test_redo_returns_next(self):
        mgr = UndoManager()
        mgr.push({"state": "A"})
        mgr.undo({"state": "B"})
        result = mgr.redo({"state": "A"})
        assert result == {"state": "B"}

    def test_undo_empty_returns_none(self):
        mgr = UndoManager()
        assert mgr.undo({"state": "X"}) is None

    def test_redo_empty_returns_none(self):
        mgr = UndoManager()
        assert mgr.redo({"state": "X"}) is None

    def test_push_clears_redo(self):
        mgr = UndoManager()
        mgr.push({"state": "A"})
        mgr.push({"state": "B"})
        mgr.undo({"state": "C"})  # redo has C
        assert mgr.can_redo
        mgr.push({"state": "D"})  # new branch — redo cleared
        assert not mgr.can_redo

    def test_clear_empties_both_stacks(self):
        mgr = UndoManager()
        mgr.push({"state": "A"})
        mgr.push({"state": "B"})
        mgr.undo({"state": "C"})
        mgr.clear()
        assert not mgr.can_undo
        assert not mgr.can_redo


class TestUndoManagerLimits:
    """Stack size enforcement."""

    def test_max_undo_levels(self):
        mgr = UndoManager(max_levels=3)
        mgr.push({"n": 1})
        mgr.push({"n": 2})
        mgr.push({"n": 3})
        mgr.push({"n": 4})  # Drops oldest ({n: 1})
        assert mgr.undo_count == 3
        # Undo should return 3, 2, but NOT 1
        mgr.undo({"n": 5})  # returns {n: 4}
        mgr.undo({"n": 4})  # returns {n: 3}
        result = mgr.undo({"n": 3})  # returns {n: 2}
        assert result == {"n": 2}
        assert mgr.undo({"n": 2}) is None  # {n: 1} was dropped

    def test_default_max_levels_is_10(self):
        mgr = UndoManager()
        assert mgr._max_levels == MAX_UNDO_LEVELS == 10

    def test_multiple_undo_redo_sequence(self):
        mgr = UndoManager()
        mgr.push({"v": 0})  # state before A
        mgr.push({"v": 1})  # state before B
        mgr.push({"v": 2})  # state before C

        # Current state is {v: 3}, undo 3 times
        s3 = mgr.undo({"v": 3})
        assert s3 == {"v": 2}
        s2 = mgr.undo({"v": 2})
        assert s2 == {"v": 1}
        s1 = mgr.undo({"v": 1})
        assert s1 == {"v": 0}

        # Redo 3 times
        r1 = mgr.redo({"v": 0})
        assert r1 == {"v": 1}
        r2 = mgr.redo({"v": 1})
        assert r2 == {"v": 2}
        r3 = mgr.redo({"v": 2})
        assert r3 == {"v": 3}


# ===================================================================
# GeometryController undo/redo integration
# ===================================================================

class TestControllerUndo:
    """Undo/redo via controller methods."""

    def setup_method(self):
        self.ctrl = GeometryController()
        self.ctrl.load_template(CollimatorType.FAN_BEAM)
        # Clear undo stack from template load
        self.ctrl.clear_undo()

    def test_stage_dimension_change_is_undoable(self):
        old_w = self.ctrl.geometry.stages[0].outer_width
        self.ctrl.set_stage_dimensions(0, width=999.0)
        assert self.ctrl.geometry.stages[0].outer_width == 999.0

        self.ctrl.undo()
        assert self.ctrl.geometry.stages[0].outer_width == old_w

    def test_redo_restores_change(self):
        old_w = self.ctrl.geometry.stages[0].outer_width
        self.ctrl.set_stage_dimensions(0, width=999.0)
        self.ctrl.undo()
        assert self.ctrl.geometry.stages[0].outer_width == old_w

        self.ctrl.redo()
        assert self.ctrl.geometry.stages[0].outer_width == 999.0

    def test_add_stage_is_undoable(self):
        n_before = self.ctrl.geometry.stage_count
        self.ctrl.add_stage()
        assert self.ctrl.geometry.stage_count == n_before + 1

        self.ctrl.undo()
        assert self.ctrl.geometry.stage_count == n_before

    def test_remove_stage_is_undoable(self):
        n_before = self.ctrl.geometry.stage_count
        removed_name = self.ctrl.geometry.stages[1].name
        self.ctrl.remove_stage(1)
        assert self.ctrl.geometry.stage_count == n_before - 1

        self.ctrl.undo()
        assert self.ctrl.geometry.stage_count == n_before
        assert self.ctrl.geometry.stages[1].name == removed_name

    def test_set_stage_material_is_undoable(self):
        old_mat = self.ctrl.geometry.stages[0].material_id
        self.ctrl.set_stage_material(0, "W")
        assert self.ctrl.geometry.stages[0].material_id == "W"

        self.ctrl.undo()
        assert self.ctrl.geometry.stages[0].material_id == old_mat

    def test_source_change_is_undoable(self):
        old_y = self.ctrl.geometry.source.position.y
        self.ctrl.set_source_position(0.0, -500.0)
        assert self.ctrl.geometry.source.position.y == -500.0

        self.ctrl.undo()
        assert self.ctrl.geometry.source.position.y == old_y

    def test_detector_change_is_undoable(self):
        old_w = self.ctrl.geometry.detector.width
        self.ctrl.set_detector_width(800.0)
        assert self.ctrl.geometry.detector.width == 800.0

        self.ctrl.undo()
        assert self.ctrl.geometry.detector.width == old_w

    def test_phantom_add_is_undoable(self):
        n_before = len(self.ctrl.geometry.phantoms)
        self.ctrl.add_phantom(PhantomType.WIRE)
        assert len(self.ctrl.geometry.phantoms) == n_before + 1

        self.ctrl.undo()
        assert len(self.ctrl.geometry.phantoms) == n_before

    def test_phantom_remove_is_undoable(self):
        self.ctrl.add_phantom(PhantomType.WIRE)
        self.ctrl.clear_undo()
        n_before = len(self.ctrl.geometry.phantoms)

        self.ctrl.remove_phantom(0)
        assert len(self.ctrl.geometry.phantoms) == n_before - 1

        self.ctrl.undo()
        assert len(self.ctrl.geometry.phantoms) == n_before

    def test_undo_emits_geometry_changed(self):
        self.ctrl.set_stage_dimensions(0, width=999.0)
        spy = MagicMock()
        self.ctrl.geometry_changed.connect(spy)
        self.ctrl.undo()
        spy.assert_called_once()

    def test_undo_emits_undo_state_changed(self):
        self.ctrl.set_stage_dimensions(0, width=999.0)
        spy = MagicMock()
        self.ctrl.undo_state_changed.connect(spy)
        self.ctrl.undo()
        spy.assert_called()

    def test_can_undo_after_mutation(self):
        assert not self.ctrl.can_undo
        self.ctrl.set_stage_dimensions(0, width=999.0)
        assert self.ctrl.can_undo

    def test_can_redo_after_undo(self):
        self.ctrl.set_stage_dimensions(0, width=999.0)
        assert not self.ctrl.can_redo
        self.ctrl.undo()
        assert self.ctrl.can_redo

    def test_clear_undo_empties_stacks(self):
        self.ctrl.set_stage_dimensions(0, width=999.0)
        self.ctrl.clear_undo()
        assert not self.ctrl.can_undo
        assert not self.ctrl.can_redo

    def test_batch_mode_single_checkpoint(self):
        """Batch mode: multiple mutations produce only one undo step."""
        self.ctrl.begin_undo_batch()
        self.ctrl.set_stage_dimensions(0, width=100.0)
        self.ctrl.set_stage_dimensions(0, width=200.0)
        self.ctrl.set_stage_dimensions(0, width=300.0)
        self.ctrl.end_undo_batch()

        # Only one undo step
        assert self.ctrl.can_undo
        self.ctrl.undo()
        assert not self.ctrl.can_undo
        # Width should be back to original (before batch)
        assert self.ctrl.geometry.stages[0].outer_width != 300.0

    def test_active_stage_index_clamped_on_undo(self):
        """If undo removes stages, active index should be clamped."""
        self.ctrl.add_stage()  # Now 4 stages
        self.ctrl.clear_undo()
        self.ctrl.select_stage(3)  # Select last
        self.ctrl.remove_stage(3)
        # active_stage_index is now clamped to 2
        self.ctrl.undo()
        # After undo, 4 stages restored, index should be valid
        assert 0 <= self.ctrl.active_stage_index < self.ctrl.geometry.stage_count


class TestControllerUndoLimit:
    """Verify max undo levels enforcement."""

    def setup_method(self):
        self.ctrl = GeometryController()
        self.ctrl.load_template(CollimatorType.SLIT)
        self.ctrl.clear_undo()

    def test_max_10_undo_levels(self):
        for i in range(15):
            self.ctrl.set_stage_dimensions(0, width=100.0 + i)

        # Should only be able to undo 10 times
        count = 0
        while self.ctrl.can_undo:
            self.ctrl.undo()
            count += 1
        assert count == MAX_UNDO_LEVELS


# ===================================================================
# Clipboard operations
# ===================================================================

class TestControllerClipboard:
    """Cut/Copy/Paste/Delete for stages and phantoms."""

    def setup_method(self):
        self.ctrl = GeometryController()
        self.ctrl.load_template(CollimatorType.FAN_BEAM)
        self.ctrl.clear_undo()

    def test_copy_stage(self):
        self.ctrl.select_stage(0)
        self.ctrl.copy_selected()
        assert self.ctrl.has_clipboard
        assert self.ctrl.clipboard_type == "stage"

    def test_paste_stage_adds_new(self):
        self.ctrl.select_stage(0)
        self.ctrl.copy_selected()
        n_before = self.ctrl.geometry.stage_count
        self.ctrl.paste()
        assert self.ctrl.geometry.stage_count == n_before + 1

    def test_paste_stage_has_offset(self):
        orig_y = self.ctrl.geometry.stages[0].y_position
        self.ctrl.select_stage(0)
        self.ctrl.copy_selected()
        self.ctrl.paste()
        # Last stage should have offset y_position
        new_stage = self.ctrl.geometry.stages[-1]
        assert new_stage.y_position != orig_y

    def test_cut_stage_removes(self):
        self.ctrl.select_stage(1)
        n_before = self.ctrl.geometry.stage_count
        self.ctrl.cut_selected()
        assert self.ctrl.geometry.stage_count == n_before - 1
        assert self.ctrl.has_clipboard

    def test_cut_last_stage_blocked(self):
        """Cannot cut if it's the only stage."""
        self.ctrl.load_template(CollimatorType.PENCIL_BEAM)
        self.ctrl.clear_undo()
        self.ctrl.select_stage(0)
        n_before = self.ctrl.geometry.stage_count
        self.ctrl.cut_selected()
        assert self.ctrl.geometry.stage_count == n_before  # Unchanged

    def test_delete_stage(self):
        self.ctrl.select_stage(1)
        n_before = self.ctrl.geometry.stage_count
        self.ctrl.delete_selected()
        assert self.ctrl.geometry.stage_count == n_before - 1

    def test_delete_is_undoable(self):
        n_before = self.ctrl.geometry.stage_count
        self.ctrl.select_stage(1)
        self.ctrl.delete_selected()
        self.ctrl.undo()
        assert self.ctrl.geometry.stage_count == n_before

    def test_copy_phantom(self):
        self.ctrl.add_phantom(PhantomType.WIRE)
        self.ctrl.clear_undo()
        self.ctrl.select_phantom(0)
        self.ctrl.copy_selected(target_type="phantom")
        assert self.ctrl.has_clipboard
        assert self.ctrl.clipboard_type == "phantom"

    def test_paste_phantom(self):
        self.ctrl.add_phantom(PhantomType.WIRE)
        self.ctrl.clear_undo()
        self.ctrl.select_phantom(0)
        self.ctrl.copy_selected(target_type="phantom")
        n_before = len(self.ctrl.geometry.phantoms)
        self.ctrl.paste()
        assert len(self.ctrl.geometry.phantoms) == n_before + 1

    def test_delete_phantom(self):
        self.ctrl.add_phantom(PhantomType.WIRE)
        self.ctrl.clear_undo()
        n_before = len(self.ctrl.geometry.phantoms)
        self.ctrl.select_phantom(0)
        self.ctrl.delete_selected(target_type="phantom")
        assert len(self.ctrl.geometry.phantoms) == n_before - 1

    def test_paste_without_clipboard_is_noop(self):
        n_before = self.ctrl.geometry.stage_count
        self.ctrl.paste()
        assert self.ctrl.geometry.stage_count == n_before

    def test_copy_paste_preserves_material(self):
        self.ctrl.set_stage_material(0, "W")
        self.ctrl.clear_undo()
        self.ctrl.select_stage(0)
        self.ctrl.copy_selected()
        self.ctrl.paste()
        new_stage = self.ctrl.geometry.stages[-1]
        assert new_stage.material_id == "W"
