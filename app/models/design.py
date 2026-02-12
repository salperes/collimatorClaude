"""Design metadata models for list views and version history.

Lightweight dataclasses — no full geometry data.

Reference: Phase-06 spec.
"""

from dataclasses import dataclass, field


@dataclass
class DesignSummary:
    """Lightweight design metadata for list/browser views."""
    id: str = ""
    name: str = ""
    description: str = ""
    collimator_type: str = ""
    tags: list[str] = field(default_factory=list)
    is_favorite: bool = False
    created_at: str = ""
    updated_at: str = ""
    thumbnail_png: bytes | None = None


@dataclass
class DesignVersion:
    """Single version history entry."""
    id: str = ""
    design_id: str = ""
    version_number: int = 0
    change_note: str = ""
    created_at: str = ""


@dataclass
class SimulationSummary:
    """Lightweight simulation metadata for list views."""
    id: str = ""
    design_id: str = ""
    name: str = ""
    energy_keV: float = 0.0
    num_rays: int = 0
    include_buildup: bool = False
    include_scatter: bool = False
    computation_time_ms: int = 0
    created_at: str = ""
