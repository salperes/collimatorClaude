"""Geometry template factories for standard collimator types.

Each factory creates a fully configured CollimatorGeometry with realistic
default dimensions [mm], layers, and source/detector placement.

Reference: Phase-03 spec — FR-1.2 Geometry Templates.
"""

from app.models.geometry import (
    ApertureConfig,
    CollimatorGeometry,
    CollimatorLayer,
    CollimatorStage,
    CollimatorType,
    DetectorConfig,
    LayerPurpose,
    Point2D,
    SourceConfig,
    StagePurpose,
)


def create_fan_beam_template() -> CollimatorGeometry:
    """Create a 3-stage fan-beam collimator geometry.

    Layout::

        Source (y=-150mm)
        [Stage 0: Dahili]  120x100mm  Pb 40mm + SS304 5mm
            gap 30mm
        [Stage 1: Yelpaze]  80x60mm   W 25mm   fan_angle=30 deg
            gap 20mm
        [Stage 2: Penumbra]  60x40mm  Pb 15mm
        Detector (y=+350mm, width=500mm)

    Returns:
        Pre-configured fan-beam CollimatorGeometry [mm, degree].
    """
    stages = [
        CollimatorStage(
            name="Dahili",
            order=0,
            purpose=StagePurpose.PRIMARY_SHIELDING,
            outer_width=120.0,
            outer_height=100.0,
            aperture=ApertureConfig(fan_angle=35.0, fan_slit_width=3.0),
            layers=[
                CollimatorLayer(order=0, material_id="Pb", thickness=40.0,
                                purpose=LayerPurpose.PRIMARY_SHIELDING),
                CollimatorLayer(order=1, material_id="SS304", thickness=5.0,
                                purpose=LayerPurpose.STRUCTURAL),
            ],
            gap_after=30.0,
        ),
        CollimatorStage(
            name="Yelpaze",
            order=1,
            purpose=StagePurpose.FAN_DEFINITION,
            outer_width=80.0,
            outer_height=60.0,
            aperture=ApertureConfig(fan_angle=30.0, fan_slit_width=2.0),
            layers=[
                CollimatorLayer(order=0, material_id="W", thickness=25.0,
                                purpose=LayerPurpose.PRIMARY_SHIELDING),
            ],
            gap_after=20.0,
        ),
        CollimatorStage(
            name="Penumbra",
            order=2,
            purpose=StagePurpose.PENUMBRA_TRIMMER,
            outer_width=60.0,
            outer_height=40.0,
            aperture=ApertureConfig(fan_angle=30.0, fan_slit_width=1.5),
            layers=[
                CollimatorLayer(order=0, material_id="Pb", thickness=15.0,
                                purpose=LayerPurpose.PRIMARY_SHIELDING),
            ],
            gap_after=0.0,
        ),
    ]

    return CollimatorGeometry(
        name="Fan-Beam Sablon",
        type=CollimatorType.FAN_BEAM,
        source=SourceConfig(
            position=Point2D(0.0, -150.0),
            energy_kVp=160.0,
            focal_spot_size=1.0,
        ),
        stages=stages,
        detector=DetectorConfig(
            position=Point2D(0.0, 350.0),
            width=500.0,
            distance_from_source=500.0,
        ),
    )


def create_pencil_beam_template() -> CollimatorGeometry:
    """Create a single-stage pencil-beam collimator geometry.

    Layout::

        Source (y=-100mm)
        [Stage 0: Kalem Isini]  100x200mm  Pb 40mm + W 10mm  pencil_d=5mm
        Detector (y=+300mm, width=100mm)

    Returns:
        Pre-configured pencil-beam CollimatorGeometry [mm, degree].
    """
    stages = [
        CollimatorStage(
            name="Kalem Isini",
            order=0,
            purpose=StagePurpose.PRIMARY_SHIELDING,
            outer_width=100.0,
            outer_height=200.0,
            aperture=ApertureConfig(pencil_diameter=5.0),
            layers=[
                CollimatorLayer(order=0, material_id="Pb", thickness=40.0,
                                purpose=LayerPurpose.PRIMARY_SHIELDING),
                CollimatorLayer(order=1, material_id="W", thickness=10.0,
                                purpose=LayerPurpose.SECONDARY_SHIELDING),
            ],
            gap_after=0.0,
        ),
    ]

    return CollimatorGeometry(
        name="Pencil-Beam Sablon",
        type=CollimatorType.PENCIL_BEAM,
        source=SourceConfig(
            position=Point2D(0.0, -100.0),
            energy_kVp=160.0,
            focal_spot_size=1.0,
        ),
        stages=stages,
        detector=DetectorConfig(
            position=Point2D(0.0, 300.0),
            width=100.0,
            distance_from_source=400.0,
        ),
    )


def create_slit_template() -> CollimatorGeometry:
    """Create a simple single-stage slit collimator geometry.

    Layout::

        Source (y=-175mm, 150mm above collimator entry)
        [Stage 0: Kolimatör]  200x50mm  Pb 96mm
            aperture: 8mm input → 4mm output (taper ≈ 2.29°)
        Detector (y=+225mm, width=400mm, SDD=400mm)

    Returns:
        Pre-configured slit CollimatorGeometry [mm, degree].
    """
    import math
    # taper_angle: input 8mm → output 4mm over 50mm height
    # per side: (4-2) / 50 = 0.04 → atan(0.04) ≈ 2.291°
    taper_deg = math.degrees(math.atan(2.0 / 50.0))

    stages = [
        CollimatorStage(
            name="Kolimatör",
            order=0,
            purpose=StagePurpose.PRIMARY_SHIELDING,
            outer_width=200.0,
            outer_height=50.0,
            aperture=ApertureConfig(
                slit_width=4.0,
                taper_angle=taper_deg,
            ),
            layers=[
                CollimatorLayer(order=0, material_id="Pb", thickness=96.0,
                                purpose=LayerPurpose.PRIMARY_SHIELDING),
            ],
            gap_after=0.0,
        ),
    ]

    return CollimatorGeometry(
        name="Slit Sablon",
        type=CollimatorType.SLIT,
        source=SourceConfig(
            position=Point2D(0.0, -175.0),
            energy_kVp=160.0,
            focal_spot_size=1.0,
        ),
        stages=stages,
        detector=DetectorConfig(
            position=Point2D(0.0, 225.0),
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
