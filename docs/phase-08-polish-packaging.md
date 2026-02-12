# Phase 8 — Cilalama, Paketleme ve Test

## Amac
Tum modullerin entegrasyon testi, V&V (dogrulama), performans optimizasyonu, UI cilalama, PyInstaller ile paketleme.

## Kapsam & Bagimliliklar
- **Bagimlilik:** Phase 1-6 tamamlanmis olmali (Phase 7 opsiyonel)
- **Son faz** — uretim hazirlik calismasi

## Olusturulacak/Guncellenen Dosyalar

```
build.spec                    # PyInstaller build konfigurasyonu
scripts/
├── build_exe.py              # PyInstaller tek dosya build
└── build_portable.py         # Portable klasor build

tests/
├── test_integration.py       # Entegrasyon testleri (BM-10 genisleme)
└── conftest.py               # Ortak test fixture'lari

resources/
├── icons/
│   ├── app_icon.ico          # Windows
│   ├── app_icon.icns         # macOS
│   ├── app_icon.png          # Linux
│   ├── fan_beam.svg
│   ├── pencil_beam.svg
│   ├── slit.svg
│   └── toolbar/              # Arac cubugu ikonlari
└── splash.png                # Acilis ekrani
```

## Gorevler

### 1. Entegrasyon Testi
- Tum modullerin birlikte calisma testi
- Tam simulasyon senaryosu: geometri olustur -> ray-trace -> metrik hesapla -> PDF rapor
- Farkli kolimator tipleri (fan/pencil/slit) icin tam donus testi
- Farkli enerji seviyeleri (80kVp - 6MeV) testi
- Kaydedilip yuklenip tekrar simulasyon calistirma testi

### 2. V&V (Dogrulama) Calistirilmasi
- Tum BM-1 ile BM-10 arasi benchmark testlerini calistir
- Test raporu olustur: `pytest --html=validation_report.html`
- Her basarisiz test icin koken neden analizi
- Referans kaynaklarla son karsilastirma

#### Dogrulama Stratejisi:

| Seviye | Aciklama | Yontem |
|--------|----------|--------|
| V1 — Birim Dogrulama | Her core fonksiyonu bagimsiz test | pytest, analitik formul karsilastirma |
| V2 — Referans Karsilastirma | NIST XCOM, ANSI/ANS-6.4.3 ile | Yayinlanmis referans veriler |
| V3 — Capraz Dogrulama | GP vs Taylor, HVL iki yontem | Farkli yontemlerle ayni sonuc |
| V4 — Uc Durum | Sifir kalinlik, cok kalin, K-edge | Sinir kosullari |
| V5 — Entegrasyon | Tam simulasyon senaryosu | Geometri -> ray-trace -> metrik |

#### Genel Toleranslar:

| Hesaplama | Maks Hata |
|-----------|-----------|
| mu/rho (NIST) | +/-1% |
| HVL/TVL | +/-2% |
| Alasim karisim | +/-3% |
| Build-up GP (<=20 mfp) | +/-5% |
| Build-up GP (>20 mfp) | +/-10% |
| Klein-Nishina sigma_KN | +/-0.5% |
| Isin profili iletim (build-up yok) | +/-2% |
| Isin profili iletim (build-up dahil) | +/-10% |
| Penumbra genisligi | +/-5% veya +/-0.5mm |
| Scatter ray-tracing | +/-30% (kalitatif) |

### 3. Performans Optimizasyonu

| Islem | Hedef |
|-------|-------|
| Tek enerji zayiflama | < 50 ms |
| Enerji taramasi (100 nokta) | < 500 ms |
| Klein-Nishina (180 bin) | < 100 ms |
| Isin profili (1000 isin, scatter yok) | < 2 s |
| Isin profili (1000 isin, tek sacilma) | < 15 s |
| Canvas yeniden cizim | < 16 ms (60 fps) |
| PDF rapor | < 5 s |

Optimizasyon stratejileri:
- NumPy vektorizasyon (loop yerine array islemleri)
- SciPy interpolasyon (log-log interp icin scipy.interpolate)
- QThread worker pool (concurrent.futures ThreadPoolExecutor)
- pyqtgraph downsampling (buyuk veri setleri icin)
- QGraphicsScene item caching (setCacheMode)

### 4. UI Cilalama
- QSS polish: tum widget'larin tutarli gorunumu
- Ikon seti: toolbar, kolimator tipleri, durum gostergeci
- Splash screen (acilis ekrani)
- MeV modu uyari mesaji implementasyonu
- Scatter uyari mesaji implementasyonu
- Klavye kisayollari tutarlilik kontrolu
- Tab order kontrolu
- Tooltip'ler tum onemli ogeler icin

### 5. Pencere Duzeni Yonetimi
- QSettings ile pencere pozisyonu, boyutu kaydetme
- Panel durumlar (acik/kapali, boyut) kaydetme
- Son acilan tasarim kaydetme
- F11 tam ekran modu
- Sonraki acilista geri yukleme

### 6. PyInstaller Paketleme

#### Installer (tek .exe)
```python
# build.spec
a = Analysis(
    ['main.py'],
    datas=[
        ('data/', 'data/'),
        ('resources/', 'resources/'),
        ('app/ui/styles/', 'app/ui/styles/'),
    ],
    hiddenimports=['pyqtgraph', 'matplotlib.backends.backend_qt5agg'],
)
exe = EXE(pyz, a.scripts, a.binaries, a.datas,
    name='CollimatorDesignTool',
    icon='resources/icons/app_icon.ico',
    onefile=True,
)
```

#### Portable (klasor)
```python
exe = EXE(pyz, a.scripts,
    name='CollimatorDesignTool',
    onefile=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name='CollimatorDesignTool_Portable')
```
- Portable: USB'den calisir, kullanici verileri `user_data/` altinda

### 7. Dosya Uzantisi Iliskilendirme
- .cdt dosyasi cift tikla uygulamayi acar (installer surumunde)
- Windows: registry kaydi
- macOS: Info.plist UTI tanimlama

### 8. Platform Testi
- Windows 10/11
- macOS 12+
- Linux (Ubuntu 22.04+)
- Her platformda: pencere, canvas, grafikler, PDF, DB testi

## Test Surec Kurallari

1. Tum BM testleri `tests/` icinde pytest ile otomatize
2. Test isimleri: `test_BM_X_Y()` formati
3. Benchmark marker: `@pytest.mark.benchmark`
4. Entegrasyon marker: `@pytest.mark.integration`
5. Her commit'te BM-1 ile BM-9 otomatik calisir
6. BM-10 her release oncesi calistirilir
7. Basarisiz test: beklenen, hesaplanan, yuzde sapma ve referans kaynak belirtir
8. Dogrulama raporu: `pytest --html=validation_report.html`

## Kabul Kriterleri

- [ ] Tum BM-1 ile BM-10 benchmark testleri geciyor
- [ ] Entegrasyon testi: tam senaryo (geometri -> simulasyon -> rapor) basarili
- [ ] Performans hedefleri karsilaniyor
- [ ] UI tutarli ve cilali gorunuyor (koyu tema)
- [ ] Ikon seti tam
- [ ] MeV ve scatter uyari mesajlari gosteriliyor
- [ ] QSettings pencere duzeni kaydetme/geri yukleme calisiyor
- [ ] PyInstaller .exe build basarili (Windows)
- [ ] Portable build basarili
- [ ] .cdt dosya iliskilendirme calisiyor
- [ ] En az Windows ve bir ek platformda (macOS veya Linux) test edilmis

## Gelecek Surum Notlari (v2+ Kapsam Disi)

Bu surumde YOKTUR, ancak mimari genisletilebilir olmalidir:
1. Coklu sacilma ray-tracing (Full) — importance sampling, varyans azaltma
2. Monte Carlo simulasyonu — MCNP/Geant4 entegrasyonu
3. 3D gorsellestirme — Qt3D veya VTK
4. Spektrum editoru — SpekCalc benzeri
5. Cok yaprakli kolimator (MLC) destegi
6. Maliyet optimizasyonu — malzeme maliyeti + agirlik + performans
7. Coklu dil (i18n) — TR/EN
8. Kullanici tanimli malzeme ekleme

## Referans Kaynaklar

| Kisaltma | Referans | Kullanim |
|----------|----------|----------|
| NIST XCOM | Berger et al., NBSIR 87-3597 | mu/rho degerleri |
| ANSI/ANS-6.4.3 | 1991, Gamma-Ray Buildup Factors | Build-up tablo |
| WAPD-1628 | Shure & Wallace, 1988 | Taylor parametreleri |
| DLC-129 | ORNL/RSIC-49/R1 | GP katsayilari |
| Harima (1986) | Nucl. Sci. Eng., 94, 24-35 | GP formulu |
| Klein & Nishina (1929) | Z. Physik, 52, 853 | KN formulu |
| NCRP-151 | Report No. 151, 2005 | Zirhlama standartlari |
| IEC 60601-2-44 | X-ray CT equipment | Penumbra/leakage tanimlari |

> **FRD Referans:** §2.5, §8.4, §9, §11, §12
