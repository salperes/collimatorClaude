"""Multi-stage geometry model tests.

Validates CollimatorStage, CollimatorGeometry, backward compatibility,
and convenience properties.
"""

import pytest

from app.models.geometry import (
    CollimatorGeometry,
    CollimatorStage,
    CollimatorBody,
    CollimatorType,
    CollimatorLayer,
    ApertureConfig,
    StagePurpose,
    LayerPurpose,
    Point2D,
    SourceConfig,
    DetectorConfig,
)


class TestCollimatorStage:
    def test_default_stage(self):
        stage = CollimatorStage()
        assert stage.outer_width == 100.0
        assert stage.outer_height == 200.0
        assert stage.purpose == StagePurpose.PRIMARY_SHIELDING
        assert stage.gap_after == 0.0
        assert stage.layers == []
        assert stage.name == ""
        assert stage.order == 0
        assert stage.id  # non-empty UUID

    def test_named_stage(self):
        stage = CollimatorStage(
            name="Fan",
            order=1,
            purpose=StagePurpose.FAN_DEFINITION,
            outer_width=80.0,
            outer_height=60.0,
            gap_after=20.0,
        )
        assert stage.name == "Fan"
        assert stage.order == 1
        assert stage.purpose == StagePurpose.FAN_DEFINITION
        assert stage.gap_after == 20.0

    def test_stage_with_layers(self):
        layer = CollimatorLayer(material_id="Pb", thickness=50.0, order=0)
        stage = CollimatorStage(name="Primary", layers=[layer])
        assert len(stage.layers) == 1
        assert stage.layers[0].material_id == "Pb"


class TestCollimatorBodyAlias:
    def test_alias_is_same_class(self):
        assert CollimatorBody is CollimatorStage

    def test_alias_creates_stage(self):
        body = CollimatorBody(name="Legacy", outer_width=120.0)
        assert isinstance(body, CollimatorStage)
        assert body.name == "Legacy"
        assert body.outer_width == 120.0


class TestSingleStageGeometry:
    def test_default_geometry_has_one_stage(self):
        g = CollimatorGeometry()
        assert g.stage_count == 1
        assert len(g.stages) == 1
        assert g.type == CollimatorType.FAN_BEAM

    def test_body_property_returns_first_stage(self):
        g = CollimatorGeometry()
        assert g.body is g.stages[0]

    def test_single_stage_total_height(self):
        g = CollimatorGeometry()
        assert g.total_height == 200.0  # default outer_height

    def test_backward_compatible_access(self):
        g = CollimatorGeometry()
        g.body.outer_width = 150.0
        assert g.stages[0].outer_width == 150.0


class TestMultiStageGeometry:
    def _make_3stage(self) -> CollimatorGeometry:
        return CollimatorGeometry(
            name="3-Stage Fan",
            stages=[
                CollimatorStage(
                    name="Internal", order=0,
                    purpose=StagePurpose.PRIMARY_SHIELDING,
                    outer_width=120.0, outer_height=100.0,
                    gap_after=30.0,
                ),
                CollimatorStage(
                    name="Fan", order=1,
                    purpose=StagePurpose.FAN_DEFINITION,
                    outer_width=80.0, outer_height=60.0,
                    gap_after=20.0,
                ),
                CollimatorStage(
                    name="Penumbra", order=2,
                    purpose=StagePurpose.PENUMBRA_TRIMMER,
                    outer_width=60.0, outer_height=40.0,
                    gap_after=0.0,
                ),
            ],
        )

    def test_stage_count(self):
        g = self._make_3stage()
        assert g.stage_count == 3

    def test_total_height(self):
        g = self._make_3stage()
        # stages: 100 + 60 + 40 = 200mm
        # gaps: 30 + 20 = 50mm (last stage's gap_after ignored)
        assert g.total_height == pytest.approx(250.0)

    def test_body_returns_first_stage(self):
        g = self._make_3stage()
        assert g.body.name == "Internal"

    def test_stage_ordering(self):
        g = self._make_3stage()
        assert g.stages[0].name == "Internal"
        assert g.stages[1].name == "Fan"
        assert g.stages[2].name == "Penumbra"

    def test_each_stage_has_own_aperture(self):
        g = self._make_3stage()
        g.stages[0].aperture = ApertureConfig(fan_angle=35.0)
        g.stages[1].aperture = ApertureConfig(fan_angle=30.0, fan_slit_width=2.0)
        g.stages[2].aperture = ApertureConfig(fan_angle=30.0, fan_slit_width=1.5)
        assert g.stages[0].aperture.fan_angle == 35.0
        assert g.stages[1].aperture.fan_slit_width == 2.0
        assert g.stages[2].aperture.fan_slit_width == 1.5

    def test_each_stage_independent_layers(self):
        g = self._make_3stage()
        g.stages[0].layers = [
            CollimatorLayer(material_id="Pb", thickness=50.0),
        ]
        g.stages[1].layers = [
            CollimatorLayer(material_id="W", thickness=30.0),
        ]
        assert len(g.stages[0].layers) == 1
        assert len(g.stages[1].layers) == 1
        assert g.stages[0].layers[0].material_id == "Pb"
        assert g.stages[1].layers[0].material_id == "W"


class TestStagePurposeEnum:
    def test_all_values(self):
        assert StagePurpose.PRIMARY_SHIELDING.value == "primary_shielding"
        assert StagePurpose.FAN_DEFINITION.value == "fan_definition"
        assert StagePurpose.PENUMBRA_TRIMMER.value == "penumbra_trimmer"
        assert StagePurpose.CUSTOM.value == "custom"


class TestEdgeCases:
    def test_empty_stages_total_height(self):
        g = CollimatorGeometry(stages=[])
        assert g.total_height == 0.0
        assert g.stage_count == 0

    def test_empty_stages_body_returns_default(self):
        g = CollimatorGeometry(stages=[])
        body = g.body
        assert isinstance(body, CollimatorStage)

    def test_single_stage_gap_after_ignored(self):
        g = CollimatorGeometry(
            stages=[CollimatorStage(outer_height=100.0, gap_after=999.0)]
        )
        # Single stage: gap_after should not contribute to total_height
        assert g.total_height == 100.0
