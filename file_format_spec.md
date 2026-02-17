# Collimator Project File Format Specification (.json)

This document describes the JSON structure used to save and load Collimator Design Tool projects.

## Root Object

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | string | Name of the project/design. |
| `source` | object | Configuration of the radiation source (X-Ray/LINAC). |
| `detector` | object | Configuration of the detector plane. |
| `stages` | array | List of collimator stages objects. |
| `probes` | array | List of dose probe objects. |
| `phantoms` | array | List of phantom objects (Wire/Grid). |

---

## 1. Source Configuration (`source`)

Describes the X-Ray tube or LINAC source parameters.

| Field | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `focal_spot_size_mm` | float | mm | Size of the focal spot. |
| `distribution` | string | - | "uniform" or "gaussian". |
| `energy_kev` | float | keV | Photon energy maximum. |
| `current_ma` | float | mA | Tube current (Used in X-Ray mode < 1000 keV). |
| `use_linac_simulation` | bool | - | If true, enables LINAC simulation logic (for > 1 MeV). |
| `linac_dose_rate_Gy_min_he` | float | Gy/min | Dose rate at reference PPS for High Energy mode. |
| `linac_dose_rate_Gy_min_le` | float | Gy/min | Dose rate at reference PPS for Low Energy mode. |
| `linac_ref_pps_hz` | float | Hz | Reference Pulse Repetition Frequency. |
| `linac_current_pps_hz` | float | Hz | Operational Pulse Repetition Frequency. |
| `pulse_width_us` | float | µs | Pulse width. |
| `linac_mode` | string | - | "HE", "LE", or "INTERLACED". |

---

## 2. Detector Configuration (`detector`)

| Field | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `distance_mm` | float | mm | Distance from source to detector plane (Z-axis). |
| `width_mm` | float | mm | Physical width of the detector (X-axis). |

---

## 3. Collimator Stages (`stages`)

Each item in the `stages` array represents a physical collimator block.

| Field | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `id` | string | UUID | Unique identifier. |
| `name` | string | - | Display name of the stage. |
| `distance_from_source_mm` | float | mm | Position of the stage's **front face** on Z-axis. |
| `depth_mm` | float | mm | Thickness of the stage along Z-axis. |
| `outer_width_mm` | float | mm | Total width of the stage block. |
| `aperture_type` | string | - | "slit", "pinhole", or "open". |
| `aperture_width_entry_mm` | float | mm | Width of the opening at the front face. |
| `aperture_width_exit_mm` | float | mm | Width of the opening at the back face. |
| `aperture_height_entry_mm` | float | mm | Height of the opening (used for pinhole/3D). |
| `aperture_height_exit_mm` | float | mm | Height of the opening (used for pinhole/3D). |
| `layers` | array | - | List of material layers within the stage. |

### Layers (`layers`)

| Field | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `id` | string | UUID | Unique identifier. |
| `material_id` | string | - | Material ID (e.g., "Pb", "W", "Fe", "SS304", "Al", "Cu"). |
| `thickness_mm` | float | mm | Thickness of this specific layer. |
| `purpose` | string | - | "shielding", "structural", or "filter". |

---

## 4. Dose Probes (`probes`)

Point measurement devices.

| Field | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `id` | string | UUID | Unique identifier. |
| `name` | string | - | Label for the probe. |
| `x_mm` | float | mm | Horizontal position (offset from center). |
| `z_mm` | float | mm | Distance from source. |
| `result_dose_rate` | float | Gy/min | Calculated dose rate at this point (Result). |

---

## 5. Phantoms (`phantoms`)

Test objects placed in the beam. Structure depends on `type`.

### Common Fields
| Field | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `id` | string | UUID | Unique identifier. |
| `name` | string | - | Name of the phantom. |
| `type` | string | - | "wire" or "grid". |
| `z_mm` | float | mm | Distance from source. |
| `material_id` | string | - | Material ID (e.g., "SS304", "Cu"). |
| `offset_x_mm` | float | mm | Vertical offset (in UI) / Horizontal in simulation logic. |

### Wire Phantom (type="wire")
| Field | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `diameter_mm` | float | mm | Diameter of the wire. |

### Grid Phantom (type="grid")
| Field | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `bar_width_mm` | float | mm | Width of each bar. |
| `bar_thickness_mm` | float | mm | Thickness of the grid (Z-depth). |
| `bar_spacing_mm` | float | mm | Air gap between bars. |
| `num_bars` | int | - | Number of bars in the grid. |

---

## Example JSON

```json
{
    "name": "Test Project",
    "source": {
        "focal_spot_size_mm": 2.0,
        "distribution": "gaussian",
        "energy_kev": 6000.0,
        "current_ma": 1.0,
        "linac_dose_rate_Gy_min_he": 0.008,
        "linac_dose_rate_Gy_min_le": 0.0025,
        "linac_ref_pps_hz": 260.0,
        "linac_current_pps_hz": 260.0,
        "pulse_width_us": 3.0,
        "linac_mode": "HE",
        "use_linac_simulation": true,
        "manual_dose_rate_Gy_min": 10.0,
        "simulation_ray_count_k": 10
    },
    "detector": {
        "distance_mm": 1000.0,
        "width_mm": 600.0
    },
    "stages": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Stage 1",
            "distance_from_source_mm": 100.0,
            "depth_mm": 50.0,
            "outer_width_mm": 150.0,
            "aperture_type": "slit",
            "aperture_width_entry_mm": 10.0,
            "aperture_width_exit_mm": 10.0,
            "aperture_height_entry_mm": 10.0,
            "aperture_height_exit_mm": 10.0,
            "layers": [
                {
                    "id": "layer-uuid-1",
                    "material_id": "Pb",
                    "thickness_mm": 50.0,
                    "purpose": "shielding"
                }
            ]
        }
    ],
    "probes": [],
    "phantoms": [
        {
            "id": "phantom-uuid-1",
            "name": "Resolution Wire",
            "type": "wire",
            "z_mm": 500.0,
            "material_id": "SS304",
            "diameter_mm": 1.5,
            "offset_x_mm": 0.0
        }
    ]
}
```
