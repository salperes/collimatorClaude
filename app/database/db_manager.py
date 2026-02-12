"""SQLite database manager — connection, schema creation, and initialization.

Creates 8 tables on first run:
  materials, attenuation_data, designs, design_versions,
  simulation_results, calculation_results, notes, app_settings.

Reference: FRD §3 — Data Models, Phase-01 spec.
"""

import sqlite3
from pathlib import Path

from app.constants import DB_FILENAME

_SCHEMA_SQL = """
-- Material database
CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    atomic_number REAL NOT NULL,
    density REAL NOT NULL,
    color TEXT NOT NULL,
    category TEXT NOT NULL,
    composition_json TEXT
);

-- Attenuation data (NIST XCOM)
CREATE TABLE IF NOT EXISTS attenuation_data (
    material_id TEXT NOT NULL,
    energy_keV REAL NOT NULL,
    mass_attenuation REAL NOT NULL,
    mass_energy_absorption REAL,
    photoelectric REAL,
    compton REAL,
    pair_production REAL,
    PRIMARY KEY (material_id, energy_keV),
    FOREIGN KEY (material_id) REFERENCES materials(id)
);

-- User designs
CREATE TABLE IF NOT EXISTS designs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    collimator_type TEXT NOT NULL,
    geometry_json TEXT NOT NULL,
    thumbnail_png BLOB,
    tags TEXT,
    is_favorite INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Design versions
CREATE TABLE IF NOT EXISTS design_versions (
    id TEXT PRIMARY KEY,
    design_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    geometry_json TEXT NOT NULL,
    change_note TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE CASCADE
);

-- Simulation results
CREATE TABLE IF NOT EXISTS simulation_results (
    id TEXT PRIMARY KEY,
    design_id TEXT NOT NULL,
    design_version INTEGER,
    name TEXT,
    config_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    compton_result_json TEXT,
    energy_keV REAL NOT NULL,
    num_rays INTEGER NOT NULL,
    include_buildup INTEGER DEFAULT 1,
    include_scatter INTEGER DEFAULT 0,
    computation_time_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE CASCADE
);

-- Calculation results
CREATE TABLE IF NOT EXISTS calculation_results (
    id TEXT PRIMARY KEY,
    design_id TEXT,
    calc_type TEXT NOT NULL,
    input_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE SET NULL
);

-- Notes
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    parent_type TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Application settings
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

EXPECTED_TABLES = [
    "materials",
    "attenuation_data",
    "designs",
    "design_versions",
    "simulation_results",
    "calculation_results",
    "notes",
    "app_settings",
]


class DatabaseManager:
    """Manages SQLite database connection and schema lifecycle."""

    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            db_path = Path.cwd() / DB_FILENAME
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def db_path(self) -> Path:
        return self._db_path

    def connect(self) -> sqlite3.Connection:
        """Open (or return existing) database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def initialize_database(self) -> None:
        """Create all tables if they don't exist."""
        conn = self.connect()
        conn.executescript(_SCHEMA_SQL)
        conn.commit()

    def get_tables(self) -> list[str]:
        """Return list of table names in the database."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row[0] for row in cursor.fetchall()]

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
