"""Tests for app.database.design_repository — CRUD, versioning, simulation results.

Uses an in-memory SQLite database for isolation.
"""

import json
import numpy as np
import pytest

from app.database.db_manager import DatabaseManager
from app.database.design_repository import DesignRepository
from app.models.geometry import (
    CollimatorGeometry,
    CollimatorStage,
    CollimatorType,
    StagePurpose,
)
from app.models.simulation import (
    BeamProfile,
    QualityMetrics,
    SimulationConfig,
    SimulationResult,
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def repo(tmp_path):
    """Fresh in-memory repository for each test."""
    db = DatabaseManager(tmp_path / "test.db")
    db.initialize_database()
    return DesignRepository(db)


def _make_geometry(name: str = "Test Design", ctype: CollimatorType = CollimatorType.FAN_BEAM) -> CollimatorGeometry:
    """Create a minimal geometry for testing."""
    return CollimatorGeometry(
        id="",
        name=name,
        type=ctype,
        stages=[
            CollimatorStage(
                id="s0",
                name="Primary",
                purpose=StagePurpose.PRIMARY_SHIELDING,
                outer_width=100.0,
                outer_height=200.0,
            ),
        ],
    )


def _make_result(energy: float = 1000.0) -> SimulationResult:
    """Create a minimal simulation result."""
    return SimulationResult(
        energy_keV=energy,
        num_rays=360,
        beam_profile=BeamProfile(
            positions_mm=np.linspace(-50, 50, 20),
            intensities=np.ones(20) * 0.5,
            angles_rad=np.linspace(-0.3, 0.3, 20),
        ),
        quality_metrics=QualityMetrics(fwhm_mm=60.0),
        elapsed_seconds=0.8,
        include_buildup=True,
    )


# ── Design CRUD ──────────────────────────────────────────────────────

class TestDesignCRUD:
    """Basic save/load/update/delete operations."""

    def test_save_and_load(self, repo):
        geo = _make_geometry("My Design")
        design_id = repo.save_design(geo, "My Design", "Test description", ["tag1", "tag2"])

        loaded = repo.load_design(design_id)
        assert loaded.name == "My Design"
        assert loaded.type == CollimatorType.FAN_BEAM
        assert len(loaded.stages) == 1

    def test_save_creates_first_version(self, repo):
        geo = _make_geometry()
        design_id = repo.save_design(geo, "Design A")

        versions = repo.get_version_history(design_id)
        assert len(versions) == 1
        assert versions[0].version_number == 1
        assert versions[0].change_note == "Ilk kayit"

    def test_load_nonexistent_raises(self, repo):
        with pytest.raises(KeyError):
            repo.load_design("nonexistent-id")

    def test_update_creates_new_version(self, repo):
        geo = _make_geometry()
        design_id = repo.save_design(geo, "Design B")

        geo2 = _make_geometry("Updated")
        repo.update_design(design_id, geo2, "Changed dimensions")

        versions = repo.get_version_history(design_id)
        assert len(versions) == 2
        assert versions[0].version_number == 2  # newest first
        assert versions[0].change_note == "Changed dimensions"

    def test_delete_design(self, repo):
        geo = _make_geometry()
        design_id = repo.save_design(geo, "To Delete")
        repo.delete_design(design_id)

        with pytest.raises(KeyError):
            repo.load_design(design_id)

    def test_get_design_name(self, repo):
        geo = _make_geometry()
        design_id = repo.save_design(geo, "Named Design")
        assert repo.get_design_name(design_id) == "Named Design"

    def test_get_design_name_nonexistent(self, repo):
        assert repo.get_design_name("nope") == ""


# ── List & Filter ────────────────────────────────────────────────────

class TestListDesigns:
    """Design listing with filters."""

    def test_list_all(self, repo):
        repo.save_design(_make_geometry(), "Design 1")
        repo.save_design(_make_geometry(), "Design 2")
        designs = repo.list_designs()
        assert len(designs) == 2

    def test_filter_by_type(self, repo):
        repo.save_design(_make_geometry(ctype=CollimatorType.FAN_BEAM), "Fan")
        repo.save_design(_make_geometry(ctype=CollimatorType.PENCIL_BEAM), "Pencil")

        fans = repo.list_designs(filter_type="fan_beam")
        assert len(fans) == 1
        assert fans[0].name == "Fan"

    def test_filter_by_tag(self, repo):
        repo.save_design(_make_geometry(), "Tagged", tags=["medical", "test"])
        repo.save_design(_make_geometry(), "Untagged")

        tagged = repo.list_designs(filter_tag="medical")
        assert len(tagged) == 1
        assert tagged[0].name == "Tagged"

    def test_search_text(self, repo):
        repo.save_design(_make_geometry(), "Alpha Design", "Desc alpha")
        repo.save_design(_make_geometry(), "Beta Design", "Desc beta")

        results = repo.list_designs(search_text="Alpha")
        assert len(results) == 1
        assert results[0].name == "Alpha Design"

    def test_favorites_only(self, repo):
        d1 = repo.save_design(_make_geometry(), "Fav")
        repo.save_design(_make_geometry(), "Not Fav")
        repo.toggle_favorite(d1)

        favs = repo.list_designs(favorites_only=True)
        assert len(favs) == 1
        assert favs[0].name == "Fav"


# ── Favorites & Thumbnails ───────────────────────────────────────────

class TestFavoriteAndThumbnail:

    def test_toggle_favorite(self, repo):
        design_id = repo.save_design(_make_geometry(), "Test")

        # Initially not favorite
        designs = repo.list_designs()
        assert designs[0].is_favorite is False

        # Toggle on
        repo.toggle_favorite(design_id)
        designs = repo.list_designs()
        assert designs[0].is_favorite is True

        # Toggle off
        repo.toggle_favorite(design_id)
        designs = repo.list_designs()
        assert designs[0].is_favorite is False

    def test_update_thumbnail(self, repo):
        design_id = repo.save_design(_make_geometry(), "Thumb")
        thumbnail = b"\x89PNG\r\n\x1a\nfake_png_data"
        repo.update_thumbnail(design_id, thumbnail)

        # Verify thumbnail stored (read raw)
        conn = repo._db.connect()
        row = conn.execute(
            "SELECT thumbnail_png FROM designs WHERE id = ?", (design_id,)
        ).fetchone()
        assert row[0] == thumbnail


# ── Version History ──────────────────────────────────────────────────

class TestVersionHistory:

    def test_version_ordering(self, repo):
        geo = _make_geometry()
        design_id = repo.save_design(geo, "Versioned")

        for i in range(3):
            repo.update_design(design_id, geo, f"Update {i + 1}")

        versions = repo.get_version_history(design_id)
        assert len(versions) == 4  # 1 initial + 3 updates
        # Newest first
        assert versions[0].version_number == 4
        assert versions[-1].version_number == 1

    def test_load_specific_version(self, repo):
        geo1 = _make_geometry("Version 1")
        design_id = repo.save_design(geo1, "V1")

        geo2 = _make_geometry("Version 2")
        repo.update_design(design_id, geo2, "Bump")

        loaded_v1 = repo.load_version(design_id, 1)
        assert loaded_v1 is not None

    def test_load_nonexistent_version(self, repo):
        design_id = repo.save_design(_make_geometry(), "Test")
        with pytest.raises(KeyError):
            repo.load_version(design_id, 999)

    def test_restore_version(self, repo):
        geo = _make_geometry()
        design_id = repo.save_design(geo, "Restore Test")
        repo.update_design(design_id, geo, "V2 changes")

        repo.restore_version(design_id, 1)

        versions = repo.get_version_history(design_id)
        assert len(versions) == 3
        assert "geri yuklendi" in versions[0].change_note


# ── Simulation Results ───────────────────────────────────────────────

class TestSimulationResults:

    def test_save_and_load(self, repo):
        design_id = repo.save_design(_make_geometry(), "Sim Design")
        config = SimulationConfig(energy_points=[1000.0], num_rays=360)
        result = _make_result()

        sim_id = repo.save_simulation_result(design_id, config, result, "Test Sim")

        loaded_config, loaded_result = repo.load_simulation_result(sim_id)
        assert loaded_result.energy_keV == 1000.0
        assert loaded_result.num_rays == 360
        np.testing.assert_allclose(
            loaded_result.beam_profile.positions_mm,
            result.beam_profile.positions_mm,
            rtol=1e-10,
        )

    def test_list_simulation_results(self, repo):
        design_id = repo.save_design(_make_geometry(), "Multi Sim")
        config = SimulationConfig()

        repo.save_simulation_result(design_id, config, _make_result(500.0))
        repo.save_simulation_result(design_id, config, _make_result(1000.0))

        sims = repo.list_simulation_results(design_id)
        assert len(sims) == 2

    def test_auto_name(self, repo):
        design_id = repo.save_design(_make_geometry(), "Auto Name")
        config = SimulationConfig()
        result = _make_result(662.0)
        result.num_rays = 720

        repo.save_simulation_result(design_id, config, result)

        sims = repo.list_simulation_results(design_id)
        assert "662" in sims[0].name
        assert "720" in sims[0].name

    def test_delete_simulation(self, repo):
        design_id = repo.save_design(_make_geometry(), "Del Sim")
        config = SimulationConfig()
        sim_id = repo.save_simulation_result(design_id, config, _make_result())

        repo.delete_simulation_result(sim_id)

        sims = repo.list_simulation_results(design_id)
        assert len(sims) == 0

    def test_load_nonexistent_simulation(self, repo):
        with pytest.raises(KeyError):
            repo.load_simulation_result("nonexistent")


# ── Settings ─────────────────────────────────────────────────────────

class TestSettings:

    def test_get_set(self, repo):
        repo.set_setting("theme", "dark")
        assert repo.get_setting("theme") == "dark"

    def test_get_default(self, repo):
        assert repo.get_setting("missing", "default") == "default"

    def test_upsert(self, repo):
        repo.set_setting("key", "value1")
        repo.set_setting("key", "value2")
        assert repo.get_setting("key") == "value2"


# ── Recent Designs ───────────────────────────────────────────────────

class TestRecentDesigns:

    def test_save_adds_to_recent(self, repo):
        d1 = repo.save_design(_make_geometry(), "Recent 1")
        d2 = repo.save_design(_make_geometry(), "Recent 2")

        recent = repo.get_recent_designs()
        assert len(recent) == 2
        # Most recent first
        assert recent[0].name == "Recent 2"
        assert recent[1].name == "Recent 1"

    def test_recent_limit(self, repo):
        for i in range(15):
            repo.save_design(_make_geometry(), f"Design {i}")

        recent = repo.get_recent_designs(limit=5)
        assert len(recent) == 5

    def test_recent_no_duplicates(self, repo):
        d1 = repo.save_design(_make_geometry(), "Dup Test")
        # Manually add again
        repo._add_recent(d1)

        recent_json = repo.get_setting("recent_designs")
        recent_ids = json.loads(recent_json)
        assert recent_ids.count(d1) == 1
