# X-Ray TIR Collimator Design Tool

X-Ray TIR tarama sistemlerinde kullanilan kolimatorlerin tasarimi, analizi ve optimizasyonu icin PyQt6 tabanli masaustu muhendislik araci.

## Tech Stack

- **Python** >= 3.11
- **UI:** PyQt6 >= 6.6, QSS dark theme
- **Charts:** pyqtgraph >= 0.13 (realtime), matplotlib >= 3.8 (polar plots)
- **Compute:** NumPy >= 1.26, SciPy >= 1.12
- **Database:** SQLite3 (built-in)
- **PDF:** ReportLab >= 4.0
- **Packaging:** PyInstaller >= 6.0

## Dizin Yapisi

```
collimator/
├── main.py                     # Entry point
├── requirements.txt
├── CLAUDE.md                   # Bu dosya
├── frd_collimator.md           # Ana FRD dokumani (referans)
├── docs/                       # Faz dosyalari
│   ├── phase-01-infrastructure.md
│   ├── phase-02-physics-engine.md
│   ├── phase-03-canvas-editor.md
│   ├── phase-04-ray-tracing.md
│   ├── phase-05-visualization.md
│   ├── phase-06-design-management.md
│   ├── phase-07-scatter-ray-tracing.md
│   └── phase-08-polish-packaging.md
├── app/
│   ├── __init__.py
│   ├── application.py          # QApplication, tema yukleme
│   ├── main_window.py          # QMainWindow
│   ├── constants.py
│   ├── core/                   # Is mantigi (UI'dan bagimsiz)
│   │   ├── units.py            # Birim donusum (KRITIK - tek donusum noktasi)
│   │   ├── physics_engine.py
│   │   ├── material_database.py
│   │   ├── projection_engine.py # Analitik projeksiyon (phantom → detektor profili, MTF)
│   │   ├── beam_simulation.py
│   │   ├── ray_tracer.py
│   │   ├── build_up_factors.py
│   │   ├── compton_engine.py
│   │   ├── scatter_tracer.py
│   │   ├── klein_nishina_sampler.py
│   │   └── spectrum_models.py
│   ├── models/                 # Veri modelleri (dataclass)
│   │   ├── material.py
│   │   ├── geometry.py
│   │   ├── phantom.py          # Test nesneleri (Wire, LinePair, Grid)
│   │   ├── projection.py       # Projeksiyon sonuc modelleri (MTF, profil)
│   │   ├── simulation.py
│   │   └── compton.py
│   ├── ui/                     # PyQt6 arayuz
│   │   ├── styles/             # QSS tema + renk paleti
│   │   ├── canvas/             # QGraphicsScene/View kolimator editoru
│   │   ├── panels/             # Yan paneller (malzeme, katman, parametre, sonuc)
│   │   ├── charts/             # Grafik widget'lari
│   │   ├── dialogs/            # Diyalog pencereleri
│   │   ├── widgets/            # Ozel widget'lar
│   │   └── toolbar.py
│   ├── workers/                # QThread arka plan hesaplama
│   │   └── projection_worker.py # Projeksiyon hesaplama thread'i
│   ├── export/                 # PDF, CSV, JSON, image export
│   └── database/               # SQLite CRUD
├── data/
│   ├── nist_xcom/              # NIST XCOM zayiflama verileri (JSON)
│   ├── buildup_coefficients.json
│   └── collimator.db           # SQLite (runtime'da olusur)
├── resources/                  # Ikonlar, splash screen
└── tests/                      # pytest test suite
```

## Birim Sistemi (KRITIK)

Birim karisikligi en yuksek hata riskini tasir. Asagidaki kurallar kesinlikle uygulanmalidir:

### Internal birimler (app/core/)

| Buyukluk | Birim | Not |
|----------|-------|-----|
| Uzunluk | **cm** | Her yerde cm |
| Enerji | **keV** | MeV degerleri giris noktasinda cevirilir |
| Yogunluk | g/cm3 | NIST uyumlu |
| Kutle zayiflama katsayisi | cm2/g | NIST XCOM formati |
| Lineer zayiflama katsayisi | cm-1 | mu = (mu/rho) * rho |
| Tesir kesiti | cm2 | Klein-Nishina, toplam sigma |
| Kalinlik (optik) | mfp (birimsiz) | Build-up faktoru girdisi |
| Aci | **radian** | UI'da dereceye cevrilir |

### UI birimleri (app/ui/)

| Buyukluk | Birim |
|----------|-------|
| Uzunluk | **mm** |
| Enerji | **keV** veya **MeV** (kullanici secimi) |
| Aci | **derece** |

### Donusum kurallari

1. Birim donusumu **YALNIZCA** `app/core/units.py` uzerinden yapilir
2. UI -> Core cagrisindan once: `mm_to_cm()`, `deg_to_rad()`
3. Core -> UI sonuc gosteriminde: `cm_to_mm()`, `rad_to_deg()`
4. Core fonksiyonlari **asla** mm kabul etmez ve **asla** mm dondirmez
5. Build-up hesabinda: `thickness_cm -> mfp` donusumu build-up fonksiyonundan hemen once yapilir
6. Her core fonksiyonunun docstring'inde giris/cikis birimleri acikca yazilir

## Multi-Stage Mimari (v2.0)

Kolimator tasarimi **cok asamali** (multi-stage) mimariye sahiptir:

```
Kaynak → [Stage 0: Internal] → (gap) → [Stage 1: Fan] → (gap) → [Stage 2: Penumbra] → Detektor
```

- **`CollimatorStage`**: Her stage bagimsiz bir govdedir (kendi aperture, katmanlar, boyutlar)
- **`CollimatorGeometry.stages`**: `list[CollimatorStage]` — 1-N arasi stage
- **`gap_after`**: Stage uzerinde, sonraki stage'e kadar bosluk (mm). Son stage'de ignored.
- **`StagePurpose`**: PRIMARY_SHIELDING, FAN_DEFINITION, PENUMBRA_TRIMMER, vb.
- **Geriye uyumluluk**: `CollimatorBody = CollimatorStage` (deprecated alias), `geometry.body` → `stages[0]`
- Tek stage'li tasarim = eski tek-govde modeli
- **Kompozit katman**: `CollimatorLayer.inner_material_id` + `inner_width` — ic/dis zon destegi (orn. ortasi W, disi Pb)

## Kod Kurallari

### Genel
- Python 3.11+ ozellikleri kullanilabilir (match/case, tomllib, vb.)
- `dataclass` veya `Pydantic` modeller kullanilir (dict degil)
- Type hints zorunlu (fonksiyon imzalari ve donusleri)
- Docstring'lerde birim belirtme zorunlu (core/ modulleri icin)

### UI Thread Kurali
- **Tum agir hesaplamalar** (simulasyon, scatter, enerji taramasi) QThread worker uzerinden calistirilmalidir
- Ana UI thread **asla** bloklanmamalidir
- Worker'lar `progress` sinyali ile ilerleme cubugunu gunceller
- Worker'lar `result_ready` sinyali ile sonucu UI'a iletir

### Alaşim Hesabi
Alasimlarin (SS304, SS316, Bronze) mu/rho degerleri **mixture rule** ile hesaplanir:
```
(mu/rho)_alloy = SUM(w_i * (mu/rho)_i)
```

### Build-up Faktoru
- Birincil yontem: **GP (Geometric Progression)** formulu
- Alternatif: **Taylor** iki-terimli ustel formul
- Veri kaynagi: `buildup_coefficients.json`
- Cok katmanli: Kalos formulu veya son malzeme yontemi

## Test Kurallari

- Framework: **pytest**
- Benchmark testleri: `test_BM_X_Y()` format (FRD Bolum 11)
- Her test, beklenen degeri, hesaplanan degeri ve yuzde sapmayi raporlar
- Toleranslar FRD Bolum 11.2'de tanimli
- Marker: `@pytest.mark.benchmark` (CI'da otomatik calisir)
- Entegrasyon testleri: `@pytest.mark.integration` (release oncesi)

## Gelistirme Fazlari

| Faz | Dosya | Kapsam |
|-----|-------|--------|
| 1 | `docs/phase-01-infrastructure.md` | Proje iskeleti, veri modelleri, birim sistemi, DB, tema |
| 2 | `docs/phase-02-physics-engine.md` | Fizik motoru, malzeme DB, Beer-Lambert, build-up, Compton analitik |
| 3 | `docs/phase-03-canvas-editor.md` | Canvas editoru, geometri sablonlari, katman yonetimi |
| 4 | `docs/phase-04-ray-tracing.md` | Ray-tracing simulasyonu, kalite metrikleri |
| 5 | `docs/phase-05-visualization.md` | pyqtgraph/matplotlib grafikler |
| 6 | `docs/phase-06-design-management.md` | Kaydet/yukle, versiyon, PDF rapor, export |
| 7 | `docs/phase-07-scatter-ray-tracing.md` | Scatter ray-tracing (opsiyonel) |
| 8 | `docs/phase-08-polish-packaging.md` | Test, V&V, performans, PyInstaller |

## Performans Hedefleri

| Islem | Hedef |
|-------|-------|
| Tek enerji zayiflama hesabi | < 50 ms |
| Enerji taramasi (100 nokta) | < 500 ms |
| Klein-Nishina hesabi (180 bin) | < 100 ms |
| Isin profili (1000 isin, scatter yok) | < 2 s |
| Isin profili (1000 isin, tek sacilma) | < 15 s |
| Analitik projeksiyon (tek phantom) | < 200 ms |
| MTF hesabi (FFT) | < 100 ms |
| Canvas yeniden cizim | < 16 ms (60 fps) |
| PDF rapor | < 5 s |

## Mevcut Veri Dosyalari

- `buildup_coefficients.json` — GP + Taylor build-up katsayilari (mevcut)
- `data/nist_xcom/*.json` — NIST XCOM zayiflama verileri (Phase 1'de olusturulacak)
- `data/collimator.db` — SQLite DB (runtime'da otomatik olusur)
