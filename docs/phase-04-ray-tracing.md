# Phase 4 — Birincil Ray-Tracing Simulasyonu

## Amac
Geometrik ray-tracing ile isin profili hesaplamak. Kaynak noktasindan kolimator geometrisi uzerinden isinlari takip edip, Beer-Lambert zayiflama ile detektor duzlemindeki siddeti hesaplamak. Kalite metriklerini (penumbra, flatness, leakage, collimation ratio) hesaplamak.

## Kapsam & Bagimliliklar
- **Bagimlilik:** Phase 1 (modeller), Phase 2 (fizik motoru), Phase 3 (canvas geometri)
- **Bu fazda Compton scatter ray-tracing YOKTUR** — sadece birincil isinlar
- Phase 5 (grafikler) bu fazin sonuclarini gorsellestirr

## Olusturulacak Dosyalar

```
app/core/
├── ray_tracer.py           # Geometrik isin takibi (ray-collimator kesisim)
├── beam_simulation.py      # BeamSimulation sinifi (profil hesabi)

app/workers/
├── simulation_worker.py    # QThread — isin profili simulasyonu
└── calculation_worker.py   # QThread — enerji/kalinlik taramasi

app/ui/panels/
└── results_panel.py        # Sag panel — hizli hesaplama sonuclari (guncelleme)

tests/
├── test_ray_tracer.py      # Ray-collimator kesisim testleri
└── test_simulation.py      # BM-10 entegrasyon testleri
```

## API Arayuzleri

### RayTracer (app/core/ray_tracer.py)

```python
from dataclasses import dataclass

@dataclass
class Ray:
    origin_x: float    # cm
    origin_y: float    # cm
    angle: float       # radian
    energy_keV: float  # keV

@dataclass
class Intersection:
    entry_x: float     # cm
    entry_y: float     # cm
    exit_x: float      # cm
    exit_y: float      # cm
    path_length: float # cm
    layer_id: str
    material_id: str

@dataclass
class StageIntersection:
    """Tek bir stage icin isin kesisim sonuclari."""
    stage_id: str
    stage_order: int
    passes_aperture: bool
    layer_intersections: list[Intersection]
    total_path_length: float  # cm

class RayTracer:
    def trace_ray(self, ray: Ray, geometry: CollimatorGeometry) -> list[StageIntersection]:
        """
        Tek bir isinin kolimator geometrisi ile kesisim noktalarini hesaplar.
        geometry.stages uzerinde iterasyon yaparak her stage icin ayri kesisim hesaplar.

        Args:
            ray: Isin (origin, aci, enerji) [cm, radian, keV]
            geometry: Kolimator geometrisi — geometry.stages listesi uzerinden
                      her stage icin katman kesisimleri hesaplanir
                      [boyutlar mm cinsinden — fonksiyon icinde cm'ye cevrilir]
        Returns:
            StageIntersection listesi: her stage icin aperture durumu ve
            katman kesisimleri (giris/cikis noktasi, yol uzunlugu [cm])
        """

    def passes_through_aperture(self, ray: Ray, geometry: CollimatorGeometry) -> bool:
        """Isin acikliktan gecip gecmedigini kontrol eder."""

    def compute_ray_angles(self, num_rays: int, geometry: CollimatorGeometry) -> list[float]:
        """
        Kaynak noktasindan gonderilecek isin acilarini hesaplar.
        Fan-beam: yelpaze acisi araliginda esit dagilimli
        Pencil-beam/Slit: tum kolimator genisligi araliginda
        Returns: Aci listesi [radian]
        """

    def compute_detector_position(self, ray: Ray, detector: DetectorConfig) -> float:
        """Isinin detektor duzlemindeki pozisyonunu hesaplar. Returns: [cm]"""
```

### BeamSimulation (app/core/beam_simulation.py)

```python
class BeamSimulation:
    def __init__(self, physics_engine: PhysicsEngine, ray_tracer: RayTracer): ...

    def calculate_beam_profile(self, geometry: CollimatorGeometry,
                               energy_keV: float, num_rays: int = 360,
                               include_buildup: bool = True,
                               progress_callback: callable = None
                               ) -> SimulationResult:
        """
        Tam isin profili hesaplar.

        Algoritma:
        1. Kaynak noktasindan num_rays adet isin gonder
        2. Her isin icin geometry.stages uzerinde iterasyon yap
        3. Her stage icin ray_tracer ile kesisim bul
        4. Tum stage aperture'lerinden gecenler: transmission = 1.0
        5. Herhangi bir stage govdesinden gecenler: toplam cok katmanli Beer-Lambert hesabi
        6. Build-up dahilse: B faktoru ile duzeltme
        7. Detektor duzleminde pozisyon ve siddet kaydet
        8. Kalite metriklerini hesapla

        Returns: SimulationResult (beam_profile, quality_metrics, energy_analysis)
        """

    def compare_energies(self, geometry: CollimatorGeometry,
                         energies_keV: list[float], num_rays: int
                         ) -> dict[float, SimulationResult]:
        """Birden fazla enerjide profil hesaplar (karsilastirma icin)."""
```

### QThread Workers

```python
# app/workers/simulation_worker.py
class SimulationWorker(QThread):
    progress = pyqtSignal(int)            # Ilerleme yuzdesi (0-100)
    result_ready = pyqtSignal(object)     # SimulationResult
    error = pyqtSignal(str)               # Hata mesaji

    def __init__(self, geometry, energy_keV, num_rays, include_buildup): ...
    def run(self): ...
    def cancel(self): ...

# app/workers/calculation_worker.py
class CalculationWorker(QThread):
    progress = pyqtSignal(int)
    result_ready = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, calc_type, params): ...
    def run(self): ...
```

## Ray-Tracing Algoritmasi

```python
# Pseudocode — Multi-stage kolimator destekli
def calculate_beam_profile(geometry, energy_keV, num_rays):
    results = []
    source = geometry.source.position  # mm -> cm donusumu

    # Stage pozisyonlarini isin ekseni boyunca hesapla
    stage_positions = compute_stage_z_positions(geometry.stages)

    for i in range(num_rays):
        angle = compute_ray_angle(i, num_rays, geometry)
        ray = Ray(origin=source, angle=angle, energy=energy_keV)

        total_mu_x = 0.0
        passes_all_apertures = True

        for stage_idx, stage in enumerate(geometry.stages):
            stage_z = stage_positions[stage_idx]
            local_intersections = intersect(ray, stage, stage_z)

            if passes_through_aperture(ray, stage.aperture, stage_z):
                # Bu stage'in aperture'unden gecti — zayiflama yok
                continue
            else:
                passes_all_apertures = False
                for intersection in local_intersections:
                    mu = get_linear_attenuation(intersection.material_id, energy_keV)
                    total_mu_x += mu * intersection.path_length

            # Stage'ler arasi bosluk: hava/vakum, zayiflama yok

        if passes_all_apertures:
            transmission = 1.0  # Tum aperture'lerden gecti
        else:
            transmission = exp(-total_mu_x)
            if include_buildup:
                B = calculate_buildup_factor(energy_keV, total_mu_x, primary_material)
                transmission *= B

        detector_pos = compute_detector_position(ray, geometry.detector)
        results.append({"angle": angle, "position": detector_pos, "transmission": transmission})

    quality = calculate_quality_metrics(results)
    return SimulationResult(beam_profile=results, quality_metrics=quality)
```

## Kalite Metrikleri

### FR-3.4.1 Penumbra Genisligi (mm)

```
1. Isin profilinde normalize siddet I(x) dizisi (0-1)
2. I_max = mean(I(merkez bolge))
3. Profil kenarinda (sol ve sag ayri):
   x_80 = I(x) = 0.80 * I_max pozisyonu (interpole)
   x_20 = I(x) = 0.20 * I_max pozisyonu (interpole)
4. Penumbra = |x_80 - x_20| [mm, detektor duzleminde]
5. Genel metrik = max(sol, sag)
```

Threshold secimleri: %20-%80 (varsayilan), %10-%90, %50 (FWHM)

| Kolimator Tipi | Kabul Edilebilir | Mukemmel |
|----------------|-----------------|----------|
| Fan-beam (TIR) | < 10 mm | < 5 mm |
| Pencil-beam | < 3 mm | < 1 mm |
| Slit | < 5 mm | < 2 mm |

### FR-3.4.2 Alan Homojenligi / Flatness (%)

```
1. Yararli isin alani: FWHM sinirlari icindeki bolge
2. Duzluk degerlendirme alani: FWHM'nin %80'i (kenarlardan %10 haric)
3. I_max = max(I(x)), I_min = min(I(x))
4. Flatness (%) = 100 * (I_max - I_min) / (I_max + I_min)
```

| Flatness | Durum |
|----------|-------|
| < 3% | Mukemmel |
| 3-10% | Kabul edilebilir |
| > 10% | Kotu |

### FR-3.4.3 Kacak Radyasyon / Leakage (%)

```
1. Zirhlenmis bolge: FWHM kenari disindaki bolge (penumbra HARIC)
2. Leakage_avg (%) = 100 * mean(I_leak) / I_primary
3. Leakage_max (%) = 100 * max(I_leak) / I_primary
```

| Leakage | Durum |
|---------|-------|
| < 0.1% | Mukemmel (radyoterapi seviyesi) |
| 0.1-1% | Iyi (TIR icin yeterli) |
| 1-5% | Kabul edilebilir |
| > 5% | Yetersiz |

> Build-up dahil/haric iki deger ayri gosterilmelidir.

### FR-3.4.4 Kolimasyon Orani (Collimation Ratio)

```
CR = I_primary_mean / I_leakage_mean
CR_dB = 10 * log10(CR)
```

| CR | dB | Durum |
|----|----|-------|
| > 1000 | > 30 dB | Mukemmel |
| 100-1000 | 20-30 dB | Iyi |
| 10-100 | 10-20 dB | Kabul edilebilir |
| < 10 | < 10 dB | Yetersiz |

### FR-3.4.6 UI Gosterim
- Kalite metrikleri "Sonuc Karti" (score card) olarak gosterilir
- Her metrik: sayisal deger, birim, renk kodlu durum gostergesi (yesil/sari/kirmizi)
- Threshold degerleri kullanici tarafindan ozellestirilebilir
- "Tumunu Gec" / "Bazilari Basarisiz" ozet gosterge

## Kabul Kriterleri & Benchmark Testleri

### BM-10: Basit Geometri Entegrasyon Testleri

| Test ID | Geometri | Enerji | Beklenen Davranis |
|---------|----------|--------|-------------------|
| BM-10.1 | Slit, 100mm Pb, 5mm aciklik | 1000 keV | Aciklik: T~1.0, Zirh: T~exp(-8.04)~0.00032 |
| BM-10.2 | Ayni geometri, build-up dahil | 1000 keV | Zirh: T*B > T (build-up yok), leakage artmali |
| BM-10.3 | Pencil-beam, 50mm Pb, 2mm aciklik | 500 keV | Penumbra < 3mm, leakage < 0.1% |
| BM-10.4 | Simetri testi: simetrik geometri | herhangi | Sol penumbra ~ sag penumbra (+/-5%) |
| BM-10.5 | Aciklik = 0 (kapali) | herhangi | Tum profil ~ leakage seviyesinde |
| BM-10.6 | Katman yok (acik) | herhangi | Tum profil ~ 1.0 (tam iletim) |
| BM-10.7 | 2-stage slit, Pb 50mm + W 30mm, 5mm aperture, 20mm gap | 1000 keV | Stage-1 + Stage-2 toplam zayiflama, gap katkisi sifir |
| BM-10.8 | 3-stage fan-beam (Internal+Fan+Penumbra) | 1000 keV | Aperture kesisimi nihai beam seklini belirler |

### Faz 4 Tamamlanma Kriterleri:
- [ ] RayTracer tek isin kolimator kesisimini dogru hesapliyor
- [ ] BeamSimulation tam profil uretiyor (aciklik + zirhlama bolgesi)
- [ ] Build-up dahil/haric hesaplama calisiyor
- [ ] SimulationWorker QThread ile calisiyor (UI bloklanmiyor)
- [ ] Progress sinyali ilerleme cubugunu guncelliyor
- [ ] Kalite metrikleri (penumbra, flatness, leakage, CR) dogru hesaplaniyor
- [ ] Sonuc karti dogru renk kodlamasini gosteriyor
- [ ] BM-10.1 – BM-10.8 testleri geciyor
- [ ] 1000 isin simulasyonu < 2 saniye
- [ ] Simulasyon sonuclari veritabanina kaydediyor

## Notlar
- Isin sayisi kullanici tarafindan ayarlanabilir (varsayilan 360, aralik 100-10000)
- Fan-beam icin trapez geometri kesisimi, Pencil-beam/Slit icin dikdortgen
- Birim donusumu: geometry mm cinsinden gelir, ray_tracer icinde cm'ye cevirilir
- Build-up faktoru geometri duzeltmesi: acikliktan gecen isin B=1.0, zirhlama icin tam B
- SimulationWorker cancel() ile iptal edilebilmeli

> **FRD Referans:** §4.3 (FR-3.1, FR-3.4), §7.5, §5.3, §5.7, §11.7
