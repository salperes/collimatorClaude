# X-Ray TIR Kolimatör Tasarım Aracı — Gereksinim Dokümanı

**Doküman Kodu:** CDT-SRS-001  
**Versiyon:** 2.0  
**Tarih:** 2026-02-10  
**Durum:** Taslak  
**Değişiklik:** v2.0 — Multi-Stage (Çok Aşamalı) kolimatör mimarisi. CollimatorBody → CollimatorStage. Tek gövde yerine değişken sayıda stage (1-N). v1.5: V&V çerçevesi, kalite metrikleri, PDF rapor formatı.

---

## 1. Proje Tanımı

### 1.1 Amaç

Bu uygulama, X-Ray TIR (Taşıt İnceleme Radyografi) tarama sistemlerinde kullanılan kolimatörlerin tasarımını, analiz edilmesini ve optimizasyonunu sağlayan bir mühendislik aracıdır. Kullanıcı; kolimatör geometrisini interaktif canvas üzerinde çizebilir, çok katmanlı malzeme yapısını tanımlayabilir, farklı enerji seviyelerinde (80 kVp – 6 MeV) zırhlama performansını hesaplayabilir ve ışın profili simülasyonları gerçekleştirebilir.

### 1.2 Kapsam

| Parametre | Değer |
|-----------|-------|
| Enerji aralığı | 80 kVp – 6 MeV |
| Kolimatör tipleri | Fan-beam, Pencil-beam, Slit |
| Malzeme yaklaşımı | Çok aşamalı, çok katmanlı (multi-stage, multi-layer) |
| Desteklenen malzemeler | Pb, W, SS304/SS316, Bi, Al, Cu, Bronz |
| Platform | Python (PyQt6) masaüstü uygulaması |
| Dağıtım | Installer (.exe/.dmg/.deb) + Portable |
| Kullanım senaryosu | Bireysel mühendislik aracı (tek kullanıcı) |

### 1.3 Hedef Kullanıcı

Radyasyon mühendisleri, NDT uzmanları ve güvenlik tarama sistemi tasarımcıları. Kullanıcının temel radyasyon fiziği bilgisine sahip olduğu varsayılır.

### 1.4 Tanımlar ve Kısaltmalar

| Terim | Açıklama |
|-------|----------|
| **kVp** | Kilo-Volt peak — X-ışını tüpünün en yüksek voltaj değeri |
| **MeV** | Mega Elektron Volt — yüksek enerjili foton birimi |
| **μ/ρ** | Kütle zayıflama katsayısı (cm²/g) |
| **μ** | Lineer zayıflama katsayısı (cm⁻¹) = (μ/ρ) × ρ |
| **HVL** | Half-Value Layer — ışın şiddetini %50 azaltan malzeme kalınlığı |
| **TVL** | Tenth-Value Layer — ışın şiddetini %90 azaltan malzeme kalınlığı |
| **MFP** | Mean Free Path — ortalama serbest yol |
| **Beer-Lambert** | I = I₀ × e^(−μx) — foton zayıflama denklemi |
| **Build-up faktörü (B)** | Saçılmış radyasyonun katkısını modelleyen düzeltme çarpanı |
| **Fan-beam** | Yelpaze şeklinde yayılan ışın geometrisi |
| **Pencil-beam** | Dar, kalem şeklinde paralel ışın geometrisi |
| **Slit** | Dar yarık açıklıktan geçen ışın geometrisi |
| **LINAC** | Lineer hızlandırıcı (MeV seviyesi X-ışını kaynağı) |
| **NDT** | Tahribatsız test (Non-Destructive Testing) |
| **TIR** | Taşıt İnceleme Radyografi |
| **Klein-Nishina** | Compton saçılmanın diferansiyel tesir kesitini veren kuantum elektrodinamik formülü |
| **dσ/dΩ** | Diferansiyel tesir kesiti (cm²/sr) — birim katı açı başına saçılma olasılığı |
| **Compton kenarı** | Compton saçılmada 180° geriye saçılmış fotonun enerji sınırı |
| **r₀ (r_e)** | Klasik elektron yarıçapı = 2.818 × 10⁻¹³ cm |
| **σ_KN** | Klein-Nishina toplam Compton tesir kesiti (cm²/elektron) |
| **Saçılma açısı (θ)** | Fotonun orijinal yönü ile saçılma sonrası yönü arasındaki açı |
| **Geri sekme elektronu** | Compton saçılmada enerji alan elektron |

---

## 2. Sistem Mimarisi

### 2.1 Teknoloji Stack

```
┌──────────────────────────────────────────────────────────┐
│              MASAÜSTÜ UYGULAMA (Python / PyQt6)           │
│                                                          │
│  UI Katmanı (PyQt6)                                      │
│  ├── Canvas Editör: QGraphicsScene / QGraphicsView       │
│  ├── Grafikler: pyqtgraph (gerçek zamanlı, hızlı)        │
│  ├── Polar Plot: matplotlib (Klein-Nishina için)         │
│  ├── UI Bileşenler: PyQt6 Widgets + özel bileşenler      │
│  └── Tema: QSS (Qt Style Sheets) — koyu tema             │
│                                                          │
│  İş Mantığı Katmanı (Python)                             │
│  ├── Fizik Motoru: NumPy + SciPy                         │
│  ├── Malzeme DB: NIST XCOM verileri (JSON + SQLite)      │
│  ├── Simülasyon: Ray-tracing + Compton scatter           │
│  ├── Build-up: GP + Taylor (buildup_coefficients.json)   │
│  └── Arka plan hesaplama: QThread / concurrent.futures    │
│                                                          │
│  Dışa Aktarım Katmanı                                   │
│  ├── PDF: ReportLab                                      │
│  ├── CSV: csv modülü                                     │
│  ├── Görüntü: PNG/SVG (QGraphicsScene.render)            │
│  └── Proje dosyası: JSON                                 │
│                                                          │
│  Veri Katmanı                                            │
│  ├── SQLite (malzeme DB + kullanıcı tasarımları)         │
│  └── JSON veri dosyaları (NIST XCOM, build-up katsayıları)│
├──────────────────────────────────────────────────────────┤
│  Dağıtım                                                 │
│  ├── PyInstaller → tek .exe (Windows) / .app (macOS)     │
│  ├── Portable: klasörden çalışan versiyon                │
│  └── pip install: geliştirici kurulumu                   │
└──────────────────────────────────────────────────────────┘
```

### 2.2 Proje Dizin Yapısı

```
collimator-design-tool/
├── main.py                            # Uygulama entry point
├── requirements.txt                   # Python bağımlılıkları
├── setup.py                           # pip install için
├── pyproject.toml                     # Modern Python paketleme
├── build.spec                         # PyInstaller build konfigürasyonu
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── application.py                 # QApplication başlatma, tema yükleme
│   ├── main_window.py                 # Ana pencere (QMainWindow)
│   ├── constants.py                   # Uygulama sabitleri
│   │
│   ├── core/                          # İş mantığı (UI'dan bağımsız)
│   │   ├── __init__.py
│   │   ├── physics_engine.py          # Beer-Lambert, HVL/TVL hesaplamaları
│   │   ├── material_database.py       # Malzeme veritabanı yöneticisi
│   │   ├── beam_simulation.py         # Işın profili simülasyonu
│   │   ├── ray_tracer.py              # Geometrik ışın takibi
│   │   ├── build_up_factors.py        # Build-up faktör hesaplamaları (GP + Taylor)
│   │   ├── compton_engine.py          # Klein-Nishina, Compton kinematiği, σ_KN
│   │   ├── scatter_tracer.py          # Compton scatter ray-tracing motoru
│   │   ├── klein_nishina_sampler.py   # Kahn algoritması ile açısal örnekleme
│   │   └── spectrum_models.py         # kVp/MeV spektrum modelleri
│   │
│   ├── models/                        # Veri modelleri (dataclass / Pydantic)
│   │   ├── __init__.py
│   │   ├── material.py                # Material, AttenuationDataPoint
│   │   ├── geometry.py                # CollimatorGeometry, Layer, Aperture
│   │   ├── simulation.py              # SimulationConfig, SimulationResult
│   │   └── compton.py                 # ComptonConfig, ComptonAnalysis
│   │
│   ├── ui/                            # PyQt6 arayüz bileşenleri
│   │   ├── __init__.py
│   │   ├── styles/
│   │   │   ├── dark_theme.qss         # Koyu tema QSS dosyası
│   │   │   └── colors.py              # Renk paleti sabitleri
│   │   │
│   │   ├── canvas/                    # Kolimatör çizim editörü
│   │   │   ├── __init__.py
│   │   │   ├── collimator_scene.py    # QGraphicsScene — ana sahne
│   │   │   ├── collimator_view.py     # QGraphicsView — zoom/pan kontrolü
│   │   │   ├── geometry_items.py      # QGraphicsItem alt sınıfları (gövde, katman, açıklık)
│   │   │   ├── source_item.py         # Kaynak noktası grafik öğesi
│   │   │   ├── detector_item.py       # Detektör çizgisi grafik öğesi
│   │   │   ├── beam_lines_item.py     # Işın yolu çizgileri
│   │   │   ├── scatter_overlay.py     # Saçılma etkileşim noktaları görselleştirme
│   │   │   ├── dimension_item.py      # Ölçü etiketleri ve çizgileri
│   │   │   ├── grid_item.py           # Izgara arka plan
│   │   │   └── ruler_item.py          # Cetvel (üst/sol kenar)
│   │   │
│   │   ├── panels/                    # Yan paneller
│   │   │   ├── __init__.py
│   │   │   ├── material_panel.py      # Sol panel — malzeme listesi + detay kartı
│   │   │   ├── layer_panel.py         # Sağ panel — katman yönetimi
│   │   │   ├── properties_panel.py    # Sağ panel — boyut/parametre girişleri
│   │   │   ├── results_panel.py       # Sağ panel — hızlı hesaplama sonuçları
│   │   │   └── energy_panel.py        # Enerji seçici (slider + preset'ler)
│   │   │
│   │   ├── charts/                    # Grafik bileşenleri
│   │   │   ├── __init__.py
│   │   │   ├── base_chart.py          # Ortak grafik widget'ı (pyqtgraph tabanlı)
│   │   │   ├── beam_profile_chart.py  # Işın profili grafiği
│   │   │   ├── attenuation_chart.py   # μ/ρ vs enerji grafiği (log-log)
│   │   │   ├── hvl_chart.py           # HVL vs enerji grafiği
│   │   │   ├── transmission_chart.py  # İletim vs kalınlık grafiği
│   │   │   ├── klein_nishina_chart.py # Klein-Nishina polar plot (matplotlib)
│   │   │   ├── compton_energy_chart.py # Saçılmış foton enerji spektrumu
│   │   │   ├── angle_energy_chart.py  # Açı vs enerji kaybı interaktif
│   │   │   └── spr_chart.py           # Scatter-to-Primary Ratio profili
│   │   │
│   │   ├── dialogs/                   # Diyalog pencereleri
│   │   │   ├── __init__.py
│   │   │   ├── export_dialog.py       # Dışa aktarım diyaloğu
│   │   │   ├── design_manager.py      # Tasarım kaydet/yükle diyaloğu
│   │   │   ├── simulation_dialog.py   # Simülasyon konfigürasyonu
│   │   │   ├── compton_config_dialog.py # Compton saçılma ayarları
│   │   │   └── about_dialog.py        # Hakkında diyaloğu
│   │   │
│   │   ├── widgets/                   # Özel widget'lar
│   │   │   ├── __init__.py
│   │   │   ├── energy_slider.py       # Enerji slider + sayısal input birleşik widget
│   │   │   ├── material_card.py       # Malzeme kartı widget'ı (mini grafik dahil)
│   │   │   ├── layer_row.py           # Katman satırı widget'ı (sürüklenebilir)
│   │   │   ├── color_swatch.py        # Malzeme renk karesi
│   │   │   ├── collapsible_section.py # Daraltılabilir bölüm widget'ı
│   │   │   └── status_indicator.py    # Durum gösterge widget'ı
│   │   │
│   │   └── toolbar.py                 # Ana araç çubuğu
│   │
│   ├── workers/                       # Arka plan hesaplama thread'leri
│   │   ├── __init__.py
│   │   ├── simulation_worker.py       # QThread — ışın profili simülasyonu
│   │   ├── scatter_worker.py          # QThread — Compton scatter ray-tracing
│   │   ├── export_worker.py           # QThread — PDF/CSV oluşturma
│   │   └── calculation_worker.py      # QThread — enerji/kalınlık taraması
│   │
│   ├── export/                        # Dışa aktarım modülleri
│   │   ├── __init__.py
│   │   ├── pdf_report.py              # ReportLab ile PDF rapor oluşturma
│   │   ├── csv_export.py              # CSV dışa aktarım
│   │   ├── json_export.py             # Proje/geometri JSON dışa aktarım
│   │   └── image_export.py            # Canvas PNG/SVG dışa aktarım
│   │
│   └── database/                      # Veritabanı katmanı
│       ├── __init__.py
│       ├── db_manager.py              # SQLite bağlantı yönetimi
│       ├── material_repository.py     # Malzeme CRUD
│       └── design_repository.py       # Tasarım CRUD
│
├── data/                              # Uygulama verileri
│   ├── nist_xcom/                     # NIST XCOM zayıflama verileri
│   │   ├── lead.json
│   │   ├── tungsten.json
│   │   ├── steel_304.json
│   │   ├── steel_316.json
│   │   ├── bismuth.json
│   │   ├── aluminum.json
│   │   ├── copper.json
│   │   └── bronze.json
│   ├── buildup_coefficients.json      # GP + Taylor build-up katsayıları
│   └── collimator.db                  # SQLite veritabanı (ilk çalıştırmada oluşur)
│
├── resources/                         # Uygulama kaynakları
│   ├── icons/                         # Uygulama ikonları
│   │   ├── app_icon.ico               # Windows ikonu
│   │   ├── app_icon.icns              # macOS ikonu
│   │   ├── app_icon.png               # Linux ikonu
│   │   ├── fan_beam.svg               # Kolimatör tipi ikonları
│   │   ├── pencil_beam.svg
│   │   ├── slit.svg
│   │   └── toolbar/                   # Araç çubuğu ikonları
│   └── splash.png                     # Açılış ekranı görseli
│
├── tests/
│   ├── __init__.py
│   ├── test_physics_engine.py
│   ├── test_materials.py
│   ├── test_compton.py
│   ├── test_ray_tracer.py
│   ├── test_buildup.py
│   └── test_simulation.py
│
└── scripts/
    ├── build_exe.py                   # PyInstaller build scripti
    ├── build_portable.py              # Portable build scripti
    └── load_nist_data.py              # NIST XCOM verilerini indirip JSON'a dönüştürme
```

### 2.3 Çalışma Ortamı

| Bileşen | Detay |
|---------|-------|
| Python | ≥ 3.11 |
| UI Framework | PyQt6 ≥ 6.6 |
| Grafikler | pyqtgraph ≥ 0.13, matplotlib ≥ 3.8 |
| Hesaplama | NumPy ≥ 1.26, SciPy ≥ 1.12 |
| Veritabanı | SQLite3 (Python built-in) |
| PDF | ReportLab ≥ 4.0 |
| Paketleme | PyInstaller ≥ 6.0 |
| OS Desteği | Windows 10/11, macOS 12+, Linux (Ubuntu 22.04+) |

### 2.4 Python Bağımlılıkları (requirements.txt)

```
PyQt6>=6.6.0
pyqtgraph>=0.13.3
matplotlib>=3.8.0
numpy>=1.26.0
scipy>=1.12.0
reportlab>=4.0.0
pyinstaller>=6.0.0
```

### 2.5 Dağıtım Stratejisi

#### 2.5.1 Installer (.exe / .dmg / .deb)

PyInstaller ile tek dosya dağıtım:

```python
# build.spec temel yapısı
a = Analysis(
    ['main.py'],
    pathex=[],
    datas=[
        ('data/', 'data/'),              # NIST verileri + buildup katsayıları
        ('resources/', 'resources/'),     # İkonlar, splash screen
        ('app/ui/styles/', 'app/ui/styles/'),  # QSS tema dosyaları
    ],
    hiddenimports=['pyqtgraph', 'matplotlib.backends.backend_qt5agg'],
)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name='CollimatorDesignTool',
    icon='resources/icons/app_icon.ico',  # Windows
    onefile=True,                          # Tek .exe
)
```

#### 2.5.2 Portable (klasörden çalışır)

```python
# onefile=False → klasör bazlı dağıtım
exe = EXE(
    pyz, a.scripts,
    name='CollimatorDesignTool',
    onefile=False,  # Klasör modunda
)
coll = COLLECT(exe, a.binaries, a.datas, name='CollimatorDesignTool_Portable')
```

Portable sürüm, USB bellekten veya paylaşımlı klasörden çalışabilir. Kullanıcı verileri (tasarımlar, ayarlar) uygulama klasörü altında `user_data/` dizinine kaydedilir.

---

## 3. Veri Modelleri

### 3.1 Malzeme Şeması

```python
# app/models/material.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

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
    mass_attenuation: float                # μ/ρ (cm²/g) — toplam (coherent dahil)
    mass_energy_absorption: float          # μ_en/ρ (cm²/g)
    photoelectric: float                   # Fotoelektrik bileşen
    compton: float                         # Compton saçılma bileşeni
    pair_production: float                 # Çift üretimi bileşeni (>1.022 MeV)

@dataclass
class Material:
    id: str                                # "Pb", "W", "SS304", "SS316", "Bi", "Al", "Cu", "Bronze"
    name: str                              # Görüntülenecek ad
    symbol: str                            # Kimyasal sembol
    atomic_number: float                   # Atom numarası (alaşımlar için efektif Z)
    density: float                         # Yoğunluk (g/cm³)
    color: str                             # QGraphicsScene renk kodu (hex)
    category: MaterialCategory             # Malzeme sınıfı
    composition: list[Composition] = field(default_factory=list)  # Alaşımlar için bileşim
    attenuation_data: list[AttenuationDataPoint] = field(default_factory=list)
```

### 3.2 Malzeme Referans Değerleri

Aşağıdaki malzemeler uygulamada hazır olarak bulunmalıdır. Zayıflama katsayıları NIST XCOM veritabanından alınacaktır.

| Malzeme | Sembol | Z (efektif) | Yoğunluk (g/cm³) | Canvas Renk | Kategori |
|---------|--------|-------------|-------------------|-------------|----------|
| Kurşun | Pb | 82 | 11.34 | `#5C6BC0` (koyu mavi) | pure_element |
| Tungsten | W | 74 | 19.30 | `#FF7043` (turuncu) | pure_element |
| Paslanmaz Çelik 304 | SS304 | ~25.8 | 8.00 | `#78909C` (gri) | alloy |
| Paslanmaz Çelik 316 | SS316 | ~25.8 | 8.00 | `#90A4AE` (açık gri) | alloy |
| Bizmut | Bi | 83 | 9.78 | `#AB47BC` (mor) | pure_element |
| Alüminyum | Al | 13 | 2.70 | `#66BB6A` (yeşil) | pure_element |
| Bakır | Cu | 29 | 8.96 | `#EF5350` (kırmızı) | pure_element |
| Bronz (CuSn) | Bronze | ~29.5 | 8.80 | `#FFA726` (amber) | alloy |

### 3.3 Alaşım Bileşimleri

```json
{
  "SS304": {
    "composition": [
      {"element": "Fe", "weight_fraction": 0.695},
      {"element": "Cr", "weight_fraction": 0.190},
      {"element": "Ni", "weight_fraction": 0.095},
      {"element": "Mn", "weight_fraction": 0.020}
    ]
  },
  "SS316": {
    "composition": [
      {"element": "Fe", "weight_fraction": 0.655},
      {"element": "Cr", "weight_fraction": 0.170},
      {"element": "Ni", "weight_fraction": 0.120},
      {"element": "Mo", "weight_fraction": 0.025},
      {"element": "Mn", "weight_fraction": 0.020},
      {"element": "Si", "weight_fraction": 0.010}
    ]
  },
  "Bronze": {
    "composition": [
      {"element": "Cu", "weight_fraction": 0.880},
      {"element": "Sn", "weight_fraction": 0.120}
    ]
  }
}
```

### 3.4 Kolimatör Geometri Şeması

```python
# app/models/geometry.py
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
    """Stage'in ışın yolundaki fonksiyonel amacı."""
    PRIMARY_SHIELDING = "primary_shielding"
    SECONDARY_SHIELDING = "secondary_shielding"
    FAN_DEFINITION = "fan_definition"
    PENUMBRA_TRIMMER = "penumbra_trimmer"
    FILTER = "filter"
    CUSTOM = "custom"

@dataclass
class Point2D:
    x: float = 0.0                        # mm
    y: float = 0.0                        # mm

@dataclass
class SourceConfig:
    position: Point2D = field(default_factory=Point2D)
    energy_kVp: Optional[float] = None     # kVp modunda
    energy_MeV: Optional[float] = None     # MeV modunda
    focal_spot_size: float = 1.0           # mm — odak noktası boyutu

@dataclass
class ApertureConfig:
    # Fan-beam için
    fan_angle: Optional[float] = None      # derece — yelpaze açısı
    fan_slit_width: Optional[float] = None # mm — yarık genişliği (ışın düzleminde)
    # Pencil-beam için
    pencil_diameter: Optional[float] = None # mm — dairesel açıklık çapı
    # Slit için
    slit_width: Optional[float] = None     # mm — yarık genişliği
    slit_height: Optional[float] = None    # mm — yarık yüksekliği
    # Ortak
    taper_angle: float = 0.0               # derece — konikleşme açısı (0 = düz kenar)

@dataclass
class CollimatorLayer:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order: int = 0                         # Sıra (0 = en iç katman)
    material_id: str = ""                  # Malzeme referansı ("Pb", "W", vb.)
    thickness: float = 0.0                 # mm — katman kalınlığı
    purpose: LayerPurpose = LayerPurpose.PRIMARY_SHIELDING

@dataclass
class CollimatorStage:
    """Işın yolundaki tek bir kolimatör aşaması (gövde).

    Her stage bağımsız bir kolimatör gövdesidir: kendi aperture'ü,
    katmanları ve fiziksel boyutları vardır. Stage'ler ışın ekseni
    boyunca kaynaktan dedektöre doğru sıralanır.

    Örnek 3-stage düzen:
        Kaynak → [Internal] → (boşluk) → [Fan] → (boşluk) → [Penumbra] → Dedektör
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""                         # "Internal", "Fan", "Penumbra"
    order: int = 0                         # Işın ekseni sırası (0 = kaynağa en yakın)
    purpose: StagePurpose = StagePurpose.PRIMARY_SHIELDING
    outer_width: float = 100.0             # mm — toplam genişlik
    outer_height: float = 200.0            # mm — ışın ekseni boyunca yükseklik
    aperture: ApertureConfig = field(default_factory=ApertureConfig)
    layers: list[CollimatorLayer] = field(default_factory=list)
    gap_after: float = 0.0                 # mm — sonraki stage'e kadar boşluk

# Geriye uyumluluk alias'ı (deprecated)
CollimatorBody = CollimatorStage

@dataclass
class DetectorConfig:
    position: Point2D = field(default_factory=lambda: Point2D(0, 500))
    width: float = 500.0                   # mm — aktif alan genişliği
    distance_from_source: float = 1000.0   # mm — SDD

@dataclass
class CollimatorGeometry:
    """Tek veya çok aşamalı kolimatör tasarım geometrisi.

    Tasarım, ışın ekseni boyunca sıralanan bir veya daha fazla
    stage'den oluşur. Stage'ler boşluklarla (hava/vakum) ayrılır.
    Tek stage'li tasarımlar stages listesinde tek eleman içerir.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Yeni Tasarım"
    type: CollimatorType = CollimatorType.FAN_BEAM
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: SourceConfig = field(default_factory=SourceConfig)
    stages: list[CollimatorStage] = field(default_factory=lambda: [CollimatorStage()])
    detector: DetectorConfig = field(default_factory=DetectorConfig)
```

> **Multi-Stage Mimari (v2.0):** Kolimatör tasarımı artık bir veya daha fazla stage'den oluşur.
> Her stage bağımsız bir gövdedir (kendi aperture, katman, boyut). Stage'ler arası boşluklar
> `gap_after` alanı ile tanımlanır. Tek stage'li tasarımlar eski tek-gövde modeliyle uyumludur.
> `CollimatorBody` alias'ı geriye uyumluluk için korunmuştur.

### 3.5 Simülasyon Şeması

```python
# app/models/simulation.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ComptonConfig:
    enabled: bool = False
    max_scatter_order: int = 1             # 1 = tek saçılma, 2+ = çoklu
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

interface SimulationResult {
  id: string;
  config_id: string;
  timestamp: string;

  // Işın profili sonuçları
  beam_profile: {
    angle: number;                     // derece veya mm (detektör düzleminde)
    intensity: number;                 // normalize edilmiş (0-1)
    transmission: number;              // iletim oranı
  }[];

  // Enerji bazlı sonuçlar
  energy_analysis: {
    energy_keV: number;
    total_attenuation_dB: number;      // dB cinsinden toplam zayıflama
    transmission_percent: number;      // % iletim
    hvl_mm: number;                    // mm cinsinden HVL
    tvl_mm: number;                    // mm cinsinden TVL
    per_layer: {
      layer_id: string;
      material_id: string;
      thickness_mm: number;
      attenuation_dB: number;
      transmission_percent: number;
    }[];
  }[];

  // Kolimasyon kalitesi metrikleri
  quality_metrics: {
    penumbra_width_mm: number;         // Yarı gölge genişliği
    field_uniformity_percent: number;  // Alan homojenliği (%)
    leakage_percent: number;           // Kaçak radyasyon (%)
    collimation_ratio: number;         // Kolimasyon oranı
    scatter_fraction: number;          // Saçılma fraksiyonu (saçılmış / toplam)
  };

  // Compton saçılma sonuçları
  compton_analysis?: {
    // Klein-Nishina diferansiyel kesit dağılımı
    klein_nishina_distribution: {
      angle_deg: number;               // Saçılma açısı (0–180°)
      dsigma_domega: number;           // dσ/dΩ (cm²/sr/elektron)
      scattered_energy_keV: number;    // O açıdaki saçılmış foton enerjisi
      recoil_electron_energy_keV: number; // Geri sekme elektron enerjisi
    }[];

    // Saçılmış foton enerji spektrumu
    scattered_spectrum: {
      energy_keV: number;              // Enerji bin merkezi
      intensity: number;               // Normalize edilmiş şiddet (0-1)
      scatter_angle_deg: number;       // Bu enerjiye karşılık gelen açı
    }[];

    // Toplam Compton tesir kesiti
    total_cross_section: {
      sigma_KN_per_electron: number;   // cm²/elektron
      sigma_KN_per_atom: number;       // cm²/atom (Z ile çarpılmış)
      mu_compton: number;              // Compton lineer zayıflama katsayısı (cm⁻¹)
    };

    // Scatter ray-tracing sonuçları (kolimatör geometrisinde)
    scatter_map?: {
      interaction_points: {
        x: number; y: number;          // Etkileşim noktası (mm)
        layer_id: string;              // Hangi katmanda
        material_id: string;           // Hangi malzemede
        incident_energy_keV: number;   // Gelen foton enerjisi
        scattered_energy_keV: number;  // Saçılan foton enerjisi
        scatter_angle_deg: number;     // Saçılma açısı
        reaches_detector: boolean;     // Detektöre ulaşıyor mu?
        escaped: boolean;              // Kolimatörden dışarı kaçıyor mu?
      }[];
      detector_scatter_profile: {
        position_mm: number;           // Detektör üzerindeki pozisyon
        scatter_intensity: number;     // Saçılma kaynaklı şiddet
        primary_intensity: number;     // Birincil ışın şiddeti
        scatter_to_primary_ratio: number; // SPR (Scatter-to-Primary Ratio)
      }[];
    };
  };
}
```

### 3.6 Tasarım Kayıt Şeması (SQLite)

```sql
-- Kullanıcı tasarımları
CREATE TABLE designs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    collimator_type TEXT NOT NULL,          -- "fan_beam" | "pencil_beam" | "slit"
    geometry_json TEXT NOT NULL,            -- CollimatorGeometry JSON (güncel hali)
    thumbnail_png BLOB,                    -- Canvas küçük önizleme (200×150 px)
    tags TEXT,                             -- Virgülle ayrılmış etiketler
    is_favorite INTEGER DEFAULT 0,         -- Favorilere eklendi mi?
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tasarım versiyonları (her kaydetmede otomatik versiyon oluşur)
CREATE TABLE design_versions (
    id TEXT PRIMARY KEY,
    design_id TEXT NOT NULL,               -- FK → designs.id
    version_number INTEGER NOT NULL,       -- 1, 2, 3...
    geometry_json TEXT NOT NULL,            -- O versiyondaki geometri
    change_note TEXT,                      -- Kullanıcı notu (opsiyonel)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE CASCADE
);

-- Simülasyon sonuçları (her çalıştırma kaydedilir)
CREATE TABLE simulation_results (
    id TEXT PRIMARY KEY,
    design_id TEXT NOT NULL,               -- FK → designs.id
    design_version INTEGER,                -- Hangi versiyon üzerinde çalıştırıldı
    name TEXT,                             -- Kullanıcı tarafından adlandırılabilir
    config_json TEXT NOT NULL,             -- SimulationConfig JSON
    result_json TEXT NOT NULL,             -- SimulationResult JSON (beam_profile, quality_metrics)
    compton_result_json TEXT,              -- ComptonAnalysis JSON (varsa)
    energy_keV REAL NOT NULL,              -- Simülasyonun enerji seviyesi
    num_rays INTEGER NOT NULL,
    include_buildup INTEGER DEFAULT 1,
    include_scatter INTEGER DEFAULT 0,
    computation_time_ms INTEGER,           -- Hesaplama süresi
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE CASCADE
);

-- Hesaplama sonuçları (hızlı hesaplamalar — zayıflama, HVL, vb.)
CREATE TABLE calculation_results (
    id TEXT PRIMARY KEY,
    design_id TEXT,                         -- FK → designs.id (opsiyonel)
    calc_type TEXT NOT NULL,                -- "attenuation" | "energy_sweep" | "thickness_sweep" | "hvl_tvl"
    input_json TEXT NOT NULL,               -- Hesaplama girdileri
    result_json TEXT NOT NULL,              -- Hesaplama sonuçları
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE SET NULL
);

-- Kullanıcı notları (tasarım veya simülasyona eklenebilir)
CREATE TABLE notes (
    id TEXT PRIMARY KEY,
    parent_type TEXT NOT NULL,              -- "design" | "simulation" | "calculation"
    parent_id TEXT NOT NULL,                -- İlgili kaydın id'si
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Uygulama ayarları (pencere düzeni, son açılan tasarım, vb.)
CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Malzeme veritabanı (NIST verileri)
CREATE TABLE materials (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    atomic_number REAL NOT NULL,
    density REAL NOT NULL,
    color TEXT NOT NULL,
    category TEXT NOT NULL,
    composition_json TEXT               -- Alaşım bileşimi JSON
);

-- Zayıflama verileri (NIST XCOM)
CREATE TABLE attenuation_data (
    material_id TEXT NOT NULL,
    energy_keV REAL NOT NULL,
    mass_attenuation REAL NOT NULL,     -- μ/ρ (cm²/g)
    mass_energy_absorption REAL,        -- μ_en/ρ (cm²/g)
    photoelectric REAL,
    compton REAL,
    pair_production REAL,
    PRIMARY KEY (material_id, energy_keV),
    FOREIGN KEY (material_id) REFERENCES materials(id)
);
```

---

## 4. Fonksiyonel Gereksinimler

### 4.1 MODÜL 1 — Kolimatör Geometri Editörü (Canvas)

#### FR-1.1 Canvas Alanı

- **FR-1.1.1:** 2D interaktif canvas alanı sunulmalıdır. Canvas, kolimatörün enine kesit görünümünü (cross-section) gösterir.
- **FR-1.1.2:** Canvas arka planında ölçekli ızgara (grid) bulunmalıdır. Izgara aralığı: 1mm, 5mm, 10mm, 50mm seçilebilir.
- **FR-1.1.3:** Zoom (fare tekerleği veya pinch) ve pan (sürükle) desteklenmelidir. Zoom aralığı: %10 – %1000.
- **FR-1.1.4:** Canvas üzerinde bir cetvel (ruler) gösterilmelidir (üst ve sol kenar, mm/cm birimi ile).
- **FR-1.1.5:** Canvas boyutu otomatik olarak pencere boyutuna uyum sağlamalıdır (responsive).

#### FR-1.2 Geometri Şablonları

Kullanıcı, kolimatör tipini seçtiğinde canvas üzerinde varsayılan bir şablon geometri oluşturulmalıdır:

- **FR-1.2.1 Fan-beam şablonu:**
  - Kaynak noktası (üstte, odak noktası ikonu ile)
  - Trapezoid kolimatör gövdesi (yukarı doğru daralan)
  - Yelpaze açısı gösterge çizgileri
  - Detektör çizgisi (altta)

- **FR-1.2.2 Pencil-beam şablonu:**
  - Kaynak noktası
  - Dikdörtgen kolimatör gövdesi, ortada dairesel/dikdörtgen kanal
  - Paralel ışın gösterge çizgileri
  - Detektör noktası

- **FR-1.2.3 Slit şablonu:**
  - Kaynak noktası
  - Dikdörtgen kolimatör gövdesi, ortada dar yarık
  - Yarık genişliği ölçü çizgisi
  - Detektör çizgisi

#### FR-1.3 Boyut Düzenleme

- **FR-1.3.1:** Kolimatör gövde boyutları (genişlik, yükseklik) canvas üzerinde tutma noktaları (handles) ile sürükleyerek veya sayısal giriş panelinden değiştirilebilmelidir.
- **FR-1.3.2:** Açıklık (aperture) boyutları benzer şekilde düzenlenebilmelidir.
- **FR-1.3.3:** Kaynak ve detektör konumları sürüklenebilmelidir.
- **FR-1.3.4:** Tüm boyut değişiklikleri anlık olarak ölçü etiketleri (dimension labels) ile canvas üzerinde gösterilmelidir.
- **FR-1.3.5:** Boyut değerleri bir yan panel (Properties Panel) üzerinde de sayısal olarak girilebilmeli ve değişiklikler canvas'a yansımalıdır.

#### FR-1.4 Katman Yönetimi

- **FR-1.4.1:** Sağ tarafta bir "Katmanlar" (Layers) paneli bulunmalıdır.
- **FR-1.4.2:** Kullanıcı "Katman Ekle" butonu ile yeni katman ekleyebilmelidir. Yeni katman eklendiğinde kolimatör gövdesi dıştan içe doğru genişler.
- **FR-1.4.3:** Her katman satırında şunlar gösterilmelidir:
  - Sıra numarası
  - Malzeme seçici (dropdown — malzeme adı + renk karesi)
  - Kalınlık girişi (mm, sayısal input)
  - Katman amacı seçici: "Birincil Zırhlama", "İkincil Zırhlama", "Yapısal", "Filtre"
  - Sil butonu
- **FR-1.4.4:** Katman sırası sürükle-bırak (drag & drop) ile değiştirilebilmelidir.
- **FR-1.4.5:** Canvas üzerinde her katman, ilgili malzemenin renk kodu ile doldurulmuş olarak gösterilmelidir. Katmanlar arası sınır çizgileri (dashed) ile ayrılmalıdır.
- **FR-1.4.6:** Bir katmana tıklandığında ilgili katman canvas üzerinde vurgulanmalı ve sağ panelde seçili olmalıdır.

#### FR-1.5 Kaynak ve Detektör

- **FR-1.5.1:** Kaynak pozisyonu bir ikon (nokta veya yıldız) ile gösterilmelidir. Odak noktası boyutu (focal spot size) ölçü etiketi ile belirtilmelidir.
- **FR-1.5.2:** Kaynak-detektör mesafesi (SDD) otomatik hesaplanıp bir ölçü çizgisi ile gösterilmelidir.
- **FR-1.5.3:** Işın yolu, kaynak noktasından açıklıktan geçerek detektöre ulaşan çizgiler ile sembolik olarak gösterilmelidir (yarı-saydam renk).

#### FR-1.6 Tasarım Yönetimi (Kayıt, Yükleme, Versiyon Geçmişi)

##### FR-1.6.1 Tasarım Kaydetme

- **FR-1.6.1.1:** `Ctrl+S` ile aktif tasarım kaydedilebilmelidir. İlk kaydetmede isim, açıklama ve etiket girişi diyaloğu gösterilir.
- **FR-1.6.1.2:** `Ctrl+Shift+S` ile "Farklı Kaydet" — mevcut tasarımın kopyası yeni isimle oluşturulur.
- **FR-1.6.1.3:** Her kaydetme işleminde otomatik versiyon oluşturulmalıdır (design_versions tablosu). Kullanıcı isteğe bağlı olarak değişiklik notu ekleyebilir.
- **FR-1.6.1.4:** Canvas'ın küçük önizleme görüntüsü (thumbnail, 200×150 px) otomatik olarak kaydedilmelidir.
- **FR-1.6.1.5:** Başlık çubuğunda aktif tasarım adı gösterilmeli, kaydedilmemiş değişiklikler varsa yıldız (*) işareti eklenmelidir.

##### FR-1.6.2 Tasarım Yükleme ve Tarama

- **FR-1.6.2.1:** `Ctrl+O` ile tasarım yükleme diyaloğu açılmalıdır.
- **FR-1.6.2.2:** Tasarım listesi şu bilgileri göstermelidir: thumbnail, isim, kolimatör tipi, son değişiklik tarihi, etiketler, favori durumu.
- **FR-1.6.2.3:** Listede filtreleme: kolimatör tipine göre (fan/pencil/slit), etiketlere göre, yalnızca favoriler.
- **FR-1.6.2.4:** Listede arama: isim ve açıklama alanlarında metin araması.
- **FR-1.6.2.5:** Son açılan tasarımlar (recent) menüden hızlıca erişilebilir olmalıdır (`Dosya > Son Kullanılanlar`).

##### FR-1.6.3 Versiyon Geçmişi

- **FR-1.6.3.1:** Aktif tasarımın versiyon geçmişi bir panel veya diyalog ile görüntülenebilmelidir.
- **FR-1.6.3.2:** Her versiyon için: versiyon numarası, tarih/saat, değişiklik notu gösterilmelidir.
- **FR-1.6.3.3:** Herhangi bir önceki versiyon seçilip canvas'ta önizlenebilmelidir.
- **FR-1.6.3.4:** "Bu versiyona geri dön" ile önceki bir versiyon aktif tasarım yapılabilmelidir (yeni versiyon olarak eklenir, geçmiş silinmez).

##### FR-1.6.4 Simülasyon Sonuçları Saklama

- **FR-1.6.4.1:** Her simülasyon çalıştırmasının sonucu otomatik olarak veritabanına kaydedilmelidir.
- **FR-1.6.4.2:** Kaydedilen sonuçlar: simülasyon konfigürasyonu, ışın profili, kalite metrikleri, Compton analizi (varsa), hesaplama süresi.
- **FR-1.6.4.3:** Bir tasarıma ait simülasyon sonuçları kronolojik olarak listelenebilmelidir.
- **FR-1.6.4.4:** Kullanıcı bir simülasyon sonucuna isim verebilmelidir (ör. "6 MeV — 2 katman Pb+W").
- **FR-1.6.4.5:** Birden fazla simülasyon sonucu seçilip grafik üzerinde karşılaştırılabilmelidir (overlay).
- **FR-1.6.4.6:** Simülasyon sonuçları silinebilmelidir.

##### FR-1.6.5 Proje Dosyası (.cdt)

- **FR-1.6.5.1:** Tasarım, tüm versiyonları, simülasyon sonuçları ve notlar tek bir `.cdt` dosyasına (JSON+ZIP formatı) dışa aktarılabilmelidir.
- **FR-1.6.5.2:** Bir `.cdt` dosyası uygulamaya içe aktarılabilmelidir.
- **FR-1.6.5.3:** `.cdt` dosya uzantısı sistem ile ilişkilendirilmeli, çift tıkla uygulama açılmalıdır (installer sürümünde).
- **FR-1.6.5.4:** `.cdt` dosyası şu bölümleri içerir:
  - `design.json` — Geometri tanımı (güncel versiyon)
  - `versions/` — Tüm versiyon geçmişi
  - `simulations/` — Tüm simülasyon sonuçları
  - `notes.json` — Tasarım ve simülasyona ait notlar
  - `thumbnail.png` — Önizleme görüntüsü
  - `metadata.json` — Uygulama versiyonu, oluşturma tarihi, dosya formatı versiyonu

##### FR-1.6.6 Geometri JSON Dışa/İçe Aktarım

- **FR-1.6.6.1:** Geometri tanımı salt JSON olarak dışa aktarılabilmelidir (simülasyon sonuçları hariç, sadece geometri). Bu, basit paylaşım ve diğer araçlarla entegrasyon için.
- **FR-1.6.6.2:** JSON geometri dosyası uygulamaya içe aktarılabilmelidir.

##### FR-1.6.7 Notlar

- **FR-1.6.7.1:** Tasarıma ve simülasyon sonuçlarına metin notları eklenebilmelidir.
- **FR-1.6.7.2:** Notlar, ilgili öğenin yanında küçük bir ikon ile gösterilmelidir.

---

### 4.2 MODÜL 2 — Malzeme Veritabanı ve Enerji Hesaplama Motoru

#### FR-2.1 Malzeme Veritabanı

- **FR-2.1.1:** Bölüm 3.2'de tanımlanan 8 malzeme (Pb, W, SS304, SS316, Bi, Al, Cu, Bronze) uygulama ile birlikte gelmelidir. Her malzeme için NIST XCOM veritabanından alınan kütle zayıflama katsayısı (μ/ρ) verileri 1 keV – 20 MeV aralığında hazır olmalıdır.
- **FR-2.1.2:** Alaşımlar (SS304, SS316, Bronze) için μ/ρ değerleri, ağırlık fraksiyonları kullanılarak karışım kuralı (mixture rule) ile hesaplanmalıdır:

```
(μ/ρ)_alaşım = Σ wᵢ × (μ/ρ)ᵢ
```

burada wᵢ = elemanın ağırlık fraksiyonu, (μ/ρ)ᵢ = elemanın zayıflama katsayısı.

- **FR-2.1.3:** Her malzeme bir "Malzeme Kartı" bileşeni ile gösterilmelidir. Kart üzerinde: isim, sembol, Z, yoğunluk, renk kodu, ve μ/ρ vs enerji mini grafiği bulunmalıdır.

#### FR-2.2 Enerji Seviyesi Yönetimi

- **FR-2.2.1:** Kullanıcı enerji seviyesini iki modda seçebilmelidir:
  - **kVp modu (80–300 kVp):** X-ray tüp kaynağı. Ortalama foton enerjisi ≈ kVp/3 olarak alınır (Kramers yaklaşımı). İsteğe bağlı olarak filtrelenmiş spektrum modeli de hesaplanabilir.
  - **MeV modu (0.5–6 MeV):** LINAC kaynağı. Monoenerjik veya basitleştirilmiş Bremsstrahlung spektrumu.
- **FR-2.2.2:** Enerji seçimi bir slider + sayısal input bileşeni ile yapılmalıdır.
- **FR-2.2.3:** Önceden tanımlı enerji presetleri sunulmalıdır:

| Preset Adı | Enerji | Tipik Kullanım |
|-------------|--------|----------------|
| Bagaj Tarama | 80 kVp | Havalimanı bagaj |
| Kargo Düşük | 160 kVp | Palet/koli tarama |
| Kargo Orta | 320 kVp | Araç tarama |
| LINAC Düşük | 1 MeV | Araç tarama |
| LINAC Orta | 3.5 MeV | Konteyner tarama |
| LINAC Yüksek | 6 MeV | Yüksek yoğunluklu kargo |

#### FR-2.3 Temel Hesaplamalar

Aşağıdaki hesaplamalar backend fizik motoru tarafından gerçekleştirilmelidir:

- **FR-2.3.1 Lineer Zayıflama Katsayısı:**
```
μ (cm⁻¹) = (μ/ρ) × ρ
```

- **FR-2.3.2 Beer-Lambert Zayıflama (tek katman):**
```
I/I₀ = e^(−μx)
```
burada x = malzeme kalınlığı (cm).

- **FR-2.3.3 Çok Katmanlı Zayıflama (composite):**
```
I/I₀ = e^(−Σ μᵢxᵢ) = Π e^(−μᵢxᵢ)
```
burada i = her katman indeksi.

- **FR-2.3.4 Build-up Faktörü Dahil Zayıflama:**
```
I/I₀ = B(E, μx) × e^(−μx)
```
Build-up faktörü B, Taylor veya Berger formülasyonu ile hesaplanmalıdır. B değerleri enerji ve μx (mean free path sayısı) cinsinden tablo veya parametrik formül olarak saklanmalıdır.

- **FR-2.3.5 HVL Hesabı:**
```
HVL = ln(2) / μ = 0.693 / μ    (cm)
```

- **FR-2.3.6 TVL Hesabı:**
```
TVL = ln(10) / μ = 2.303 / μ   (cm)
```

- **FR-2.3.7 MFP (Mean Free Path):**
```
MFP = 1 / μ   (cm)
```

- **FR-2.3.8 Zayıflama dB cinsinden:**
```
Attenuation (dB) = −10 × log₁₀(I/I₀)
```

#### FR-2.4 Hesaplama Sonuç Paneli

- **FR-2.4.1:** Seçili enerji seviyesinde her katman için ayrı ayrı ve toplam olarak şu değerler gösterilmelidir:
  - İletim oranı (%)
  - Zayıflama (dB)
  - HVL (mm)
  - TVL (mm)
- **FR-2.4.2:** Sonuçlar tablo formatında gösterilmeli, son satır "TOPLAM" olmalıdır.
- **FR-2.4.3:** Sonuçlar build-up faktörü dahil/hariç olarak iki kolon ile karşılaştırılabilir olmalıdır.

---

### 4.3 MODÜL 3 — Işın Profili Simülasyonu ve Görselleştirme

#### FR-3.1 Simülasyon Motoru

- **FR-3.1.1:** Backend, geometrik ray-tracing prensibi ile ışın profili hesaplamalıdır. Kaynak noktasından belirli açısal aralıklarla ışınlar (rays) gönderilir; her ışın kolimatör geometrisi ile kesişim testi yapılarak geçtiği malzeme katmanları ve kalınlıkları hesaplanır.
- **FR-3.1.2:** Her ışın için çok katmanlı Beer-Lambert zayıflama hesabı uygulanarak detektör düzlemindeki şiddet hesaplanır.
- **FR-3.1.3:** Işın sayısı (açısal çözünürlük) kullanıcı tarafından ayarlanabilmelidir. Varsayılan: 360 ışın, aralık: 100–10000.
- **FR-3.1.4:** Simülasyon süresi tahmini gösterilmelidir.

#### FR-3.2 Işın Profili Grafiği

- **FR-3.2.1:** X ekseni: açı (derece) veya detektör düzlemindeki pozisyon (mm). Y ekseni: normalize edilmiş şiddet (0–1) veya iletim oranı (%).
- **FR-3.2.2:** Grafik üzerinde şu bölgeler görsel olarak ayrılmalıdır:
  - **Useful beam** (yararlı ışın alanı) — açıklıktan geçen ışınlar
  - **Penumbra** (yarı gölge) — geçiş bölgesi
  - **Shielded region** (zırhlanmış bölge) — kolimatör gövdesinden geçen (sızdıran) ışınlar
- **FR-3.2.3:** Grafik interaktif olmalı: hover'da değerler tooltip ile gösterilmeli, zoom yapılabilmelidir.
- **FR-3.2.4:** Birden fazla enerji seviyesinin profilleri aynı grafikte karşılaştırılabilmelidir (overlay).

#### FR-3.3 Enerji Spektrumu Grafikleri

- **FR-3.3.1:** Malzeme bazında μ/ρ vs enerji grafiği (log-log ölçek):
  - X ekseni: Foton enerjisi (keV), logaritmik
  - Y ekseni: μ/ρ (cm²/g), logaritmik
  - Alt bileşenler (fotoelektrik, Compton, çift üretimi) ayrı eğriler olarak
- **FR-3.3.2:** Malzeme karşılaştırma grafiği: Seçilen malzemelerin μ/ρ eğrileri aynı grafikte.
- **FR-3.3.3:** HVL vs enerji grafiği: Farklı malzemeler için HVL değerlerinin enerji ile değişimi.
- **FR-3.3.4:** İletim vs kalınlık grafiği: Seçili enerjide farklı malzemeler için kalınlığa göre iletim oranı.

#### FR-3.4 Kalite Metrikleri

- **FR-3.4.1:** Simülasyon sonunda aşağıdaki kalite metrikleri hesaplanmalı ve gösterilmelidir. Her metrik için hesaplama algoritması, threshold tanımları ve referans standartlar aşağıda belirtilmiştir.

##### FR-3.4.1 Penumbra Genişliği (mm)

**Tanım:** Işın profili kenarındaki geçiş bölgesinin genişliği — yararlı ışın alanından zırhlanmış bölgeye geçişte şiddetin kademeli düşüş yaptığı alan.

**Hesaplama algoritması:**
```
1. Işın profilinde normalize edilmiş şiddet I(x) dizisini al (0–1 aralığı)
2. Yararlı ışın alanının merkezindeki ortalama şiddeti hesapla: I_max = mean(I(merkez bölge))
3. Profil kenarında (sol ve sağ ayrı ayrı) şu noktaları bul:
   - x_80 = I(x) = 0.80 × I_max noktasının pozisyonu (interpole edilmiş)
   - x_20 = I(x) = 0.20 × I_max noktasının pozisyonu (interpole edilmiş)
4. Penumbra = |x_80 − x_20|   (mm cinsinden, detektör düzleminde)
5. Sol ve sağ penumbra ayrı raporlanır; genel metrik = max(sol, sağ)
```

**Threshold tanımları (IEC 60601-2-44 ve IEC 61217 uyumlu):**

| Penumbra Tanımı | Kullanılan Seviyeler | Kullanım Alanı |
|-----------------|----------------------|----------------|
| **%20–%80** (varsayılan) | I = 0.20 × I_max → 0.80 × I_max | Endüstriyel / TIR kolimatörler |
| **%10–%90** | I = 0.10 × I_max → 0.90 × I_max | Medikal radyoterapi uyumlu |
| **%50 (FWHM)** | I = 0.50 × I_max → 0.50 × I_max (her iki kenar) | Yararlı alan genişliği tanımı |

**UI'da seçim:** Kullanıcı penumbra threshold'unu %10–%90, %20–%80, veya özel değer olarak seçebilmelidir. Varsayılan: %20–%80.

**Tipik kabul edilebilir değerler:**

| Kolimatör Tipi | Kabul Edilebilir Penumbra | Mükemmel |
|----------------|--------------------------|----------|
| Fan-beam (TIR) | < 10 mm (detektör düzleminde) | < 5 mm |
| Pencil-beam | < 3 mm | < 1 mm |
| Slit | < 5 mm | < 2 mm |

##### FR-3.4.2 Alan Homojenliği / Flatness (%)

**Tanım:** Yararlı ışın alanı (useful beam field) içindeki şiddet dağılımının düzgünlüğü.

**Hesaplama algoritması:**
```
1. Yararlı ışın alanını tanımla: %50 iletim (FWHM) sınırları içindeki bölge
2. Bu bölgenin %80'ini "düzlük değerlendirme alanı" (flattened region) olarak al
   (kenarlardan %10'ar hariç — penumbra etkisini dışlamak için)
3. Düzlük değerlendirme alanı içinde:
   I_max = max(I(x))
   I_min = min(I(x))
4. Flatness (%) = 100 × (I_max − I_min) / (I_max + I_min)
```

**Alternatif metrik — Uniformity Index:**
```
Uniformity (%) = 100 × (1 − (I_max − I_min) / I_mean)
```

**Tipik kabul edilebilir değerler:**

| Flatness | Durum |
|----------|-------|
| < 3% | Mükemmel — homojen alan |
| 3–10% | Kabul edilebilir |
| > 10% | Kötü — kolimatör geometrisi veya kaynak pozisyonu düzeltilmeli |

##### FR-3.4.3 Kaçak Radyasyon / Leakage (%)

**Tanım:** Kolimatör gövdesi (zırhlanmış bölge) üzerinden sızan radyasyonun, yararlı ışın şiddetine oranı.

**Hesaplama algoritması:**
```
1. Işın profilinde "zırhlanmış bölge"yi tanımla:
   - Yararlı alan sınırının (FWHM kenarı) dışındaki bölge
   - Penumbra geçiş bölgesi HARİÇ (penumbra bitiş noktasından itibaren)
2. Zırhlanmış bölgedeki iletim değerlerini al: I_leak(x)
3. Ortalama kaçak: Leakage_avg (%) = 100 × mean(I_leak) / I_primary
   burada I_primary = yararlı alan merkez şiddeti
4. Maksimum kaçak: Leakage_max (%) = 100 × max(I_leak) / I_primary
5. Her ikisi de raporlanır.
```

**Zırhlanmış bölge segmentasyonu (profil üzerinde):**
```
|←—— Zırhlanmış ——→|←Penumbra→|←—— Yararlı Alan ——→|←Penumbra→|←—— Zırhlanmış ——→|
                    x_20/x_10  x_80/x_90            x_80/x_90  x_20/x_10
```

**Tipik kabul edilebilir değerler (NCRP Report No. 151 / IEC 60601):**

| Leakage | Durum | Not |
|---------|-------|-----|
| < 0.1% | Mükemmel | Radyoterapi seviyesi (1/1000) |
| 0.1–1% | İyi | TIR kolimatörler için yeterli |
| 1–5% | Kabul edilebilir | Düşük güvenlik gereksinimleri için |
| > 5% | Yetersiz | Zırhlama kalınlığı artırılmalı |

> **Build-up etkisi:** Kaçak radyasyon hesabında build-up faktörü dahil ve hariç sonuçlar ayrı gösterilmelidir. Build-up dahil değer her zaman daha yüksektir ve konservatif tasarım için bu değer kullanılmalıdır.

##### FR-3.4.4 Kolimasyon Oranı (Collimation Ratio)

**Tanım:** Yararlı alan şiddetinin kaçak radyasyon şiddetine oranı. Kolimatörün "seçicilik" performansını gösterir.

**Hesaplama:**
```
CR = I_primary_mean / I_leakage_mean
```
Ayrıca dB cinsinden:
```
CR_dB = 10 × log₁₀(CR) = 10 × log₁₀(I_primary / I_leakage)
```

**Tipik kabul edilebilir değerler:**

| CR | CR (dB) | Durum |
|----|---------|-------|
| > 1000 | > 30 dB | Mükemmel |
| 100–1000 | 20–30 dB | İyi |
| 10–100 | 10–20 dB | Kabul edilebilir |
| < 10 | < 10 dB | Yetersiz |

##### FR-3.4.5 Scatter-to-Primary Ratio — SPR (Compton modülü aktifse)

**Tanım:** Detektör düzleminde saçılma kaynaklı şiddetin birincil ışın şiddetine oranı.

**Hesaplama:**
```
SPR(x) = I_scatter(x) / I_primary(x)
SPR_mean = mean(SPR(x))   (tüm detektör üzerinde)
SPR_max = max(SPR(x))
```

**Tipik değerler (kolimatör kalınlığına bağlı):**

| SPR | Durum |
|-----|-------|
| < 0.05 | Mükemmel — saçılma ihmal edilebilir |
| 0.05–0.20 | Kabul edilebilir |
| > 0.20 | Yüksek — kolimatör tasarımı iyileştirilmeli |

##### FR-3.4.6 Kullanıcı Arayüzünde Gösterim

- **FR-3.4.6.1:** Kalite metrikleri bir "Sonuç Kartı" (score card) olarak gösterilmelidir. Her metrik için: sayısal değer, birim, ve renk kodlu durum göstergesi (yeşil/sarı/kırmızı — yukarıdaki threshold'lara göre).
- **FR-3.4.6.2:** Kullanıcı, threshold değerlerini özelleştirebilmelidir (varsayılanlar yukarıdaki tablolardadır).
- **FR-3.4.6.3:** "Tümünü Geç" / "Bazıları Başarısız" özet gösterge metriklerin üst kısmında gösterilmelidir.

#### FR-3.5 Compton Saçılma Modülü

##### FR-3.5.1 Klein-Nishina Diferansiyel Kesit Hesabı

- **FR-3.5.1.1:** Seçili enerji seviyesinde Klein-Nishina diferansiyel tesir kesiti (dσ/dΩ) hesaplanmalı ve polar grafik olarak gösterilmelidir.
- **FR-3.5.1.2:** Grafik üzerinde şunlar gösterilmelidir:
  - Polar plot: saçılma açısı (0–180°) vs dσ/dΩ (cm²/sr/elektron)
  - Thomson saçılma (klasik limit, düşük enerji) kesik çizgi ile karşılaştırma
  - Öne saçılma (forward scattering) ve geriye saçılma (back scattering) bölgeleri renk kodlu
- **FR-3.5.1.3:** Enerji slider'ı değiştikçe Klein-Nishina dağılımı anlık güncellenmeli, böylece kullanıcı yüksek enerjide öne saçılma baskınlığını interaktif olarak görebilmelidir.
- **FR-3.5.1.4:** Her açı için saçılmış foton enerjisi ve geri sekme elektron enerjisi tooltip ile gösterilmelidir.
- **FR-3.5.1.5:** Toplam Klein-Nishina tesir kesiti (σ_KN) sayısal olarak gösterilmelidir:
  - Elektron başına (cm²/elektron)
  - Atom başına (cm²/atom) — Z ile çarpılmış
  - Lineer zayıflama katsayısına katkısı (cm⁻¹)

##### FR-3.5.2 Compton Saçılmış Foton Enerji Spektrumu

- **FR-3.5.2.1:** Seçili gelen foton enerjisinde, saçılma sonrası foton enerji dağılımı histogramı gösterilmelidir.
  - X ekseni: Saçılmış foton enerjisi (keV)
  - Y ekseni: Olasılık yoğunluğu (dσ/dE)
  - Compton kenarı (180° saçılma = minimum enerji) dikey çizgi ile işaretli
- **FR-3.5.2.2:** Aynı grafikte geri sekme elektron enerji spektrumu ayrı eğri olarak gösterilmelidir.
- **FR-3.5.2.3:** Birden fazla gelen foton enerjisi overlay olarak karşılaştırılabilmelidir.
- **FR-3.5.2.4:** Compton kenarı enerjisi ve ortalama saçılmış foton enerjisi sayısal olarak gösterilmelidir.

##### FR-3.5.3 Saçılma Açısı vs Enerji Kaybı Grafiği (İnteraktif)

- **FR-3.5.3.1:** İnteraktif bir grafik ile Compton saçılma kinematiği gösterilmelidir:
  - X ekseni: Saçılma açısı θ (0–180°)
  - Y1 ekseni (sol): Saçılmış foton enerjisi E' (keV)
  - Y2 ekseni (sağ): Geri sekme elektron enerjisi T (keV)
  - Her iki eğri aynı grafikte çift-eksenli olarak
- **FR-3.5.3.2:** Grafik üzerinde interaktif crosshair: kullanıcı fareyi herhangi bir açıya getirdiğinde ilgili E', T, enerji kaybı oranı (ΔE/E₀) ve dalga boyu kayması (Δλ) gösterilmelidir.
- **FR-3.5.3.3:** Gelen foton enerjisi (E₀) bir slider ile değiştirilebilmeli ve grafik anlık güncellenmelidir.
- **FR-3.5.3.4:** Önceden tanımlı enerji presetleri (80 keV, 160 keV, 320 keV, 1 MeV, 3.5 MeV, 6 MeV) tek tıkla seçilebilmelidir.
- **FR-3.5.3.5:** Dalga boyu formunda Compton kayması da gösterilmelidir: Δλ = λ_C(1 − cosθ) burada λ_C = 0.02426 Å (Compton dalga boyu).

##### FR-3.5.4 Kolimatör Geometrisinde Saçılmış Foton Takibi (Scatter Ray-Tracing)

- **FR-3.5.4.1:** Birincil ray-tracing simülasyonuna ek olarak, kolimatör malzemesinde Compton saçılması ile üretilen ikincil fotonlar takip edilmelidir.
- **FR-3.5.4.2:** Her birincil ışın, kolimatör malzemesine girdiğinde belirli aralıklarla (step-size ile, varsayılan: 1mm) etkileşim noktaları örneklenir. Her etkileşim noktasında:
  1. Compton etkileşim olasılığı hesaplanır: P_compton = (σ_compton / σ_total) × (1 − e^(−μ·Δx))
  2. Etkileşim gerçekleşirse, Klein-Nishina dağılımına göre bir saçılma açısı (θ) örneklenir
  3. Saçılmış foton enerjisi Compton formülü ile hesaplanır
  4. Saçılmış foton yeni yönünde takip edilir (kolimatör içinden çıkana kadar veya enerji kesim değerinin altına düşene kadar)
  5. Saçılmış foton detektöre ulaşırsa, detektör profili üzerindeki katkısı kaydedilir
- **FR-3.5.4.3:** Saçılma derecesi ayarlanabilir olmalıdır:
  - 1. derece saçılma (tek saçılma) — varsayılan, hızlı
  - 2. derece saçılma (çift saçılma) — daha doğru ama yavaş
  - Kullanıcı tarafından seçilebilir (varsayılan: 1)
- **FR-3.5.4.4:** Canvas üzerinde saçılma etkileşim noktaları ve saçılmış ışın yolları görselleştirilebilmelidir:
  - Birincil ışınlar: düz çizgi (mevcut)
  - Saçılma etkileşim noktaları: küçük daireler (turuncu)
  - Saçılmış foton yolları: kesik çizgi (kırmızı, yarı-saydam)
  - Detektöre ulaşan saçılmış fotonlar: vurgulu (parlak kırmızı)
  - Bu görselleştirme performans nedeniyle sadece düşük ışın sayısında (<100) etkinleşmelidir
- **FR-3.5.4.5:** Detektör düzleminde Scatter-to-Primary Ratio (SPR) profili ayrı bir grafik olarak gösterilmelidir:
  - X ekseni: Detektör pozisyonu (mm)
  - Y ekseni: SPR (oran, birimsiz)
  - SPR = saçılma kaynaklı şiddet / birincil ışın şiddeti
- **FR-3.5.4.6:** Scatter ray-tracing sonuçları toplu sonuçlara dahil edilmelidir:
  - Toplam saçılma fraksiyonu (%)
  - Saçılma kaynaklı detektör gürültüsü tahmini
  - Kolimatörden kaçan saçılmış fotonların yüzdesi ve ortalama enerjisi

---

### 4.4 MODÜL 4 — Rapor ve Dışa Aktarım

#### FR-4.1 PDF Rapor

- **FR-4.1.1:** "Rapor Oluştur" butonu ile kapsamlı PDF rapor üretilmelidir. Kullanıcı dahil edilecek bölümleri seçebilmelidir.
- **FR-4.1.2:** Rapor ReportLab kütüphanesi ile oluşturulmalıdır. Sayfa boyutu A4, kenar boşlukları 20mm.
- **FR-4.1.3:** Rapor dosya adı otomatik oluşturulur: `CDT_Report_{tasarım_adı}_{tarih}.pdf`

##### FR-4.1.4 PDF Rapor İçerik Yapısı

Rapor aşağıdaki bölümlerden oluşur. Kullanıcı her bölümü dahil/hariç seçebilir:

**Sayfa 1 — Kapak Sayfası**
- Rapor başlığı: "Kolimatör Tasarım Raporu"
- Tasarım adı ve açıklaması
- Kolimatör tipi (Fan-beam / Pencil-beam / Slit)
- Rapor tarihi ve saat
- Uygulama versiyonu
- Uygulama logosu (varsa)

**Bölüm A — Geometri Özeti (1-2 sayfa)**
- Canvas görüntüsü (yüksek çözünürlük PNG, raporun 1/2 sayfa genişliğinde)
- Boyut etiketleri canvas görüntüsü üzerinde
- Genel parametreler tablosu:

| Parametre | Değer | Birim |
|-----------|-------|-------|
| Kolimatör tipi | Fan-beam | — |
| Dış genişlik | 200 | mm |
| Dış yükseklik | 300 | mm |
| Açıklık genişliği | 5.0 | mm |
| Yelpaze açısı | 30 | derece |
| Kaynak-Detektör mesafesi | 1000 | mm |
| Odak noktası boyutu | 1.0 | mm |

**Bölüm B — Katman Yapısı Tablosu (1 sayfa)**
- Dıştan içe sıralı katman tablosu:

| Sıra | Malzeme | Kalınlık (mm) | Yoğunluk (g/cm³) | Amaç | Renk |
|------|---------|---------------|-------------------|------|------|
| 1 | Pb | 50.0 | 11.35 | Birincil zırhlama | ■ |
| 2 | SS304 | 10.0 | 8.00 | Yapısal | ■ |
| 3 | W | 20.0 | 19.30 | İkincil zırhlama | ■ |

- Toplam kalınlık, toplam ağırlık (kg/m — birim uzunluk başına) hesaplanarak gösterilir.

**Bölüm C — Zayıflama Analizi (2-3 sayfa)**
- Enerji taraması sonuç tablosu (seçili enerji noktaları):

| Enerji (keV) | μ/ρ total (cm²/g) | μ (cm⁻¹) | İletim (%) | Zayıflama (dB) | HVL (mm) | TVL (mm) |
|--------------|---------------------|-----------|------------|----------------|----------|----------|

- Her katman için ayrı zayıflama katkısı tablosu:

| Katman | Malzeme | Kalınlık (mm) | μx (mfp) | Katman İletimi (%) |
|--------|---------|---------------|----------|---------------------|

- **İletim vs Enerji grafiği** (log-log, tüm katmanlar birleşik ve ayrı ayrı)
- **μ/ρ vs Enerji grafiği** (log-log, kullanılan malzemeler, fotoelektrik/Compton/çift üretimi alt bileşenleri)
- **İletim vs Kalınlık grafiği** (seçili enerji noktaları için)

**Bölüm D — Build-up Analizi (1 sayfa)**
- Build-up dahil ve hariç sonuçların yan yana karşılaştırma tablosu:

| Enerji (keV) | İletim (build-up YOK) (%) | Build-up Faktörü (B) | İletim (build-up DAHİL) (%) | Fark Oranı |
|--------------|---------------------------|----------------------|------------------------------|------------|

- Kullanılan build-up yöntemi (GP veya Taylor) belirtilir.
- Build-up faktörü vs enerji grafiği (seçili kalınlıklar için)

**Bölüm E — Işın Profili (1-2 sayfa)**
- Işın profili grafiği (X: pozisyon mm, Y: normalize şiddet):
  - Yararlı alan, penumbra ve zırhlanmış bölgeler renk kodlu
  - Build-up dahil/hariç overlay (isteğe bağlı)
- Çoklu enerji karşılaştırma grafiği (seçilmişse)
- Profil sayısal verileri tablosu (her 10. nokta veya kullanıcı seçimi)

**Bölüm F — Kalite Metrikleri (1 sayfa)**
- Metrik sonuç kartı (score card formatında):

| Metrik | Değer | Birim | Durum |
|--------|-------|-------|-------|
| Penumbra (sol) | 4.2 | mm | ✅ İyi |
| Penumbra (sağ) | 4.5 | mm | ✅ İyi |
| Alan homojenliği (Flatness) | 2.1 | % | ✅ Mükemmel |
| Kaçak radyasyon (ortalama) | 0.032 | % | ✅ Mükemmel |
| Kaçak radyasyon (maksimum) | 0.089 | % | ✅ Mükemmel |
| Kolimasyon oranı | 3125 | — | ✅ > 1000 |
| Kolimasyon oranı | 34.9 | dB | ✅ > 30 dB |
| SPR (ortalama) | 0.03 | — | ✅ < 0.05 |

- Durum göstergeleri: ✅ Kabul, ⚠️ Dikkat, ❌ Yetersiz (Bölüm FR-3.4 threshold'larına göre)
- Kullanılan penumbra tanımı (%20–%80 veya %10–%90) belirtilir.

**Bölüm G — Compton Saçılma Analizi (1-2 sayfa, isteğe bağlı)**
- Klein-Nishina polar plot görüntüsü (seçili enerji)
- Saçılmış foton enerji spektrumu grafiği
- SPR profil grafiği (detektör boyunca)
- Toplam saçılma fraksiyonu ve ortalama saçılmış foton enerjisi

**Bölüm H — Model Varsayımları ve Uyarılar (1 sayfa)**
- Kullanılan fizik modeli özeti (Beer-Lambert + build-up + tek saçılma)
- Bölüm 8.1.2'deki LINAC sınırlamaları (MeV modundaysa)
- Bölüm 8.1.3'teki scatter sınırlamaları (saçılma aktifse)
- "Bu sonuçlar ön-boyutlandırma ve karşılaştırma amaçlıdır" uyarısı

**Bölüm I — Doğrulama Özeti (opsiyonel, 1 sayfa)**
- Son çalıştırılan benchmark test sonuçları (Bölüm 11 BM test'leri)
- Geçen/kalan test sayısı
- Doğrulama tarihi

**Son Sayfa — Alt Bilgi**
- "Bu rapor Collimator Design Tool v{X.Y} ile oluşturulmuştur."
- Rapor oluşturma tarihi ve saati
- Sayfa numaraları (X / toplam)

##### FR-4.1.5 Rapor Oluşturma Diyaloğu

- Kullanıcı dahil edilecek bölümleri checkbox ile seçer (varsayılan: A-F dahil, G-I isteğe bağlı).
- Rapor enerji aralığı ve nokta sayısı seçilir.
- "Önizle" butonu ile tahmini sayfa sayısı gösterilir.
- "Oluştur" butonu ile PDF üretimi başlar (QThread üzerinde, ilerleme çubuğu ile).
- Oluşturulan PDF, dosya diyaloğu ile kayıt yeri seçilir.

#### FR-4.2 CSV Dışa Aktarım

- **FR-4.2.1:** Hesaplama sonuçları CSV olarak dışa aktarılabilmelidir.
- **FR-4.2.2:** CSV formatı: enerji (keV), malzeme, kalınlık (mm), μ/ρ, μ, HVL, TVL, iletim (%), zayıflama (dB).

#### FR-4.3 Geometri Dışa Aktarım

- **FR-4.3.1:** Kolimatör geometrisi JSON dosyası olarak dışa aktarılıp tekrar içe aktarılabilmelidir.
- **FR-4.3.2:** Canvas görüntüsü PNG/SVG olarak dışa aktarılabilmelidir.

---

## 5. Servis Katmanı Arayüzleri (Python Sınıfları)

> Not: Masaüstü uygulamada REST API yoktur. İş mantığı doğrudan Python sınıfları üzerinden çağrılır. UI (PyQt6) → Servis → Core katmanı şeklinde katmanlı mimari kullanılır. Ağır hesaplamalar QThread worker'lar aracılığıyla arka planda çalıştırılır.

### 5.1 MaterialService

```python
# app/core/material_database.py
class MaterialService:
    def get_all_materials(self) -> list[Material]: ...
    def get_material(self, material_id: str) -> Material: ...
    def get_attenuation_data(self, material_id: str,
                             min_energy_keV: float = 1.0,
                             max_energy_keV: float = 20000.0) -> list[AttenuationDataPoint]: ...
    def get_mu_rho(self, material_id: str, energy_keV: float) -> float: ...
    def get_mu_rho_alloy(self, composition: list[Composition], energy_keV: float) -> float: ...
```

### 5.2 PhysicsEngine

```python
# app/core/physics_engine.py
class PhysicsEngine:
    def calculate_attenuation(self, layers: list[CollimatorLayer],
                              energy_keV: float,
                              include_buildup: bool = False) -> AttenuationResult: ...
    def energy_sweep(self, layers: list[CollimatorLayer],
                     min_keV: float, max_keV: float, steps: int,
                     include_buildup: bool = False) -> list[AttenuationResult]: ...
    def calculate_hvl_tvl(self, material_id: str, energy_keV: float) -> HvlTvlResult: ...
    def thickness_sweep(self, material_id: str, energy_keV: float,
                        max_thickness_mm: float, steps: int) -> list[ThicknessSweepPoint]: ...
```

### 5.3 BeamSimulation

```python
# app/core/beam_simulation.py
class BeamSimulation:
    def calculate_beam_profile(self, geometry: CollimatorGeometry,
                               energy_keV: float, num_rays: int,
                               include_buildup: bool = True,
                               compton_config: ComptonConfig = None,
                               progress_callback: callable = None
                               ) -> SimulationResult: ...
    def compare_energies(self, geometry: CollimatorGeometry,
                         energies_keV: list[float], num_rays: int
                         ) -> dict[float, SimulationResult]: ...
```

### 5.4 ComptonEngine

```python
# app/core/compton_engine.py
class ComptonEngine:
    def klein_nishina_distribution(self, energy_keV: float,
                                   angular_bins: int = 180
                                   ) -> KleinNishinaResult: ...
    def scattered_energy_spectrum(self, energy_keV: float,
                                  num_bins: int = 100) -> ComptonSpectrumResult: ...
    def angle_energy_map(self, energy_keV: float,
                         angular_steps: int = 361) -> AngleEnergyMapResult: ...
    def cross_section_vs_energy(self, min_keV: float, max_keV: float,
                                steps: int) -> CrossSectionResult: ...
    def material_compton_fractions(self, material_ids: list[str],
                                   min_keV: float, max_keV: float,
                                   steps: int) -> MaterialComparisonResult: ...

# app/core/scatter_tracer.py
class ScatterTracer:
    def scatter_simulation(self, geometry: CollimatorGeometry,
                           energy_keV: float, num_primary_rays: int,
                           config: ComptonConfig,
                           step_size_mm: float = 1.0,
                           progress_callback: callable = None
                           ) -> ScatterSimulationResult: ...
```

### 5.5 DesignRepository

```python
# app/database/design_repository.py
class DesignRepository:
    # --- Tasarım CRUD ---
    def list_designs(self, filter_type: str = None,
                     filter_tag: str = None,
                     favorites_only: bool = False) -> list[DesignSummary]: ...
    def save_design(self, geometry: CollimatorGeometry, name: str,
                    description: str = "", tags: list[str] = None) -> str: ...
    def load_design(self, design_id: str) -> CollimatorGeometry: ...
    def update_design(self, design_id: str, geometry: CollimatorGeometry,
                      change_note: str = None) -> None: ...
    """Her update çağrısında otomatik olarak design_versions tablosuna yeni versiyon eklenir."""
    def delete_design(self, design_id: str) -> None: ...
    def toggle_favorite(self, design_id: str) -> None: ...
    def update_thumbnail(self, design_id: str, thumbnail: bytes) -> None: ...

    # --- Versiyon Geçmişi ---
    def get_version_history(self, design_id: str) -> list[DesignVersion]: ...
    def load_version(self, design_id: str, version_number: int) -> CollimatorGeometry: ...
    def restore_version(self, design_id: str, version_number: int) -> None: ...
    """Belirtilen versiyonu aktif tasarım olarak geri yükler (yeni versiyon olarak)."""

    # --- Simülasyon Sonuçları ---
    def save_simulation_result(self, design_id: str,
                               config: SimulationConfig,
                               result: SimulationResult,
                               name: str = None) -> str: ...
    def list_simulation_results(self, design_id: str) -> list[SimulationSummary]: ...
    def load_simulation_result(self, simulation_id: str) -> SimulationResult: ...
    def delete_simulation_result(self, simulation_id: str) -> None: ...

    # --- Hesaplama Sonuçları ---
    def save_calculation_result(self, design_id: str,
                                calc_type: str, input_data: dict,
                                result_data: dict) -> str: ...
    def list_calculation_results(self, design_id: str) -> list[dict]: ...

    # --- Notlar ---
    def add_note(self, parent_type: str, parent_id: str, content: str) -> str: ...
    def get_notes(self, parent_type: str, parent_id: str) -> list[dict]: ...
    def delete_note(self, note_id: str) -> None: ...

    # --- Proje Dosyası (.cdt) ---
    def export_project_file(self, design_id: str, output_path: str) -> None: ...
    """Tasarımı, tüm versiyonları, simülasyon sonuçlarını ve notları
    tek bir .cdt (JSON+ZIP) dosyasına paketler."""
    def import_project_file(self, input_path: str) -> str: ...
    """Bir .cdt dosyasından tasarımı ve ilişkili verileri içe aktarır."""

    # --- Uygulama Ayarları ---
    def get_setting(self, key: str, default: str = None) -> str: ...
    def set_setting(self, key: str, value: str) -> None: ...
    def get_recent_designs(self, limit: int = 10) -> list[DesignSummary]: ...
```

### 5.6 ExportService

```python
# app/export/
class PdfReportExporter:
    def generate_report(self, geometry: CollimatorGeometry,
                        simulation_result: SimulationResult,
                        output_path: str,
                        include_sections: list[str] = None) -> None: ...

class CsvExporter:
    def export_attenuation(self, results: list[AttenuationResult], output_path: str) -> None: ...
    def export_beam_profile(self, result: SimulationResult, output_path: str) -> None: ...

class ImageExporter:
    def export_canvas(self, scene: 'QGraphicsScene', output_path: str,
                      format: str = "png") -> None: ...

class JsonExporter:
    def export_geometry(self, geometry: CollimatorGeometry, output_path: str) -> None: ...
    def import_geometry(self, input_path: str) -> CollimatorGeometry: ...
```

### 5.7 Arka Plan İşlem Yönetimi (QThread Workers)

```python
# app/workers/simulation_worker.py
from PyQt6.QtCore import QThread, pyqtSignal

class SimulationWorker(QThread):
    progress = pyqtSignal(int)            # İlerleme yüzdesi (0-100)
    result_ready = pyqtSignal(object)     # SimulationResult
    error = pyqtSignal(str)               # Hata mesajı

    def __init__(self, geometry, energy_keV, num_rays, config): ...
    def run(self): ...
    def cancel(self): ...

class ScatterWorker(QThread):
    progress = pyqtSignal(int)
    scatter_point = pyqtSignal(object)    # Anlık scatter noktası (canvas'a çiz)
    result_ready = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, geometry, energy_keV, compton_config): ...
    def run(self): ...
    def cancel(self): ...
```

> **Önemli:** Tüm hesaplama yoğun işlemler (simülasyon, scatter ray-tracing, enerji taraması) QThread worker'lar üzerinden çalışmalıdır. Ana UI thread'i asla bloklamamalıdır. Worker'lar `progress` sinyali ile ilerleme çubuğunu günceller, `result_ready` sinyali ile sonucu UI'a iletir.

## 6. UI/UX Gereksinimleri

### 6.1 Genel Arayüz Düzeni

```
┌─────────────────────────────────────────────────────────────────────┐
│  ÜSTMENU (Toolbar)                                                  │
│  [Dosya ▼] [Kolimatör Tipi ▼] [Enerji: ████░░ 160 kVp] [Simüle ▶] │
├────────────┬───────────────────────────────────┬────────────────────┤
│ SOL PANEL  │        MERKEZ ALAN                │   SAĞ PANEL       │
│            │                                   │                    │
│ Malzeme    │   ┌───────────────────────────┐   │  Katmanlar         │
│ Listesi    │   │                           │   │  ┌──────────────┐ │
│            │   │    KOLİMATÖR CANVAS       │   │  │ 1. W  │ 5mm │ │
│ [Pb ■]     │   │    (İnteraktif 2D Çizim)  │   │  │ 2. Pb │ 20mm│ │
│ [W  ■]     │   │                           │   │  │ 3. SS │ 3mm │ │
│ [SS ■]     │   │    Kaynak ★               │   │  └──────────────┘ │
│ [Bi ■]     │   │      \ | /                │   │  [+ Katman Ekle]  │
│ [Al ■]     │   │    ┌─┤ ├─┐               │   │                    │
│ [Cu ■]     │   │    │ │ │ │  Kolimatör     │   │  Parametreler      │
│ [Br ■]     │   │    │ │ │ │               │   │  ┌──────────────┐ │
│            │   │    └─┤ ├─┘               │   │  │ Genişlik: mm │ │
│ Malzeme    │   │      Detektör ━━━         │   │  │ Yükseklik:mm │ │
│ Detayı     │   │                           │   │  │ Açıklık: mm  │ │
│ ┌────────┐ │   └───────────────────────────┘   │  │ SDD: mm      │ │
│ │ μ/ρ    │ │                                   │  └──────────────┘ │
│ │ grafiği│ │                                   │                    │
│ └────────┘ │                                   │  Hızlı Sonuçlar   │
│            │                                   │  ┌──────────────┐ │
│            │                                   │  │ İletim: %    │ │
│            │                                   │  │ HVL: mm      │ │
│            │                                   │  │ TVL: mm      │ │
│            │                                   │  │ Kaçak: %     │ │
│            │                                   │  └──────────────┘ │
├────────────┴───────────────────────────────────┴────────────────────┤
│  ALT PANEL (Tab'lı grafik alanı)                                    │
│  [Işın Profili] [μ/ρ Karşılaştırma] [HVL/TVL] [İletim vs Kalınlık] │
│  [Compton Analiz] [Klein-Nishina] [SPR Profili]                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                     GRAFİK ALANI                                ││
│  │              (Seçili tab'a göre değişir)                        ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Tasarım Dili

- **Tema:** Koyu tema (dark mode) — QSS (Qt Style Sheets) ile uygulanır. `app/ui/styles/dark_theme.qss` dosyasından yüklenir.
- **Renk paleti:** Koyu arka plan (#0F172A), panel arka planları (#1E293B), vurgu rengi (#3B82F6 — mavi), uyarı (#F59E0B — amber), hata (#EF4444 — kırmızı). Renkler `app/ui/styles/colors.py` içinde sabit olarak tanımlanır.
- **Tipografi:** Sistem monospace fontu (JetBrains Mono tercih edilir, yoksa Consolas/Menlo fallback) sayısal değerler için; sistem UI fontu genel metin için.
- **Canvas stili:** QGraphicsScene koyu arka plan, parlak ışın yolu çizgileri, malzeme katmanları QBrush ile ilgili renk kodlarıyla.
- **Widget stili:** QSS ile özelleştirilmiş QGroupBox, QPushButton, QSlider, QTableWidget bileşenleri. Native hissiyat korunarak koyu tema uygulanır.

### 6.3 Pencere Yönetimi

- Minimum pencere boyutu: 1280×800 piksel.
- Sol ve sağ paneller QDockWidget olarak uygulanmalıdır — sürüklenebilir, daraltılabilir, yüzer (floating) yapılabilir.
- Alt grafik paneli QSplitter ile yüksekliği ayarlanabilir olmalıdır.
- Pencere düzeni (panel pozisyonları, boyutları) QSettings ile kaydedilmeli ve sonraki açılışta geri yüklenmelidir.
- Tam ekran modu (F11) desteklenmelidir.
- Canvas alanı her zaman merkez widget olarak kalmalıdır.

---

## 7. Fizik Motoru Detayları

### 7.1 NIST XCOM Veri Entegrasyonu

Fizik motoru, NIST XCOM veritabanından alınan kütle zayıflama katsayılarını kullanır. Veri formatı:

```json
{
  "material_id": "Pb",
  "data_source": "NIST XCOM",
  "energy_range_keV": [1, 20000],
  "data_points": [
    {
      "energy_keV": 1.0,
      "total_with_coherent": 5753.0,
      "total_without_coherent": 5621.0,
      "photoelectric": 5612.0,
      "compton": 0.0862,
      "pair_nuclear": 0.0,
      "pair_electron": 0.0
    },
    // ... daha fazla veri noktası
  ]
}
```

Backend, iki veri noktası arasındaki enerji değerleri için log-log interpolasyon uygulamalıdır:

```python
# Log-log interpolasyon
import numpy as np

def interpolate_mu_rho(energy_keV, data_points):
    log_energies = np.log(data_points["energy_keV"])
    log_mu_rho = np.log(data_points["mass_attenuation"])
    log_E = np.log(energy_keV)
    return np.exp(np.interp(log_E, log_energies, log_mu_rho))
```

### 7.2 kVp Spektrum Modeli

80–300 kVp aralığında X-ray tüpü spektrumu Kramers yaklaşımı ile modellenebilir:

```
Φ(E) ∝ Z × (E_max − E) / E
```

burada E_max = kVp × 1 keV, Z = anot atom numarası (W anot için Z=74).

Basitleştirilmiş ortalama enerji yaklaşımı:
```
E_avg ≈ kVp / 3    (filtresiz)
E_avg ≈ kVp / 2.5  (Al filtreli, tipik)
```

Kullanıcı arayüzünde iki seçenek sunulmalıdır:
1. **Monoenerjik mod:** E = kVp/3 veya kullanıcı tanımlı
2. **Spektrum modu:** Kramers modeli + Al/Cu filtreleme (isteğe bağlı, gelişmiş)

### 7.3 MeV Bremsstrahlung Spektrum Modeli

LINAC kaynakları için basitleştirilmiş spektrum:
- Ortalama enerji ≈ E_endpoint / 3
- Monoenerjik yaklaşım yeterlidir (ilk sürüm için)

### 7.4 Build-up Faktörü

Geniş ışın (broad beam) koşullarında saçılmış fotonların katkısı build-up faktörü ile modellenir. Uygulama **iki formülasyon** desteklemelidir:

#### 7.4.1 Geometric Progression (GP) Formülü (Birincil — Önerilen)

GP formülü, ANSI/ANS-6.4.3 verilerini %birkaç hata ile yeniden üretir ve Taylor'dan daha doğrudur:

```
B(E, x) = 1 + (b − 1)(Kˣ − 1) / (K − 1)    K ≠ 1
B(E, x) = 1 + (b − 1)x                        K = 1

K(x) = c·xᵃ + d·[tanh(x/Xk − 2) − tanh(−2)] / [1 − tanh(−2)]
```

5 fitting parametresi: **b, c, a, Xk, d** — her malzeme ve enerji noktası için tablo halinde saklanır.

#### 7.4.2 Taylor İki-Terimli Üstel Formül

```
B(E, μx) = A₁ × e^(−α₁·μx) + (1 − A₁) × e^(−α₂·μx)
```

3 fitting parametresi: **A₁, α₁, α₂** — daha basit, hızlı hesaplama.

#### 7.4.3 Veri Kaynağı: `buildup_coefficients.json`

Build-up katsayıları `buildup_coefficients.json` dosyasında saklanır. Bu dosya şunları içerir:

| İçerik | Açıklama |
|--------|----------|
| GP parametreleri (b, c, a, Xk, d) | Pb, W, Fe, Al, Cu, Bi için 15-23 enerji noktasında (0.015–15 MeV) |
| Taylor parametreleri (A₁, α₁, α₂) | Pb, W, Fe, Al için 13-17 enerji noktasında |
| EBF tabloları | Her malzeme için 1–40 mfp aralığında doğrudan buildup faktör değerleri |
| Alaşım karışım kuralları | SS304, SS316, Bronze için Zeq bazlı interpolasyon talimatları |
| Kolimatör geometri düzeltmeleri | Dar ışın vs geniş ışın geometri düzeltme notları |

**Kaynak referanslar:**
- ANSI/ANS-6.4.3-1991 (temel veri seti)
- WAPD-1628 (Taylor parametreleri, Shure & Wallace, 1988)
- ORNL/RSIC-49/R1 DLC-129 (GP katsayı dosyaları)
- Atak et al. (2019) — Pb, Fe, W MCNP doğrulaması
- Kiyani et al. (2013) — MCNP4C ile doğrulanmış EBF tabloları
- EXABCal (Olarinoye, 2019) — GP fitting Python implementasyonu

#### 7.4.4 Çok Katmanlı Zırhlama İçin Build-up

Çok katmanlı kolimatör tasarımlarında efektif build-up faktörü için üç yöntem desteklenmelidir:

1. **Eşdeğer malzeme yöntemi:** Kompozitin Zeq'i hesaplanıp tek malzeme gibi değerlendirilir (±15-20% doğruluk)
2. **Son malzeme yöntemi:** En dıştaki malzemenin build-up faktörü toplam mfp ile kullanılır (konservatif)
3. **Kalos formülü:** `B_toplam ≈ B₁(μ₁x₁) × B₂(μ₂x₂)` — iki katmanlı zırh için ±10-15% doğruluk

#### 7.4.5 Kolimatör Geometri Düzeltmesi

ANSI/ANS-6.4.3 verileri sonsuz homojen ortamda nokta izotropik kaynak içindir. Kolimatör dar-ışın geometrisinde build-up önemli ölçüde düşüktür:

- **Açıklıktan geçen birincil ışın:** B ≈ 1.0 (build-up ihmal edilebilir)
- **Zırhlamadan sızan radyasyon:** Tam build-up faktörü kullanılır (konservatif tahmin)
- **Geometri düzeltme faktörü:** 0.3–0.7 aralığında, kolimasyon oranına bağlı olarak uygulanabilir

### 7.5 Geometrik Ray-Tracing Algoritması

```python
# Pseudocode: Işın profili hesaplama
def calculate_beam_profile(geometry, energy_keV, num_rays):
    results = []
    source = geometry.source.position
    
    for i in range(num_rays):
        angle = compute_ray_angle(i, num_rays, geometry)
        ray = Ray(origin=source, angle=angle)
        
        # Kolimatör geometrisi ile kesişim testi
        intersections = ray_collimator_intersection(ray, geometry.body)
        
        if passes_through_aperture(ray, geometry.body.aperture):
            # Açıklıktan geçen ışın — sadece hava
            transmission = 1.0
        else:
            # Kolimatör gövdesinden geçen ışın
            total_mu_x = 0.0
            for intersection in intersections:
                layer = find_layer(intersection, geometry.body.layers)
                mu = get_linear_attenuation(layer.material_id, energy_keV)
                path_length = intersection.exit_point - intersection.entry_point
                total_mu_x += mu * path_length
            
            transmission = math.exp(-total_mu_x)
            
            if include_buildup:
                B = calculate_buildup_factor(energy_keV, total_mu_x, primary_material)
                transmission *= B
        
        detector_position = compute_detector_position(ray, geometry.detector)
        results.append({
            "angle": angle,
            "detector_position": detector_position,
            "transmission": transmission
        })
    
    return results
```

### 7.6 Compton Saçılma Fizik Motoru

#### 7.6.1 Compton Saçılma Kinematiği

Compton saçılmada foton-elektron etkileşimi sonucu fotonun enerjisi ve yönü değişir.

**Saçılmış foton enerjisi (Compton formülü):**
```
E' = E₀ / [1 + (E₀ / m_e c²)(1 − cosθ)]
```
burada:
- E₀ = gelen foton enerjisi (keV)
- E' = saçılmış foton enerjisi (keV)
- θ = saçılma açısı (0–180°)
- m_e c² = 511 keV (elektron durağan kütle enerjisi)

**Geri sekme elektron enerjisi:**
```
T = E₀ − E' = E₀ × [α(1 − cosθ)] / [1 + α(1 − cosθ)]
```
burada α = E₀ / (m_e c²) = E₀ / 511 keV

**Compton kenarı (180° geriye saçılma):**
```
E'_min = E₀ / (1 + 2α)
T_max = E₀ × 2α / (1 + 2α)
```

**Dalga boyu kayması:**
```
Δλ = λ_C × (1 − cosθ)
```
burada λ_C = h/(m_e c) = 0.02426 Å (Compton dalga boyu)

#### 7.6.2 Klein-Nishina Diferansiyel Tesir Kesiti

Klein-Nishina formülü, Compton saçılmanın açısal dağılımını tam kuantum elektrodinamik çerçevesinde verir:

```
dσ/dΩ = (r₀²/2) × (E'/E₀)² × [E'/E₀ + E₀/E' − sin²θ]
```

Alternatif form (α parametresi ile):
```
dσ/dΩ = (r₀²/2) × [1/(1 + α(1−cosθ))]² × [1 + cos²θ + α²(1−cosθ)² / (1 + α(1−cosθ))]
```

burada:
- r₀ = klasik elektron yarıçapı = 2.818 × 10⁻¹³ cm
- α = E₀ / 511 keV

**Thomson limiti (düşük enerji, α → 0):**
```
dσ/dΩ |_Thomson = (r₀²/2) × (1 + cos²θ)
```

#### 7.6.3 Toplam Klein-Nishina Tesir Kesiti

Toplam Compton tesir kesiti (elektron başına), dσ/dΩ'nın tüm katı açıya integre edilmesiyle elde edilir:

```
σ_KN = 2π r₀² { [(1+α)/α²] × [2(1+α)/(1+2α) − ln(1+2α)/α] + ln(1+2α)/(2α) − (1+3α)/(1+2α)² }
```

**Pratik birimler:**
- σ_KN birimi: cm²/elektron
- Atom başına: σ_atom = Z × σ_KN (Z = atom numarası)
- Lineer zayıflama katsayısına katkı: μ_compton = (N_A × ρ / A) × Z × σ_KN

burada N_A = Avogadro sayısı, ρ = yoğunluk, A = atom ağırlığı.

**Alaşımlar için:**
```
μ_compton_alaşım = ρ × N_A × Σ (wᵢ × Zᵢ × σ_KN(E) / Aᵢ)
```

#### 7.6.4 Klein-Nishina Açısal Örnekleme (Scatter Ray-Tracing İçin)

Scatter ray-tracing simülasyonunda, her etkileşim noktasında Klein-Nishina dağılımına göre bir saçılma açısı örneklenmelidir. Kahn algoritması (rejection sampling) kullanılabilir:

```python
# Pseudocode: Klein-Nishina açısal örnekleme (Kahn yöntemi)
def sample_compton_angle(energy_keV):
    alpha = energy_keV / 511.0
    
    while True:
        # Üç rastgele sayı üret
        r1, r2, r3 = random(), random(), random()
        
        if r1 <= (1 + 2*alpha) / (9 + 2*alpha):
            # Düşük enerji dalı
            xi = 1 + 2*alpha*r2
            if r3 <= 4 * (1/xi - 1/xi**2):
                break
        else:
            # Yüksek enerji dalı
            xi = (1 + 2*alpha) / (1 + 2*alpha*r2)
            cos_theta = 1 - (xi - 1) / alpha
            if r3 <= 0.5 * (cos_theta**2 + 1/xi):
                break
    
    cos_theta = 1 - (xi - 1) / alpha
    theta = math.acos(cos_theta)
    
    # Saçılmış foton enerjisi
    E_scattered = energy_keV / xi
    
    # Azimut açısı (izotropik)
    phi = 2 * math.pi * random()
    
    return theta, phi, E_scattered
```

#### 7.6.5 Scatter Ray-Tracing Algoritması

```python
# Pseudocode: Compton saçılma dahil ışın profili hesaplama
def calculate_beam_profile_with_scatter(geometry, energy_keV, num_rays, compton_config):
    primary_results = []
    scatter_results = []
    
    source = geometry.source.position
    
    for i in range(num_rays):
        angle = compute_ray_angle(i, num_rays, geometry)
        ray = Ray(origin=source, angle=angle, energy=energy_keV)
        
        intersections = ray_collimator_intersection(ray, geometry.body)
        
        if passes_through_aperture(ray, geometry.body.aperture):
            primary_results.append({"position": ..., "intensity": 1.0, "type": "primary"})
        else:
            # Birincil zayıflama hesabı (mevcut)
            total_mu_x = 0.0
            
            for intersection in intersections:
                layer = find_layer(intersection, geometry.body.layers)
                material = get_material(layer.material_id)
                mu_total = get_linear_attenuation(material, energy_keV)
                mu_compton = get_compton_attenuation(material, energy_keV)
                path_length = intersection.path_length  # cm
                total_mu_x += mu_total * path_length
                
                if compton_config.enabled:
                    # Saçılma etkileşim noktalarını örnekle
                    step_size = 0.1  # cm (1mm adım)
                    position = intersection.entry_point
                    remaining_energy = energy_keV
                    
                    while position < intersection.exit_point:
                        # Compton etkileşim olasılığı
                        P_interact = 1 - math.exp(-mu_total * step_size)
                        P_compton = (mu_compton / mu_total) * P_interact
                        
                        if random() < P_compton:
                            # Etkileşim gerçekleşti
                            theta, phi, E_scattered = sample_compton_angle(remaining_energy)
                            
                            if E_scattered > compton_config.min_energy_cutoff_keV:
                                # Saçılmış fotonu takip et
                                scatter_ray = create_scatter_ray(
                                    origin=position,
                                    original_direction=ray.direction,
                                    theta=theta, phi=phi,
                                    energy=E_scattered
                                )
                                
                                # Saçılmış ışının kalan kolimatörden geçişi
                                scatter_transmission = trace_scatter_ray(
                                    scatter_ray, geometry, 
                                    compton_config.max_scatter_order - 1  # kalan saçılma hakkı
                                )
                                
                                if scatter_transmission.reaches_detector:
                                    scatter_results.append({
                                        "position": scatter_transmission.detector_position,
                                        "intensity": scatter_transmission.intensity,
                                        "energy": E_scattered,
                                        "scatter_angle": theta,
                                        "interaction_point": position,
                                        "type": "scatter"
                                    })
                        
                        position += step_size
            
            transmission = math.exp(-total_mu_x)
            primary_results.append({"position": ..., "intensity": transmission, "type": "primary"})
    
    # Sonuçları birleştir
    return combine_primary_and_scatter(primary_results, scatter_results)
```

#### 7.6.6 Compton/Toplam Zayıflama Oranı

Her malzeme ve enerji noktası için Compton etkileşimin toplam zayıflamaya oranı NIST XCOM verilerinden alınır:

```
f_compton(E) = σ_compton(E) / σ_total(E)
```

Bu oran, scatter ray-tracing'de etkileşim tipini belirlemek için kullanılır. Enerji bölgelerine göre tipik oranlar:

| Enerji Aralığı | Pb (Z=82) | Fe (Z=26) | Al (Z=13) |
|----------------|-----------|-----------|-----------|
| 80 keV | ~0.05 | ~0.30 | ~0.75 |
| 200 keV | ~0.15 | ~0.65 | ~0.92 |
| 500 keV | ~0.45 | ~0.90 | ~0.98 |
| 1 MeV | ~0.65 | ~0.95 | ~0.99 |
| 3 MeV | ~0.55 | ~0.85 | ~0.95 |
| 6 MeV | ~0.40 | ~0.70 | ~0.85 |

> Not: 3-6 MeV'de çift üretimi (pair production) devreye girdiğinden Compton oranı tekrar düşer.

### 8.1 Fiziksel Varsayımlar ve Model Sınırlamaları

#### 8.1.1 Genel Fizik Modeli Varsayımları

1. Hesaplamalar 2D enine kesit geometri üzerindendir (2.5D yaklaşım — derinlik boyutu homojen varsayılır).
2. İlk sürümde Monte Carlo simülasyonu yapılmaz; deterministik ray-tracing + Beer-Lambert kullanılır.
3. Build-up faktörü tek malzeme tabanlıdır (çok katmanlı build-up karmaşıklığı gelecek sürüme bırakılabilir).
4. Foton etkileşimleri: fotoelektrik absorpsiyon, Compton saçılma ve çift üretimi (>1.022 MeV). Rayleigh (coherent) saçılma toplam μ/ρ'ye dahildir ancak açısal olarak ayrıca modellenmez.
5. Kaynak nokta kaynak (point source) olarak modellenir; odak noktası boyutu yalnızca penumbra hesabında kullanılır.
6. Elektronlar (fotoelektron, Compton geri sekme elektronu, çift üretimi e⁺/e⁻) takip edilmez — yalnızca foton transportu yapılır. Elektronların lokal absorpsiyonu varsayılır (KERMA yaklaşımı).

#### 8.1.2 LINAC / MeV Spektrum Modeli Sınırlamaları

Bu uygulama, LINAC kaynağı için **basitleştirilmiş monoenerjik veya Kramers yaklaşımlı spektrum** kullanır. Aşağıdaki fiziksel etkiler **modellenmez** ve bu durum bilinçli bir tasarım kararıdır:

| Modellenmesi Kapsam Dışı Olan Etki | Neden | Sonuca Etkisi |
|--------------------------------------|-------|---------------|
| **Gerçek bremsstrahlung spektrumu** | Tam spektrum hesabı, tüp/target malzemesi, filtreleme kalınlığı gibi üreticiye özel bilgi gerektirir | Kolimatör kalınlığı hesapları ±10-15% konservatif sapma gösterebilir. Monoenerjik yaklaşım genelde **konservatif** sonuç verir (üst sınır tahmini). |
| **Flattening filter etkisi** | Klinik LINAC'larda yaygın, TIR sistemlerinde genellikle flattening filter yoktur (unflattened beam) | TIR senaryosunda etkisi düşüktür. Klinik senaryo ise bu aracın kapsamı dışındadır. |
| **Head scatter** | LINAC kafa geometrisinden kaynaklanan saçılma, üreticiye özel | Kolimatör tasarımını <%5 etkiler; kaynak spot boyutu parametresi ile kısmen yaklaşılabilir. |
| **Beam hardening** | Çok katmanlı geçişte düşük enerjili fotonların öncelikli absorbsiyonu, spektrumun sertleşmesi | Monoenerjik model beam hardening'i ihmal eder. Kalın zırhlamada (>5 HVL) gerçek iletim tahminimizden daha düşüktür → hesabımız **konservatiftir**. |
| **Off-axis softening** | Merkez dışı ışın yollarında spektrum yumuşaması | Fan-beam kenarlarında <%3 etki; ihmal edilebilir. |

> **Kullanıcıya gösterilecek uyarı:** Uygulama arayüzünde MeV modunda şu uyarı notu gösterilmelidir: *"LINAC kaynağı için basitleştirilmiş monoenerjik model kullanılmaktadır. Gerçek bremsstrahlung spektrumu, flattening filter ve beam hardening etkileri modellenmez. Sonuçlar kolimatör boyutlandırma ve karşılaştırma amaçlıdır; mutlak leakage değerleri için Monte Carlo doğrulaması (MCNP/FLUKA/Geant4) önerilir."*

#### 8.1.3 Compton Scatter Ray-Tracing Model Sınırlamaları

Scatter ray-tracing modülü **tam Monte Carlo simülasyonu değildir** ve aşağıdaki basitleştirmeler uygulanır:

| Basitleştirme | Gerçek Durum | Sapma Tahmini |
|---------------|--------------|---------------|
| Tek saçılma varsayımı (varsayılan) | Gerçekte çoklu saçılma önemlidir, özellikle kalın zırhlamada | Tek saçılma, gerçek saçılma katkısını %20-40 **eksik tahmin eder** (kalın Pb'de). Çift saçılma seçeneği bu farkı %10'a düşürür. |
| 2D geometri | Gerçekte 3D saçılma dağılımı | Üçüncü boyuttaki saçılma kaçağı ihmal edilir → hesap %10-20 **eksik tahmin eder** |
| Sabit adım boyutu (step-size) | Gerçekte etkileşim noktaları üstel dağılımlı | Yeterince küçük adım (≤1mm) ile iyi yaklaşım sağlanır; hata <%5 |
| Deterministik örnekleme | Tam MC rastgele örnekleme | Yeterli ışın sayısında (≥100) istatistiksel hata kabul edilebilir |
| Elektron takibi yok | Geri sekme elektronları ikincil bremsstrahlung üretebilir | MeV enerjilerinde <%2 katkı; ihmal edilebilir |

> **Kullanıcıya gösterilecek uyarı:** Scatter ray-tracing sonuçları panelinde şu not gösterilmelidir: *"Basitleştirilmiş tek/çift saçılma modeli kullanılmaktadır. Sonuçlar karşılaştırma ve ön-boyutlandırma amaçlıdır; kesin saçılma analizi için Monte Carlo doğrulaması önerilir."*

### 8.2 Birim Sistemi Standardı

> **KRİTİK:** Birim karışıklığı en yüksek hata riskini taşıyan konulardan biridir. Aşağıdaki birim sözleşmesi tüm kodda kesinlikle uygulanmalıdır.

#### 8.2.1 İç (Internal) Birim Sistemi

Tüm `core/` modülleri aşağıdaki **tek bir iç birim sistemini** kullanmalıdır:

| Büyüklük | İç Birim | Sembol | Notlar |
|----------|----------|--------|--------|
| **Uzunluk** | **cm** | cm | Fizik motoru her yerde cm kullanır |
| **Enerji** | **keV** | keV | MeV değerleri giriş noktasında keV'e çevrilir |
| **Yoğunluk** | g/cm³ | g/cm³ | NIST uyumlu |
| **Kütle zayıflama katsayısı** | cm²/g | μ/ρ | NIST XCOM formatı |
| **Lineer zayıflama katsayısı** | cm⁻¹ | μ | μ = (μ/ρ) × ρ |
| **Tesir kesiti** | cm² | σ | Klein-Nishina, toplam σ |
| **Kalınlık (optik)** | mfp (birimsiz) | μx | Build-up faktörü girdisi |
| **Açı** | radyan | rad | İç hesaplamalarda; UI'da dereceye çevrilir |

#### 8.2.2 Birim Dönüşüm Katmanı

UI ve core arasında birim dönüşümü **tek bir yerde** yapılmalıdır:

```python
# app/core/units.py

# Uzunluk dönüşümleri
def mm_to_cm(mm: float) -> float:
    """UI (mm) → Core (cm)"""
    return mm * 0.1

def cm_to_mm(cm: float) -> float:
    """Core (cm) → UI (mm)"""
    return cm * 10.0

# Enerji dönüşümleri
def MeV_to_keV(mev: float) -> float:
    return mev * 1000.0

def keV_to_MeV(kev: float) -> float:
    return kev / 1000.0

# Açı dönüşümleri
def deg_to_rad(deg: float) -> float:
    return deg * (math.pi / 180.0)

def rad_to_deg(rad: float) -> float:
    return rad * (180.0 / math.pi)

# Optik kalınlık dönüşümleri
def thickness_to_mfp(thickness_cm: float, mu_cm: float) -> float:
    """Fiziksel kalınlık → optik kalınlık (mfp)"""
    return mu_cm * thickness_cm

def mfp_to_thickness(mfp: float, mu_cm: float) -> float:
    """Optik kalınlık → fiziksel kalınlık"""
    return mfp / mu_cm

# Zayıflama dönüşümleri
def transmission_to_dB(transmission: float) -> float:
    """İletim oranı → dB zayıflama"""
    return -10.0 * math.log10(max(transmission, 1e-30))

def dB_to_transmission(dB: float) -> float:
    """dB zayıflama → iletim oranı"""
    return 10.0 ** (-dB / 10.0)
```

#### 8.2.3 Birim Sözleşmesi Kuralları

1. **UI katmanı (app/ui/):** Kullanıcı ile etkileşimde **mm** (uzunluk), **derece** (açı), **keV veya MeV** (enerji) kullanılır. Tüm QDoubleSpinBox, QSlider vb. widget'lar bu birimlerde çalışır.

2. **Core katmanı (app/core/):** Tüm hesaplamalar **cm**, **radyan**, **keV** cinsinden yapılır. Core fonksiyonları asla mm kabul etmez ve asla mm döndürmez.

3. **Dönüşüm sınırı:** Birim dönüşümü **yalnızca** UI↔Core sınırında yapılır:
   - UI → Core çağrısı öncesi: `mm_to_cm()`, `deg_to_rad()`
   - Core → UI sonuç gösterimi: `cm_to_mm()`, `rad_to_deg()`

4. **Build-up faktörü özel dikkat:** Build-up katsayı tabloları mfp (optik kalınlık) cinsinden indekslenmiştir. `thickness_to_mfp()` dönüşümü build-up hesabından hemen önce yapılmalıdır:
   ```python
   # DOĞRU KULLANIM
   mu = get_mu(material_id, energy_keV)       # cm⁻¹
   thickness_cm = mm_to_cm(thickness_mm)       # UI'dan gelen mm → cm
   mu_x = thickness_to_mfp(thickness_cm, mu)   # cm × cm⁻¹ = birimsiz (mfp)
   B = calculate_buildup_factor(energy_keV, mu_x, material_id)  # mfp girer
   I = I0 * B * math.exp(-mu_x)               # mfp cinsinden zayıflama
   ```

5. **Fonksiyon imzalarında birim belirtme:** Her core fonksiyonunun docstring'inde giriş ve çıkış birimleri açıkça yazılmalıdır:
   ```python
   def calculate_attenuation(self, thickness_cm: float, mu_per_cm: float) -> float:
       """
       Args:
           thickness_cm: Malzeme kalınlığı [cm]
           mu_per_cm: Lineer zayıflama katsayısı [cm⁻¹]
       Returns:
           transmission: İletim oranı [birimsiz, 0-1]
       """
   ```

6. **Unit test'lerde birim kontrolü:** Test suite'inde bilinen referans değerlerle birim dönüşüm zinciri doğrulanmalıdır:
   ```python
   def test_pb_1mev_transmission():
       # Pb, 1 MeV: μ/ρ = 0.0708 cm²/g, ρ = 11.35 g/cm³
       # 10 mm = 1 cm kalınlık
       mu = 0.0708 * 11.35  # = 0.8036 cm⁻¹
       t_cm = mm_to_cm(10)  # = 1.0 cm
       mfp = thickness_to_mfp(t_cm, mu)  # = 0.8036
       transmission = math.exp(-mfp)  # ≈ 0.448
       assert abs(transmission - 0.448) < 0.01
   ```

### 8.3 Yazılımsal Kısıtlar

1. Tek kullanıcılı masaüstü uygulama — ağ erişimi gerekmez (tamamen offline çalışır).
2. SQLite veritabanı Python built-in `sqlite3` modülü ile kullanılır.
3. Tüm hesaplamalar lokal olarak çalışır — harici servis bağımlılığı yoktur.
4. İlk sürümde i18n gerekmez (Türkçe veya İngilizce, tek dil).
5. PyQt6 GPL/LGPLv3 lisansı ile kullanılır. Ticari dağıtım gerekirse Qt Commercial lisans alınmalıdır.
6. PyInstaller ile paketlendiğinde tüm bağımlılıklar bundle edilir — son kullanıcıda Python kurulumu gerekmez.

### 8.4 Performans Hedefleri

| İşlem | Hedef Süre |
|-------|-----------|
| Tek enerji zayıflama hesabı | < 50 ms |
| Enerji taraması (100 nokta) | < 500 ms |
| Klein-Nishina dσ/dΩ hesabı (180 bin) | < 100 ms |
| Compton enerji spektrumu (100 bin) | < 100 ms |
| Işın profili (1000 ışın, saçılma yok) | < 2 saniye |
| Işın profili (1000 ışın, tek saçılma dahil) | < 15 saniye |
| Işın profili (1000 ışın, çift saçılma dahil) | < 60 saniye |
| Scatter ray-tracing (100 birincil ışın) | < 10 saniye |
| Canvas yeniden çizim | < 16 ms (60 fps) |
| PDF rapor oluşturma | < 5 saniye |

---

## 9. Kritik Riskler ve Risk Azaltma Stratejileri

### 9.1 RISK-1: Scatter Ray-Tracing Karmaşıklık Patlaması

**Risk:** Scatter ray-tracing modülü, görünüşte "bir feature" olmasına rağmen, aslında mini-MCNP seviyesine kayabilecek bir iş yüküdür. Geometri kesişimleri, saçılma olasılığı örneklemesi, enerji spektrumu takibi, detektör geometrisi, çoklu saçılma ve doğrulama konularını kapsar.

**Olasılık:** Yüksek  
**Etki:** Proje süresi 2-3x uzayabilir

**Azaltma stratejisi — Katmanlı Geliştirme:**

Scatter ray-tracing **üç aşamada** (Alpha → Beta → Full) geliştirilir. Her aşama kendi başına kullanılabilir durumdadır:

| Aşama | Kapsam | İş Yükü | Doğruluk |
|-------|--------|---------|----------|
| **Alpha** (v1.0 hedef) | Klein-Nishina analitik hesaplar + grafikler (polar plot, enerji spektrumu, açı-enerji haritası). Ray-tracing YOK. | 1-2 hafta | Analitik hesaplar %100 doğru |
| **Beta** (v1.1 hedef) | Alpha + tek saçılma ray-tracing (sabit adım, 2D, basit geometri kesişimleri). Canvas'ta saçılma noktaları gösterimi. | 3-4 hafta | ±20-30% saçılma tahmini |
| **Full** (v1.2+ hedef) | Beta + çoklu saçılma, varyans azaltma (importance sampling), detaylı detektör modeli, istatistiksel hata tahmini. | 4-6 hafta | ±10-15% saçılma tahmini |

**Karar noktası:** Her aşama sonunda kullanıcı geri bildirimi alınır. Beta yeterli ise Full'a geçilmez.

### 9.2 RISK-2: LINAC Spektrum Modeli Sapması

**Risk:** Monoenerjik/Kramers yaklaşımlı model, gerçek LINAC çıkışını (bremsstrahlung spektrumu, flattening filter, beam hardening, head scatter) yansıtmaz. Mutlak leakage değerlerinde ±10-20% sapma olabilir.

**Olasılık:** Kesin (bu bir model sınırlamasıdır, risk değil)  
**Etki:** Orta — sonuçlar kolimatör boyutlandırma için hâlâ faydalıdır (genelde konservatif tahmin)

**Azaltma stratejisi:**
1. ✅ Bölüm 8.1.2'de sınırlamalar açıkça belgelenmiştir.
2. ✅ UI'da MeV modunda uyarı notu gösterilecektir.
3. 🔮 Gelecek sürümde (v2+) isteğe bağlı SpekCalc benzeri spektrum editörü eklenebilir.
4. 🔮 Kullanıcı, harici bir araçtan (MCNP, FLUKA) elde ettiği spektrumu CSV olarak import edebilir (v2+).

### 9.3 RISK-3: Birim Karışıklığı (mm / cm / mfp)

**Risk:** UI mm, fizik motoru cm, build-up faktörü mfp kullanır. Bu üçlü dönüşüm zincirinde hata yapma olasılığı yüksektir. Klasik "Mars Climate Orbiter" tipi bir hata projede sessizce yanlış sonuçlar üretebilir.

**Olasılık:** Yüksek  
**Etki:** Kritik — yanlış hesap sonuçları

**Azaltma stratejisi:**
1. ✅ Bölüm 8.2'de kesin birim standardı tanımlanmıştır (core: cm/keV/rad, UI: mm/keV-MeV/derece).
2. ✅ `app/core/units.py` tek dönüşüm noktası olarak tanımlanmıştır.
3. ✅ Fonksiyon imzalarında birim açıkça belirtilecektir (docstring convention).
4. ✅ Birim dönüşüm zinciri unit test ile doğrulanacaktır (Pb 1 MeV referans hesabı).
5. **Ek öneri — tip alias kullanımı:**
   ```python
   # app/core/units.py
   from typing import NewType
   Cm = NewType('Cm', float)
   Mm = NewType('Mm', float)
   KeV = NewType('KeV', float)
   Mfp = NewType('Mfp', float)
   Radian = NewType('Radian', float)
   ```
   Bu alias'lar runtime'da maliyet oluşturmaz ama IDE'de ve code review'da birim hatalarını görünür kılar.

---

## 10. Geliştirme Aşamaları (Önerilen Yol Haritası)

### Aşama 1 — Temel Altyapı + Birim Sistemi
- [ ] Proje iskeletini oluştur (Python + PyQt6 yapısı, dizin düzeni)
- [ ] `app/core/units.py` birim dönüşüm modülünü ilk iş olarak implement et
- [ ] Birim dönüşüm unit testlerini yaz (Bölüm 8.2.3 referans hesabı)
- [ ] PyQt6 ana pencere (QMainWindow) ve koyu tema QSS oluştur
- [ ] QDockWidget tabanlı panel yapısını kur (sol, sağ, alt)
- [ ] SQLite veritabanı şemasını oluştur (db_manager.py — tüm 6 tablo)
- [ ] NIST XCOM verilerini JSON olarak hazırla ve veritabanına yükle
- [ ] MaterialService sınıfını implement et
- [ ] PhysicsEngine temel hesaplamalarını implement et (μ/ρ, HVL, TVL)

### Aşama 2 — Fizik Motoru
- [ ] Beer-Lambert çok katmanlı zayıflama hesabını implement et
- [ ] Build-up faktör hesabını implement et (GP + Taylor)
- [ ] Enerji taraması (energy sweep) fonksiyonunu implement et
- [ ] Kalınlık taraması fonksiyonunu implement et
- [ ] Alaşım karışım kuralı hesabını implement et
- [ ] Unit testleri yaz (bilinen referans değerlerle karşılaştırma)

### Aşama 2b — Compton Analitik Hesaplar (Alpha)
> Bu aşama ray-tracing İÇERMEZ. Sadece analitik Klein-Nishina hesapları ve grafikleri.
- [ ] Compton kinematiği hesabını implement et (E', T, Δλ)
- [ ] Klein-Nishina diferansiyel tesir kesiti (dσ/dΩ) hesabını implement et
- [ ] Toplam Klein-Nishina tesir kesiti (σ_KN) hesabını implement et
- [ ] Compton saçılmış foton enerji spektrumu hesabını implement et
- [ ] Compton/toplam oranı hesabını NIST verilerinden implement et
- [ ] Unit testleri yaz: Klein-Nishina'yı Thomson limiti ile doğrula, σ_KN'yi bilinen değerlerle karşılaştır

### Aşama 3 — Canvas Geometri Editörü (QGraphicsScene)
- [ ] QGraphicsScene + QGraphicsView tabanlı canvas bileşenini oluştur
- [ ] Üç kolimatör tipi için QGraphicsItem şablon geometrileri implement et
- [ ] Boyut düzenleme (sürüklenebilir handle'lar + QDoubleSpinBox) implement et
- [ ] Katman yönetimi panelini implement et (QListWidget + sürükle-bırak sıralama)
- [ ] Malzeme renk kodlaması (QBrush) ve katman görselleştirmesini implement et
- [ ] Zoom (QGraphicsView.scale), pan, ızgara, cetvel implement et
- [ ] QDockWidget panelleri (malzeme, katman, parametreler, sonuçlar) implement et

### Aşama 4 — Birincil Ray-Tracing Simülasyonu
- [ ] Geometrik ray-collimator kesişim algoritmasını implement et
- [ ] Birincil ışın profili hesabını implement et (saçılma yok)
- [ ] Build-up faktörü dahil iletim hesabını implement et
- [ ] Kalite metrikleri (penumbra, homojenite, kaçak) hesabını implement et
- [ ] SimulationWorker (QThread) implement et — ilerleme sinyali
- [ ] Sonuçları otomatik veritabanına kaydetme implement et

### Aşama 5 — Görselleştirme (pyqtgraph + matplotlib)
- [ ] pyqtgraph tabanlı base chart widget implement et
- [ ] Işın profili grafiğini implement et (pyqtgraph PlotWidget)
- [ ] μ/ρ vs enerji grafiğini implement et (log-log, pyqtgraph)
- [ ] HVL vs enerji grafiğini implement et
- [ ] İletim vs kalınlık grafiğini implement et
- [ ] Çoklu enerji overlay grafiğini implement et
- [ ] Klein-Nishina polar plot implement et (matplotlib polar axes, QWidget embed)
- [ ] Compton saçılmış foton enerji spektrumu grafiğini implement et
- [ ] Saçılma açısı vs enerji kaybı interaktif grafiğini implement et (dual-axis, slider)
- [ ] Alt QTabWidget ile grafik sekmeleri arasında geçiş implement et

### Aşama 6 — Tasarım Yönetimi ve Dışa Aktarım
- [ ] DesignRepository tam implement et (CRUD + versiyon geçmişi)
- [ ] Tasarım kaydet/yükle diyaloğu implement et (thumbnail, filtreleme, arama)
- [ ] Simülasyon sonuçları saklama ve listeleme implement et
- [ ] Simülasyon sonuçları karşılaştırma (overlay) implement et
- [ ] .cdt proje dosyası dışa/içe aktarım implement et
- [ ] PDF rapor oluşturma implement et (ReportLab)
- [ ] CSV dışa aktarım implement et
- [ ] JSON geometri dışa/içe aktarım implement et
- [ ] Canvas PNG/SVG export implement et

### Aşama 7 — Scatter Ray-Tracing (Beta) ⚠️ Opsiyonel
> Bu aşama Aşama 4 tamamlandıktan sonra başlanır. Alpha (Aşama 2b) zaten analitik Compton hesapları sağlar.
- [ ] Kahn algoritması ile Klein-Nishina açısal örnekleme implement et
- [ ] Tek saçılma ray-tracing motorunu implement et (scatter_tracer.py)
- [ ] ScatterWorker (QThread) implement et
- [ ] Canvas üzerinde saçılma etkileşim noktaları ve ışın yolları görselleştirmesini implement et
- [ ] SPR (Scatter-to-Primary Ratio) profil grafiğini implement et
- [ ] Bilinen geometri ile MCNP referans karşılaştırması yap (varsa)

### Aşama 8 — Cilalama, Paketleme ve Test
- [ ] Tüm modüllerin entegrasyon testi
- [ ] Bilinen referans değerlerle doğrulama (validation)
- [ ] MeV modu uyarı mesajının gösterildiğini doğrula
- [ ] UI/UX ince ayar (QSS polish, ikon seti)
- [ ] Performans optimizasyonu (NumPy vektörizasyon, QThread tuning)
- [ ] QSettings ile pencere düzeni kaydetme/geri yükleme
- [ ] PyInstaller ile tek dosya .exe/.app build (installer)
- [ ] PyInstaller ile portable klasör build
- [ ] .cdt dosya uzantısı ilişkilendirme (Windows registry / macOS plist)
- [ ] Windows, macOS, Linux üzerinde test
- [ ] Dokümantasyon (README, kullanım kılavuzu)

---

## 11. Doğrulama ve Doğruluk Çerçevesi (Verification & Validation)

Bu bölüm, hesaplama motorunun doğruluğunu sistematik olarak kanıtlamak için gereken benchmark test senaryolarını, referans kaynakları ve kabul kriterlerini tanımlar. Her modül bağımsız olarak doğrulanmalıdır.

### 11.1 Doğrulama Stratejisi

| Seviye | Açıklama | Yöntem |
|--------|----------|--------|
| **V1 — Birim Doğrulama** | Her core fonksiyonu bağımsız olarak test edilir | Unit test (pytest), analitik formül karşılaştırması |
| **V2 — Referans Karşılaştırma** | Sonuçlar yayınlanmış referans verilerle karşılaştırılır | NIST XCOM, ANSI/ANS-6.4.3, literatür tabloları |
| **V3 — Çapraz Doğrulama** | Farklı yöntemlerle aynı sonuca ulaşılır | GP vs Taylor build-up karşılaştırması, HVL iki yöntemle hesap |
| **V4 — Uç Durum Testi** | Sınır koşullarında davranış kontrol edilir | Sıfır kalınlık, çok yüksek kalınlık, K-edge geçişleri |
| **V5 — Entegrasyon Testi** | Birden fazla modülün birlikte çalışması | Tam simülasyon senaryosu: geometri → ray-trace → metrik |

### 11.2 Kabul Kriterleri (Genel)

| Hesaplama Tipi | Maksimum İzin Verilen Hata | Referans |
|----------------|---------------------------|----------|
| μ/ρ değerleri (NIST XCOM) | ±1% | Veri yükleme hatası olmamalı |
| Lineer μ (μ = μ/ρ × ρ) | ±1% | Birim dönüşüm doğruluğu |
| HVL hesabı | ±2% | ln(2)/μ analitik formül |
| TVL hesabı | ±2% | ln(10)/μ analitik formül |
| Alaşım karışım kuralı | ±3% | NIST alaşım verisi karşılaştırması |
| Build-up faktörü (GP) | ±5% (≤20 mfp), ±10% (>20 mfp) | ANSI/ANS-6.4.3 tablo değerleri |
| Build-up faktörü (Taylor) | ±10% (≤10 mfp), ±15% (>10 mfp) | ANSI/ANS-6.4.3 tablo değerleri |
| Klein-Nishina σ_KN | ±0.5% | Analitik formül (kapalı form) |
| Compton saçılmış foton enerjisi | ±0.1% | Analitik Compton formülü |
| Işın profili iletim (build-up yok) | ±2% | exp(-μx) analitik |
| Işın profili iletim (build-up dahil) | ±10% | MCNP/literatür karşılaştırması |
| Penumbra genişliği | ±5% veya ±0.5mm (hangisi büyükse) | Geometrik hesap |
| Scatter ray-tracing (tek saçılma) | ±30% (kalitatif) | Bu seviyede kesin doğruluk beklenmez |

### 11.3 Benchmark Test Seti — Zayıflama ve HVL/TVL

#### BM-1: Kurşun (Pb) Zayıflama Katsayıları

**Referans:** NIST XCOM (https://physics.nist.gov/PhysRefData/Xcom/html/xcom1.html)

| Test ID | Enerji (keV) | μ/ρ beklenen (cm²/g) | HVL beklenen (mm) | TVL beklenen (mm) | Tolerans |
|---------|--------------|----------------------|--------------------|--------------------|----------|
| BM-1.1 | 88 (K-edge üstü) | 5.021 | 0.122 | 0.404 | ±1% |
| BM-1.2 | 100 | 5.549 | 0.110 | 0.366 | ±1% |
| BM-1.3 | 200 | 0.999 | 0.611 | 2.030 | ±1% |
| BM-1.4 | 500 | 0.1614 | 3.78 | 12.56 | ±1% |
| BM-1.5 | 662 (Cs-137) | 0.1101 | 5.55 | 18.42 | ±1% |
| BM-1.6 | 1000 | 0.0708 | 8.62 | 28.64 | ±1% |
| BM-1.7 | 1250 (Co-60 avg) | 0.0578 | 10.56 | 35.08 | ±1% |
| BM-1.8 | 2000 | 0.0455 | 13.42 | 44.58 | ±1% |
| BM-1.9 | 6000 | 0.0388 | 15.73 | 52.25 | ±2% |

> Pb K-edge: 88.0 keV. BM-1.1 bu kenarın hemen üstünde test yaparak K-edge veri interpolasyonunun doğruluğunu kontrol eder.

#### BM-2: Tungsten (W) Zayıflama Katsayıları

**Referans:** NIST XCOM

| Test ID | Enerji (keV) | μ/ρ beklenen (cm²/g) | HVL beklenen (mm) | Tolerans |
|---------|--------------|----------------------|--------------------|----------|
| BM-2.1 | 70 (K-edge üstü) | 4.027 | 0.089 | ±1% |
| BM-2.2 | 100 | 4.438 | 0.081 | ±1% |
| BM-2.3 | 500 | 0.1370 | 2.62 | ±1% |
| BM-2.4 | 1000 | 0.0620 | 5.79 | ±1% |
| BM-2.5 | 6000 | 0.0390 | 9.20 | ±2% |

> W K-edge: 69.5 keV. BM-2.1 K-edge geçiş doğruluğunu test eder.

#### BM-3: Demir (Fe) / Çelik Referans

**Referans:** NIST XCOM + Nelson & Reilly (1991) Passive NDA

| Test ID | Malzeme | Enerji (keV) | μ/ρ beklenen (cm²/g) | Tolerans |
|---------|---------|--------------|----------------------|----------|
| BM-3.1 | Fe | 100 | 0.3717 | ±1% |
| BM-3.2 | Fe | 662 | 0.07379 | ±1% |
| BM-3.3 | Fe | 1000 | 0.05995 | ±1% |
| BM-3.4 | SS304 (alaşım) | 662 | ~0.074 | ±3% |
| BM-3.5 | SS304 (alaşım) | 1000 | ~0.060 | ±3% |

> BM-3.4–3.5: Alaşım karışım kuralının doğruluğunu test eder. SS304 μ/ρ, saf Fe'ye çok yakın olmalıdır (%70 Fe).

#### BM-4: Çok Katmanlı Zayıflama

**Referans:** Analitik hesap (elle doğrulanabilir)

| Test ID | Konfigürasyon | Enerji (keV) | Beklenen İletim | Tolerans |
|---------|---------------|--------------|-----------------|----------|
| BM-4.1 | 10mm Pb | 1000 | exp(-0.8036) = 0.4478 | ±2% |
| BM-4.2 | 5mm Pb + 5mm Fe | 1000 | exp(-0.4018) × exp(-0.2349) = 0.5293 | ±2% |
| BM-4.3 | 20mm W | 500 | exp(-2.646×0.137×2.0) = exp(-5.277) = 0.0051 | ±5% |
| BM-4.4 | 0mm (boş) | herhangi | 1.000 | kesin |
| BM-4.5 | 100mm Pb | 100 | exp(-62.98) ≈ 0 | < 10⁻²⁰ |

> BM-4.4 ve BM-4.5: Uç durum testleri — sıfır kalınlık ve çok kalın zırhlama.

### 11.4 Benchmark Test Seti — Build-up Faktörü

**Referans:** ANSI/ANS-6.4.3-1991, Harima et al. (1986), buildup_coefficients.json EBF tabloları

#### BM-5: GP Formülü Doğrulama

| Test ID | Malzeme | Enerji (MeV) | mfp | B beklenen (EBF tablosu) | Tolerans |
|---------|---------|--------------|-----|--------------------------|----------|
| BM-5.1 | Pb | 1.0 | 1 | 1.37 | ±5% |
| BM-5.2 | Pb | 1.0 | 5 | 2.39 | ±5% |
| BM-5.3 | Pb | 1.0 | 10 | 3.26 | ±5% |
| BM-5.4 | Pb | 1.0 | 20 | 4.60 | ±8% |
| BM-5.5 | Pb | 1.0 | 40 | 6.62 | ±10% |
| BM-5.6 | Pb | 0.5 | 5 | ~1.8 | ±10% |
| BM-5.7 | Fe | 1.0 | 5 | ~4.2 | ±10% |
| BM-5.8 | W | 1.0 | 5 | ~2.2 | ±10% |

> BM-5.5: Yüksek mfp'de GP doğruluğu düşer — tolerans gevşetilmiştir.

#### BM-6: GP vs Taylor Çapraz Doğrulama

| Test ID | Malzeme | Enerji (MeV) | mfp | GP sonucu | Taylor sonucu | Kabul: fark < |
|---------|---------|--------------|-----|-----------|---------------|---------------|
| BM-6.1 | Pb | 1.0 | 5 | hesaplanan | hesaplanan | 15% |
| BM-6.2 | Pb | 0.5 | 10 | hesaplanan | hesaplanan | 15% |
| BM-6.3 | Fe | 1.0 | 10 | hesaplanan | hesaplanan | 15% |

> İki yöntem arasındaki fark %15'i aşarsa uyarı loglanır. GP sonucu birincil kabul edilir.

### 11.5 Benchmark Test Seti — Compton / Klein-Nishina

#### BM-7: Klein-Nishina Analitik Doğrulama

| Test ID | Test | Beklenen | Tolerans |
|---------|------|----------|----------|
| BM-7.1 | σ_KN(E→0) | σ_Thomson = 6.6524 × 10⁻²⁵ cm² | ±0.1% |
| BM-7.2 | σ_KN(511 keV) | 2.716 × 10⁻²⁵ cm² | ±0.5% |
| BM-7.3 | σ_KN(1 MeV) | 1.772 × 10⁻²⁵ cm² | ±0.5% |
| BM-7.4 | σ_KN(6 MeV) | 0.494 × 10⁻²⁵ cm² | ±0.5% |
| BM-7.5 | dσ/dΩ(θ=0°, 10 keV) | ≈ Thomson dσ/dΩ(θ=0°) = r₀² | ±2% |
| BM-7.6 | dσ/dΩ(θ=90°, 10 keV) | ≈ Thomson dσ/dΩ(θ=90°) = r₀²/2 | ±2% |
| BM-7.7 | E'(1 MeV, θ=180°) | 169 keV (Compton kenarı) | ±0.1% |
| BM-7.8 | E'(6 MeV, θ=90°) | 427 keV | ±0.1% |
| BM-7.9 | Δλ(θ=90°) | λ_C = 0.02426 Å | kesin |
| BM-7.10 | Δλ(θ=180°) | 2 × λ_C = 0.04852 Å | kesin |

> BM-7.7–7.10: Compton kinematiği tamamen analitik olduğundan %0.1 tolerans yeterlidir.

#### BM-8: Klein-Nishina Örnekleme Doğrulama

| Test ID | Test | Yöntem | Kabul |
|---------|------|--------|-------|
| BM-8.1 | Kahn örnekleme ortalaması | 10⁶ örnek, E=1 MeV, ortalama θ hesapla | Analitik ortalamaya ±1% yakınsama |
| BM-8.2 | Açısal dağılım histogram | 10⁶ örnek → histogram, dσ/dΩ ile overlay | χ² testi p > 0.01 |
| BM-8.3 | Enerji korunumu | Her örnekte E' + T = E₀ | Kesin (floating-point hassasiyetinde) |

### 11.6 Benchmark Test Seti — Birim Dönüşüm Zinciri

#### BM-9: Uçtan Uca Birim Doğrulama

| Test ID | Senaryo | Girdi (UI birimleri) | Beklenen Sonuç | Kontrol Noktaları |
|---------|---------|----------------------|----------------|-------------------|
| BM-9.1 | Pb 10mm, 1 MeV iletim | thickness=10mm, E=1000keV | T=0.4478 | mm→cm: 1.0cm ✓, μ=0.8036 cm⁻¹ ✓, μx=0.8036 ✓ |
| BM-9.2 | Pb 10mm, 1 MeV HVL | material=Pb, E=1000keV | HVL=8.62mm | μ/ρ → μ → ln2/μ cm → ×10 mm ✓ |
| BM-9.3 | Pb 10mm build-up | thickness=10mm, E=1MeV | B≈1.37 (1 mfp) | mm→cm→mfp: 10mm→1cm→0.8036mfp ✓ |
| BM-9.4 | MeV→keV dönüşüm | E=3.5 MeV | 3500 keV | ×1000 ✓ |

### 11.7 Benchmark Test Seti — Simülasyon Entegrasyon

#### BM-10: Basit Geometri Entegrasyon Testleri

| Test ID | Geometri | Enerji | Beklenen Davranış |
|---------|----------|--------|-------------------|
| BM-10.1 | Slit, 100mm Pb, 5mm açıklık, 1 MeV | 1000 keV | Açıklık: T≈1.0, Zırh: T≈exp(-8.04)≈0.00032 |
| BM-10.2 | Aynı geometri, build-up dahil | 1000 keV | Zırh: T×B > T (build-up yok), leakage artmalı |
| BM-10.3 | Pencil-beam, 50mm Pb, 2mm açıklık | 500 keV | Penumbra < 3mm, leakage < 0.1% |
| BM-10.4 | Simetri testi: simetrik geometri | herhangi | Sol penumbra ≈ sağ penumbra (±5%) |
| BM-10.5 | Açıklık = 0 (kapalı) | herhangi | Tüm profil ≈ leakage seviyesinde |
| BM-10.6 | Katman yok (açık) | herhangi | Tüm profil ≈ 1.0 (tam iletim) |

### 11.8 Referans Kaynaklar Sözlüğü

| Kısaltma | Tam Referans | Kullanım Alanı |
|----------|--------------|----------------|
| **NIST XCOM** | Berger, M.J. et al. XCOM: Photon Cross Sections Database, NIST Standard Reference Database 8, NBSIR 87-3597 | μ/ρ değerleri (birincil kaynak) |
| **ANSI/ANS-6.4.3** | ANSI/ANS-6.4.3-1991 "Gamma-Ray Attenuation Coefficients and Buildup Factors for Engineering Materials" | Build-up faktör tabloları |
| **WAPD-1628** | Shure, K. & Wallace, O.J., WAPD-TM-1628, Westinghouse, 1988 | Taylor build-up parametreleri |
| **DLC-129** | ORNL/RSIC-49/R1, DLC-129 "Buildup Factor Data" | GP fitting katsayıları |
| **Harima (1986)** | Harima Y., "An approximation of gamma-ray buildup factors by modified geometrical progression," Nucl. Sci. Eng., 94, 24-35 | GP formülü orijinal yayın |
| **Kiyani (2013)** | Kiyani A. et al., "EBF calculations by MCNP4C and GP fitting," Ann. Nucl. Energy, 58 | MCNP doğrulamalı EBF tabloları |
| **Atak (2019)** | Atak H. et al., "MCNP-validated buildup factors for Pb, Fe, W," Radiat. Phys. Chem. | MCNP ile doğrulanmış build-up değerleri |
| **Hubbell (1982)** | Hubbell J.H., "Photon Mass Attenuation and Energy-absorption Coefficients," Int. J. Appl. Radiat. Isot., 33, 1269 | μ/ρ ve μ_en/ρ tabloları |
| **NCRP-151** | NCRP Report No. 151, "Structural Shielding Design for Medical X-Ray Imaging Facilities" (2005) | Zırhlama tasarım standartları |
| **IEC 60601-2-44** | IEC 60601-2-44 "Medical electrical equipment — X-ray equipment for computed tomography" | Penumbra ve leakage tanımları |
| **Klein & Nishina (1929)** | Klein O. & Nishina Y., "Über die Streuung von Strahlung durch freie Elektronen," Z. Physik, 52, 853 | Klein-Nishina orijinal formül |

### 11.9 Doğrulama Test Süreç Kuralları

1. **Tüm BM testleri `tests/` dizininde pytest ile otomatize edilmelidir.** Test isimleri `test_BM_X_Y()` formatında.
2. **CI/CD pipeline'ında her commit'te BM-1 ile BM-9 arası otomatik çalışmalıdır.** (Yerel geliştirmede `pytest tests/ -m benchmark`)
3. **BM-10 (entegrasyon) testleri her release öncesi çalıştırılmalıdır.**
4. **Bir test fail ederse:** hata mesajı beklenen değeri, hesaplanan değeri, yüzde sapmayı ve referans kaynağı belirtmelidir.
5. **Yeni malzeme veya enerji aralığı eklendiğinde** ilgili BM testleri de güncellenir.
6. **Doğrulama raporu:** `pytest --html=validation_report.html` ile üretilen test raporu, PDF çıktısına "Doğrulama Özeti" bölümü olarak eklenebilir.

---

## 12. Gelecek Sürüm Notları (Kapsam Dışı — v2+)

Aşağıdaki özellikler bu sürümün kapsamında **değildir**, ancak mimari bu özelliklere genişletilebilir olmalıdır:

1. **Çoklu saçılma ray-tracing (Full)** — Importance sampling, varyans azaltma, istatistiksel hata tahmini (Risk-1 Aşama 7 sonrası)
2. **Monte Carlo simülasyonu** — MCNP/Geant4 entegrasyonu veya basitleştirilmiş MC implementasyonu
3. **3D görselleştirme** — Qt3D veya VTK ile kolimatör 3D modeli
4. **Spektrum editörü** — Gerçekçi X-ray tüp spektrumu üretimi (SpekCalc benzeri) veya harici spektrum CSV import (Risk-2 azaltma)
5. **Çok yapraklı kolimatör (MLC)** desteği
6. **Maliyet optimizasyonu** — Malzeme maliyeti + ağırlık + performans çok-kriterli optimizasyon
7. **Çoklu dil** (i18n) — TR/EN desteği
8. **Kullanıcı tanımlı malzeme ekleme** — Özel alaşım veya bileşik malzeme tanımlama

---

*Doküman Sonu*
