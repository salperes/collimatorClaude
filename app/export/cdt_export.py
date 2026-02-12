"""CDT project file export/import — JSON+ZIP format.

The .cdt file is a ZIP archive containing:
  metadata.json, design.json, thumbnail.png,
  versions/*.json, simulations/*.json

Reference: Phase-06 spec — FR-1.6.5.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from io import BytesIO

from app.constants import APP_VERSION, GEOMETRY_SCHEMA_VERSION
from app.core.serializers import (
    dict_to_geometry,
    geometry_to_dict,
    simulation_config_to_dict,
    simulation_result_to_dict,
)
from app.database.design_repository import DesignRepository
from app.models.geometry import CollimatorGeometry


class CdtExporter:
    """CDT project file operations."""

    def export_project(
        self,
        design_id: str,
        repo: DesignRepository,
        output_path: str,
        thumbnail: bytes | None = None,
    ) -> None:
        """Create .cdt ZIP file with full design data.

        Args:
            design_id: Design to export.
            repo: Repository for loading data.
            output_path: Destination file path (.cdt).
            thumbnail: Pre-rendered thumbnail PNG bytes.
        """
        geometry = repo.load_design(design_id)
        versions = repo.get_version_history(design_id)
        simulations = repo.list_simulation_results(design_id)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Metadata
            metadata = {
                "app_version": APP_VERSION,
                "format_version": "1.0",
                "schema_version": GEOMETRY_SCHEMA_VERSION,
                "design_name": geometry.name,
                "created_at": datetime.now().isoformat(),
            }
            zf.writestr("metadata.json", json.dumps(metadata, indent=2, ensure_ascii=False))

            # Design geometry
            geo_dict = geometry_to_dict(geometry)
            zf.writestr("design.json", json.dumps(geo_dict, indent=2, ensure_ascii=False))

            # Thumbnail
            if thumbnail:
                zf.writestr("thumbnail.png", thumbnail)

            # Versions
            for ver in versions:
                try:
                    ver_geo = repo.load_version(design_id, ver.version_number)
                    ver_data = {
                        "version_number": ver.version_number,
                        "change_note": ver.change_note,
                        "created_at": ver.created_at,
                        "geometry": geometry_to_dict(ver_geo),
                    }
                    zf.writestr(
                        f"versions/v{ver.version_number:03d}.json",
                        json.dumps(ver_data, indent=2, ensure_ascii=False),
                    )
                except KeyError:
                    continue

            # Simulation results
            for sim in simulations:
                try:
                    config, result = repo.load_simulation_result(sim.id)
                    sim_data = {
                        "name": sim.name,
                        "created_at": sim.created_at,
                        "config": simulation_config_to_dict(config),
                        "result": simulation_result_to_dict(result),
                    }
                    zf.writestr(
                        f"simulations/{sim.id}.json",
                        json.dumps(sim_data, indent=2, ensure_ascii=False),
                    )
                except KeyError:
                    continue

    def import_project(
        self,
        input_path: str,
        repo: DesignRepository,
    ) -> str:
        """Import .cdt file and create new design in DB.

        Args:
            input_path: Source file path (.cdt).
            repo: Repository for saving data.

        Returns:
            New design_id.
        """
        with zipfile.ZipFile(input_path, "r") as zf:
            # Read design geometry
            design_data = json.loads(zf.read("design.json"))
            geometry = dict_to_geometry(design_data)

            # Read metadata for name
            metadata = {}
            if "metadata.json" in zf.namelist():
                metadata = json.loads(zf.read("metadata.json"))

            name = metadata.get("design_name", geometry.name)
            design_id = repo.save_design(geometry, name)

            # Import thumbnail
            if "thumbnail.png" in zf.namelist():
                thumbnail = zf.read("thumbnail.png")
                repo.update_thumbnail(design_id, thumbnail)

            return design_id
