"""Tests for canvas context menu, position lock, and snap features.

Tests cover:
  - Position lock on SourceItem, DetectorItem, PhantomItem, StageItem
  - Context menu target resolution (child → parent)
  - Lock-all / unlock-all
  - Independent stage movement
  - Snap-to-edge behavior
"""

import sys

import pytest

from PyQt6.QtWidgets import QApplication, QGraphicsItem
from PyQt6.QtCore import QPointF

from app.models.geometry import CollimatorGeometry, CollimatorStage, CollimatorType
from app.models.phantom import PhantomType
from app.ui.canvas.source_item import SourceItem
from app.ui.canvas.detector_item import DetectorItem
from app.ui.canvas.phantom_item import PhantomItem
from app.ui.canvas.stage_item import StageItem
from app.ui.canvas.geometry_controller import GeometryController

# QApplication instance needed for QGraphicsItem / QObject
_app = QApplication.instance() or QApplication(sys.argv)


# ── Position Lock — SourceItem ──────────────────────────────────────

class TestSourceItemLock:

    def test_default_unlocked(self):
        item = SourceItem()
        assert item.locked is False

    def test_set_locked(self):
        item = SourceItem()
        item.set_locked(True)
        assert item.locked is True

    def test_unlock(self):
        item = SourceItem()
        item.set_locked(True)
        item.set_locked(False)
        assert item.locked is False

    def test_locked_disables_movable_flag(self):
        item = SourceItem()
        item.set_locked(True)
        assert not item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable

    def test_unlocked_enables_movable_flag(self):
        item = SourceItem()
        item.set_locked(True)
        item.set_locked(False)
        assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable


# ── Position Lock — DetectorItem ────────────────────────────────────

class TestDetectorItemLock:

    def test_default_unlocked(self):
        item = DetectorItem()
        assert item.locked is False

    def test_set_locked(self):
        item = DetectorItem()
        item.set_locked(True)
        assert item.locked is True

    def test_locked_disables_movable_flag(self):
        item = DetectorItem()
        item.set_locked(True)
        assert not item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable


# ── Position Lock — PhantomItem ─────────────────────────────────────

class TestPhantomItemLock:

    def test_default_unlocked(self):
        item = PhantomItem(0, PhantomType.WIRE)
        assert item.locked is False

    def test_set_locked(self):
        item = PhantomItem(0, PhantomType.WIRE)
        item.set_locked(True)
        assert item.locked is True

    def test_locked_disables_movable_flag(self):
        item = PhantomItem(0, PhantomType.GRID)
        item.set_locked(True)
        assert not item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable


# ── Position Lock — StageItem ───────────────────────────────────────

class TestStageItemLock:

    def test_default_unlocked(self):
        item = StageItem(0)
        assert item.locked is False

    def test_set_locked(self):
        item = StageItem(0)
        item.set_locked(True)
        assert item.locked is True

    def test_locked_blocks_handle_callback(self):
        """When locked, resize handle callback should be suppressed."""
        results = []
        item = StageItem(0)
        item.set_handle_callback(lambda idx, pos, dx, dy: results.append((idx, pos, dx, dy)))
        item.set_locked(True)

        from app.ui.canvas.resize_handle import HandlePosition
        item._on_handle_moved(HandlePosition.RIGHT, 5.0, 0.0)
        assert len(results) == 0  # callback NOT called

    def test_unlocked_allows_handle_callback(self):
        results = []
        item = StageItem(0)
        item.set_handle_callback(lambda idx, pos, dx, dy: results.append((idx, pos, dx, dy)))

        from app.ui.canvas.resize_handle import HandlePosition
        item._on_handle_moved(HandlePosition.RIGHT, 5.0, 0.0)
        assert len(results) == 1


# ── Context Menu Target Resolution ──────────────────────────────────

class TestTargetResolution:
    """Test _resolve_target walks parent chain correctly."""

    def test_stage_item_resolves_to_self(self):
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        scene = CollimatorScene(ctrl)

        stage_item = scene._stage_items[0]
        assert scene._resolve_target(stage_item) is stage_item

    def test_source_resolves_to_source(self):
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        scene = CollimatorScene(ctrl)

        assert scene._resolve_target(scene._source_item) is scene._source_item

    def test_detector_resolves_to_detector(self):
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        scene = CollimatorScene(ctrl)

        assert scene._resolve_target(scene._detector_item) is scene._detector_item

    def test_none_resolves_to_none(self):
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        scene = CollimatorScene(ctrl)

        assert scene._resolve_target(None) is None

    def test_child_of_stage_resolves_to_stage(self):
        """LayerItem/ApertureItem (children of StageItem) should resolve to parent."""
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        scene = CollimatorScene(ctrl)

        stage_item = scene._stage_items[0]
        # LayerItem is a child of StageItem
        if stage_item._material_item is not None:
            resolved = scene._resolve_target(stage_item._material_item)
            assert resolved is stage_item


# ── Lock All / Unlock All ───────────────────────────────────────────

class TestLockAll:

    def test_lock_all(self):
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        ctrl.add_phantom(PhantomType.WIRE)
        scene = CollimatorScene(ctrl)

        scene._lock_all(True)

        assert scene._source_item.locked is True
        assert scene._detector_item.locked is True
        for s in scene._stage_items:
            assert s.locked is True
        for p in scene._phantom_items:
            assert p.locked is True

    def test_unlock_all(self):
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        scene = CollimatorScene(ctrl)

        scene._lock_all(True)
        scene._lock_all(False)

        assert scene._source_item.locked is False
        assert scene._detector_item.locked is False
        for s in scene._stage_items:
            assert s.locked is False


# ── StageItem Independent Movement ────────────────────────────────

class TestStageIndependentMovement:

    def test_stage_is_movable_by_default(self):
        item = StageItem(0)
        assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable

    def test_stage_sends_geometry_changes(self):
        item = StageItem(0)
        assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges

    def test_locked_disables_movable_flag(self):
        item = StageItem(0)
        item.set_locked(True)
        assert not item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable

    def test_unlocked_re_enables_movable_flag(self):
        item = StageItem(0)
        item.set_locked(True)
        item.set_locked(False)
        assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable

    def test_stages_can_have_different_positions(self):
        """After rebuild, each stage can be repositioned independently."""
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        scene = CollimatorScene(ctrl)

        if len(scene._stage_items) < 2:
            ctrl.add_stage()

        s0 = scene._stage_items[0]
        s1 = scene._stage_items[1]
        original_s0_y = s0.pos().y()
        original_s1_y = s1.pos().y()

        # Move only stage 1
        s1.setPos(s1.pos().x(), original_s1_y + 50)

        # Stage 0 stays, stage 1 moved
        assert s0.pos().y() == original_s0_y
        assert s1.pos().y() == pytest.approx(original_s1_y + 50, abs=1)


# ── Snap-to-Edge Behavior ─────────────────────────────────────────

class TestSnapBehavior:

    def _make_scene_with_two_stages(self):
        """Create a scene with 2 stages for snap testing."""
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        scene = CollimatorScene(ctrl)
        if len(scene._stage_items) < 2:
            ctrl.add_stage()
        return scene

    def test_snap_bottom_to_top(self):
        """Moving stage bottom edge near another stage's top should snap."""
        from app.ui.canvas.collimator_scene import CollimatorScene, SNAP_THRESHOLD
        scene = self._make_scene_with_two_stages()

        s0 = scene._stage_items[0]
        s1 = scene._stage_items[1]

        # Position stage 0 at known location
        scene._rebuilding = True
        s0.setPos(-50, 0)
        s1.setPos(-50, 200)
        scene._rebuilding = False

        # Propose a position where s0's bottom is close to s1's top
        # s0 height = s0.height, so bottom at proposed_y + s0.height
        # Want: (proposed_y + s0.height) ≈ 200 (s1's top)
        proposed_y = 200 - s0.height + 3  # 3mm off → within threshold
        proposed = QPointF(-50, proposed_y)
        result = scene._snap_stage_position(s0, proposed)

        # Should snap so that s0's bottom = s1's top = 200
        assert result.y() == pytest.approx(200 - s0.height, abs=0.01)

    def test_snap_top_to_bottom(self):
        """Moving stage top edge near another stage's bottom should snap."""
        from app.ui.canvas.collimator_scene import CollimatorScene, SNAP_THRESHOLD
        scene = self._make_scene_with_two_stages()

        s0 = scene._stage_items[0]
        s1 = scene._stage_items[1]

        scene._rebuilding = True
        s0.setPos(-50, 0)
        s1.setPos(-50, 200)
        scene._rebuilding = False

        # s1's top near s0's bottom (s0.height)
        proposed_y = s0.height + 2  # 2mm off from s0's bottom
        proposed = QPointF(-50, proposed_y)
        result = scene._snap_stage_position(s1, proposed)

        # Should snap s1's top to s0's bottom
        assert result.y() == pytest.approx(s0.height, abs=0.01)

    def test_snap_center_x_alignment(self):
        """Stages should snap to center-X alignment."""
        from app.ui.canvas.collimator_scene import CollimatorScene, SNAP_THRESHOLD
        scene = self._make_scene_with_two_stages()

        s0 = scene._stage_items[0]
        s1 = scene._stage_items[1]

        scene._rebuilding = True
        s0.setPos(-60, 0)      # center_x = -60 + s0.width/2
        s1.setPos(-100, 200)
        scene._rebuilding = False

        # Propose s1 at X where its center is close to s0's center
        s0_cx = -60 + s0.width / 2
        proposed_x = s0_cx - s1.width / 2 + 3  # 3mm off
        proposed = QPointF(proposed_x, 200)
        result = scene._snap_stage_position(s1, proposed)

        # Should snap center-to-center
        expected_x = s0_cx - s1.width / 2
        assert result.x() == pytest.approx(expected_x, abs=0.01)

    def test_no_snap_when_far_away(self):
        """No snap when stages are far apart."""
        from app.ui.canvas.collimator_scene import CollimatorScene, SNAP_THRESHOLD
        scene = self._make_scene_with_two_stages()

        s0 = scene._stage_items[0]
        s1 = scene._stage_items[1]

        scene._rebuilding = True
        s0.setPos(-50, 0)
        s1.setPos(-50, 500)
        scene._rebuilding = False

        # Propose s1 at a position far from s0
        proposed = QPointF(-50, 500)
        result = scene._snap_stage_position(s1, proposed)

        # Should not snap (position unchanged)
        assert result.x() == pytest.approx(-50, abs=0.01)
        assert result.y() == pytest.approx(500, abs=0.01)

    def test_no_snap_during_rebuild(self):
        """Snap is disabled during rebuild."""
        from app.ui.canvas.collimator_scene import CollimatorScene
        scene = self._make_scene_with_two_stages()

        s0 = scene._stage_items[0]
        scene._rebuilding = True
        proposed = QPointF(100, 100)
        result = scene._snap_stage_position(s0, proposed)

        assert result.x() == 100
        assert result.y() == 100
        scene._rebuilding = False

    # test_gap_items_update_after_move removed — gap items no longer exist (v3.0)


# ── X-Axis Lock ───────────────────────────────────────────────────

class TestXAxisLock:

    def test_stage_x_locked_by_default(self):
        item = StageItem(0)
        assert item.x_locked is True

    def test_source_x_locked_by_default(self):
        item = SourceItem()
        assert item.x_locked is True

    def test_detector_x_locked_by_default(self):
        item = DetectorItem()
        assert item.x_locked is True

    def test_phantom_x_locked_by_default(self):
        item = PhantomItem(0, PhantomType.WIRE)
        assert item.x_locked is True

    def test_stage_x_unlock(self):
        item = StageItem(0)
        item.set_x_locked(False)
        assert item.x_locked is False

    def test_source_x_unlock(self):
        item = SourceItem()
        item.set_x_locked(False)
        assert item.x_locked is False

    def test_stage_x_locked_constrains_x_during_drag(self):
        """When X-locked and dragging, stage should keep current X."""
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        scene = CollimatorScene(ctrl)

        s0 = scene._stage_items[0]
        original_x = s0.pos().x()

        # Simulate user drag (X-lock only applies during drag)
        s0._dragging = True
        s0.setPos(original_x + 100, s0.pos().y() + 50)
        s0._dragging = False

        # X should be constrained (unchanged), Y should move
        assert s0.pos().x() == pytest.approx(original_x, abs=0.01)

    def test_stage_x_unlocked_allows_x(self):
        """When X-unlocked, stage can move in X."""
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        scene = CollimatorScene(ctrl)

        s0 = scene._stage_items[0]
        s0.set_x_locked(False)
        original_x = s0.pos().x()

        # Move in X
        scene._rebuilding = True
        s0.setPos(original_x + 100, s0.pos().y())
        scene._rebuilding = False

        assert s0.pos().x() == pytest.approx(original_x + 100, abs=0.01)

    def test_x_lock_all(self):
        """_x_lock_all should set x_locked on all items."""
        from app.ui.canvas.collimator_scene import CollimatorScene
        ctrl = GeometryController()
        ctrl.add_phantom(PhantomType.WIRE)
        scene = CollimatorScene(ctrl)

        # Unlock all first
        scene._x_lock_all(False)
        assert scene._source_item.x_locked is False
        assert scene._detector_item.x_locked is False
        for s in scene._stage_items:
            assert s.x_locked is False
        for p in scene._phantom_items:
            assert p.x_locked is False

        # Lock all
        scene._x_lock_all(True)
        assert scene._source_item.x_locked is True
        assert scene._detector_item.x_locked is True
        for s in scene._stage_items:
            assert s.x_locked is True
        for p in scene._phantom_items:
            assert p.x_locked is True
