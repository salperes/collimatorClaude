"""Geometry template factories for standard collimator types.

Each factory creates a fully configured CollimatorGeometry with realistic
default dimensions [mm] and source/detector placement. Stage positions
are explicit (y_position relative to source at Y=0).

Reference: Phase-03 spec — FR-1.2 Geometry Templates.
"""

from app.core.i18n import t
from app.models.geometry import (
    ApertureConfig,
    CollimatorGeometry,
    CollimatorStage,
    CollimatorType,
    DetectorConfig,
    Point2D,
    SourceConfig,
    StagePurpose,
)


def create_fan_beam_template() -> CollimatorGeometry:
    """Create a 3-stage fan-beam collimator geometry.

    Layout::

        Source (y=0mm)
            25mm gap
        [Stage 0: Dahili]  120x100mm  Pb  y=25
            30mm gap
        [Stage 1: Yelpaze]  80x60mm   W   y=155
            20mm gap
        [Stage 2: Penumbra]  60x40mm  Pb  y=235
        Detector (y=500mm, width=500mm)

    Returns:
        Pre-configured fan-beam CollimatorGeometry [mm, degree].
    """
    stages = [
        CollimatorStage(
            name=t("templates.stage_internal", "Internal"),
            order=0,
            purpose=StagePurpose.PRIMARY_SHIELDING,
            outer_width=120.0,
            outer_height=100.0,
            aperture=ApertureConfig(fan_angle=35.0, fan_slit_width=3.0),
            material_id="Pb",
            y_position=25.0,
            x_offset=0.0,
        ),
        CollimatorStage(
            name=t("templates.stage_fan", "Fan"),
            order=1,
            purpose=StagePurpose.FAN_DEFINITION,
            outer_width=80.0,
            outer_height=60.0,
            aperture=ApertureConfig(fan_angle=30.0, fan_slit_width=2.0),
            material_id="W",
            y_position=155.0,
            x_offset=0.0,
        ),
        CollimatorStage(
            name=t("templates.stage_penumbra", "Penumbra"),
            order=2,
            purpose=StagePurpose.PENUMBRA_TRIMMER,
            outer_width=60.0,
            outer_height=40.0,
            aperture=ApertureConfig(fan_angle=30.0, fan_slit_width=1.5),
            material_id="Pb",
            y_position=235.0,
            x_offset=0.0,
        ),
    ]

    return CollimatorGeometry(
        name=t("templates.fan_beam", "Fan-Beam Template"),
        type=CollimatorType.FAN_BEAM,
        source=SourceConfig(
            position=Point2D(0.0, 0.0),
            energy_kVp=225.0,
            focal_spot_size=1.0,
            beam_angle=30.0,
        ),
        stages=stages,
        detector=DetectorConfig(
            position=Point2D(0.0, 500.0),
            width=500.0,
            distance_from_source=500.0,
        ),
    )


def create_pencil_beam_template() -> CollimatorGeometry:
    """Create a single-stage pencil-beam collimator geometry.

    Layout::

        Source (y=0mm)
        [Stage 0: Kalem Isini]  100x200mm  Pb  y=0
        Detector (y=400mm, width=100mm)

    Returns:
        Pre-configured pencil-beam CollimatorGeometry [mm, degree].
    """
    stages = [
        CollimatorStage(
            name=t("templates.stage_pencil", "Pencil Beam"),
            order=0,
            purpose=StagePurpose.PRIMARY_SHIELDING,
            outer_width=100.0,
            outer_height=200.0,
            aperture=ApertureConfig(pencil_diameter=5.0),
            material_id="Pb",
            y_position=0.0,
            x_offset=0.0,
        ),
    ]

    return CollimatorGeometry(
        name=t("templates.pencil_beam", "Pencil-Beam Template"),
        type=CollimatorType.PENCIL_BEAM,
        source=SourceConfig(
            position=Point2D(0.0, 0.0),
            energy_kVp=225.0,
            focal_spot_size=1.0,
            beam_angle=30.0,
        ),
        stages=stages,
        detector=DetectorConfig(
            position=Point2D(0.0, 400.0),
            width=100.0,
            distance_from_source=400.0,
        ),
    )


def create_slit_template() -> CollimatorGeometry:
    """Create a simple single-stage slit collimator geometry.

    Layout::

        Source (y=0mm)
            150mm gap
        [Stage 0: Kolimator]  200x50mm  Pb  y=150
            aperture: 8mm input -> 4mm output (taper ~ 2.29 deg)
        Detector (y=400mm, width=400mm, SDD=400mm)

    Returns:
        Pre-configured slit CollimatorGeometry [mm, degree].
    """
    import math
    # taper_angle: input 8mm -> output 4mm over 50mm height
    # per side: (4-2) / 50 = 0.04 -> atan(0.04) ~ 2.291 deg
    taper_deg = math.degrees(math.atan(2.0 / 50.0))

    stages = [
        CollimatorStage(
            name=t("templates.stage_collimator", "Collimator"),
            order=0,
            purpose=StagePurpose.PRIMARY_SHIELDING,
            outer_width=200.0,
            outer_height=50.0,
            aperture=ApertureConfig(
                slit_width=4.0,
                taper_angle=taper_deg,
            ),
            material_id="Pb",
            y_position=150.0,
            x_offset=0.0,
        ),
    ]

    return CollimatorGeometry(
        name=t("templates.slit", "Slit Template"),
        type=CollimatorType.SLIT,
        source=SourceConfig(
            position=Point2D(0.0, 0.0),
            energy_kVp=225.0,
            focal_spot_size=1.0,
            beam_angle=30.0,
        ),
        stages=stages,
        detector=DetectorConfig(
            position=Point2D(0.0, 400.0),
            width=400.0,
            distance_from_source=400.0,
        ),
    )


_TEMPLATES: dict[CollimatorType, callable] = {
    CollimatorType.FAN_BEAM: create_fan_beam_template,
    CollimatorType.PENCIL_BEAM: create_pencil_beam_template,
    CollimatorType.SLIT: create_slit_template,
}


def create_template(ctype: CollimatorType) -> CollimatorGeometry:
    """Factory: create default geometry for given collimator type.

    Args:
        ctype: Collimator beam type.

    Returns:
        New CollimatorGeometry with default template values [mm, degree].

    Raises:
        KeyError: If ctype is not a recognized CollimatorType.
    """
    return _TEMPLATES[ctype]()
