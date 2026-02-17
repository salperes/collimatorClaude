"""Undo/Redo manager — snapshot-based geometry state history.

Stores serialized geometry snapshots (dicts) in bounded stacks.
Max 10 undo levels. Pure Python class (no Qt dependency).

Reference: Phase-08 — Edit menu specification.
"""

from __future__ import annotations

from typing import Any

MAX_UNDO_LEVELS = 10


class UndoManager:
    """Snapshot-based undo/redo manager.

    Stores geometry state as serialized dicts (via geometry_to_dict).
    Each push saves a pre-mutation snapshot; undo/redo swap between stacks.

    Usage::

        mgr = UndoManager()
        mgr.push(current_snapshot)      # Before mutation
        previous = mgr.undo(current_snapshot)  # Revert
        next_ = mgr.redo(current_snapshot)     # Re-apply
    """

    def __init__(self, max_levels: int = MAX_UNDO_LEVELS) -> None:
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []
        self._max_levels = max_levels

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)

    def push(self, snapshot: dict[str, Any]) -> None:
        """Save a pre-mutation snapshot. Clears redo stack.

        Args:
            snapshot: Serialized geometry dict (from geometry_to_dict).
        """
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._max_levels:
            self._undo_stack.pop(0)  # Drop oldest
        self._redo_stack.clear()

    def undo(self, current: dict[str, Any]) -> dict[str, Any] | None:
        """Undo: push current to redo, pop from undo.

        Args:
            current: Current geometry state (will be pushed to redo stack).

        Returns:
            Previous snapshot to restore, or None if nothing to undo.
        """
        if not self._undo_stack:
            return None
        self._redo_stack.append(current)
        return self._undo_stack.pop()

    def redo(self, current: dict[str, Any]) -> dict[str, Any] | None:
        """Redo: push current to undo, pop from redo.

        Args:
            current: Current geometry state (will be pushed to undo stack).

        Returns:
            Next snapshot to restore, or None if nothing to redo.
        """
        if not self._redo_stack:
            return None
        self._undo_stack.append(current)
        return self._redo_stack.pop()

    def clear(self) -> None:
        """Clear both stacks (e.g., on new geometry load)."""
        self._undo_stack.clear()
        self._redo_stack.clear()
