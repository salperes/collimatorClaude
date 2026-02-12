# Phase 1 — Temel Altyapi + Birim Sistemi

## Amac
Proje iskeletini olusturmak: Python/PyQt6 uygulama yapisi, veri modelleri, birim donusum sistemi, SQLite veritabani semasi, koyu tema ve temel panel duzeni.

## Kapsam & Bagimliliklar
- Bu faz hicbir onceki faza bagimli degildir (ilk faz)
- Sonraki tum fazlar bu faza bagimlidir

## Olusturulacak Dosyalar

```
collimator/
├── main.py                     # Entry point
├── requirements.txt            # Python bagimliliklari
├── pyproject.toml              # Modern Python paketleme
├── app/
│   ├── __init__.py
│   ├── application.py          # QApplication baslatma, tema yukleme
│   ├── main_window.py          # Ana pencere (QMainWindow)
│   ├── constants.py            # Uygulama sabitleri
│   ├── core/
│   │   ├── __init__.py
│   │   └── units.py            # Birim donusum modulu (KRITIK)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── material.py         # Material, AttenuationDataPoint
│   │   ├── geometry.py         # CollimatorGeometry, Layer, Aperture
│   │   ├── simulation.py       # SimulationConfig, SimulationResult
│   │   └── compton.py          # ComptonConfig, ComptonAnalysis
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── styles/
│   │   │   ├── dark_theme.qss  # Koyu tema QSS
│   │   │   └── colors.py       # Renk paleti sabitleri
│   │   ├── panels/             # Bos __init__.py (sonraki fazlarda doldurulacak)
│   │   ├── canvas/             # Bos __init__.py
│   │   ├── charts/             # Bos __init__.py
│   │   ├── dialogs/            # Bos __init__.py
│   │   ├── widgets/            # Bos __init__.py
│   │   └── toolbar.py          # Placeholder toolbar
│   ├── database/
│   │   ├── __init__.py
│   │   └── db_manager.py       # SQLite baglanti yonetimi + sema olusturma
│   └── workers/
│       └── __init__.py
├── data/
│   └── (NIST JSON dosyalari bu fazda hazirlanacak)
├── resources/
│   └── icons/
├── tests/
│   ├── __init__.py
│   └── test_units.py           # Birim donusum testleri (BM-9)
└── scripts/
    └── load_nist_data.py       # NIST veri yukleme scripti
```

## Veri Modelleri

### Material (app/models/material.py)

```python
from dataclasses import dataclass, field
from enum import Enum

class MaterialCategory(Enum):
    PURE_ELEMENT = "pure_element"
    ALLOY = "alloy"

@dataclass
class Composition:
    element: str                           # "Fe", "Cr", "Ni", vb.
    weight_fraction: float                 # 0.0 – 1.0

@dataclass
class AttenuationDataPoint:
    energy_keV: float                      # Foton enerjisi (keV)
    mass_attenuation: float                # mu/rho (cm2/g) — toplam (coherent dahil)
    mass_energy_absorption: float          # mu_en/rho (cm2/g)
    photoelectric: float                   # Fotoelektrik bilesen
    compton: float                         # Compton sacilma bileseni
    pair_production: float                 # Cift uretimi bileseni (>1.022 MeV)

@dataclass
class Material:
    id: str                                # "Pb", "W", "SS304", "SS316", "Bi", "Al", "Cu", "Bronze"
    name: str                              # Goruntulenecek ad
    symbol: str                            # Kimyasal sembol
    atomic_number: float                   # Atom numarasi (alasimlar icin efektif Z)
    density: float                         # Yogunluk (g/cm3)
    color: str                             # Hex renk kodu
    category: MaterialCategory
    composition: list[Composition] = field(default_factory=list)
    attenuation_data: list[AttenuationDataPoint] = field(default_factory=list)
```

### Geometry (app/models/geometry.py)

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid
from datetime import datetime

class CollimatorType(Enum):
    FAN_BEAM = "fan_beam"
    PENCIL_BEAM = "pencil_beam"
    SLIT = "slit"

class LayerPurpose(Enum):
    PRIMARY_SHIELDING = "primary_shielding"
    SECONDARY_SHIELDING = "secondary_shielding"
    STRUCTURAL = "structural"
    FILTER = "filter"

class StagePurpose(Enum):
    """Stage'in isin yolundaki fonksiyonel amaci."""
    PRIMARY_SHIELDING = "primary_shielding"
    SECONDARY_SHIELDING = "secondary_shielding"
    FAN_DEFINITION = "fan_definition"
    PENUMBRA_TRIMMER = "penumbra_trimmer"
    FILTER = "filter"
    CUSTOM = "custom"

@dataclass
class Point2D:
    x: float = 0.0    # mm
    y: float = 0.0    # mm

@dataclass
class SourceConfig:
    position: Point2D = field(default_factory=Point2D)
    energy_kVp: Optional[float] = None
    energy_MeV: Optional[float] = None
    focal_spot_size: float = 1.0           # mm

@dataclass
class ApertureConfig:
    fan_angle: Optional[float] = None      # derece
    fan_slit_width: Optional[float] = None # mm
    pencil_diameter: Optional[float] = None # mm
    slit_width: Optional[float] = None     # mm
    slit_height: Optional[float] = None    # mm
    taper_angle: float = 0.0               # derece

@dataclass
class CollimatorLayer:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order: int = 0
    material_id: str = ""
    thickness: float = 0.0                 # mm
    purpose: LayerPurpose = LayerPurpose.PRIMARY_SHIELDING

@dataclass
class CollimatorStage:
    """Isin yolundaki tek bir kolimator asamasi.

    Her stage bagimsiz bir govdedir: kendi aperture, katman, boyut.
    Ornek: Kaynak -> [Internal] -> (bosluk) -> [Fan] -> (bosluk) -> [Penumbra] -> Detektor
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""                         # "Internal", "Fan", "Penumbra"
    order: int = 0                         # 0 = kaynaga en yakin
    purpose: StagePurpose = StagePurpose.PRIMARY_SHIELDING
    outer_width: float = 100.0             # mm
    outer_height: float = 200.0            # mm (isin ekseni boyunca)
    aperture: ApertureConfig = field(default_factory=ApertureConfig)
    layers: list[CollimatorLayer] = field(default_factory=list)
    gap_after: float = 0.0                 # mm — sonraki stage'e kadar bosluk

# Deprecated alias
CollimatorBody = CollimatorStage

@dataclass
class DetectorConfig:
    position: Point2D = field(default_factory=lambda: Point2D(0, 500))
    width: float = 500.0                   # mm
    distance_from_source: float = 1000.0   # mm (SDD)

@dataclass
class CollimatorGeometry:
    """Cok asamali kolimator tasarim geometrisi.

    stages: 1-N arasi stage. Tek stage = eski tek-govde modeli.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Yeni Tasarim"
    type: CollimatorType = CollimatorType.FAN_BEAM
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: SourceConfig = field(default_factory=SourceConfig)
    stages: list[CollimatorStage] = field(default_factory=lambda: [CollimatorStage()])
    detector: DetectorConfig = field(default_factory=DetectorConfig)
```

### Simulation (app/models/simulation.py)

```python
from dataclasses import dataclass, field

@dataclass
class ComptonConfig:
    enabled: bool = False
    max_scatter_order: int = 1
    scatter_rays_per_interaction: int = 10
    min_energy_cutoff_keV: float = 10.0
    include_klein_nishina: bool = True
    angular_bins: int = 180

@dataclass
class SimulationConfig:
    id: str = ""
    geometry_id: str = ""
    energy_points: list[float] = field(default_factory=list)  # keV
    num_rays: int = 360
    include_buildup: bool = True
    include_scatter: bool = False
    angular_resolution: float = 1.0        # derece
    compton_config: ComptonConfig = field(default_factory=ComptonConfig)
```

## Birim Donusum Modulu (app/core/units.py) — KRITIK

```python
import math
from typing import NewType

# Type alias'lar (runtime maliyeti yok, IDE'de birim hatalarini gorunur kilar)
Cm = NewType('Cm', float)
Mm = NewType('Mm', float)
KeV = NewType('KeV', float)
Mfp = NewType('Mfp', float)
Radian = NewType('Radian', float)

# Uzunluk donusumleri
def mm_to_cm(mm: float) -> Cm:
    """UI (mm) -> Core (cm)"""
    return Cm(mm * 0.1)

def cm_to_mm(cm: float) -> Mm:
    """Core (cm) -> UI (mm)"""
    return Mm(cm * 10.0)

# Enerji donusumleri
def MeV_to_keV(mev: float) -> KeV:
    return KeV(mev * 1000.0)

def keV_to_MeV(kev: float) -> float:
    return kev / 1000.0

# Aci donusumleri
def deg_to_rad(deg: float) -> Radian:
    return Radian(deg * (math.pi / 180.0))

def rad_to_deg(rad: float) -> float:
    return rad * (180.0 / math.pi)

# Optik kalinlik donusumleri
def thickness_to_mfp(thickness_cm: float, mu_cm: float) -> Mfp:
    """Fiziksel kalinlik -> optik kalinlik (mfp)"""
    return Mfp(mu_cm * thickness_cm)

def mfp_to_thickness(mfp: float, mu_cm: float) -> Cm:
    """Optik kalinlik -> fiziksel kalinlik"""
    return Cm(mfp / mu_cm)

# Zayiflama donusumleri
def transmission_to_dB(transmission: float) -> float:
    """Iletim orani -> dB zayiflama"""
    return -10.0 * math.log10(max(transmission, 1e-30))

def dB_to_transmission(dB: float) -> float:
    """dB zayiflama -> iletim orani"""
    return 10.0 ** (-dB / 10.0)
```

### Birim kurallari:
1. **Core katmani (app/core/):** cm, keV, radian
2. **UI katmani (app/ui/):** mm, keV/MeV, derece
3. **Donusum siniri:** Yalnizca UI<->Core sinirinda yapilir
4. **Build-up:** `thickness_cm -> mfp` donusumu build-up fonksiyonundan hemen once
5. **Docstring:** Her core fonksiyonunda giris/cikis birimleri acikca yazilir

> **Multi-Stage (v2.0):** `CollimatorBody` artik `CollimatorStage` olarak yeniden adlandirildi.
> Stage sayisi degisken (1-N). Her stage'in kendi aperture ve katmanlari var.
> Stage'ler arasi `gap_after` ile bosluk tanimlanir. `CollimatorBody` alias olarak duruyor.

## Malzeme Referans Degerleri

| Malzeme | ID | Z (efektif) | Yogunluk (g/cm3) | Renk | Kategori |
|---------|-----|-------------|-------------------|------|----------|
| Kursun | Pb | 82 | 11.34 | #5C6BC0 | pure_element |
| Tungsten | W | 74 | 19.30 | #FF7043 | pure_element |
| Paslanmaz Celik 304 | SS304 | ~25.8 | 8.00 | #78909C | alloy |
| Paslanmaz Celik 316 | SS316 | ~25.8 | 8.00 | #90A4AE | alloy |
| Bizmut | Bi | 83 | 9.78 | #AB47BC | pure_element |
| Aluminyum | Al | 13 | 2.70 | #66BB6A | pure_element |
| Bakir | Cu | 29 | 8.96 | #EF5350 | pure_element |
| Bronz | Bronze | ~29.5 | 8.80 | #FFA726 | alloy |

### Alasim bilesimleri:

**SS304:** Fe 69.5%, Cr 19.0%, Ni 9.5%, Mn 2.0%
**SS316:** Fe 65.5%, Cr 17.0%, Ni 12.0%, Mo 2.5%, Mn 2.0%, Si 1.0%
**Bronze:** Cu 88.0%, Sn 12.0%

## SQLite Veritabani Semasi (db_manager.py)

Asagidaki 8 tablo ilk calistirmada olusturulmalidir:

```sql
-- Malzeme veritabani
CREATE TABLE materials (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    atomic_number REAL NOT NULL,
    density REAL NOT NULL,
    color TEXT NOT NULL,
    category TEXT NOT NULL,
    composition_json TEXT
);

-- Zayiflama verileri (NIST XCOM)
CREATE TABLE attenuation_data (
    material_id TEXT NOT NULL,
    energy_keV REAL NOT NULL,
    mass_attenuation REAL NOT NULL,     -- mu/rho (cm2/g)
    mass_energy_absorption REAL,
    photoelectric REAL,
    compton REAL,
    pair_production REAL,
    PRIMARY KEY (material_id, energy_keV),
    FOREIGN KEY (material_id) REFERENCES materials(id)
);

-- Kullanici tasarimlari
CREATE TABLE designs (
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

-- Tasarim versiyonlari
CREATE TABLE design_versions (
    id TEXT PRIMARY KEY,
    design_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    geometry_json TEXT NOT NULL,
    change_note TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE CASCADE
);

-- Simulasyon sonuclari
CREATE TABLE simulation_results (
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

-- Hesaplama sonuclari
CREATE TABLE calculation_results (
    id TEXT PRIMARY KEY,
    design_id TEXT,
    calc_type TEXT NOT NULL,
    input_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE SET NULL
);

-- Notlar
CREATE TABLE notes (
    id TEXT PRIMARY KEY,
    parent_type TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Uygulama ayarlari
CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

## UI Temel Duzeni

```
+--------------------------------------------------------------------+
|  TOOLBAR                                                            |
|  [Dosya] [Kolimator Tipi] [Enerji: slider] [Simule]                |
+------------+----------------------------+--------------------------+
| SOL PANEL  |     MERKEZ ALAN            |   SAG PANEL              |
| (Malzeme)  |   KOLIMATOR CANVAS         |   (Katmanlar)            |
|            |   (QGraphicsScene/View)    |   (Parametreler)         |
|            |                            |   (Hizli Sonuclar)       |
+------------+----------------------------+--------------------------+
|  ALT PANEL (Tab'li grafik alani)                                    |
|  [Isin Profili] [mu/rho] [HVL/TVL] [Iletim vs Kalinlik] [Compton] |
+--------------------------------------------------------------------+
```

### Renk Paleti:
- Arka plan: `#0F172A`
- Panel arka plan: `#1E293B`
- Vurgu: `#3B82F6` (mavi)
- Uyari: `#F59E0B` (amber)
- Hata: `#EF4444` (kirmizi)
- Basari: `#10B981` (yesil)

### Pencere kurallari:
- Minimum boyut: 1280x800 px
- Sol/sag paneller: QDockWidget (suruklenebilir, daraltilabilir)
- Alt panel: QSplitter ile yuksekligi ayarlanabilir
- Pencere duzeni QSettings ile kaydedilir
- F11: Tam ekran
- Canvas her zaman merkez widget

## Kabul Kriterleri & Benchmark Testleri

### BM-9: Uctan Uca Birim Dogrulama

| Test ID | Senaryo | Girdi (UI birimleri) | Beklenen Sonuc | Kontrol Noktalari |
|---------|---------|----------------------|----------------|-------------------|
| BM-9.1 | Pb 10mm, 1 MeV iletim | thickness=10mm, E=1000keV | T=0.4478 | mm->cm: 1.0cm, mu=0.8036 cm-1, mux=0.8036 |
| BM-9.2 | Pb 10mm, 1 MeV HVL | material=Pb, E=1000keV | HVL=8.62mm | mu/rho -> mu -> ln2/mu cm -> x10 mm |
| BM-9.3 | Pb 10mm build-up | thickness=10mm, E=1MeV | B~1.37 (1 mfp) | mm->cm->mfp: 10mm->1cm->0.8036mfp |
| BM-9.4 | MeV->keV donusum | E=3.5 MeV | 3500 keV | x1000 |

### Faz 1 Tamamlanma Kriterleri:
- [ ] `main.py` calistirildiginda PyQt6 penceresi acilir (koyu tema)
- [ ] Sol/sag/alt paneller QDockWidget olarak gorunur
- [ ] SQLite veritabani olusur (8 tablo)
- [ ] Tum veri modelleri (material, geometry, simulation) import edilebilir
- [ ] `units.py` tum fonksiyonlari calisir
- [ ] BM-9.1 – BM-9.4 testleri gecer
- [ ] `requirements.txt` dogru bagimliliklari icerir

## Notlar
- NIST XCOM verileri bu fazda JSON olarak hazirlanir ve veritabanina yuklenir
- `scripts/load_nist_data.py` ile NIST verilerini indirip JSON'a donusturme
- Koyu tema QSS dosyasi `app/ui/styles/dark_theme.qss` icinde
- Bu fazda henuz hesaplama motoru yok, sadece iskelet ve veri katmani

> **FRD Referans:** §2 (Sistem Mimarisi), §3 (Veri Modelleri), §6 (UI/UX), §8.2 (Birim Sistemi), §8.3 (Yazilimsal Kisitlar), §11.6 (BM-9 Testleri)
