"""Design repository — CRUD operations for designs, versions, simulations.

All SQL operates against the schema defined in ``db_manager.py``.

Reference: Phase-06 spec.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from app.core.serializers import (
    dict_to_geometry,
    dict_to_simulation_config,
    dict_to_simulation_result,
    geometry_to_dict,
    simulation_config_to_dict,
    simulation_result_to_dict,
)
from app.database.db_manager import DatabaseManager
from app.models.design import DesignSummary, DesignVersion, SimulationSummary
from app.models.geometry import CollimatorGeometry
from app.models.simulation import SimulationConfig, SimulationResult


class DesignRepository:
    """CRUD repository for designs, versions, and simulation results."""

    def __init__(self, db: DatabaseManager):
        self._db = db

    # ------------------------------------------------------------------
    # Design CRUD
    # ------------------------------------------------------------------

    def list_designs(
        self,
        filter_type: str | None = None,
        filter_tag: str | None = None,
        favorites_only: bool = False,
        search_text: str | None = None,
    ) -> list[DesignSummary]:
        """List designs with optional filters."""
        conn = self._db.connect()
        sql = "SELECT id, name, description, collimator_type, tags, is_favorite, created_at, updated_at FROM designs WHERE 1=1"
        params: list = []

        if filter_type:
            sql += " AND collimator_type = ?"
            params.append(filter_type)
        if filter_tag:
            sql += " AND tags LIKE ?"
            params.append(f"%{filter_tag}%")
        if favorites_only:
            sql += " AND is_favorite = 1"
        if search_text:
            sql += " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{search_text}%", f"%{search_text}%"])

        sql += " ORDER BY updated_at DESC"
        rows = conn.execute(sql, params).fetchall()

        return [
            DesignSummary(
                id=r[0],
                name=r[1],
                description=r[2] or "",
                collimator_type=r[3],
                tags=r[4].split(",") if r[4] else [],
                is_favorite=bool(r[5]),
                created_at=r[6] or "",
                updated_at=r[7] or "",
            )
            for r in rows
        ]

    def save_design(
        self,
        geometry: CollimatorGeometry,
        name: str,
        description: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Insert new design and first version. Returns design_id."""
        conn = self._db.connect()
        design_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        geo_json = json.dumps(geometry_to_dict(geometry), ensure_ascii=False)
        tags_str = ",".join(tags) if tags else ""

        conn.execute(
            """INSERT INTO designs
               (id, name, description, collimator_type, geometry_json,
                tags, is_favorite, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (design_id, name, description, geometry.type.value,
             geo_json, tags_str, now, now),
        )

        # First version
        version_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO design_versions
               (id, design_id, version_number, geometry_json, change_note, created_at)
               VALUES (?, ?, 1, ?, ?, ?)""",
            (version_id, design_id, geo_json, "Ilk kayit", now),
        )
        conn.commit()

        # Track as recent
        self._add_recent(design_id)

        return design_id

    def load_design(self, design_id: str) -> CollimatorGeometry:
        """Load geometry for a design."""
        conn = self._db.connect()
        row = conn.execute(
            "SELECT geometry_json FROM designs WHERE id = ?", (design_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Design not found: {design_id}")
        return dict_to_geometry(json.loads(row[0]))

    def update_design(
        self,
        design_id: str,
        geometry: CollimatorGeometry,
        change_note: str | None = None,
    ) -> None:
        """Update design and create new version."""
        conn = self._db.connect()
        now = datetime.now().isoformat()
        geo_json = json.dumps(geometry_to_dict(geometry), ensure_ascii=False)

        conn.execute(
            """UPDATE designs
               SET geometry_json = ?, updated_at = ?,
                   collimator_type = ?, name = ?
               WHERE id = ?""",
            (geo_json, now, geometry.type.value, geometry.name, design_id),
        )

        # Next version number
        row = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) FROM design_versions WHERE design_id = ?",
            (design_id,),
        ).fetchone()
        next_ver = row[0] + 1

        version_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO design_versions
               (id, design_id, version_number, geometry_json, change_note, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (version_id, design_id, next_ver, geo_json,
             change_note or "", now),
        )
        conn.commit()

    def delete_design(self, design_id: str) -> None:
        """Delete design and cascade to versions + simulations."""
        conn = self._db.connect()
        conn.execute("DELETE FROM designs WHERE id = ?", (design_id,))
        conn.commit()

    def toggle_favorite(self, design_id: str) -> None:
        """Toggle the is_favorite flag."""
        conn = self._db.connect()
        conn.execute(
            "UPDATE designs SET is_favorite = 1 - is_favorite WHERE id = ?",
            (design_id,),
        )
        conn.commit()

    def update_thumbnail(self, design_id: str, thumbnail: bytes) -> None:
        """Store thumbnail PNG bytes."""
        conn = self._db.connect()
        conn.execute(
            "UPDATE designs SET thumbnail_png = ? WHERE id = ?",
            (thumbnail, design_id),
        )
        conn.commit()

    def get_design_name(self, design_id: str) -> str:
        """Get just the design name."""
        conn = self._db.connect()
        row = conn.execute(
            "SELECT name FROM designs WHERE id = ?", (design_id,)
        ).fetchone()
        return row[0] if row else ""

    # ------------------------------------------------------------------
    # Version History
    # ------------------------------------------------------------------

    def get_version_history(self, design_id: str) -> list[DesignVersion]:
        """List all versions for a design, newest first."""
        conn = self._db.connect()
        rows = conn.execute(
            """SELECT id, design_id, version_number, change_note, created_at
               FROM design_versions
               WHERE design_id = ?
               ORDER BY version_number DESC""",
            (design_id,),
        ).fetchall()
        return [
            DesignVersion(
                id=r[0], design_id=r[1], version_number=r[2],
                change_note=r[3] or "", created_at=r[4] or "",
            )
            for r in rows
        ]

    def load_version(
        self, design_id: str, version_number: int,
    ) -> CollimatorGeometry:
        """Load geometry from a specific version."""
        conn = self._db.connect()
        row = conn.execute(
            """SELECT geometry_json FROM design_versions
               WHERE design_id = ? AND version_number = ?""",
            (design_id, version_number),
        ).fetchone()
        if row is None:
            raise KeyError(f"Version {version_number} not found for {design_id}")
        return dict_to_geometry(json.loads(row[0]))

    def restore_version(
        self, design_id: str, version_number: int,
    ) -> None:
        """Restore an old version as a new version (non-destructive)."""
        geometry = self.load_version(design_id, version_number)
        self.update_design(
            design_id, geometry,
            change_note=f"Versiyon {version_number} geri yuklendi",
        )

    # ------------------------------------------------------------------
    # Simulation Results
    # ------------------------------------------------------------------

    def save_simulation_result(
        self,
        design_id: str,
        config: SimulationConfig,
        result: SimulationResult,
        name: str | None = None,
    ) -> str:
        """Persist a simulation result."""
        conn = self._db.connect()
        sim_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        config_json = json.dumps(simulation_config_to_dict(config), ensure_ascii=False)
        result_json = json.dumps(simulation_result_to_dict(result), ensure_ascii=False)

        auto_name = name or f"E={result.energy_keV:.0f}keV N={result.num_rays}"

        conn.execute(
            """INSERT INTO simulation_results
               (id, design_id, name, config_json, result_json,
                energy_keV, num_rays, include_buildup, include_scatter,
                computation_time_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sim_id, design_id, auto_name, config_json, result_json,
             result.energy_keV, result.num_rays,
             int(result.include_buildup), int(config.include_scatter),
             int(result.elapsed_seconds * 1000), now),
        )
        conn.commit()
        return sim_id

    def list_simulation_results(
        self, design_id: str,
    ) -> list[SimulationSummary]:
        """List simulation results for a design."""
        conn = self._db.connect()
        rows = conn.execute(
            """SELECT id, design_id, name, energy_keV, num_rays,
                      include_buildup, include_scatter, computation_time_ms, created_at
               FROM simulation_results
               WHERE design_id = ?
               ORDER BY created_at DESC""",
            (design_id,),
        ).fetchall()
        return [
            SimulationSummary(
                id=r[0], design_id=r[1], name=r[2] or "",
                energy_keV=r[3], num_rays=r[4],
                include_buildup=bool(r[5]), include_scatter=bool(r[6]),
                computation_time_ms=r[7] or 0, created_at=r[8] or "",
            )
            for r in rows
        ]

    def load_simulation_result(
        self, sim_id: str,
    ) -> tuple[SimulationConfig, SimulationResult]:
        """Load full simulation config and result."""
        conn = self._db.connect()
        row = conn.execute(
            "SELECT config_json, result_json FROM simulation_results WHERE id = ?",
            (sim_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Simulation not found: {sim_id}")
        config = dict_to_simulation_config(json.loads(row[0]))
        result = dict_to_simulation_result(json.loads(row[1]))
        return config, result

    def delete_simulation_result(self, sim_id: str) -> None:
        """Delete a simulation result."""
        conn = self._db.connect()
        conn.execute("DELETE FROM simulation_results WHERE id = ?", (sim_id,))
        conn.commit()

    # ------------------------------------------------------------------
    # Notes CRUD
    # ------------------------------------------------------------------

    def add_note(
        self,
        parent_type: str,
        parent_id: str,
        content: str,
    ) -> str:
        """Add a note to a design or simulation.

        Args:
            parent_type: 'design' or 'simulation'.
            parent_id: ID of the parent entity.
            content: Note text.

        Returns:
            Note ID.
        """
        conn = self._db.connect()
        note_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO notes (id, parent_type, parent_id, content)
               VALUES (?, ?, ?, ?)""",
            (note_id, parent_type, parent_id, content),
        )
        conn.commit()
        return note_id

    def get_notes(
        self,
        parent_type: str,
        parent_id: str,
    ) -> list[dict]:
        """Get all notes for a parent entity.

        Args:
            parent_type: 'design' or 'simulation'.
            parent_id: ID of the parent entity.

        Returns:
            List of dicts with id, content, created_at.
        """
        conn = self._db.connect()
        rows = conn.execute(
            """SELECT id, content, created_at
               FROM notes
               WHERE parent_type = ? AND parent_id = ?
               ORDER BY created_at DESC""",
            (parent_type, parent_id),
        ).fetchall()
        return [
            {"id": r[0], "content": r[1], "created_at": r[2] or ""}
            for r in rows
        ]

    def delete_note(self, note_id: str) -> None:
        """Delete a note by ID."""
        conn = self._db.connect()
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()

    # ------------------------------------------------------------------
    # App Settings
    # ------------------------------------------------------------------

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        """Get an application setting."""
        conn = self._db.connect()
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Set an application setting (upsert)."""
        conn = self._db.connect()
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()

    def get_recent_designs(self, limit: int = 10) -> list[DesignSummary]:
        """Get recently opened designs."""
        recent_json = self.get_setting("recent_designs", "[]")
        try:
            recent_ids = json.loads(recent_json)[:limit]
        except (json.JSONDecodeError, TypeError):
            return []

        if not recent_ids:
            return []

        conn = self._db.connect()
        placeholders = ",".join("?" for _ in recent_ids)
        rows = conn.execute(
            f"""SELECT id, name, description, collimator_type, tags,
                       is_favorite, created_at, updated_at
                FROM designs WHERE id IN ({placeholders})""",
            recent_ids,
        ).fetchall()

        # Preserve order
        by_id = {}
        for r in rows:
            by_id[r[0]] = DesignSummary(
                id=r[0], name=r[1], description=r[2] or "",
                collimator_type=r[3],
                tags=r[4].split(",") if r[4] else [],
                is_favorite=bool(r[5]),
                created_at=r[6] or "", updated_at=r[7] or "",
            )
        return [by_id[rid] for rid in recent_ids if rid in by_id]

    def _add_recent(self, design_id: str) -> None:
        """Add design to recent list (most recent first, max 10)."""
        recent_json = self.get_setting("recent_designs", "[]")
        try:
            recent_ids = json.loads(recent_json)
        except (json.JSONDecodeError, TypeError):
            recent_ids = []

        if design_id in recent_ids:
            recent_ids.remove(design_id)
        recent_ids.insert(0, design_id)
        recent_ids = recent_ids[:10]

        self.set_setting("recent_designs", json.dumps(recent_ids))
