"""External format importer — converts designs from other applications.

Reads JSON files exported by external collimator design tools and converts
them into CollimatorGeometry for use in this application.

Key differences from our native format:
  - Stages use ``distance_from_source_mm`` (absolute) instead of ``gap_after`` (relative)
  - Aperture has entry/exit widths (taper) instead of single width + taper_angle
  - Source has extra LINAC fields not present in our model
  - Layers in external format are collapsed to single material + total wall thickness
  - Phantoms use ``z_mm`` (absolute) instead of ``position_y`` (canvas coord)

Reference: file_format_spec.md, docs/phase-06-design-management.md.
"""

from __future__ import annotations

import json
import logging
import math
import uuid

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
    PhantomConfig,
    PhantomType,
    WirePhantom,
)

logger = logging.getLogger(__name__)

# External aperture_type -> our CollimatorType
_APERTURE_TYPE_MAP: dict[str, CollimatorType] = {
    "slit": CollimatorType.SLIT,
    "fan": CollimatorType.FAN_BEAM,
    "fan_beam": CollimatorType.FAN_BEAM,
    "pencil": CollimatorType.PENCIL_BEAM,
    "pencil_beam": CollimatorType.PENCIL_BEAM,
    "pinhole": CollimatorType.PENCIL_BEAM,
    "open": CollimatorType.SLIT,
}

# Source fields we actively import (everything else is logged as dropped)
_IMPORTED_SOURCE_FIELDS = {
    "focal_spot_size_mm",
    "distribution",
    "energy_kev",
    "use_linac_simulation",
    "current_ma",
    "linac_dose_rate_Gy_min_he",
    "linac_dose_rate_Gy_min_le",
    "linac_ref_pps_hz",
    "linac_current_pps_hz",
    "manual_dose_rate_Gy_min",
}


class ExternalFormatImporter:
    """Import collimator designs from external application JSON format.

    External format uses absolute stage positioning (distance_from_source_mm)
    and per-stage entry/exit aperture widths.  This importer converts
    distance_from_source_mm to y_position and entry/exit widths to
    taper_angle model.
    """

    def can_import(self, data: dict) -> bool:
        """Check if a parsed JSON dict matches the external format.

        Detection: external format has ``stages`` array where each stage
        contains ``distance_from_source_mm`` (not present in our native format).

        Args:
            data: Parsed JSON dictionary.

        Returns:
            True if format is recognized as external.
        """
        stages = data.get("stages", [])
        if not stages:
            return False
        return "distance_from_source_mm" in stages[0]

    def import_file(self, path: str) -> CollimatorGeometry:
        """Read an external JSON file and convert to CollimatorGeometry.

        Args:
            path: Path to the external JSON file.

        Returns:
            Converted CollimatorGeometry.

        Raises:
            ValueError: If the file cannot be parsed or is invalid.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not self.can_import(data):
            raise ValueError(
                "Dosya dis format olarak taninamadi. "
                "'distance_from_source_mm' alani bulunamadi."
            )

        return self._convert(data)

    def _convert(self, data: dict) -> CollimatorGeometry:
        """Core conversion from external dict to CollimatorGeometry.

        Args:
            data: Parsed external JSON data.

        Returns:
            CollimatorGeometry with all stages, source, and detector configured.
        """
        # -- Source --
        src_data = data.get("source", {})
        focal_spot = src_data.get("focal_spot_size_mm", 1.0)
        dist_str = src_data.get("distribution", "uniform").lower()
        try:
            focal_dist = FocalSpotDistribution(dist_str)
        except ValueError:
            focal_dist = FocalSpotDistribution.UNIFORM

        # Energy mapping: energy_kev → energy_kVp or energy_MeV
        energy_kev = src_data.get("energy_kev")
        use_linac = src_data.get("use_linac_simulation", False)
        energy_kVp: float | None = None
        energy_MeV: float | None = None
        if energy_kev is not None:
            if use_linac or energy_kev >= 1000.0:
                energy_MeV = energy_kev / 1000.0
                logger.info(
                    "Enerji %.0f keV → %.2f MeV (LINAC/yuksek enerji) olarak eslendi.",
                    energy_kev, energy_MeV,
                )
            else:
                energy_kVp = energy_kev
                logger.info(
                    "Enerji %.0f keV → %.0f kVp olarak eslendi.",
                    energy_kev, energy_kVp,
                )

        # Log dropped LINAC / other source fields
        dropped = [
            k for k in src_data
            if k not in _IMPORTED_SOURCE_FIELDS
        ]
        if dropped:
            logger.info(
                "Kaynak icerisindeki su alanlar desteklenmiyor (atlanacak): %s",
                ", ".join(dropped),
            )

        # -- Detector --
        det_data = data.get("detector", {})
        sdd = det_data.get("distance_mm", 1000.0)
        det_width = det_data.get("width_mm", 500.0)

        # -- Stages — sort by absolute position --
        ext_stages = data.get("stages", [])
        if not ext_stages:
            raise ValueError("Tasarimda stage bulunamadi.")

        # Sort: primary by distance_from_source, secondary by depth descending
        ext_stages = sorted(
            ext_stages,
            key=lambda s: (
                s.get("distance_from_source_mm", 0),
                -s.get("depth_mm", 0),
            ),
        )

        # Determine global collimator type from aperture types
        aperture_types = {
            s.get("aperture_type", "slit") for s in ext_stages
        }
        if "fan" in aperture_types or "fan_beam" in aperture_types:
            col_type = CollimatorType.FAN_BEAM
        elif (
            "pencil" in aperture_types
            or "pencil_beam" in aperture_types
            or "pinhole" in aperture_types
        ):
            col_type = CollimatorType.PENCIL_BEAM
        else:
            col_type = CollimatorType.SLIT

        # -- Convert each stage --
        stages: list[CollimatorStage] = []
        for i, ext_s in enumerate(ext_stages):
            stage = self._convert_stage(ext_s, i, col_type)
            stages.append(stage)

        # Dose / intensity parameters
        tube_current_mA = src_data.get("current_ma", 8.0)
        linac_dose_Gy_min = (
            src_data.get("linac_dose_rate_Gy_min_he")
            or src_data.get("linac_dose_rate_Gy_min_le")
            or src_data.get("manual_dose_rate_Gy_min")
            or 0.8
        )
        linac_pps = int(
            src_data.get("linac_current_pps_hz")
            or src_data.get("linac_ref_pps_hz")
            or 260
        )

        source = SourceConfig(
            position=Point2D(0.0, 0.0),
            energy_kVp=energy_kVp,
            energy_MeV=energy_MeV,
            focal_spot_size=focal_spot,
            focal_spot_distribution=focal_dist,
            tube_current_mA=tube_current_mA,
            linac_pps=linac_pps,
            linac_dose_rate_Gy_min=linac_dose_Gy_min,
            linac_ref_pps=linac_pps,
        )
        detector = DetectorConfig(
            position=Point2D(0.0, sdd),
            width=det_width,
            distance_from_source=sdd,
        )

        # -- Phantoms --
        phantoms = self._convert_phantoms(data.get("phantoms", []))

        # -- Probes (not supported — log & skip) --
        ext_probes = data.get("probes", [])
        if ext_probes:
            logger.info(
                "Doz proplari (%d adet) desteklenmiyor, atlanacak.",
                len(ext_probes),
            )

        return CollimatorGeometry(
            id=str(uuid.uuid4()),
            name=data.get("name", "Imported Design"),
            type=col_type,
            source=source,
            stages=stages,
            detector=detector,
            phantoms=phantoms,
        )

    # -- Stage conversion --

    @staticmethod
    def _convert_stage(
        ext: dict,
        order: int,
        col_type: CollimatorType,
    ) -> CollimatorStage:
        """Convert a single external stage dict to CollimatorStage.

        External layers are collapsed: thickest layer's material_id is used.
        distance_from_source_mm maps directly to y_position.

        Args:
            ext: External stage dictionary.
            order: Stage order index.
            col_type: Global collimator type.

        Returns:
            CollimatorStage.
        """
        depth = ext.get("depth_mm", 50.0)
        outer_width = ext.get("outer_width_mm", 100.0)
        aperture_type = ext.get("aperture_type", "slit").lower()

        # Aperture widths
        entry_w = ext.get("aperture_width_entry_mm", 10.0)
        exit_w = ext.get("aperture_width_exit_mm", entry_w)

        # For "open" aperture, the opening spans full outer_width
        if aperture_type == "open":
            entry_w = outer_width
            exit_w = outer_width

        # Taper angle from entry/exit width difference
        taper_angle = 0.0
        if abs(entry_w - exit_w) > 0.01 and depth > 0:
            taper_angle = math.degrees(
                math.atan2(abs(entry_w - exit_w) / 2.0, depth)
            )

        # Aperture height (if provided)
        entry_h = ext.get("aperture_height_entry_mm")
        exit_h = ext.get("aperture_height_exit_mm")
        slit_height = exit_h if exit_h is not None else entry_h

        aperture = ApertureConfig(
            slit_width=exit_w,
            slit_height=slit_height,
            taper_angle=taper_angle,
        )

        # Set type-specific aperture fields
        if aperture_type == "pinhole" or col_type == CollimatorType.PENCIL_BEAM:
            aperture.pencil_diameter = exit_w
        elif col_type == CollimatorType.FAN_BEAM:
            aperture.fan_slit_width = exit_w

        # Collapse external layers to single material
        ext_layers = ext.get("layers", [])
        if ext_layers:
            best = max(ext_layers, key=lambda l: l.get("thickness_mm", 0))
            material_id = best.get("material_id", "Pb")
        else:
            material_id = "Pb"

        # distance_from_source_mm → y_position
        y_position = ext.get("distance_from_source_mm", 0.0)

        return CollimatorStage(
            id=ext.get("id", str(uuid.uuid4())),
            name=ext.get("name", f"Stage {order}"),
            order=order,
            purpose=StagePurpose.CUSTOM,
            outer_width=outer_width,
            outer_height=depth,
            aperture=aperture,
            material_id=material_id,
            y_position=y_position,
            x_offset=0.0,
        )

    # -- Phantom conversion --

    @staticmethod
    def _convert_phantoms(ext_phantoms: list[dict]) -> list:
        """Convert external phantom array to our phantom models.

        Supported types:
          - ``wire`` → WirePhantom
          - ``grid`` → GridPhantom

        External ``z_mm`` maps to ``PhantomConfig.position_y`` (beam axis).

        Args:
            ext_phantoms: List of external phantom dicts.

        Returns:
            List of WirePhantom / GridPhantom instances.
        """
        phantoms = []
        for ext in ext_phantoms:
            ptype = ext.get("type", "").lower()
            z_mm = ext.get("z_mm", 300.0)
            material_id = ext.get("material_id", "W")
            name = ext.get("name", "")

            if ptype == "wire":
                diameter = ext.get("diameter_mm", 0.5)
                phantom = WirePhantom(
                    config=PhantomConfig(
                        id=ext.get("id", str(uuid.uuid4())),
                        type=PhantomType.WIRE,
                        name=name or f"Tel {diameter}mm",
                        position_y=z_mm,
                        material_id=material_id,
                    ),
                    diameter=diameter,
                )
                phantoms.append(phantom)
            elif ptype == "grid":
                bar_width = ext.get("bar_width_mm", 1.0)
                bar_spacing = ext.get("bar_spacing_mm", 1.0)
                num_bars = ext.get("num_bars", 10)
                pitch = bar_width + bar_spacing
                size = num_bars * pitch
                phantom = GridPhantom(
                    config=PhantomConfig(
                        id=ext.get("id", str(uuid.uuid4())),
                        type=PhantomType.GRID,
                        name=name or f"Grid {pitch:.1f}mm",
                        position_y=z_mm,
                        material_id=material_id,
                    ),
                    pitch=pitch,
                    wire_diameter=bar_width,
                    size=size,
                )
                phantoms.append(phantom)
            else:
                logger.warning(
                    "Bilinmeyen phantom tipi '%s' atlanacak: %s",
                    ptype, name,
                )
        return phantoms
