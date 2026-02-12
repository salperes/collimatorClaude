# Phase 2 — Fizik Motoru + Compton Analitik

## Amac
Tum hesaplama motorunu implement etmek: malzeme veritabani servisi, Beer-Lambert zayiflama, build-up faktorleri (GP + Taylor), HVL/TVL, enerji/kalinlik taramasi, Compton kinemtigi, Klein-Nishina hesaplari. Bu fazda ray-tracing YOKTUR — sadece analitik hesaplamalar.

## Kapsam & Bagimliliklar
- **Bagimlilik:** Phase 1 (veri modelleri, units.py, SQLite DB, NIST verileri)
- **Bu faz tamamlandiginda:** Tum fizik hesaplamalari calisir, UI'dan bagimsiz test edilebilir
- Ray-tracing (Phase 4) ve UI grafikleri (Phase 5) bu faza bagimlidir

## Olusturulacak Dosyalar

```
app/core/
├── material_database.py    # MaterialService - malzeme CRUD + mu/rho sorgulama
├── physics_engine.py       # PhysicsEngine - Beer-Lambert, HVL/TVL, sweep
├── build_up_factors.py     # Build-up faktor hesabi (GP + Taylor)
├── compton_engine.py       # ComptonEngine - Klein-Nishina, kinemati, sigma_KN
├── spectrum_models.py      # kVp/MeV spektrum modelleri

tests/
├── test_physics_engine.py  # BM-1 ile BM-6 arasi
├── test_materials.py       # Malzeme ve alasim testleri
├── test_compton.py         # BM-7 Klein-Nishina testleri
├── test_buildup.py         # BM-5, BM-6 build-up testleri
```

## API Arayuzleri

### MaterialService (app/core/material_database.py)

```python
class MaterialService:
    def get_all_materials(self) -> list[Material]: ...
    def get_material(self, material_id: str) -> Material: ...
    def get_attenuation_data(self, material_id: str,
                             min_energy_keV: float = 1.0,
                             max_energy_keV: float = 20000.0) -> list[AttenuationDataPoint]: ...
    def get_mu_rho(self, material_id: str, energy_keV: float) -> float:
        """
        Belirli enerji icin kutle zayiflama katsayisi dondurur.
        Iki veri noktasi arasinda log-log interpolasyon kullanilir.

        Args:
            material_id: Malzeme ID ("Pb", "W", vb.)
            energy_keV: Foton enerjisi [keV]
        Returns:
            mu_rho: Kutle zayiflama katsayisi [cm2/g]
        """
    def get_mu_rho_alloy(self, composition: list[Composition], energy_keV: float) -> float:
        """
        Alasim icin mixture rule ile mu/rho hesaplar:
        (mu/rho)_alloy = SUM(w_i * (mu/rho)_i)

        Args:
            composition: Alasim bilesimi listesi
            energy_keV: Foton enerjisi [keV]
        Returns:
            mu_rho: Alasim kutle zayiflama katsayisi [cm2/g]
        """
```

### PhysicsEngine (app/core/physics_engine.py)

```python
class PhysicsEngine:
    def __init__(self, material_service: MaterialService): ...

    def linear_attenuation(self, material_id: str, energy_keV: float) -> float:
        """
        mu [cm-1] = (mu/rho) * rho
        """

    def calculate_attenuation(self, layers: list[CollimatorLayer],
                              energy_keV: float,
                              include_buildup: bool = False) -> AttenuationResult:
        """
        Cok katmanli Beer-Lambert zayiflama:
        I/I0 = exp(-SUM(mu_i * x_i))
        Build-up dahilse: I/I0 = B(E, mu*x) * exp(-SUM(mu_i * x_i))

        Args:
            layers: Kolimator katmanlari
            energy_keV: Foton enerjisi [keV]
            include_buildup: Build-up faktoru dahil mi
        Returns:
            AttenuationResult: iletim, zayiflama_dB, katman bazli sonuclar
        """

    def energy_sweep(self, layers: list[CollimatorLayer],
                     min_keV: float, max_keV: float, steps: int,
                     include_buildup: bool = False) -> list[AttenuationResult]:
        """Belirli enerji araliginda tarama yapar."""

    def calculate_hvl_tvl(self, material_id: str, energy_keV: float) -> HvlTvlResult:
        """
        HVL = ln(2) / mu [cm] -> mm'ye cevrilecek (UI tarafinda)
        TVL = ln(10) / mu [cm]
        MFP = 1 / mu [cm]
        """

    def thickness_sweep(self, material_id: str, energy_keV: float,
                        max_thickness_mm: float, steps: int) -> list[ThicknessSweepPoint]:
        """Belirli kalinlik araliginda iletim taramasi."""
```

> **Multi-Stage Not:** `calculate_attenuation` ve `energy_sweep` metodlarindaki
> `layers: list[CollimatorLayer]` parametresi artik tek bir stage'in katmanlarini temsil eder.
> Cok asamali kolimatorde her stage icin ayri ayri cagirilir; stage'ler arasi
> birlestirme ust katmanda (ray-tracer veya orchestrator) yapilir.
> Eski `geometry.body.layers` erisimi artik `geometry.stages[i].layers` seklindedir.
> `CollimatorBody` deprecated alias olarak `CollimatorStage`'e yonlendirilmistir (bkz. Phase 1).

### BuildUpFactors (app/core/build_up_factors.py)

```python
class BuildUpFactors:
    def __init__(self, coefficients_path: str = "data/buildup_coefficients.json"): ...

    def gp_buildup(self, energy_keV: float, mfp: float, material_id: str) -> float:
        """
        GP (Geometric Progression) formulu:
        B(E, x) = 1 + (b-1)(K^x - 1)/(K-1)    K != 1
        B(E, x) = 1 + (b-1)x                    K = 1

        K(x) = c*x^a + d*[tanh(x/Xk - 2) - tanh(-2)] / [1 - tanh(-2)]

        5 fitting parametresi: b, c, a, Xk, d

        Args:
            energy_keV: Foton enerjisi [keV]
            mfp: Optik kalinlik [mfp, birimsiz]
            material_id: Malzeme ID
        Returns:
            B: Build-up faktoru [birimsiz]
        """

    def taylor_buildup(self, energy_keV: float, mfp: float, material_id: str) -> float:
        """
        Taylor formulu:
        B(E, mu*x) = A1 * exp(-alpha1 * mu*x) + (1-A1) * exp(-alpha2 * mu*x)

        3 fitting parametresi: A1, alpha1, alpha2
        """

    def get_multilayer_buildup(self, layers_mfp: list[tuple], energy_keV: float,
                                method: str = "last_material") -> float:
        """
        Cok katmanli build-up:
        - "last_material": Son malzemenin B degeri toplam mfp ile
        - "kalos": B_total = B1(mu1*x1) * B2(mu2*x2)
        - "equivalent_z": Kompozitin Zeq ile tek malzeme gibi
        """
```

### ComptonEngine (app/core/compton_engine.py)

```python
class ComptonEngine:
    # Sabitler
    ELECTRON_MASS_KEV = 511.0              # m_e*c2 [keV]
    CLASSICAL_ELECTRON_RADIUS = 2.818e-13  # r0 [cm]
    COMPTON_WAVELENGTH = 0.02426           # lambda_C [Angstrom]
    THOMSON_CROSS_SECTION = 6.6524e-25     # sigma_T [cm2]

    def scattered_energy(self, E0_keV: float, theta_rad: float) -> float:
        """
        Compton sacilmis foton enerjisi:
        E' = E0 / [1 + (E0/511)(1 - cos(theta))]

        Args:
            E0_keV: Gelen foton enerjisi [keV]
            theta_rad: Sacilma acisi [radian]
        Returns:
            E_prime: Sacilmis foton enerjisi [keV]
        """

    def recoil_electron_energy(self, E0_keV: float, theta_rad: float) -> float:
        """
        Geri sekme elektron enerjisi:
        T = E0 - E' = E0 * [alpha*(1-cos(theta))] / [1 + alpha*(1-cos(theta))]
        """

    def compton_edge(self, E0_keV: float) -> tuple[float, float]:
        """
        Compton kenari (180 derece sacilma):
        E'_min = E0 / (1 + 2*alpha)
        T_max = E0 * 2*alpha / (1 + 2*alpha)
        Returns: (E_prime_min, T_max)
        """

    def wavelength_shift(self, theta_rad: float) -> float:
        """
        Dalga boyu kaymasi:
        Delta_lambda = lambda_C * (1 - cos(theta)) [Angstrom]
        """

    def klein_nishina_differential(self, E0_keV: float, theta_rad: float) -> float:
        """
        Klein-Nishina diferansiyel tesir kesiti:
        d_sigma/d_Omega = (r0^2/2) * (E'/E0)^2 * [E'/E0 + E0/E' - sin^2(theta)]

        Returns: d_sigma/d_Omega [cm2/sr/elektron]
        """

    def klein_nishina_distribution(self, energy_keV: float,
                                   angular_bins: int = 180) -> KleinNishinaResult:
        """0-180 derece araliginda KN dagilimi hesaplar."""

    def total_cross_section(self, E0_keV: float) -> float:
        """
        Toplam Klein-Nishina tesir kesiti (sigma_KN):
        sigma_KN = 2*pi*r0^2 * { [(1+a)/a^2]*[2(1+a)/(1+2a) - ln(1+2a)/a]
                                  + ln(1+2a)/(2a) - (1+3a)/(1+2a)^2 }

        Returns: sigma_KN [cm2/elektron]
        """

    def scattered_energy_spectrum(self, energy_keV: float,
                                  num_bins: int = 100) -> ComptonSpectrumResult:
        """Sacilmis foton enerji dagilimi histogrami."""

    def angle_energy_map(self, energy_keV: float,
                         angular_steps: int = 361) -> AngleEnergyMapResult:
        """Aci vs enerji haritasi (E', T, Delta_lambda)."""

    def cross_section_vs_energy(self, min_keV: float, max_keV: float,
                                steps: int) -> CrossSectionResult:
        """Enerji araliginda sigma_KN degisimi."""
```

## Fizik Formulleri

### Beer-Lambert Zayiflama
```
Tek katman:    I/I0 = exp(-mu * x)
Cok katman:    I/I0 = exp(-SUM(mu_i * x_i)) = PRODUCT(exp(-mu_i * x_i))
Build-up ile:  I/I0 = B(E, mu*x) * exp(-mu*x)
```

#### Multi-Stage Zayiflama

Cok asamali kolimatorde her stage bagimsiz olarak degerlendirilir:

```
I/I₀ = ∏(stage) [ exp(-Σ(layer in stage)(μᵢ × xᵢ)) ]
```

Stage'ler arasi bosluklar (gap) hava/vakum olarak kabul edilir — zayiflama katkisi sifir.
Her stage'in kendi aperture'u vardir; isin bir stage'in aperture'unden gecebilir
ama baska bir stage'in malzemesine carpabilir.

Build-up faktoru: Her stage icin kendi baskin malzemesi ve optik kalinligi (mfp) ile
ayri ayri hesaplanir.

### HVL / TVL / MFP
```
HVL = ln(2) / mu = 0.693 / mu    [cm]
TVL = ln(10) / mu = 2.303 / mu   [cm]
MFP = 1 / mu                      [cm]
```

### Zayiflama dB cinsinden
```
Attenuation (dB) = -10 * log10(I/I0)
```

### Log-log interpolasyon (NIST verileri icin)
```python
def interpolate_mu_rho(energy_keV, data_points):
    log_energies = np.log(data_points["energy_keV"])
    log_mu_rho = np.log(data_points["mass_attenuation"])
    log_E = np.log(energy_keV)
    return np.exp(np.interp(log_E, log_energies, log_mu_rho))
```

### Alasim Karisim Kurali
```
(mu/rho)_alloy = SUM(w_i * (mu/rho)_i)
```
w_i = elemanin agirlik fraksiyonu, (mu/rho)_i = elemanin zayiflama katsayisi.

### GP Build-up Formulu (Birincil)
```
B(E, x) = 1 + (b-1)(K^x - 1)/(K-1)    K != 1
B(E, x) = 1 + (b-1)x                    K = 1

K(x) = c*x^a + d*[tanh(x/Xk - 2) - tanh(-2)] / [1 - tanh(-2)]
```
5 parametre: b, c, a, Xk, d — `buildup_coefficients.json` dosyasindan okunur.

### Taylor Build-up Formulu (Alternatif)
```
B(E, mu*x) = A1 * exp(-alpha1 * mu*x) + (1-A1) * exp(-alpha2 * mu*x)
```
3 parametre: A1, alpha1, alpha2.

### Cok Katmanli Build-up Yontemleri
1. **Son malzeme yontemi:** En distaki malzemenin B degeri toplam mfp ile (konservatif)
2. **Kalos formulu:** B_total = B1(mu1*x1) * B2(mu2*x2) — iki katman icin +/-10-15%
3. **Esdeger malzeme:** Kompozitin Zeq hesaplanip tek malzeme gibi (+/-15-20%)

### Compton Kinemtigi
```
E' = E0 / [1 + (E0/511)(1 - cos(theta))]     # Sacilmis foton enerjisi
T = E0 - E'                                     # Geri sekme elektron enerjisi
E'_min = E0 / (1 + 2*alpha)                    # Compton kenari (180 derece)
T_max = E0 * 2*alpha / (1 + 2*alpha)           # Maksimum elektron enerjisi
Delta_lambda = 0.02426 * (1 - cos(theta))       # Dalga boyu kaymasi [Angstrom]
```
alpha = E0 / 511 keV

### Klein-Nishina Diferansiyel Tesir Kesiti
```
d_sigma/d_Omega = (r0^2/2) * (E'/E0)^2 * [E'/E0 + E0/E' - sin^2(theta)]
```
r0 = 2.818e-13 cm (klasik elektron yaricapi)

### Thomson Limiti (dusuk enerji, alpha -> 0)
```
d_sigma/d_Omega |_Thomson = (r0^2/2) * (1 + cos^2(theta))
sigma_Thomson = 6.6524e-25 cm2
```

### Toplam Klein-Nishina Tesir Kesiti
```
sigma_KN = 2*pi*r0^2 * { [(1+a)/a^2]*[2(1+a)/(1+2a) - ln(1+2a)/a]
                          + ln(1+2a)/(2a) - (1+3a)/(1+2a)^2 }
```
- Elektron basina: cm2/elektron
- Atom basina: sigma_atom = Z * sigma_KN
- Lineer zayiflama: mu_compton = (N_A * rho / A) * Z * sigma_KN

### kVp Spektrum Modeli
```
Phi(E) proportional to Z * (E_max - E) / E    # Kramers yaklasimi
E_avg ~ kVp / 3    (filtresiz)
E_avg ~ kVp / 2.5  (Al filtreli)
```

### MeV Spektrum
- Ortalama enerji ~ E_endpoint / 3
- Ilk surum icin monoenerjik yaklasim yeterlidir

## Enerji Preset'leri

| Preset | Enerji | Kullanim |
|--------|--------|----------|
| Bagaj Tarama | 80 kVp | Havalimani bagaj |
| Kargo Dusuk | 160 kVp | Palet/koli |
| Kargo Orta | 320 kVp | Arac tarama |
| LINAC Dusuk | 1 MeV | Arac tarama |
| LINAC Orta | 3.5 MeV | Konteyner |
| LINAC Yuksek | 6 MeV | Yuksek yogunluk |

## Model Sinirliliklari

### LINAC / MeV icin uyari:
"LINAC kaynagi icin basitlestirilmis monoenerjik model kullanilmaktadir. Gercek bremsstrahlung spektrumu, flattening filter ve beam hardening etkileri modellenmez. Sonuclar kolimator boyutlandirma ve karsilastirma amaclidir; mutlak leakage degerleri icin Monte Carlo dogrulamasi (MCNP/FLUKA/Geant4) onerilir."

### Modellenmeyen etkiler:
- Gercek bremsstrahlung spektrumu (+/-10-15% konservatif sapma)
- Flattening filter (TIR'da genellikle yok)
- Beam hardening (monoenerjik model ihmal eder, konservatif)
- Head scatter (<%5 etki)
- Off-axis softening (<%3 etki)

## Kabul Kriterleri & Benchmark Testleri

### BM-1: Kursun (Pb) Zayiflama Katsayilari (NIST XCOM referans)

| Test ID | Enerji (keV) | mu/rho beklenen (cm2/g) | HVL beklenen (mm) | TVL beklenen (mm) | Tolerans |
|---------|--------------|------------------------|--------------------|--------------------|----------|
| BM-1.1 | 88 (K-edge ustu) | 5.021 | 0.122 | 0.404 | +/-1% |
| BM-1.2 | 100 | 5.549 | 0.110 | 0.366 | +/-1% |
| BM-1.3 | 200 | 0.999 | 0.611 | 2.030 | +/-1% |
| BM-1.4 | 500 | 0.1614 | 3.78 | 12.56 | +/-1% |
| BM-1.5 | 662 (Cs-137) | 0.1101 | 5.55 | 18.42 | +/-1% |
| BM-1.6 | 1000 | 0.0708 | 8.62 | 28.64 | +/-1% |
| BM-1.7 | 1250 (Co-60 avg) | 0.0578 | 10.56 | 35.08 | +/-1% |
| BM-1.8 | 2000 | 0.0455 | 13.42 | 44.58 | +/-1% |
| BM-1.9 | 6000 | 0.0388 | 15.73 | 52.25 | +/-2% |

> Pb K-edge: 88.0 keV

### BM-2: Tungsten (W) Zayiflama Katsayilari

| Test ID | Enerji (keV) | mu/rho beklenen (cm2/g) | HVL beklenen (mm) | Tolerans |
|---------|--------------|------------------------|--------------------|----------|
| BM-2.1 | 70 (K-edge ustu) | 4.027 | 0.089 | +/-1% |
| BM-2.2 | 100 | 4.438 | 0.081 | +/-1% |
| BM-2.3 | 500 | 0.1370 | 2.62 | +/-1% |
| BM-2.4 | 1000 | 0.0620 | 5.79 | +/-1% |
| BM-2.5 | 6000 | 0.0390 | 9.20 | +/-2% |

> W K-edge: 69.5 keV

### BM-3: Demir (Fe) / Celik Referans

| Test ID | Malzeme | Enerji (keV) | mu/rho beklenen | Tolerans |
|---------|---------|--------------|-----------------|----------|
| BM-3.1 | Fe | 100 | 0.3717 | +/-1% |
| BM-3.2 | Fe | 662 | 0.07379 | +/-1% |
| BM-3.3 | Fe | 1000 | 0.05995 | +/-1% |
| BM-3.4 | SS304 (alasim) | 662 | ~0.074 | +/-3% |
| BM-3.5 | SS304 (alasim) | 1000 | ~0.060 | +/-3% |

### BM-4: Cok Katmanli Zayiflama

| Test ID | Konfigrasyon | Enerji (keV) | Beklenen Iletim | Tolerans |
|---------|--------------|--------------|-----------------|----------|
| BM-4.1 | 10mm Pb | 1000 | exp(-0.8036) = 0.4478 | +/-2% |
| BM-4.2 | 5mm Pb + 5mm Fe | 1000 | 0.5293 | +/-2% |
| BM-4.3 | 20mm W | 500 | 0.0051 | +/-5% |
| BM-4.4 | 0mm (bos) | herhangi | 1.000 | kesin |
| BM-4.5 | 100mm Pb | 100 | ~0 (< 1e-20) | < 1e-20 |

### BM-5: GP Formulu Dogrulama (ANSI/ANS-6.4.3 referans)

| Test ID | Malzeme | Enerji (MeV) | mfp | B beklenen | Tolerans |
|---------|---------|--------------|-----|------------|----------|
| BM-5.1 | Pb | 1.0 | 1 | 1.37 | +/-5% |
| BM-5.2 | Pb | 1.0 | 5 | 2.39 | +/-5% |
| BM-5.3 | Pb | 1.0 | 10 | 3.26 | +/-5% |
| BM-5.4 | Pb | 1.0 | 20 | 4.60 | +/-8% |
| BM-5.5 | Pb | 1.0 | 40 | 6.62 | +/-10% |
| BM-5.6 | Pb | 0.5 | 5 | ~1.8 | +/-10% |
| BM-5.7 | Fe | 1.0 | 5 | ~4.2 | +/-10% |
| BM-5.8 | W | 1.0 | 5 | ~2.2 | +/-10% |

### BM-6: GP vs Taylor Capraz Dogrulama

| Test ID | Malzeme | Enerji (MeV) | mfp | Kabul: fark < |
|---------|---------|--------------|-----|---------------|
| BM-6.1 | Pb | 1.0 | 5 | 15% |
| BM-6.2 | Pb | 0.5 | 10 | 15% |
| BM-6.3 | Fe | 1.0 | 10 | 15% |

### BM-7: Klein-Nishina Analitik Dogrulama

| Test ID | Test | Beklenen | Tolerans |
|---------|------|----------|----------|
| BM-7.1 | sigma_KN(E->0) | sigma_Thomson = 6.6524e-25 cm2 | +/-0.1% |
| BM-7.2 | sigma_KN(511 keV) | 2.716e-25 cm2 | +/-0.5% |
| BM-7.3 | sigma_KN(1 MeV) | 1.772e-25 cm2 | +/-0.5% |
| BM-7.4 | sigma_KN(6 MeV) | 0.494e-25 cm2 | +/-0.5% |
| BM-7.5 | d_sigma/d_Omega(0 deg, 10 keV) | ~ Thomson d_sigma/d_Omega(0 deg) = r0^2 | +/-2% |
| BM-7.6 | d_sigma/d_Omega(90 deg, 10 keV) | ~ Thomson d_sigma/d_Omega(90 deg) = r0^2/2 | +/-2% |
| BM-7.7 | E'(1 MeV, 180 deg) | 169 keV (Compton kenari) | +/-0.1% |
| BM-7.8 | E'(6 MeV, 90 deg) | 427 keV | +/-0.1% |
| BM-7.9 | Delta_lambda(90 deg) | 0.02426 Angstrom | kesin |
| BM-7.10 | Delta_lambda(180 deg) | 0.04852 Angstrom | kesin |

### Genel Toleranslar:

| Hesaplama | Maks Hata |
|-----------|-----------|
| mu/rho (NIST XCOM) | +/-1% |
| Lineer mu | +/-1% |
| HVL / TVL | +/-2% |
| Alasim karisim kurali | +/-3% |
| Build-up GP (<=20 mfp) | +/-5% |
| Build-up GP (>20 mfp) | +/-10% |
| Build-up Taylor (<=10 mfp) | +/-10% |
| Klein-Nishina sigma_KN | +/-0.5% |
| Compton enerji | +/-0.1% |

### Faz 2 Tamamlanma Kriterleri:
- [ ] MaterialService tum 8 malzeme icin mu/rho dondurur
- [ ] Log-log interpolasyon calisiyor
- [ ] Alasim mixture rule calisiyor (SS304, SS316, Bronze)
- [ ] PhysicsEngine tek ve cok katmanli zayiflama hesaplar
- [ ] Energy sweep ve thickness sweep calisir
- [ ] GP ve Taylor build-up faktoru hesaplanir
- [ ] ComptonEngine: E', T, Compton kenari, Delta_lambda hesaplar
- [ ] Klein-Nishina d_sigma/d_Omega ve sigma_KN hesaplar
- [ ] BM-1 ile BM-7 arasi tum benchmark testleri gecer
- [ ] Tum core fonksiyonlari docstring'de birim belirtir

## Notlar
- Bu fazda UI grafikleri YOKTUR — grafik implementation Phase 5'te
- ComptonEngine sadece analitik hesaplamalar yapar, ray-tracing YOKTUR (Phase 7)
- buildup_coefficients.json dosyasi projede zaten mevcuttur
- NIST XCOM verileri Phase 1'de hazirlanmis olmalidir
- Compton/toplam zayiflama orani NIST verilerinden okunur (her malzeme icin farkli)

> **FRD Referans:** §4.2, §7.1-7.4, §7.6.1-7.6.3, §5.1-5.2, §5.4, §8.1, §11.3-11.5
