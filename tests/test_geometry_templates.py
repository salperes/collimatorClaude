"""Tests for geometry template factories.

Validates that each collimator type template produces correct
structure: stage counts, material, y_position, aperture configs, source/detector.
"""

import pytest

from app.models.geometry import (
    CollimatorType, CollimatorGeometry, FocalSpotDistribution,
)
from app.ui.canvas.geometry_templates import (
    create_fan_beam_template,
    create_pencil_beam_template,
    create_slit_template,
    create_template,
)
from app.constants import MATERIAL_IDS


# ---------------------------------------------------------------------------
# Fan-beam template
# ---------------------------------------------------------------------------

class TestFanBeamTemplate:
    """Tests for fan-beam (3-stage) template."""

    def setup_method(self):
        self.geo = create_fan_beam_template()

    def test_type_is_fan_beam(self):
        assert self.geo.type == CollimatorType.FAN_BEAM

    def test_has_3_stages(self):
        assert self.geo.stage_count == 3

    def test_stage_names(self):
        names = [s.name for s in self.geo.stages]
        assert names == ["Dahili", "Yelpaze", "Penumbra"]

    def test_stage_order_ascending(self):
        orders = [s.order for s in self.geo.stages]
        assert orders == [0, 1, 2]

    def test_all_stages_have_positive_dimensions(self):
        for stage in self.geo.stages:
            assert stage.outer_width > 0
            assert stage.outer_height > 0

    def test_stage_materials_are_valid(self):
        for stage in self.geo.stages:
            assert stage.material_id in MATERIAL_IDS

    def test_fan_beam_stage_0(self):
        """Stage 0 (Dahili): Pb, y=25."""
        stage = self.geo.stages[0]
        assert stage.material_id == "Pb"
        assert stage.y_position == 25.0

    def test_fan_beam_stage_1(self):
        """Stage 1 (Yelpaze): W, y=155."""
        stage = self.geo.stages[1]
        assert stage.material_id == "W"
        assert stage.y_position == 155.0

    def test_fan_beam_stage_2(self):
        """Stage 2 (Penumbra): Pb, y=235."""
        stage = self.geo.stages[2]
        assert stage.material_id == "Pb"
        assert stage.y_position == 235.0

    def test_fan_angle_set_on_stages(self):
        for stage in self.geo.stages:
            assert stage.aperture.fan_angle is not None
            assert stage.aperture.fan_angle > 0

    def test_y_positions_increasing(self):
        positions = [s.y_position for s in self.geo.stages]
        assert positions == sorted(positions)
        assert positions[0] > 0  # gap between source and first stage

    def test_source_at_origin(self):
        assert self.geo.source.position.y == 0.0

    def test_detector_below_source(self):
        assert self.geo.detector.position.y > 0

    def test_total_height_positive(self):
        assert self.geo.total_height > 0


# ---------------------------------------------------------------------------
# Pencil-beam template
# ---------------------------------------------------------------------------

class TestPencilBeamTemplate:
    """Tests for pencil-beam (single-stage) template."""

    def setup_method(self):
        self.geo = create_pencil_beam_template()

    def test_type_is_pencil_beam(self):
        assert self.geo.type == CollimatorType.PENCIL_BEAM

    def test_has_1_stage(self):
        assert self.geo.stage_count == 1

    def test_pencil_diameter_set(self):
        assert self.geo.stages[0].aperture.pencil_diameter is not None
        assert self.geo.stages[0].aperture.pencil_diameter > 0

    def test_has_material(self):
        assert self.geo.stages[0].material_id

    def test_pencil_beam_material(self):
        """Pencil-beam: Pb."""
        stage = self.geo.stages[0]
        assert stage.material_id == "Pb"

    def test_pencil_beam_y_position(self):
        assert self.geo.stages[0].y_position == 0.0

    def test_source_and_detector_present(self):
        assert self.geo.source.position.y == 0.0
        assert self.geo.detector.position.y > 0


# ---------------------------------------------------------------------------
# Slit template
# ---------------------------------------------------------------------------

class TestSlitTemplate:
    """Tests for slit (single-stage, tapered) template."""

    def setup_method(self):
        self.geo = create_slit_template()

    def test_type_is_slit(self):
        assert self.geo.type == CollimatorType.SLIT

    def test_has_1_stage(self):
        assert self.geo.stage_count == 1

    def test_slit_width_set(self):
        stage = self.geo.stages[0]
        assert stage.aperture.slit_width is not None
        assert stage.aperture.slit_width == 4.0

    def test_taper_angle_set(self):
        stage = self.geo.stages[0]
        assert stage.aperture.taper_angle > 0
        # Input half-width should be 4mm, output half-width 2mm
        import math
        input_hw = stage.aperture.slit_width / 2.0 + \
            stage.outer_height * math.tan(math.radians(stage.aperture.taper_angle))
        assert input_hw == pytest.approx(4.0, abs=0.01)

    def test_dimensions(self):
        stage = self.geo.stages[0]
        assert stage.outer_width == 200.0
        assert stage.outer_height == 50.0

    def test_slit_material(self):
        """Slit: Pb."""
        stage = self.geo.stages[0]
        assert stage.material_id == "Pb"

    def test_slit_y_position(self):
        """Slit: collimator at y=150mm."""
        assert self.geo.stages[0].y_position == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

class TestCreateTemplate:
    """Tests for the create_template() factory."""

    def test_fan_beam_factory(self):
        geo = create_template(CollimatorType.FAN_BEAM)
        assert geo.type == CollimatorType.FAN_BEAM
        assert geo.stage_count == 3

    def test_pencil_beam_factory(self):
        geo = create_template(CollimatorType.PENCIL_BEAM)
        assert geo.type == CollimatorType.PENCIL_BEAM
        assert geo.stage_count == 1

    def test_slit_factory(self):
        geo = create_template(CollimatorType.SLIT)
        assert geo.type == CollimatorType.SLIT
        assert geo.stage_count == 1

    def test_each_template_has_unique_ids(self):
        g1 = create_template(CollimatorType.FAN_BEAM)
        g2 = create_template(CollimatorType.FAN_BEAM)
        assert g1.id != g2.id

    def test_all_templates_have_sdd(self):
        for ctype in CollimatorType:
            geo = create_template(ctype)
            assert geo.detector.distance_from_source > 0

    def test_all_templates_default_uniform_distribution(self):
        for ctype in CollimatorType:
            geo = create_template(ctype)
            assert (
                geo.source.focal_spot_distribution
                == FocalSpotDistribution.UNIFORM
            )
