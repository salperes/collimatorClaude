"""Application-wide constants.

Reference: FRD §8.3 — Software constraints.
"""

APP_NAME = "Collimator Design Tool"
APP_VERSION = "0.1.0"
APP_ORGANIZATION = "MSS"

# Window constraints
MIN_WINDOW_WIDTH = 1280
MIN_WINDOW_HEIGHT = 800

# Canvas defaults
DEFAULT_ZOOM = 1.0
MIN_ZOOM = 0.1
MAX_ZOOM = 10.0

# Simulation defaults
DEFAULT_NUM_RAYS = 360
DEFAULT_ANGULAR_RESOLUTION = 1.0  # degree
MIN_ENERGY_KEV = 1.0
MAX_ENERGY_KEV = 20_000.0  # 20 MeV

# Database
DB_FILENAME = "collimator.db"

# Material IDs (canonical)
MATERIAL_IDS = ["Pb", "W", "SS304", "SS316", "Bi", "Al", "Cu", "Bronze"]

# Multi-stage geometry
GEOMETRY_SCHEMA_VERSION = "2.0"
MAX_STAGES = 10
MIN_STAGES = 1
DEFAULT_GAP_MM = 0.0

# Canvas grid
GRID_SPACING_OPTIONS = [1.0, 5.0, 10.0, 50.0]  # mm
DEFAULT_GRID_SPACING = 10.0  # mm

# Canvas visual
HANDLE_SIZE = 6  # pixels (cosmetic, zoom-invariant)
LAYER_OPACITY = 0.85  # 85% fill (brighter for dark background)
LAYER_BORDER_OPACITY = 0.4  # 40% dashed borders
BEAM_LINE_OPACITY = 0.4  # 40% beam path lines
RULER_WIDTH = 30  # pixels

# Phantom / Projection
MAX_PHANTOMS = 10
PROJECTION_SAMPLES_WIRE = 1000
PROJECTION_SAMPLES_LP = 2000

# Ray-tracing simulation
RAY_TRACE_SAMPLES_PER_STAGE = 100
MAX_NUM_RAYS = 10_000
MIN_NUM_RAYS = 100

# Quality metric thresholds — penumbra [mm]
PENUMBRA_EXCELLENT_FAN_MM = 5.0
PENUMBRA_ACCEPTABLE_FAN_MM = 10.0
PENUMBRA_EXCELLENT_PENCIL_MM = 1.0
PENUMBRA_ACCEPTABLE_PENCIL_MM = 3.0
PENUMBRA_EXCELLENT_SLIT_MM = 2.0
PENUMBRA_ACCEPTABLE_SLIT_MM = 5.0

# Quality metric thresholds — flatness [%]
FLATNESS_EXCELLENT_PCT = 3.0
FLATNESS_ACCEPTABLE_PCT = 10.0

# Quality metric thresholds — leakage [%]
LEAKAGE_EXCELLENT_PCT = 0.1
LEAKAGE_ACCEPTABLE_PCT = 5.0

# Quality metric thresholds — collimation ratio [dB]
CR_EXCELLENT_DB = 30.0
CR_ACCEPTABLE_DB = 10.0
