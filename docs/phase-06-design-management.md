# Phase 6 — Tasarim Yonetimi ve Disa Aktarim

## Amac

Tasarim kaydetme/yukleme, versiyon gecmisi, simulasyon sonuclari saklama, .cdt proje dosyasi, PDF rapor, CSV/JSON/PNG disa aktarim.

## Kapsam & Bagimliliklar

- **Bagimlilik:** Phase 1 (DB semasi), Phase 3 (canvas), Phase 4 (simulasyon sonuclari), Phase 5 (grafikler)
- **Tum onceki fazlar tamamlanmis olmalidir**

## Olusturulacak Dosyalar

```
app/database/
├── material_repository.py   # Malzeme CRUD (Phase 1'de baslangic, burada tamamlanir)
└── design_repository.py     # Tasarim CRUD + versiyon + simulasyon sonuclari

app/ui/dialogs/
├── __init__.py
├── export_dialog.py         # Disa aktarim diyalogu
├── design_manager.py        # Tasarim kaydet/yukle diyalogu
├── simulation_dialog.py     # Simulasyon konfigurasyon diyalogu
└── about_dialog.py          # Hakkinda diyalogu

app/export/
├── __init__.py
├── pdf_report.py            # ReportLab ile PDF rapor
├── csv_export.py            # CSV disa aktarim
├── json_export.py           # Proje/geometri JSON
└── image_export.py          # Canvas PNG/SVG disa aktarim

app/workers/
└── export_worker.py         # QThread — PDF/CSV olusturma
```

## API Arayuzleri

### DesignRepository (app/database/design_repository.py)

> **Not:** `CollimatorGeometry` icindeki `CollimatorBody` sinifi artik `CollimatorStage` olarak yeniden adlandirilmistir.
> Geriye uyumluluk icin `CollimatorBody` deprecated alias olarak korunmaktadir.
> Yeni kod `CollimatorStage` kullanmalidir.

```python
class DesignRepository:
    # --- Tasarim CRUD ---
    def list_designs(self, filter_type: str = None, filter_tag: str = None,
                     favorites_only: bool = False) -> list[DesignSummary]: ...
    def save_design(self, geometry: CollimatorGeometry, name: str,
                    description: str = "", tags: list[str] = None) -> str: ...
    def load_design(self, design_id: str) -> CollimatorGeometry: ...
    def update_design(self, design_id: str, geometry: CollimatorGeometry,
                      change_note: str = None) -> None: ...
    # Her update'te otomatik versiyon olusturulur (design_versions tablosu)
    def delete_design(self, design_id: str) -> None: ...
    def toggle_favorite(self, design_id: str) -> None: ...
    def update_thumbnail(self, design_id: str, thumbnail: bytes) -> None: ...

    # --- Versiyon Gecmisi ---
    def get_version_history(self, design_id: str) -> list[DesignVersion]: ...
    def load_version(self, design_id: str, version_number: int) -> CollimatorGeometry: ...
    def restore_version(self, design_id: str, version_number: int) -> None: ...

    # --- Simulasyon Sonuclari ---
    def save_simulation_result(self, design_id: str, config: SimulationConfig,
                               result: SimulationResult, name: str = None) -> str: ...
    def list_simulation_results(self, design_id: str) -> list[SimulationSummary]: ...
    def load_simulation_result(self, simulation_id: str) -> SimulationResult: ...
    def delete_simulation_result(self, simulation_id: str) -> None: ...

    # --- Notlar ---
    def add_note(self, parent_type: str, parent_id: str, content: str) -> str: ...
    def get_notes(self, parent_type: str, parent_id: str) -> list[dict]: ...
    def delete_note(self, note_id: str) -> None: ...

    # --- Proje Dosyasi (.cdt) ---
    def export_project_file(self, design_id: str, output_path: str) -> None: ...
    def import_project_file(self, input_path: str) -> str: ...

    # --- Ayarlar ---
    def get_setting(self, key: str, default: str = None) -> str: ...
    def set_setting(self, key: str, value: str) -> None: ...
    def get_recent_designs(self, limit: int = 10) -> list[DesignSummary]: ...
```

### ExportService

```python
class PdfReportExporter:
    def generate_report(self, geometry: CollimatorGeometry,
                        simulation_result: SimulationResult,
                        output_path: str,
                        include_sections: list[str] = None) -> None: ...

class CsvExporter:
    def export_attenuation(self, results: list[AttenuationResult], output_path: str) -> None: ...
    def export_beam_profile(self, result: SimulationResult, output_path: str) -> None: ...

class ImageExporter:
    def export_canvas(self, scene: QGraphicsScene, output_path: str, format: str = "png") -> None: ...

class JsonExporter:
    def export_geometry(self, geometry: CollimatorGeometry, output_path: str) -> None: ...
    def import_geometry(self, input_path: str) -> CollimatorGeometry: ...
```

## Fonksiyonel Gereksinimler

### FR-1.6.1 Tasarim Kaydetme

- Ctrl+S: Aktif tasarimi kaydet. Ilk kaydda isim/aciklama/etiket diyalogu
- Ctrl+Shift+S: Farkli Kaydet — kopyayi yeni isimle olustur
- Her kaydda otomatik versiyon (design_versions tablosu)
- Opsiyonel degisiklik notu
- Thumbnail (200x150 px) otomatik olusturulur
- Baslik cubugunda tasarim adi, kaydedilmemis degisiklik icin yildiz (*)

### FR-1.6.2 Tasarim Yukleme

- Ctrl+O: Tasarim yukleme diyalogu
- Liste gosterimi: thumbnail, isim, kolimator tipi, tarih, etiketler, favori
- Filtreleme: kolimator tipi, etiket, yalniz favoriler
- Arama: isim ve aciklama icinde metin arama
- Son kullanilan tasarimlar: Dosya > Son Kullanilanlar menusu

### FR-1.6.3 Versiyon Gecmisi

- Panel/diyalog ile goruntuleme
- Her versiyon: numara, tarih/saat, degisiklik notu
- Secili versiyonu canvas'ta onizleme
- "Bu versiyona geri don" — yeni versiyon olarak eklenir, gecmis silinmez

### FR-1.6.4 Simulasyon Sonuclari

- Her simulasyon calistirmasinin sonucu otomatik DB'ye kaydedilir
- Kronolojik listeleme
- Kullanici isimlendirme (orn. "6 MeV — 2 katman Pb+W")
- Birden fazla sonuc grafik uzerinde karsilastirma (overlay)
- Silme destegi

### FR-1.6.5 Proje Dosyasi (.cdt)

- JSON+ZIP formati
- Icerik:
  - design.json — Geometri tanimi
  - versions/ — Tum versiyon gecmisi
  - simulations/ — Tum simulasyon sonuclari
  - notes.json — Notlar
  - thumbnail.png — Onizleme
  - metadata.json — Uygulama versiyonu, tarih, format versiyonu
- .cdt dosya uzantisi iliskilendirme (installer surumunde)
- Import/export destegi

### FR-1.6.6 Geometri JSON

- Salt geometri JSON olarak disa aktarim (simulasyon sonuclari haric)
- Iceaktarim destegi

**Schema Versioning (v2.0):**
- `geometry_json` artik multi-stage formatta: `"stages": [...]` (eski format: `"body": {...}`)
- Eski v1.x dosyalari import sirasinda otomatik migrate edilir (body → stages[0])
- Export her zaman v2.0 formatinda yapilir

### FR-4.1 PDF Rapor (9 Bolumlu)

Rapor bolumleri (kullanici her bolumu dahil/haric secebilir):

**Sayfa 1 — Kapak:** Baslik, tasarim adi, kolimator tipi, tarih, versiyon

**Bolum A — Geometri Ozeti (1-2 sayfa):**
- Canvas goruntusu (yuksek cozunurluk PNG)
- Genel parametreler tablosu (tip, boyutlar, aciklik, SDD, focal spot)

**Bolum B — Stage & Katman Yapisi (1-2 sayfa):**
- Her stage icin ayri tablo: stage adi, amac (purpose), boyutlar, gap_after
- Her stage icinde katman detaylari: malzeme, kalinlik, amac
- Toplam stage sayisi ve toplam yukseklik ozeti

**Bolum C — Zayiflama Analizi (2-3 sayfa):**
- Enerji taramasi sonuc tablosu
- Her katman icin ayri zayiflama katkisi tablosu
- Iletim vs Enerji grafigi (log-log)
- mu/rho vs Enerji grafigi
- Iletim vs Kalinlik grafigi

**Bolum D — Build-up Analizi (1 sayfa):**
- Build-up dahil/haric karsilastirma tablosu
- Build-up yontemi (GP/Taylor) belirtilir
- Build-up vs enerji grafigi

**Bolum E — Isin Profili (1-2 sayfa):**
- Profil grafigi (bolgeler renk kodlu)
- Coklu enerji karsilastirma (secilmisse)
- Profil sayisal veriler tablosu

**Bolum F — Kalite Metrikleri (1 sayfa):**
- Score card formati: deger, birim, durum gostergesi
- Penumbra, flatness, leakage, CR, SPR

**Bolum G — Compton Analizi (1-2 sayfa, opsiyonel):**
- KN polar plot, enerji spektrumu, SPR profili

**Bolum H — Model Varsayimlari ve Uyarilar (1 sayfa):**
- Fizik modeli ozeti, LINAC sinirliliklari, scatter sinirliliklari

**Bolum I — Dogrulama Ozeti (opsiyonel):**
- Son benchmark test sonuclari

**Son Sayfa:** Alt bilgi — uygulama versiyonu, tarih, sayfa numaralari

### FR-4.1.5 Rapor Diyalogu

- Checkbox ile bolum secimi (varsayilan: A-F dahil, G-I opsiyonel)
- Enerji araligi ve nokta sayisi
- "Onizle" ile tahmini sayfa sayisi
- "Olustur" ile QThread uzerinde uretim + ilerleme cubugu
- Dosya diyalogu ile kayit yeri secimi

**Rapor dosya adi:** CDT_Report_{tasarim_adi}_{tarih}.pdf
**Sayfa boyutu:** A4, kenar bosluklari 20mm
**Teknoloji:** ReportLab

### FR-4.2 CSV

- Enerji (keV), malzeme, kalinlik (mm), mu/rho, mu, HVL, TVL, iletim (%), zayiflama (dB)

### FR-4.3 Goruntu

- Canvas PNG/SVG disa aktarim (QGraphicsScene.render)

## Kabul Kriterleri

- [ ] Tasarim kaydedilip tekrar yuklenebiliyor (Ctrl+S / Ctrl+O)
- [ ] Versiyon gecmisi dogru calisiyor (her kaydda yeni versiyon)
- [ ] Versiyona geri donme calisiyor
- [ ] Simulasyon sonuclari DB'ye kaydediliyor ve listeleniyor
- [ ] .cdt dosyasi export/import calisiyor
- [ ] PDF rapor olusturuluyor (en az A-F bolumleri)
- [ ] CSV disa aktarim calisiyor
- [ ] JSON geometri export/import calisiyor
- [ ] Canvas PNG export calisiyor
- [ ] Tasarim listesinde filtreleme ve arama calisiyor
- [ ] Son kullanilanlar menusu calisiyor
- [ ] Thumbnail dogru olusturuluyor
- [ ] Baslik cubugunda tasarim adi ve kaydedilmemis gosterge calisiyor

## Notlar

- ReportLab ile PDF uretimi QThread uzerinde yapilmali (UI bloklanmamali)
- .cdt dosyasi aslinda ZIP'lenmis JSON dosyalaridir (zipfile modulu)
- Thumbnail: QGraphicsScene.render() ile 200x150 boyutunda
- Grafik goruntuleri rapora pyqtgraph/matplotlib export ile eklenir
- CSV dosyalari BOM ile UTF-8 formatinda (Excel uyumlu)

> **FRD Referans:** §4.1 (FR-1.6), §4.4, §5.5-5.6
