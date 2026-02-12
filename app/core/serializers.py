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
    CollimatorLayer,
    CollimatorStage,
    CollimatorType,
    DetectorConfig,
    FocalSpotDistribution,
    LayerPurpose,
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

    Handles v1.x migration (``body`` → ``stages[0]``).

    Args:
        data: JSON-parsed dict.

    Returns:
        Reconstructed CollimatorGeometry.
    """
    data = dict(data)  # shallow copy
    data.pop("schema_version", None)

    # v1.x migration
    if "body" in data and "stages" not in data:
        data["stages"] = [data.pop("body")]

    return CollimatorGeometry(
        id=data.get("id", ""),
        name=data.get("name", "Yeni Tasarim"),
        type=CollimatorType(data["type"]) if "type" in data else CollimatorType.FAN_BEAM,
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        source=_dict_to_source(data.get("source", {})),
        stages=[_dict_to_stage(s) for s in data.get("stages", [])],
        detector=_dict_to_detector(data.get("detector", {})),
        phantoms=[_dict_to_phantom(p) for p in data.get("phantoms", [])],
    )


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
    return CollimatorStage(
        id=d.get("id", ""),
        name=d.get("name", ""),
        order=d.get("order", 0),
        purpose=StagePurpose(d["purpose"]) if "purpose" in d else StagePurpose.PRIMARY_SHIELDING,
        outer_width=d.get("outer_width", 100.0),
        outer_height=d.get("outer_height", 200.0),
        aperture=_dict_to_aperture(d.get("aperture", {})),
        layers=[_dict_to_layer(l) for l in d.get("layers", [])],
        gap_after=d.get("gap_after", 0.0),
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


def _dict_to_layer(d: dict) -> CollimatorLayer:
    if not d:
        return CollimatorLayer()
    return CollimatorLayer(
        id=d.get("id", ""),
        order=d.get("order", 0),
        material_id=d.get("material_id", ""),
        thickness=d.get("thickness", 0.0),
        purpose=LayerPurpose(d["purpose"]) if "purpose" in d else LayerPurpose.PRIMARY_SHIELDING,
        inner_material_id=d.get("inner_material_id"),
        inner_width=d.get("inner_width", 0.0),
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
    )
