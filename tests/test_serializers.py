"""Tests for app.core.serializers — round-trip dataclass ↔ dict conversion.

Covers:
  - Geometry round-trip (Enum, nested dataclasses, phantom union)
  - NumPy array preservation in SimulationResult
  - v1.x schema migration (body → stages[0])
  - v2.x layer migration (layers list → material_id)
  - v2→v3 position migration (gap_after → y_position)
  - Edge cases: empty phantoms, optional fields, default values
"""

import numpy as np
import pytest

from app.constants import GEOMETRY_SCHEMA_VERSION
from app.core.serializers import (
    dict_to_geometry,
    dict_to_simulation_config,
    dict_to_simulation_result,
    geometry_to_dict,
    simulation_config_to_dict,
    simulation_result_to_dict,
)
from app.models.geometry import (
    ApertureConfig,
    CollimatorGeometry,
    CollimatorStage,
    CollimatorType,
    DetectorConfig,
    FocalSpotDistribution,
    Point2D,
    SourceConfig,
    StagePurpose,
)
from app.models.phantom import (
    GridPhantom,
    LinePairPhantom,
    PhantomConfig,
    PhantomType,
    WirePhantom,
)
from app.models.simulation import (
    BeamProfile,
    ComptonConfig,
    MetricStatus,
    QualityMetric,
    QualityMetrics,
    SimulationConfig,
    SimulationResult,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _make_geometry(**kwargs) -> CollimatorGeometry:
    """Build a test geometry with sensible defaults."""
    defaults = dict(
        id="test-geo-001",
        name="Test Collimator",
        type=CollimatorType.FAN_BEAM,
        source=SourceConfig(
            position=Point2D(0.0, 0.0),
            energy_kVp=320,
            focal_spot_size=2.0,
            focal_spot_distribution=FocalSpotDistribution.GAUSSIAN,
        ),
        stages=[
            CollimatorStage(
                id="stage-0",
                name="Primary",
                order=0,
                purpose=StagePurpose.PRIMARY_SHIELDING,
                outer_width=120.0,
                outer_height=250.0,
                aperture=ApertureConfig(fan_angle=30.0, fan_slit_width=5.0),
                material_id="Pb",
                y_position=25.0,
                x_offset=0.0,
            ),
        ],
        detector=DetectorConfig(
            position=Point2D(0, 500),
            width=400.0,
            distance_from_source=1000.0,
        ),
        phantoms=[],
    )
    defaults.update(kwargs)
    return CollimatorGeometry(**defaults)


def _make_simulation_result() -> SimulationResult:
    """Build a test simulation result with real arrays."""
    positions = np.linspace(-100, 100, 50)
    intensities = np.exp(-0.5 * (positions / 30) ** 2)
    angles = np.linspace(-0.5, 0.5, 50)

    return SimulationResult(
        energy_keV=1000.0,
        num_rays=360,
        beam_profile=BeamProfile(
            positions_mm=positions,
            intensities=intensities,
            angles_rad=angles,
        ),
        quality_metrics=QualityMetrics(
            penumbra_left_mm=4.5,
            penumbra_right_mm=4.8,
            penumbra_max_mm=4.8,
            flatness_pct=2.1,
            leakage_avg_pct=0.05,
            leakage_max_pct=0.12,
            collimation_ratio=2000.0,
            collimation_ratio_dB=33.0,
            fwhm_mm=60.0,
            metrics=[
                QualityMetric(
                    name="Penumbra",
                    value=4.8,
                    unit="mm",
                    status=MetricStatus.EXCELLENT,
                    threshold_excellent=5.0,
                    threshold_acceptable=10.0,
                ),
            ],
            all_pass=True,
        ),
        elapsed_seconds=1.5,
        include_buildup=True,
    )


# ── Geometry serialization ───────────────────────────────────────────

class TestGeometrySerialization:
    """geometry_to_dict / dict_to_geometry round-trip."""

    def test_round_trip_basic(self):
        geo = _make_geometry()
        d = geometry_to_dict(geo)
        restored = dict_to_geometry(d)

        assert restored.id == geo.id
        assert restored.name == geo.name
        assert restored.type == CollimatorType.FAN_BEAM

    def test_schema_version_embedded(self):
        d = geometry_to_dict(_make_geometry())
        assert d["schema_version"] == GEOMETRY_SCHEMA_VERSION

    def test_enums_serialized_as_values(self):
        d = geometry_to_dict(_make_geometry())
        assert d["type"] == "fan_beam"
        assert d["stages"][0]["purpose"] == "primary_shielding"
        assert d["source"]["focal_spot_distribution"] == "gaussian"

    def test_source_round_trip(self):
        geo = _make_geometry()
        restored = dict_to_geometry(geometry_to_dict(geo))

        assert restored.source.position.x == 0.0
        assert restored.source.energy_kVp == 320
        assert restored.source.focal_spot_size == 2.0
        assert restored.source.focal_spot_distribution == FocalSpotDistribution.GAUSSIAN

    def test_stage_round_trip(self):
        geo = _make_geometry()
        restored = dict_to_geometry(geometry_to_dict(geo))

        assert len(restored.stages) == 1
        s = restored.stages[0]
        assert s.id == "stage-0"
        assert s.name == "Primary"
        assert s.purpose == StagePurpose.PRIMARY_SHIELDING
        assert s.outer_width == 120.0
        assert s.outer_height == 250.0
        assert s.y_position == 25.0
        assert s.x_offset == 0.0

    def test_aperture_round_trip(self):
        geo = _make_geometry()
        restored = dict_to_geometry(geometry_to_dict(geo))
        a = restored.stages[0].aperture
        assert a.fan_angle == 30.0
        assert a.fan_slit_width == 5.0

    def test_material_round_trip(self):
        geo = _make_geometry()
        restored = dict_to_geometry(geometry_to_dict(geo))
        s = restored.stages[0]
        assert s.material_id == "Pb"

    def test_detector_round_trip(self):
        geo = _make_geometry()
        restored = dict_to_geometry(geometry_to_dict(geo))
        assert restored.detector.width == 400.0
        assert restored.detector.distance_from_source == 1000.0

    def test_multi_stage(self):
        stages = [
            CollimatorStage(id="s0", order=0, purpose=StagePurpose.PRIMARY_SHIELDING,
                            material_id="W", y_position=25.0),
            CollimatorStage(id="s1", order=1, purpose=StagePurpose.FAN_DEFINITION,
                            material_id="Pb", y_position=155.0),
            CollimatorStage(id="s2", order=2, purpose=StagePurpose.PENUMBRA_TRIMMER,
                            material_id="Cu", y_position=235.0),
        ]
        geo = _make_geometry(stages=stages)
        restored = dict_to_geometry(geometry_to_dict(geo))

        assert len(restored.stages) == 3
        assert restored.stages[0].purpose == StagePurpose.PRIMARY_SHIELDING
        assert restored.stages[0].material_id == "W"
        assert restored.stages[0].y_position == 25.0
        assert restored.stages[1].purpose == StagePurpose.FAN_DEFINITION
        assert restored.stages[1].material_id == "Pb"
        assert restored.stages[2].purpose == StagePurpose.PENUMBRA_TRIMMER
        assert restored.stages[2].material_id == "Cu"

    def test_empty_geometry(self):
        geo = CollimatorGeometry()
        d = geometry_to_dict(geo)
        restored = dict_to_geometry(d)
        assert restored.type == CollimatorType.FAN_BEAM
        assert len(restored.stages) >= 1

    def test_collimator_types(self):
        for ctype in CollimatorType:
            geo = _make_geometry(type=ctype)
            restored = dict_to_geometry(geometry_to_dict(geo))
            assert restored.type == ctype


# ── v1.x Migration ───────────────────────────────────────────────────

class TestV1Migration:
    """v1.x schema migration: body → stages[0]."""

    def test_v1_body_migrated_to_stages(self):
        v1_data = {
            "id": "v1-design",
            "name": "Old Design",
            "type": "fan_beam",
            "source": {"position": {"x": 0, "y": 0}},
            "body": {
                "id": "body-0",
                "name": "Main",
                "outer_width": 100.0,
                "outer_height": 200.0,
                "material_id": "Pb",
            },
            "detector": {},
        }
        geo = dict_to_geometry(v1_data)
        assert len(geo.stages) == 1
        assert geo.stages[0].id == "body-0"
        assert geo.stages[0].outer_width == 100.0
        assert geo.stages[0].material_id == "Pb"

    def test_v1_with_stages_ignored(self):
        """If both body and stages exist, stages wins."""
        v1_data = {
            "type": "slit",
            "stages": [{"id": "s0"}],
            "body": {"id": "body-ignored"},
        }
        geo = dict_to_geometry(v1_data)
        assert geo.stages[0].id == "s0"


# ── v2.x Layer Migration ─────────────────────────────────────────────

class TestLayerMigration:
    """v2.x layer migration: layers list → material_id."""

    def test_single_layer_migrated(self):
        """Old single-layer stage migrates material_id."""
        data = {
            "type": "fan_beam",
            "stages": [{
                "id": "stage-old",
                "purpose": "primary_shielding",
                "outer_width": 120.0,
                "outer_height": 250.0,
                "layers": [
                    {
                        "id": "layer-0",
                        "order": 0,
                        "material_id": "W",
                        "thickness": 15.0,
                        "purpose": "primary_shielding",
                    },
                ],
            }],
            "source": {"position": {"x": 0, "y": 0}},
            "detector": {},
        }
        geo = dict_to_geometry(data)
        s = geo.stages[0]
        assert s.material_id == "W"

    def test_multi_layer_takes_first_material(self):
        """Old multi-layer stage takes first material."""
        data = {
            "type": "fan_beam",
            "stages": [{
                "id": "stage-old",
                "layers": [
                    {"material_id": "Pb", "thickness": 20.0},
                    {"material_id": "SS304", "thickness": 5.0},
                    {"material_id": "Cu", "thickness": 3.0},
                ],
            }],
            "source": {"position": {"x": 0, "y": 0}},
            "detector": {},
        }
        geo = dict_to_geometry(data)
        s = geo.stages[0]
        assert s.material_id == "Pb"

    def test_empty_layers_uses_defaults(self):
        """Old stage with empty layers list falls back to defaults."""
        data = {
            "type": "fan_beam",
            "stages": [{
                "id": "stage-old",
                "layers": [],
            }],
            "source": {},
            "detector": {},
        }
        geo = dict_to_geometry(data)
        s = geo.stages[0]
        assert s.material_id == "Pb"  # default

    def test_new_format_not_affected_by_migration(self):
        """Stage with material_id set directly is not overwritten by layers key."""
        data = {
            "type": "fan_beam",
            "stages": [{
                "id": "stage-new",
                "material_id": "W",
                "y_position": 50.0,
                "layers": [
                    {"material_id": "Pb", "thickness": 10.0},
                ],
            }],
            "source": {},
            "detector": {},
        }
        geo = dict_to_geometry(data)
        s = geo.stages[0]
        # material_id is already set, so layers migration should NOT overwrite
        assert s.material_id == "W"
        assert s.y_position == 50.0

    def test_v1_body_with_layers_migrated(self):
        """v1 body key + old layers format: both migrations apply."""
        data = {
            "id": "v1-with-layers",
            "type": "fan_beam",
            "source": {"position": {"x": 0, "y": 0}},
            "body": {
                "id": "body-0",
                "outer_width": 100.0,
                "outer_height": 200.0,
                "layers": [
                    {"material_id": "W", "thickness": 10.0},
                    {"material_id": "Pb", "thickness": 15.0},
                ],
            },
            "detector": {},
        }
        geo = dict_to_geometry(data)
        assert len(geo.stages) == 1
        assert geo.stages[0].material_id == "W"


# ── v2→v3 Position Migration ─────────────────────────────────────────

class TestPositionMigration:
    """v2→v3 migration: gap_after + source_to_assembly_distance → y_position."""

    def test_single_stage_with_assembly_distance(self):
        """source_to_assembly_distance maps to first stage y_position."""
        data = {
            "type": "slit",
            "source_to_assembly_distance": 150.0,
            "stages": [{
                "id": "s0",
                "outer_height": 50.0,
            }],
            "source": {"position": {"x": 0, "y": 0}},
            "detector": {},
        }
        geo = dict_to_geometry(data)
        assert geo.stages[0].y_position == pytest.approx(150.0, abs=0.1)

    def test_multi_stage_gap_migration(self):
        """Multiple stages with gap_after compute correct y_positions."""
        data = {
            "type": "fan_beam",
            "source_to_assembly_distance": 25.0,
            "stages": [
                {"id": "s0", "outer_height": 100.0, "gap_after": 30.0},
                {"id": "s1", "outer_height": 60.0, "gap_after": 20.0},
                {"id": "s2", "outer_height": 40.0},
            ],
            "source": {"position": {"x": 0, "y": 0}},
            "detector": {},
        }
        geo = dict_to_geometry(data)
        # y0 = 25.0, y1 = 25+100+30 = 155, y2 = 155+60+20 = 235
        assert geo.stages[0].y_position == pytest.approx(25.0, abs=0.1)
        assert geo.stages[1].y_position == pytest.approx(155.0, abs=0.1)
        assert geo.stages[2].y_position == pytest.approx(235.0, abs=0.1)

    def test_explicit_y_position_not_overwritten(self):
        """If stages already have y_position, migration does not apply."""
        data = {
            "type": "fan_beam",
            "stages": [
                {"id": "s0", "y_position": 50.0, "outer_height": 100.0},
                {"id": "s1", "y_position": 200.0, "outer_height": 60.0},
            ],
            "source": {},
            "detector": {},
        }
        geo = dict_to_geometry(data)
        assert geo.stages[0].y_position == 50.0
        assert geo.stages[1].y_position == 200.0


# ── Phantom serialization ────────────────────────────────────────────

class TestPhantomSerialization:
    """Phantom union types with _phantom_type discriminator."""

    def test_wire_phantom_round_trip(self):
        phantom = WirePhantom(
            config=PhantomConfig(
                id="p1", type=PhantomType.WIRE,
                name="Tel 0.5mm", material_id="W",
            ),
            diameter=0.5,
        )
        geo = _make_geometry(phantoms=[phantom])
        d = geometry_to_dict(geo)

        # Check discriminator
        assert d["phantoms"][0]["_phantom_type"] == "wire"

        restored = dict_to_geometry(d)
        p = restored.phantoms[0]
        assert isinstance(p, WirePhantom)
        assert p.diameter == 0.5
        assert p.config.material_id == "W"

    def test_line_pair_phantom_round_trip(self):
        phantom = LinePairPhantom(
            config=PhantomConfig(
                id="p2", type=PhantomType.LINE_PAIR,
                name="LP 2 lp/mm", material_id="Pb",
            ),
            frequency=2.0,
            bar_thickness=0.5,
            num_cycles=10,
        )
        geo = _make_geometry(phantoms=[phantom])
        restored = dict_to_geometry(geometry_to_dict(geo))
        p = restored.phantoms[0]
        assert isinstance(p, LinePairPhantom)
        assert p.frequency == 2.0
        assert p.num_cycles == 10

    def test_grid_phantom_round_trip(self):
        phantom = GridPhantom(
            config=PhantomConfig(
                id="p3", type=PhantomType.GRID,
                name="Grid 1mm", material_id="Cu",
            ),
            pitch=1.0,
            wire_diameter=0.1,
            size=50.0,
        )
        geo = _make_geometry(phantoms=[phantom])
        restored = dict_to_geometry(geometry_to_dict(geo))
        p = restored.phantoms[0]
        assert isinstance(p, GridPhantom)
        assert p.pitch == 1.0
        assert p.config.material_id == "Cu"

    def test_multiple_phantom_types(self):
        phantoms = [
            WirePhantom(config=PhantomConfig(type=PhantomType.WIRE)),
            LinePairPhantom(config=PhantomConfig(type=PhantomType.LINE_PAIR)),
            GridPhantom(config=PhantomConfig(type=PhantomType.GRID)),
        ]
        geo = _make_geometry(phantoms=phantoms)
        restored = dict_to_geometry(geometry_to_dict(geo))
        assert isinstance(restored.phantoms[0], WirePhantom)
        assert isinstance(restored.phantoms[1], LinePairPhantom)
        assert isinstance(restored.phantoms[2], GridPhantom)

    def test_no_phantoms(self):
        geo = _make_geometry(phantoms=[])
        d = geometry_to_dict(geo)
        assert d["phantoms"] == []
        restored = dict_to_geometry(d)
        assert restored.phantoms == []


# ── Simulation serialization ─────────────────────────────────────────

class TestSimulationSerialization:
    """SimulationResult ↔ dict with NumPy array preservation."""

    def test_result_round_trip(self):
        result = _make_simulation_result()
        d = simulation_result_to_dict(result)
        restored = dict_to_simulation_result(d)

        assert restored.energy_keV == 1000.0
        assert restored.num_rays == 360
        assert restored.elapsed_seconds == 1.5
        assert restored.include_buildup is True

    def test_numpy_arrays_preserved(self):
        result = _make_simulation_result()
        d = simulation_result_to_dict(result)
        restored = dict_to_simulation_result(d)

        np.testing.assert_allclose(
            restored.beam_profile.positions_mm,
            result.beam_profile.positions_mm,
            rtol=1e-10,
        )
        np.testing.assert_allclose(
            restored.beam_profile.intensities,
            result.beam_profile.intensities,
            rtol=1e-10,
        )
        np.testing.assert_allclose(
            restored.beam_profile.angles_rad,
            result.beam_profile.angles_rad,
            rtol=1e-10,
        )

    def test_arrays_are_lists_in_dict(self):
        """Serialized form uses plain lists, not numpy arrays."""
        result = _make_simulation_result()
        d = simulation_result_to_dict(result)
        assert isinstance(d["beam_profile"]["positions_mm"], list)
        assert isinstance(d["beam_profile"]["intensities"], list)

    def test_quality_metrics_round_trip(self):
        result = _make_simulation_result()
        d = simulation_result_to_dict(result)
        restored = dict_to_simulation_result(d)

        qm = restored.quality_metrics
        assert qm.penumbra_left_mm == 4.5
        assert qm.flatness_pct == 2.1
        assert qm.collimation_ratio_dB == 33.0
        assert qm.all_pass is True

    def test_quality_metric_enum(self):
        result = _make_simulation_result()
        d = simulation_result_to_dict(result)
        restored = dict_to_simulation_result(d)

        m = restored.quality_metrics.metrics[0]
        assert m.name == "Penumbra"
        assert m.status == MetricStatus.EXCELLENT

    def test_empty_result(self):
        result = SimulationResult()
        d = simulation_result_to_dict(result)
        restored = dict_to_simulation_result(d)
        assert restored.energy_keV == 0.0
        assert len(restored.beam_profile.positions_mm) == 0


class TestSimulationConfigSerialization:
    """SimulationConfig ↔ dict."""

    def test_config_round_trip(self):
        config = SimulationConfig(
            id="sim-001",
            geometry_id="geo-001",
            energy_points=[100.0, 500.0, 1000.0],
            num_rays=720,
            include_buildup=True,
            include_scatter=False,
            compton_config=ComptonConfig(
                enabled=True,
                max_scatter_order=2,
                angular_bins=360,
            ),
        )
        d = simulation_config_to_dict(config)
        restored = dict_to_simulation_config(d)

        assert restored.id == "sim-001"
        assert restored.num_rays == 720
        assert restored.energy_points == [100.0, 500.0, 1000.0]
        assert restored.compton_config.enabled is True
        assert restored.compton_config.max_scatter_order == 2

    def test_empty_config(self):
        config = SimulationConfig()
        d = simulation_config_to_dict(config)
        restored = dict_to_simulation_config(d)
        assert restored.num_rays == 5000
        assert restored.include_buildup is True
