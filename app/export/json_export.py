"""JSON geometry export/import.

Exports CollimatorGeometry as formatted JSON with schema version.
Imports with automatic v1.x → v2.0 migration.

Reference: Phase-06 spec — FR-1.6.6.
"""

from __future__ import annotations

import json

from app.constants import GEOMETRY_SCHEMA_VERSION
from app.core.serializers import dict_to_geometry, geometry_to_dict
from app.models.geometry import CollimatorGeometry


class JsonExporter:
    """JSON geometry file operations."""

    def export_geometry(
        self, geometry: CollimatorGeometry, output_path: str,
    ) -> None:
        """Write geometry as formatted JSON file.

        Args:
            geometry: The geometry to export.
            output_path: Destination file path (.json).
        """
        data = geometry_to_dict(geometry)
        data["schema_version"] = GEOMETRY_SCHEMA_VERSION
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def import_geometry(self, input_path: str) -> CollimatorGeometry:
        """Read geometry from JSON file.

        Handles v1.x migration automatically.

        Args:
            input_path: Source file path (.json).

        Returns:
            Reconstructed CollimatorGeometry.
        """
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return dict_to_geometry(data)
