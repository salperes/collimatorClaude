"""Serialization utilities — dataclass ↔ JSON-safe dict conversion.

Handles Enum fields, NumPy arrays, phantom union types, and schema migration.
Used by DesignRepository, export modules, and .cdt project files.

Reference: Phase-06 spec.
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any

import numpy as np

from app.constants import GEOMETRY_SCHEMA_VERSION
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
    AnyPhantom,
    GridPhantom,
    LinePairPhantom,
    PhantomConfig,
    PhantomType,
    ProjectionMethod,
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


# =====================================================================
# Generic helpers
# =====================================================================


def _serialize_value(val: Any) -> Any:
    """Convert a value to a JSON-safe type."""
    if val is None:
        return None
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, np.ndarray):
        return val.tolist()
    if dataclasses.is_dataclass(val) and not isinstance(val, type):
        return _dataclass_to_dict(val)
    if isinstance(val, list):
        return [_serialize_value(v) for v in val]
    if isinstance(val, (int, float, str, bool)):
        return val
    return str(val)


def _dataclass_to_dict(obj: Any) -> dict:
    """Recursively convert a dataclass to a JSON-safe dict."""
    result = {}
    for f in dataclasses.fields(obj):
        val = getattr(obj, f.name)
        result[f.name] = _serialize_value(val)
    return result


# =====================================================================
# Geometry serialization
# =====================================================================


def geometry_to_dict(geometry: CollimatorGeometry) -> dict:
    """Serialize CollimatorGeometry to a JSON-safe dict.

    Args:
        geometry: The geometry to serialize.

    Returns:
        Dict with schema_version embedded. Enums as strings,
        phantoms tagged with ``_phantom_type`` discriminator.
    """
    d = _dataclass_to_dict(geometry)
    d["schema_version"] = GEOMETRY_SCHEMA_VERSION

    # Tag phantoms for union deserialization
    if d.get("phantoms"):
        for i, p in enumerate(d["phantoms"]):
            phantom = geometry.phantoms[i]
            p["_phantom_type"] = phantom.config.type.value

    return d


def dict_to_geometry(data: dict) -> CollimatorGeometry:
    """Deserialize dict to CollimatorGeometry.

    Handles v1.x migration (``body`` → ``stages[0]``) and v2.x migration
    (``source_to_assembly_distance`` + ``gap_after`` → explicit ``y_position``).

    Args:
        data: JSON-parsed dict.

    Returns:
        Reconstructed CollimatorGeometry.
    """
    data = dict(data)  # shallow copy
    schema_version = data.pop("schema_version", "1.0")

    # v1.x migration
    if "body" in data and "stages" not in data:
        data["stages"] = [data.pop("body")]

    source = _dict_to_source(data.get("source", {}))
    raw_stages = data.get("stages", [])
    stages = [_dict_to_stage(s) for s in raw_stages]
    detector = _dict_to_detector(data.get("detector", {}))

    # v2.x → v3.0 migration: compute y_position from gaps
    if not _has_explicit_positions(raw_stages):
        _migrate_positions(stages, raw_stages, data, source)

    return CollimatorGeometry(
        id=data.get("id", ""),
        name=data.get("name", "Yeni Tasarim"),
        type=CollimatorType(data["type"]) if "type" in data else CollimatorType.FAN_BEAM,
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        source=source,
        stages=stages,
        detector=detector,
        phantoms=[_dict_to_phantom(p) for p in data.get("phantoms", [])],
    )


def _has_explicit_positions(raw_stages: list[dict]) -> bool:
    """Check if stages already have explicit y_position (v3.0+ format)."""
    return any("y_position" in s for s in raw_stages)


def _migrate_positions(
    stages: list[CollimatorStage],
    raw_stages: list[dict],
    data: dict,
    source: SourceConfig,
) -> None:
    """Compute y_position from old gap_after + source_to_assembly_distance."""
    src_to_asm = data.get("source_to_assembly_distance")

    if src_to_asm is not None:
        y_offset = source.position.y + src_to_asm
    else:
        # Legacy: assembly centered at Y=0
        total_h = sum(s.outer_height for s in stages)
        total_gaps = sum(
            raw_stages[i].get("gap_after", 0.0)
            for i in range(len(raw_stages) - 1)
        ) if len(raw_stages) > 1 else 0.0
        y_offset = -(total_h + total_gaps) / 2.0
        source.position = Point2D(source.position.x, 0.0)

    for i, stage in enumerate(stages):
        stage.y_position = y_offset
        stage.x_offset = 0.0
        y_offset += stage.outer_height
        if i < len(raw_stages) - 1:
            y_offset += raw_stages[i].get("gap_after", 0.0)


def _dict_to_source(d: dict) -> SourceConfig:
    if not d:
        return SourceConfig()
    return SourceConfig(
        position=Point2D(**d["position"]) if "position" in d else Point2D(),
        energy_kVp=d.get("energy_kVp"),
        energy_MeV=d.get("energy_MeV"),
        focal_spot_size=d.get("focal_spot_size", 1.0),
        focal_spot_distribution=FocalSpotDistribution(
            d["focal_spot_distribution"]
        ) if "focal_spot_distribution" in d else FocalSpotDistribution.UNIFORM,
        beam_angle=d.get("beam_angle", 0.0),
        tube_current_mA=d.get("tube_current_mA", 8.0),
        tube_output_method=d.get("tube_output_method", "empirical"),
        linac_pps=d.get("linac_pps", 260),
        linac_dose_rate_Gy_min=d.get("linac_dose_rate_Gy_min", 0.8),
        linac_ref_pps=d.get("linac_ref_pps", 260),
    )


def _dict_to_detector(d: dict) -> DetectorConfig:
    if not d:
        return DetectorConfig()
    return DetectorConfig(
        position=Point2D(**d["position"]) if "position" in d else Point2D(0, 500),
        width=d.get("width", 500.0),
        distance_from_source=d.get("distance_from_source", 1000.0),
    )


def _dict_to_stage(d: dict) -> CollimatorStage:
    if not d:
        return CollimatorStage()

    # Migration: old layers list → single material
    material_id = d.get("material_id", "")
    if "layers" in d and d["layers"] and not material_id:
        old_layers = d["layers"]
        material_id = old_layers[0].get("material_id", "Pb")
    if not material_id:
        material_id = "Pb"

    return CollimatorStage(
        id=d.get("id", ""),
        name=d.get("name", ""),
        order=d.get("order", 0),
        purpose=StagePurpose(d["purpose"]) if "purpose" in d else StagePurpose.PRIMARY_SHIELDING,
        outer_width=d.get("outer_width", 100.0),
        outer_height=d.get("outer_height", 200.0),
        aperture=_dict_to_aperture(d.get("aperture", {})),
        material_id=material_id,
        y_position=d.get("y_position", 0.0),
        x_offset=d.get("x_offset", 0.0),
    )


def _dict_to_aperture(d: dict) -> ApertureConfig:
    if not d:
        return ApertureConfig()
    return ApertureConfig(
        fan_angle=d.get("fan_angle"),
        fan_slit_width=d.get("fan_slit_width"),
        pencil_diameter=d.get("pencil_diameter"),
        slit_width=d.get("slit_width"),
        slit_height=d.get("slit_height"),
        taper_angle=d.get("taper_angle", 0.0),
    )


# =====================================================================
# Phantom union serialization
# =====================================================================


def _dict_to_phantom(d: dict) -> AnyPhantom:
    """Reconstruct a phantom from dict using ``_phantom_type`` discriminator."""
    ptype = d.pop("_phantom_type", None)
    if ptype is None:
        ptype = d.get("config", {}).get("type", "wire")

    config = _dict_to_phantom_config(d.get("config", {}))

    match ptype:
        case "wire":
            return WirePhantom(config=config, diameter=d.get("diameter", 0.5))
        case "line_pair":
            return LinePairPhantom(
                config=config,
                frequency=d.get("frequency", 1.0),
                bar_thickness=d.get("bar_thickness", 1.0),
                num_cycles=d.get("num_cycles", 5),
            )
        case "grid":
            return GridPhantom(
                config=config,
                pitch=d.get("pitch", 1.0),
                wire_diameter=d.get("wire_diameter", 0.1),
                size=d.get("size", 50.0),
            )
        case _:
            return WirePhantom(config=config)


def _dict_to_phantom_config(d: dict) -> PhantomConfig:
    if not d:
        return PhantomConfig()
    return PhantomConfig(
        id=d.get("id", ""),
        type=PhantomType(d["type"]) if "type" in d else PhantomType.WIRE,
        name=d.get("name", ""),
        position_y=d.get("position_y", 300.0),
        material_id=d.get("material_id", "W"),
        enabled=d.get("enabled", True),
    )


# =====================================================================
# Simulation serialization
# =====================================================================


def simulation_config_to_dict(config: SimulationConfig) -> dict:
    """Serialize SimulationConfig to JSON-safe dict."""
    return _dataclass_to_dict(config)


def dict_to_simulation_config(data: dict) -> SimulationConfig:
    """Deserialize dict to SimulationConfig."""
    if not data:
        return SimulationConfig()
    return SimulationConfig(
        id=data.get("id", ""),
        geometry_id=data.get("geometry_id", ""),
        energy_points=data.get("energy_points", []),
        num_rays=data.get("num_rays", 360),
        include_buildup=data.get("include_buildup", True),
        include_scatter=data.get("include_scatter", False),
        angular_resolution=data.get("angular_resolution", 1.0),
        compton_config=ComptonConfig(**{
            k: data["compton_config"][k]
            for k in data["compton_config"]
        }) if data.get("compton_config") else ComptonConfig(),
    )


def simulation_result_to_dict(result: SimulationResult) -> dict:
    """Serialize SimulationResult to JSON-safe dict.

    BeamProfile NDArrays are converted to lists via ``.tolist()``.
    """
    return _dataclass_to_dict(result)


def dict_to_simulation_result(data: dict) -> SimulationResult:
    """Deserialize dict to SimulationResult.

    Lists are converted back to ``np.array(dtype=np.float64)``
    for BeamProfile fields.
    """
    if not data:
        return SimulationResult()

    bp_data = data.get("beam_profile", {})
    beam_profile = BeamProfile(
        positions_mm=np.array(bp_data.get("positions_mm", []), dtype=np.float64),
        intensities=np.array(bp_data.get("intensities", []), dtype=np.float64),
        angles_rad=np.array(bp_data.get("angles_rad", []), dtype=np.float64),
    )

    qm_data = data.get("quality_metrics", {})
    metrics_list = []
    for m in qm_data.get("metrics", []):
        metrics_list.append(QualityMetric(
            name=m.get("name", ""),
            value=m.get("value", 0.0),
            unit=m.get("unit", ""),
            status=MetricStatus(m["status"]) if "status" in m else MetricStatus.POOR,
            threshold_excellent=m.get("threshold_excellent", 0.0),
            threshold_acceptable=m.get("threshold_acceptable", 0.0),
        ))

    quality_metrics = QualityMetrics(
        penumbra_left_mm=qm_data.get("penumbra_left_mm", 0.0),
        penumbra_right_mm=qm_data.get("penumbra_right_mm", 0.0),
        penumbra_max_mm=qm_data.get("penumbra_max_mm", 0.0),
        flatness_pct=qm_data.get("flatness_pct", 0.0),
        leakage_avg_pct=qm_data.get("leakage_avg_pct", 0.0),
        leakage_max_pct=qm_data.get("leakage_max_pct", 0.0),
        collimation_ratio=qm_data.get("collimation_ratio", 0.0),
        collimation_ratio_dB=qm_data.get("collimation_ratio_dB", 0.0),
        fwhm_mm=qm_data.get("fwhm_mm", 0.0),
        metrics=metrics_list,
        all_pass=qm_data.get("all_pass", False),
    )

    return SimulationResult(
        energy_keV=data.get("energy_keV", 0.0),
        num_rays=data.get("num_rays", 0),
        beam_profile=beam_profile,
        quality_metrics=quality_metrics,
        elapsed_seconds=data.get("elapsed_seconds", 0.0),
        include_buildup=data.get("include_buildup", False),
        unattenuated_dose_rate_Gy_h=data.get("unattenuated_dose_rate_Gy_h", 0.0),
    )
