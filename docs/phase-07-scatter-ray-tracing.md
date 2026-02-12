# Phase 7 — Scatter Ray-Tracing (Opsiyonel)

## Amac
Kolimator malzemesinde Compton sacilmasi ile uretilen ikincil fotonlari takip etmek. Klein-Nishina dagilimina gore acisal ornekleme (Kahn algoritmasi), tek/cift sacilma simulasyonu, SPR profili, canvas uzerinde sacilma gorsellestirmesi.

## Kapsam & Bagimliliklar
- **Bagimlilik:** Phase 2 (ComptonEngine), Phase 4 (ray-tracing altyapisi, RayTracer)
- **Bu faz OPSIYONELDIR** — Phase 2'deki analitik Compton hesaplari (Alpha) zaten kullanilabilir durumda
- Risk yonetimi: FRD RISK-1'e gore katmanli gelistirme stratejisi (Alpha -> Beta -> Full)
- Bu faz "Beta" asamasidir — tek sacilma ray-tracing

## Olusturulacak Dosyalar

```
app/core/
├── klein_nishina_sampler.py   # Kahn algoritmasi ile acisal ornekleme
└── scatter_tracer.py          # Compton scatter ray-tracing motoru

app/workers/
└── scatter_worker.py          # QThread — scatter simulasyonu

app/ui/canvas/
└── scatter_overlay.py         # Sacilma etkilesim noktalari gorsellestirme

app/ui/charts/
└── spr_chart.py               # SPR profil grafigi (guncelleme)

tests/
└── test_scatter.py            # BM-8 testleri
```

## API Arayuzleri

### KleinNishinaSampler (app/core/klein_nishina_sampler.py)

```python
class KleinNishinaSampler:
    def sample_compton_angle(self, energy_keV: float) -> tuple[float, float, float]:
        """
        Kahn algoritmasi (rejection sampling) ile Klein-Nishina dagilimina gore
        sacilma acisi ornekler.

        Args:
            energy_keV: Gelen foton enerjisi [keV]
        Returns:
            (theta, phi, E_scattered):
            - theta: Sacilma acisi [radian]
            - phi: Azimut acisi [radian] (0-2pi, izotropik)
            - E_scattered: Sacilmis foton enerjisi [keV]
        """
```

#### Kahn Algoritmasi:
```python
def sample_compton_angle(energy_keV):
    alpha = energy_keV / 511.0

    while True:
        r1, r2, r3 = random(), random(), random()

        if r1 <= (1 + 2*alpha) / (9 + 2*alpha):
            # Dusuk enerji dali
            xi = 1 + 2*alpha*r2
            if r3 <= 4 * (1/xi - 1/xi**2):
                break
        else:
            # Yuksek enerji dali
            xi = (1 + 2*alpha) / (1 + 2*alpha*r2)
            cos_theta = 1 - (xi - 1) / alpha
            if r3 <= 0.5 * (cos_theta**2 + 1/xi):
                break

    cos_theta = 1 - (xi - 1) / alpha
    theta = acos(cos_theta)
    E_scattered = energy_keV / xi
    phi = 2 * pi * random()

    return theta, phi, E_scattered
```

### ScatterTracer (app/core/scatter_tracer.py)

```python
@dataclass
class ScatterInteraction:
    x: float               # Etkilesim noktasi [cm]
    y: float               # [cm]
    layer_id: str
    material_id: str
    incident_energy_keV: float
    scattered_energy_keV: float
    scatter_angle_deg: float
    reaches_detector: bool
    escaped: bool

@dataclass
class ScatterSimulationResult:
    interaction_points: list[ScatterInteraction]
    detector_scatter_profile: list[dict]  # position_mm, scatter_intensity, primary_intensity, SPR
    total_scatter_fraction: float
    mean_scattered_energy_keV: float
    escaped_fraction: float
    # Not: SPR (Scatter-to-Primary Ratio) tum stage'ler uzerinden birlesik hesaplanir.
    # Her stage'in scatter katkisi toplanarak toplam SPR elde edilir.

class ScatterTracer:
    def __init__(self, physics_engine, ray_tracer, compton_engine, sampler): ...

    def scatter_simulation(self, geometry: CollimatorGeometry,
                           energy_keV: float, num_primary_rays: int,
                           config: ComptonConfig,
                           step_size_mm: float = 1.0,
                           progress_callback: callable = None
                           ) -> ScatterSimulationResult:
        """
        Compton scatter ray-tracing simulasyonu (multi-stage).

        Algoritma:
        1. Her birincil isin kolimator stage'lerine sirayla girdiginde
        2. Her stage icin ayri intersection hesaplanir:
           for stage in geometry.stages:
               intersections = ray_stage_intersection(ray, stage)
               # Her intersection noktasinda scatter uretimi
               # Scatter isinlari kalan stage'lerden gecirilerek izlenir
        3. Belirli aralikla (step_size) etkilesim noktalari orneklenir
        4. Her noktada Compton etkilesim olasiligi:
           P_compton = (sigma_compton / sigma_total) * (1 - exp(-mu * delta_x))
        5. Etkilesim gerceklesirse Kahn ile sacilma acisi orneklenir
        6. Sacilmis foton enerjisi Compton formulu ile hesaplanir
        7. Sacilmis foton yeni yonunde takip edilir (kalan stage'ler dahil)
        8. Detektore ulasirsa detektor profiline katkisi kaydedilir
        """
```

## Scatter Ray-Tracing Algoritmasi (Detay)

```python
def calculate_beam_profile_with_scatter(geometry, energy_keV, num_rays, compton_config):
    primary_results = []
    scatter_results = []
    source = geometry.source.position

    for i in range(num_rays):
        angle = compute_ray_angle(i, num_rays, geometry)
        ray = Ray(origin=source, angle=angle, energy=energy_keV)

        # Multi-stage scatter: her stage icin ayri intersection
        # Her stage'in malzemesi bagimsiz scatter uretir;
        # scatter isinlari kalan stage'lerden gecer
        all_intersections = []
        passes_aperture = True
        for stage in geometry.stages:
            stage_intersections = ray_stage_intersection(ray, stage)
            all_intersections.extend(stage_intersections)
            if not passes_through_aperture(ray, stage.aperture):
                passes_aperture = False

        if passes_aperture:
            primary_results.append({"position": ..., "intensity": 1.0, "type": "primary"})
        else:
            total_mu_x = 0.0

            for intersection in all_intersections:
                material = get_material(intersection.material_id)
                mu_total = get_linear_attenuation(material, energy_keV)
                mu_compton = get_compton_attenuation(material, energy_keV)
                path_length = intersection.path_length  # cm
                total_mu_x += mu_total * path_length

                if compton_config.enabled:
                    step_size = 0.1  # cm (1mm)
                    position = intersection.entry_point
                    remaining_energy = energy_keV

                    while position < intersection.exit_point:
                        P_interact = 1 - exp(-mu_total * step_size)
                        P_compton = (mu_compton / mu_total) * P_interact

                        if random() < P_compton:
                            theta, phi, E_scattered = sample_compton_angle(remaining_energy)

                            if E_scattered > compton_config.min_energy_cutoff_keV:
                                scatter_ray = create_scatter_ray(position, ray.direction,
                                                                  theta, phi, E_scattered)
                                scatter_transmission = trace_scatter_ray(
                                    scatter_ray, geometry,
                                    compton_config.max_scatter_order - 1)

                                if scatter_transmission.reaches_detector:
                                    scatter_results.append({...})

                        position += step_size

            transmission = exp(-total_mu_x)
            primary_results.append({"position": ..., "intensity": transmission, "type": "primary"})

    return combine_primary_and_scatter(primary_results, scatter_results)
```

## Compton/Toplam Zayiflama Orani

NIST XCOM verilerinden okunur:
```
f_compton(E) = sigma_compton(E) / sigma_total(E)
```

| Enerji | Pb (Z=82) | Fe (Z=26) | Al (Z=13) |
|--------|-----------|-----------|-----------|
| 80 keV | ~0.05 | ~0.30 | ~0.75 |
| 200 keV | ~0.15 | ~0.65 | ~0.92 |
| 500 keV | ~0.45 | ~0.90 | ~0.98 |
| 1 MeV | ~0.65 | ~0.95 | ~0.99 |
| 3 MeV | ~0.55 | ~0.85 | ~0.95 |
| 6 MeV | ~0.40 | ~0.70 | ~0.85 |

> 3-6 MeV'de cift uretimi devreye girdiginden Compton orani duser.

## Canvas Gorsellestirme (scatter_overlay.py)

- Birincil isinlar: duz cizgi (mevcut)
- Sacilma etkilesim noktalari: kucuk daireler (turuncu, #FFA726)
- Sacilmis foton yollari: kesik cizgi (kirmizi, #EF4444, yari-saydam)
- Detektore ulasan sacilmis fotonlar: parlak kirmizi vurgu
- **Performans siniri:** Bu gorsellestirme sadece dusuk isin sayisinda (<100) etkinlesir

## Model Sinirliliklari (Kullaniciya gosterilecek uyari)

"Basitlestirilmis tek/cift sacilma modeli kullanilmaktadir. Sonuclar karsilastirma ve on-boyutlandirma amaclidir; kesin sacilma analizi icin Monte Carlo dogrulamasi onerilir."

| Basitlestirme | Sapma Tahmini |
|---------------|---------------|
| Tek sacilma varsayimi | Gercek sacilmayi %20-40 eksik tahmin eder |
| 2D geometri | Ucuncu boyut sacilmasi ihmal, %10-20 eksik |
| Sabit adim boyutu | <=1mm ile hata <%5 |
| Elektron takibi yok | MeV'de <%2 katki |

## Kabul Kriterleri & Benchmark Testleri

### BM-8: Klein-Nishina Ornekleme Dogrulama

| Test ID | Test | Yontem | Kabul |
|---------|------|--------|-------|
| BM-8.1 | Kahn ornekleme ortalamasi | 10^6 ornek, E=1MeV, ortalama theta | Analitik ortalamaya +/-1% yakinasma |
| BM-8.2 | Acisal dagilim histogram | 10^6 ornek -> histogram, d_sigma/d_Omega ile overlay | Chi-kare testi p > 0.01 |
| BM-8.3 | Enerji korunumu | Her ornekte E' + T = E0 | Kesin (floating-point hassasiyetinde) |

### Faz 7 Tamamlanma Kriterleri:
- [ ] Kahn algoritmasi sacilma acisi ornekliyor
- [ ] BM-8.1 — ortalama aci analitik degere yakiniyor
- [ ] BM-8.2 — acisal dagilim KN ile uyumlu
- [ ] BM-8.3 — enerji korunumu saglaniyor
- [ ] ScatterTracer tek sacilma simulasyonu calisiyor
- [ ] ScatterWorker QThread ile calisiyor (iptal edilebilir)
- [ ] SPR profili hesaplaniyor ve grafige yansitiliyor
- [ ] Canvas uzerinde sacilma noktalari gorsellestiriliyor (dusuk isin sayisinda)
- [ ] 100 birincil isin scatter simulasyonu < 10 saniye
- [ ] Scatter sonuclari genel sonuclara dahil ediliyor (sacilma fraksiyonu, SPR)

## Notlar
- Bu faz tamamen opsiyoneldir — Phase 2'deki analitik Compton hesaplari tek basina kullanilabilir
- Coklu sacilma (Full) gelecek surume birakilabilir (v1.2+)
- Performans: NumPy vektorizasyon onemli (loop'lar yavas)
- Rastgele sayi ureteci: numpy.random (hizli)
- Scatter overlay performans nedeniyle max 100 isin ile sinirli

> **FRD Referans:** §4.3 (FR-3.5.4), §7.6.4-7.6.6, §9.1, §11.5 (BM-8)
