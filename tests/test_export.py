"""Tests for export modules — JSON, CSV, CDT.

PNG/image export tests are skipped (requires QApplication).
PDF tests are skipped (requires ReportLab + complex setup).
"""

import csv
import json
import zipfile

import numpy as np
import pytest

from app.constants import GEOMETRY_SCHEMA_VERSION
from app.database.db_manager import DatabaseManager
from app.database.design_repository import DesignRepository
from app.export.csv_export import CsvExporter
from app.export.json_export import JsonExporter
from app.export.cdt_export import CdtExporter
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


# ── Helpers ──────────────────────────────────────────────────────────

def _make_geometry(name: str = "Export Test") -> CollimatorGeometry:
    return CollimatorGeometry(
        name=name,
        type=CollimatorType.FAN_BEAM,
        stages=[
            CollimatorStage(
                id="s0",
                name="Primary",
                purpose=StagePurpose.PRIMARY_SHIELDING,
                material_id="Pb",
                y_position=25.0,
            ),
        ],
    )


def _make_result() -> SimulationResult:
    return SimulationResult(
        energy_keV=1000.0,
        num_rays=360,
        beam_profile=BeamProfile(
            positions_mm=np.array([-50.0, -25.0, 0.0, 25.0, 50.0]),
            intensities=np.array([0.01, 0.5, 1.0, 0.5, 0.01]),
            angles_rad=np.array([-0.2, -0.1, 0.0, 0.1, 0.2]),
        ),
        quality_metrics=QualityMetrics(fwhm_mm=50.0),
        elapsed_seconds=1.0,
    )


@pytest.fixture
def repo(tmp_path):
    db = DatabaseManager(tmp_path / "test.db")
    db.initialize_database()
    return DesignRepository(db)


# ── JSON Export ──────────────────────────────────────────────────────

class TestJsonExport:
    """JSON geometry export/import round-trip."""

    def test_export_creates_file(self, tmp_path):
        exporter = JsonExporter()
        geo = _make_geometry()
        path = str(tmp_path / "test.json")

        exporter.export_geometry(geo, path)
        assert (tmp_path / "test.json").exists()

    def test_export_contains_schema_version(self, tmp_path):
        exporter = JsonExporter()
        geo = _make_geometry()
        path = str(tmp_path / "test.json")

        exporter.export_geometry(geo, path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["schema_version"] == GEOMETRY_SCHEMA_VERSION

    def test_export_formatted(self, tmp_path):
        exporter = JsonExporter()
        geo = _make_geometry()
        path = str(tmp_path / "test.json")

        exporter.export_geometry(geo, path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Formatted JSON has indentation
        assert "  " in content

    def test_round_trip(self, tmp_path):
        exporter = JsonExporter()
        geo = _make_geometry("Round Trip Test")
        path = str(tmp_path / "roundtrip.json")

        exporter.export_geometry(geo, path)
        loaded = exporter.import_geometry(path)

        assert loaded.type == CollimatorType.FAN_BEAM
        assert len(loaded.stages) == 1
        assert loaded.stages[0].material_id == "Pb"

    def test_unicode_support(self, tmp_path):
        exporter = JsonExporter()
        geo = _make_geometry("Kolimatör Tasarımı")
        path = str(tmp_path / "unicode.json")

        exporter.export_geometry(geo, path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Turkish characters preserved (ensure_ascii=False)
        assert "Kolimatör" in json.dumps(data, ensure_ascii=False)


# ── CSV Export ───────────────────────────────────────────────────────

class TestCsvExport:
    """CSV export with BOM UTF-8."""

    def test_beam_profile_csv(self, tmp_path):
        exporter = CsvExporter()
        result = _make_result()
        path = str(tmp_path / "beam.csv")

        exporter.export_beam_profile(result, path)
        assert (tmp_path / "beam.csv").exists()

    def test_beam_profile_bom(self, tmp_path):
        exporter = CsvExporter()
        result = _make_result()
        path = str(tmp_path / "beam.csv")

        exporter.export_beam_profile(result, path)
        with open(path, "rb") as f:
            bom = f.read(3)
        assert bom == b"\xef\xbb\xbf"  # UTF-8 BOM

    def test_beam_profile_columns(self, tmp_path):
        exporter = CsvExporter()
        result = _make_result()
        path = str(tmp_path / "beam.csv")

        exporter.export_beam_profile(result, path)
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)

        assert header == ["Position (mm)", "Intensity", "Angle (degree)"]

    def test_beam_profile_row_count(self, tmp_path):
        exporter = CsvExporter()
        result = _make_result()
        path = str(tmp_path / "beam.csv")

        exporter.export_beam_profile(result, path)
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header + 5 data rows
        assert len(rows) == 6

    def test_attenuation_csv(self, tmp_path):
        exporter = CsvExporter()
        rows = [
            {
                "energy_keV": 100,
                "material": "Pb",
                "thickness_mm": 10,
                "mu_rho": 5.55,
                "mu": 63.0,
                "hvl_mm": 0.11,
                "tvl_mm": 0.37,
                "transmission_pct": 0.1,
                "attenuation_dB": 30.0,
            },
        ]
        path = str(tmp_path / "atten.csv")

        exporter.export_attenuation_summary(rows, path)
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)
            data = next(reader)

        assert "Energy (keV)" in header
        assert data[0] == "100"
        assert data[1] == "Pb"


# ── CDT Export ───────────────────────────────────────────────────────

class TestCdtExport:
    """CDT project file (ZIP) export/import."""

    def test_export_creates_zip(self, tmp_path, repo):
        design_id = repo.save_design(_make_geometry(), "CDT Test")
        exporter = CdtExporter()
        path = str(tmp_path / "test.cdt")

        exporter.export_project(design_id, repo, path)
        assert zipfile.is_zipfile(path)

    def test_zip_contents(self, tmp_path, repo):
        design_id = repo.save_design(_make_geometry(), "Contents")
        exporter = CdtExporter()
        path = str(tmp_path / "contents.cdt")

        exporter.export_project(design_id, repo, path)
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()

        assert "metadata.json" in names
        assert "design.json" in names
        assert any(n.startswith("versions/") for n in names)

    def test_metadata_fields(self, tmp_path, repo):
        design_id = repo.save_design(_make_geometry("Meta Test"), "Meta Test")
        exporter = CdtExporter()
        path = str(tmp_path / "meta.cdt")

        exporter.export_project(design_id, repo, path)
        with zipfile.ZipFile(path, "r") as zf:
            metadata = json.loads(zf.read("metadata.json"))

        assert "app_version" in metadata
        assert "schema_version" in metadata
        assert metadata["design_name"] == "Meta Test"

    def test_thumbnail_included(self, tmp_path, repo):
        design_id = repo.save_design(_make_geometry(), "Thumb CDT")
        thumb = b"\x89PNG_test_data"
        repo.update_thumbnail(design_id, thumb)

        exporter = CdtExporter()
        path = str(tmp_path / "thumb.cdt")

        exporter.export_project(design_id, repo, path, thumbnail=thumb)
        with zipfile.ZipFile(path, "r") as zf:
            assert "thumbnail.png" in zf.namelist()
            assert zf.read("thumbnail.png") == thumb

    def test_import_creates_design(self, tmp_path, repo):
        # Export first
        design_id = repo.save_design(_make_geometry("Import Me"), "Import Me")
        exporter = CdtExporter()
        path = str(tmp_path / "import.cdt")
        exporter.export_project(design_id, repo, path)

        # Import
        new_id = exporter.import_project(path, repo)
        assert new_id != design_id

        # Verify imported design exists
        loaded = repo.load_design(new_id)
        assert loaded.type == CollimatorType.FAN_BEAM

    def test_import_preserves_name(self, tmp_path, repo):
        design_id = repo.save_design(_make_geometry("Named Export"), "Named Export")
        exporter = CdtExporter()
        path = str(tmp_path / "named.cdt")
        exporter.export_project(design_id, repo, path)

        new_id = exporter.import_project(path, repo)
        name = repo.get_design_name(new_id)
        assert name == "Named Export"

    def test_simulation_included_in_zip(self, tmp_path, repo):
        design_id = repo.save_design(_make_geometry(), "With Sim")
        config = SimulationConfig()
        result = _make_result()
        repo.save_simulation_result(design_id, config, result, "Test Sim")

        exporter = CdtExporter()
        path = str(tmp_path / "sims.cdt")
        exporter.export_project(design_id, repo, path)

        with zipfile.ZipFile(path, "r") as zf:
            sim_files = [n for n in zf.namelist() if n.startswith("simulations/")]
        assert len(sim_files) == 1
