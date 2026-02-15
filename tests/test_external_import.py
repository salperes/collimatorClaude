"""Tests for ExternalFormatImporter — external JSON file format import.

Covers: energy mapping, aperture types (slit/pinhole/open), aperture height,
phantom import (wire/grid), probe skip, layer collapse, multi-stage gaps.
"""

import json

import pytest

from app.export.external_import import ExternalFormatImporter
from app.models.geometry import CollimatorType
from app.models.phantom import WirePhantom, GridPhantom


# ── Helpers ──────────────────────────────────────────────────────────

def _make_external_data(**overrides) -> dict:
    """Minimal valid external format data."""
    data = {
        "name": "Test Project",
        "source": {
            "focal_spot_size_mm": 2.0,
            "distribution": "gaussian",
            "energy_kev": 160.0,
        },
        "detector": {
            "distance_mm": 1000.0,
            "width_mm": 600.0,
        },
        "stages": [
            {
                "id": "stage-1",
                "name": "Stage 1",
                "distance_from_source_mm": 100.0,
                "depth_mm": 50.0,
                "outer_width_mm": 150.0,
                "aperture_type": "slit",
                "aperture_width_entry_mm": 10.0,
                "aperture_width_exit_mm": 10.0,
                "layers": [
                    {
                        "id": "layer-1",
                        "material_id": "Pb",
                        "thickness_mm": 50.0,
                        "purpose": "shielding",
                    }
                ],
            }
        ],
        "probes": [],
        "phantoms": [],
    }
    data.update(overrides)
    return data


def _write_and_import(tmp_path, data: dict):
    """Write external data to JSON file and import it."""
    path = str(tmp_path / "external.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    importer = ExternalFormatImporter()
    return importer.import_file(path)


@pytest.fixture
def importer():
    return ExternalFormatImporter()


# ── Format Detection ────────────────────────────────────────────────

class TestCanImport:

    def test_detects_external_format(self, importer):
        data = _make_external_data()
        assert importer.can_import(data) is True

    def test_rejects_native_format(self, importer):
        data = {"stages": [{"outer_width": 100.0}]}
        assert importer.can_import(data) is False

    def test_rejects_empty_stages(self, importer):
        data = {"stages": []}
        assert importer.can_import(data) is False

    def test_rejects_no_stages(self, importer):
        data = {"name": "No stages"}
        assert importer.can_import(data) is False


# ── Basic Import ────────────────────────────────────────────────────

class TestBasicImport:

    def test_name_imported(self, tmp_path):
        geo = _write_and_import(tmp_path, _make_external_data(name="My Design"))
        assert geo.name == "My Design"

    def test_default_name(self, tmp_path):
        data = _make_external_data()
        del data["name"]
        geo = _write_and_import(tmp_path, data)
        assert geo.name == "Imported Design"

    def test_stage_count(self, tmp_path):
        geo = _write_and_import(tmp_path, _make_external_data())
        assert len(geo.stages) == 1

    def test_detector_sdd(self, tmp_path):
        geo = _write_and_import(tmp_path, _make_external_data())
        assert geo.detector.distance_from_source == 1000.0

    def test_detector_width(self, tmp_path):
        geo = _write_and_import(tmp_path, _make_external_data())
        assert geo.detector.width == 600.0

    def test_source_focal_spot(self, tmp_path):
        geo = _write_and_import(tmp_path, _make_external_data())
        assert geo.source.focal_spot_size == 2.0

    def test_source_distribution_gaussian(self, tmp_path):
        geo = _write_and_import(tmp_path, _make_external_data())
        assert geo.source.focal_spot_distribution.value == "gaussian"

    def test_first_stage_y_position(self, tmp_path):
        geo = _write_and_import(tmp_path, _make_external_data())
        assert geo.stages[0].y_position == 100.0


# ── Energy Mapping ──────────────────────────────────────────────────

class TestEnergyMapping:

    def test_low_energy_maps_to_kvp(self, tmp_path):
        data = _make_external_data()
        data["source"]["energy_kev"] = 160.0
        data["source"]["use_linac_simulation"] = False
        geo = _write_and_import(tmp_path, data)
        assert geo.source.energy_kVp == 160.0
        assert geo.source.energy_MeV is None

    def test_high_energy_maps_to_mev(self, tmp_path):
        data = _make_external_data()
        data["source"]["energy_kev"] = 6000.0
        geo = _write_and_import(tmp_path, data)
        assert geo.source.energy_MeV == 6.0
        assert geo.source.energy_kVp is None

    def test_linac_flag_forces_mev(self, tmp_path):
        data = _make_external_data()
        data["source"]["energy_kev"] = 800.0
        data["source"]["use_linac_simulation"] = True
        geo = _write_and_import(tmp_path, data)
        assert geo.source.energy_MeV == 0.8
        assert geo.source.energy_kVp is None

    def test_no_energy_leaves_none(self, tmp_path):
        data = _make_external_data()
        del data["source"]["energy_kev"]
        geo = _write_and_import(tmp_path, data)
        assert geo.source.energy_kVp is None
        assert geo.source.energy_MeV is None

    def test_exactly_1000_kev_maps_to_mev(self, tmp_path):
        data = _make_external_data()
        data["source"]["energy_kev"] = 1000.0
        geo = _write_and_import(tmp_path, data)
        assert geo.source.energy_MeV == 1.0


# ── Aperture Types ──────────────────────────────────────────────────

class TestApertureTypes:

    def test_slit_type(self, tmp_path):
        data = _make_external_data()
        data["stages"][0]["aperture_type"] = "slit"
        geo = _write_and_import(tmp_path, data)
        assert geo.type == CollimatorType.SLIT

    def test_pinhole_maps_to_pencil_beam(self, tmp_path):
        data = _make_external_data()
        data["stages"][0]["aperture_type"] = "pinhole"
        geo = _write_and_import(tmp_path, data)
        assert geo.type == CollimatorType.PENCIL_BEAM
        assert geo.stages[0].aperture.pencil_diameter == 10.0

    def test_open_uses_full_width(self, tmp_path):
        data = _make_external_data()
        data["stages"][0]["aperture_type"] = "open"
        data["stages"][0]["outer_width_mm"] = 150.0
        geo = _write_and_import(tmp_path, data)
        assert geo.stages[0].aperture.slit_width == 150.0

    def test_fan_type(self, tmp_path):
        data = _make_external_data()
        data["stages"][0]["aperture_type"] = "fan"
        geo = _write_and_import(tmp_path, data)
        assert geo.type == CollimatorType.FAN_BEAM
        assert geo.stages[0].aperture.fan_slit_width == 10.0

    def test_taper_angle_computed(self, tmp_path):
        data = _make_external_data()
        data["stages"][0]["aperture_width_entry_mm"] = 20.0
        data["stages"][0]["aperture_width_exit_mm"] = 10.0
        data["stages"][0]["depth_mm"] = 50.0
        geo = _write_and_import(tmp_path, data)
        # taper = atan2((20-10)/2, 50) = atan2(5, 50) ≈ 5.71°
        assert abs(geo.stages[0].aperture.taper_angle - 5.71) < 0.1


# ── Aperture Height ─────────────────────────────────────────────────

class TestApertureHeight:

    def test_height_imported(self, tmp_path):
        data = _make_external_data()
        data["stages"][0]["aperture_height_entry_mm"] = 8.0
        data["stages"][0]["aperture_height_exit_mm"] = 12.0
        geo = _write_and_import(tmp_path, data)
        assert geo.stages[0].aperture.slit_height == 12.0

    def test_entry_height_only(self, tmp_path):
        data = _make_external_data()
        data["stages"][0]["aperture_height_entry_mm"] = 8.0
        geo = _write_and_import(tmp_path, data)
        assert geo.stages[0].aperture.slit_height == 8.0

    def test_no_height_leaves_none(self, tmp_path):
        data = _make_external_data()
        geo = _write_and_import(tmp_path, data)
        assert geo.stages[0].aperture.slit_height is None


# ── Layer Collapse ──────────────────────────────────────────────────

class TestLayerCollapse:

    def test_single_layer_material(self, tmp_path):
        geo = _write_and_import(tmp_path, _make_external_data())
        assert geo.stages[0].material_id == "Pb"

    def test_multi_layer_uses_thickest_material(self, tmp_path):
        data = _make_external_data()
        data["stages"][0]["layers"] = [
            {"material_id": "Al", "thickness_mm": 5.0},
            {"material_id": "W", "thickness_mm": 30.0},
            {"material_id": "Pb", "thickness_mm": 15.0},
        ]
        geo = _write_and_import(tmp_path, data)
        assert geo.stages[0].material_id == "W"

    def test_no_layers_defaults_to_pb(self, tmp_path):
        data = _make_external_data()
        data["stages"][0]["layers"] = []
        data["stages"][0]["depth_mm"] = 40.0
        geo = _write_and_import(tmp_path, data)
        assert geo.stages[0].material_id == "Pb"


# ── Multi-Stage Gaps ────────────────────────────────────────────────

class TestMultiStageGaps:

    def _two_stage_data(self):
        data = _make_external_data()
        data["stages"].append({
            "id": "stage-2",
            "name": "Stage 2",
            "distance_from_source_mm": 200.0,
            "depth_mm": 30.0,
            "outer_width_mm": 120.0,
            "aperture_type": "slit",
            "aperture_width_entry_mm": 8.0,
            "aperture_width_exit_mm": 8.0,
            "layers": [{"material_id": "W", "thickness_mm": 30.0}],
        })
        return data

    def test_two_stages_imported(self, tmp_path):
        geo = _write_and_import(tmp_path, self._two_stage_data())
        assert len(geo.stages) == 2

    def test_y_positions(self, tmp_path):
        # Stage 1: distance_from_source_mm=100 → y_position=100
        # Stage 2: distance_from_source_mm=200 → y_position=200
        geo = _write_and_import(tmp_path, self._two_stage_data())
        assert geo.stages[0].y_position == 100.0
        assert geo.stages[1].y_position == 200.0

    def test_stages_sorted_by_distance(self, tmp_path):
        data = self._two_stage_data()
        # Reverse order in JSON — should still sort correctly
        data["stages"] = list(reversed(data["stages"]))
        geo = _write_and_import(tmp_path, data)
        assert geo.stages[0].name == "Stage 1"
        assert geo.stages[1].name == "Stage 2"


# ── Phantom Import ──────────────────────────────────────────────────

class TestPhantomImport:

    def test_wire_phantom_imported(self, tmp_path):
        data = _make_external_data(phantoms=[
            {
                "id": "p1",
                "name": "Resolution Wire",
                "type": "wire",
                "z_mm": 500.0,
                "material_id": "SS304",
                "diameter_mm": 1.5,
                "offset_x_mm": 0.0,
            }
        ])
        geo = _write_and_import(tmp_path, data)
        assert len(geo.phantoms) == 1
        assert isinstance(geo.phantoms[0], WirePhantom)

    def test_wire_phantom_fields(self, tmp_path):
        data = _make_external_data(phantoms=[
            {
                "id": "p1",
                "name": "Wire 2mm",
                "type": "wire",
                "z_mm": 450.0,
                "material_id": "Cu",
                "diameter_mm": 2.0,
                "offset_x_mm": 5.0,
            }
        ])
        geo = _write_and_import(tmp_path, data)
        w = geo.phantoms[0]
        assert w.diameter == 2.0
        assert w.config.position_y == 450.0
        assert w.config.material_id == "Cu"
        assert w.config.name == "Wire 2mm"

    def test_grid_phantom_imported(self, tmp_path):
        data = _make_external_data(phantoms=[
            {
                "id": "p2",
                "name": "Test Grid",
                "type": "grid",
                "z_mm": 600.0,
                "material_id": "SS304",
                "bar_width_mm": 1.0,
                "bar_thickness_mm": 2.0,
                "bar_spacing_mm": 1.5,
                "num_bars": 10,
                "offset_x_mm": 0.0,
            }
        ])
        geo = _write_and_import(tmp_path, data)
        assert len(geo.phantoms) == 1
        assert isinstance(geo.phantoms[0], GridPhantom)

    def test_grid_phantom_fields(self, tmp_path):
        data = _make_external_data(phantoms=[
            {
                "id": "p2",
                "name": "Grid",
                "type": "grid",
                "z_mm": 600.0,
                "material_id": "Fe",
                "bar_width_mm": 1.0,
                "bar_spacing_mm": 1.5,
                "num_bars": 10,
                "bar_thickness_mm": 2.0,
                "offset_x_mm": 0.0,
            }
        ])
        geo = _write_and_import(tmp_path, data)
        g = geo.phantoms[0]
        # pitch = bar_width + bar_spacing = 2.5
        assert g.pitch == 2.5
        # wire_diameter = bar_width
        assert g.wire_diameter == 1.0
        # size = num_bars * pitch = 25.0
        assert g.size == 25.0
        assert g.config.position_y == 600.0
        assert g.config.material_id == "Fe"

    def test_multiple_phantoms(self, tmp_path):
        data = _make_external_data(phantoms=[
            {"type": "wire", "z_mm": 300.0, "material_id": "W",
             "diameter_mm": 0.5, "offset_x_mm": 0.0},
            {"type": "grid", "z_mm": 400.0, "material_id": "Cu",
             "bar_width_mm": 0.5, "bar_spacing_mm": 0.5,
             "num_bars": 5, "bar_thickness_mm": 1.0, "offset_x_mm": 0.0},
        ])
        geo = _write_and_import(tmp_path, data)
        assert len(geo.phantoms) == 2
        assert isinstance(geo.phantoms[0], WirePhantom)
        assert isinstance(geo.phantoms[1], GridPhantom)

    def test_unknown_phantom_type_skipped(self, tmp_path):
        data = _make_external_data(phantoms=[
            {"type": "cylinder", "z_mm": 300.0, "material_id": "W"},
        ])
        geo = _write_and_import(tmp_path, data)
        assert len(geo.phantoms) == 0

    def test_no_phantoms_key(self, tmp_path):
        data = _make_external_data()
        del data["phantoms"]
        geo = _write_and_import(tmp_path, data)
        assert len(geo.phantoms) == 0


# ── Probes (skip) ───────────────────────────────────────────────────

class TestProbes:

    def test_probes_skipped_no_error(self, tmp_path):
        data = _make_external_data(probes=[
            {"id": "pr1", "name": "Center", "x_mm": 0.0, "z_mm": 500.0},
        ])
        geo = _write_and_import(tmp_path, data)
        # No probe model — just ensure no crash
        assert geo is not None


# ── Full Example (from spec) ────────────────────────────────────────

class TestFullExample:

    def test_spec_example(self, tmp_path):
        """Import the example from file_format_spec.md."""
        data = {
            "name": "Test Project",
            "source": {
                "focal_spot_size_mm": 2.0,
                "distribution": "gaussian",
                "energy_kev": 6000.0,
                "current_ma": 1.0,
                "linac_dose_rate_Gy_min_he": 0.008,
                "linac_dose_rate_Gy_min_le": 0.0025,
                "linac_ref_pps_hz": 260.0,
                "linac_current_pps_hz": 260.0,
                "pulse_width_us": 3.0,
                "linac_mode": "HE",
                "use_linac_simulation": True,
                "manual_dose_rate_Gy_min": 10.0,
                "simulation_ray_count_k": 10,
            },
            "detector": {
                "distance_mm": 1000.0,
                "width_mm": 600.0,
            },
            "stages": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Stage 1",
                    "distance_from_source_mm": 100.0,
                    "depth_mm": 50.0,
                    "outer_width_mm": 150.0,
                    "aperture_type": "slit",
                    "aperture_width_entry_mm": 10.0,
                    "aperture_width_exit_mm": 10.0,
                    "aperture_height_entry_mm": 10.0,
                    "aperture_height_exit_mm": 10.0,
                    "layers": [
                        {
                            "id": "layer-uuid-1",
                            "material_id": "Pb",
                            "thickness_mm": 50.0,
                            "purpose": "shielding",
                        }
                    ],
                }
            ],
            "probes": [],
            "phantoms": [
                {
                    "id": "phantom-uuid-1",
                    "name": "Resolution Wire",
                    "type": "wire",
                    "z_mm": 500.0,
                    "material_id": "SS304",
                    "diameter_mm": 1.5,
                    "offset_x_mm": 0.0,
                }
            ],
        }

        geo = _write_and_import(tmp_path, data)

        # Source
        assert geo.source.energy_MeV == 6.0
        assert geo.source.energy_kVp is None
        assert geo.source.focal_spot_size == 2.0
        assert geo.source.focal_spot_distribution.value == "gaussian"

        # Detector
        assert geo.detector.distance_from_source == 1000.0
        assert geo.detector.width == 600.0

        # Stage
        assert len(geo.stages) == 1
        s = geo.stages[0]
        assert s.name == "Stage 1"
        assert s.material_id == "Pb"
        assert s.y_position == 100.0
        assert s.outer_width == 150.0
        assert s.outer_height == 50.0
        assert s.aperture.slit_width == 10.0
        assert s.aperture.slit_height == 10.0

        # Phantom
        assert len(geo.phantoms) == 1
        p = geo.phantoms[0]
        assert isinstance(p, WirePhantom)
        assert p.diameter == 1.5
        assert p.config.material_id == "SS304"
        assert p.config.position_y == 500.0

        # Global
        assert geo.type == CollimatorType.SLIT


# ── Error Handling ──────────────────────────────────────────────────

class TestErrorHandling:

    def test_invalid_format_raises(self, tmp_path):
        data = {"name": "Bad", "stages": [{"outer_width_mm": 100}]}
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            json.dump(data, f)

        importer = ExternalFormatImporter()
        with pytest.raises(ValueError, match="distance_from_source_mm"):
            importer.import_file(path)

    def test_empty_stages_raises(self, tmp_path):
        data = {"name": "Empty", "stages": []}
        path = str(tmp_path / "empty.json")
        with open(path, "w") as f:
            json.dump(data, f)

        importer = ExternalFormatImporter()
        with pytest.raises(ValueError):
            importer.import_file(path)
