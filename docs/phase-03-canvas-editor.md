# Phase 3 — Kolimator Geometri Editoru (Canvas)

## Amac
QGraphicsScene/QGraphicsView tabanli interaktif 2D canvas editoru olusturmak. Kolimator enine kesit goruntusunu cizme, boyut duzenleme, katman yonetimi, kaynak/detektor konumlandirma.

## Kapsam & Bagimliliklar
- **Bagimlilik:** Phase 1 (veri modelleri, temel UI yapisi, malzeme renk kodlari)
- **Bu fazda hesaplama motoru KULLANILMAZ** — yalnizca gorsel editor
- Phase 4 (ray-tracing) ve Phase 5 (grafikler) bu faza bagimlidir

## Olusturulacak Dosyalar

```
app/ui/canvas/
├── __init__.py
├── collimator_scene.py    # QGraphicsScene — ana sahne
├── collimator_view.py     # QGraphicsView — zoom/pan kontrolu
├── geometry_items.py      # QGraphicsItem alt siniflari (govde, katman, aciklik)
├── stage_item.py          # Stage grafik ogesi (StageItem)
├── gap_item.py            # Stage arasi bosluk grafik ogesi
├── source_item.py         # Kaynak noktasi grafik ogesi
├── detector_item.py       # Detektor cizgisi grafik ogesi
├── beam_lines_item.py     # Isin yolu cizgileri (sembolik)
├── dimension_item.py      # Olcu etiketleri ve cizgileri
├── grid_item.py           # Izgara arka plan
└── ruler_item.py          # Cetvel (ust/sol kenar)

app/ui/panels/
├── __init__.py
├── material_panel.py      # Sol panel — malzeme listesi + detay karti
├── layer_panel.py         # Sag panel — katman yonetimi
├── properties_panel.py    # Sag panel — boyut/parametre girisleri
└── energy_panel.py        # Enerji secici (slider + preset)

app/ui/widgets/
├── __init__.py
├── energy_slider.py       # Enerji slider + sayisal input birlesik widget
├── material_card.py       # Malzeme karti widget'i
├── layer_row.py           # Katman satiri widget'i (suruklenebilir)
├── color_swatch.py        # Malzeme renk karesi
└── collapsible_section.py # Daraltilabilir bolum widget'i

app/ui/toolbar.py          # Ana arac cubugu (guncelleme)
```

## Fonksiyonel Gereksinimler

### FR-1.1 Canvas Alani
- **FR-1.1.1:** 2D interaktif canvas — kolimatorun enine kesit gorunumu (cross-section)
- **FR-1.1.2:** Olcekli izgara (grid): 1mm, 5mm, 10mm, 50mm secenekleri
- **FR-1.1.3:** Zoom (fare tekerlegi/pinch) ve pan (surukle). Zoom: %10 – %1000
- **FR-1.1.4:** Cetvel (ruler) — ust ve sol kenar, mm/cm birimi
- **FR-1.1.5:** Canvas boyutu pencere boyutuna uyum saglar (responsive)

### FR-1.2 Geometri Sablonlari
Kolimator tipi secildiginde varsayilan sablon olusturulur:

**FR-1.2.1 Fan-beam sablonu:**
- Kaynak noktasi (ustte, odak noktasi ikonu)
- Trapezoid kolimator govdesi (yukari dogru daralan)
- Yelpaze acisi gosterge cizgileri
- Detektor cizgisi (altta)

**FR-1.2.2 Pencil-beam sablonu:**
- Kaynak noktasi
- Dikdortgen kolimator govdesi, ortada dairesel/dikdortgen kanal
- Paralel isin gosterge cizgileri
- Detektor noktasi

**FR-1.2.3 Slit sablonu:**
- Kaynak noktasi
- Dikdortgen kolimator govdesi, ortada dar yarik
- Yarik genisligi olcu cizgisi
- Detektor cizgisi

### FR-1.3 Boyut Duzenleme
- **FR-1.3.1:** Govde boyutlari (genislik, yukseklik) — handle'lar ile surukleme veya sayisal giris
- **FR-1.3.2:** Aciklik (aperture) boyutlari — benzer sekilde
- **FR-1.3.3:** Kaynak ve detektor konumlari suruklenebilir
- **FR-1.3.4:** Boyut degisiklikleri anlik olcu etiketleri (dimension labels) ile canvas'ta
- **FR-1.3.5:** Properties Panel'de sayisal giris, canvas'a yansiyan

### FR-1.4 Katman Yonetimi
- **FR-1.4.1:** Sag tarafta "Katmanlar" paneli
- **FR-1.4.2:** "Katman Ekle" butonu — distan ice dogru genisler
- **FR-1.4.3:** Her katman satiri: sira no, malzeme dropdown (ad + renk karesi), kalinlik (mm input), amac secici, sil butonu
- **FR-1.4.4:** Katman sirasi surukle-birak (drag & drop)
- **FR-1.4.5:** Canvas'ta her katman malzeme renk koduyla doldurulmus, katmanlar arasi kesik cizgi (dashed)
- **FR-1.4.6:** Katmana tiklandiginda canvas'ta vurgulanir ve panelde secili olur

**Stage Yonetimi (Multi-Stage):**
- Sag panelde stage secici (dropdown veya tab bar)
- Her stage'in kendi katman listesi
- "Stage Ekle" / "Stage Sil" butonlari
- Stage siralama (yukari/asagi)
- Stage isim ve amac (purpose) duzenleme
- Stage boyutlari ve gap_after duzenleme
- Secili stage canvas'ta vurgulanir

### FR-1.5 Kaynak ve Detektor
- **FR-1.5.1:** Kaynak pozisyonu ikon (nokta/yildiz), focal spot size olcu etiketi
- **FR-1.5.2:** Kaynak-detektor mesafesi (SDD) otomatik hesaplanip olcu cizgisi ile gosterilir
- **FR-1.5.3:** Isin yolu: kaynak -> aciklik -> detektor cizgileri (yari-saydam renk)

## Kolimator Geometri Modeli (Referans)

```python
# Phase 1'de tanimlanan modeller kullanilir (multi-stage mimari):
# - CollimatorType: FAN_BEAM, PENCIL_BEAM, SLIT
# - CollimatorStage: outer_width, outer_height, aperture, layers, purpose, gap_after
#     (NOT: Eski CollimatorBody artik kullanimdan kaldirilmistir.
#      geometry.body, geriye uyumluluk icin geometry.stages[0] alias'idir.)
# - CollimatorLayer: material_id, thickness, purpose
# - ApertureConfig: fan_angle, slit_width, pencil_diameter, taper_angle
# - SourceConfig: position, energy, focal_spot_size
# - DetectorConfig: position, width, distance_from_source
#
# Her stage bagimsiz bir govdedir ve kendi aperture + layer listesine sahiptir.
# Tipik stage amaclarï: "internal", "fan", "penumbra"
# Stage'ler geometry.stages[i] ile indekslenir (0 = kaynaga en yakin).
```

## Canvas Uygulama Detaylari

### QGraphicsScene Hiyerarsisi

```
Scene hierarchy:
+-- GridItem (arka plan grid)
+-- RulerItem (ust + sol cetvel)
+-- StageGroupItem (tum stage'lerin konteyneri)
|   +-- StageItem[0] "Internal" (en ust, kaynaga yakin)
|   |   +-- LayerItem[0]
|   |   +-- LayerItem[1]
|   |   +-- ApertureItem
|   +-- GapItem[0] (kesikli cizgi bolge, mesafe etiketi)
|   +-- StageItem[1] "Fan"
|   |   +-- LayerItem[0]
|   |   +-- ApertureItem
|   +-- GapItem[1]
|   +-- StageItem[2] "Penumbra"
|       +-- LayerItem[0]
|       +-- ApertureItem
+-- SourceItem
+-- DetectorItem
+-- BeamLinesItem (tum stage'lerden gecen isinlar)
+-- DimensionItem[] (per-stage ve toplam boyutlar)
```

### Zoom/Pan Implementasyonu
```python
# QGraphicsView'da:
# - wheelEvent: zoom (scale faktor)
# - mousePressEvent + mouseMoveEvent: pan (ScrollHandDrag)
# - Zoom aralik: 0.1x – 10x (min %10, max %1000)
# - Zoom merkezi: fare pozisyonu (AnchorUnderMouse)
```

### Handle (Tutma Noktasi) Sistemi
- Govde koseleri ve kenarlari icin resize handle'lar
- Aciklik icin resize handle'lar
- Handle gorunumu: kucuk kareler (6x6px), hover'da buyur
- Handle surukleme ile boyut degisikligi -> Properties Panel senkronize

### Katman Gorsellestirme
- Her katman QGraphicsRectItem (veya trapez icin QGraphicsPolygonItem)
- Dolgu: malzeme renk kodu, %70 opasite (alfa=178)
- Katmanlar arasi sinir: dashed line, 1px, #FFFFFF %30
- Secili katman: parlak kenarlık (highlight), daha yuksek opasite

## UI Panel Detaylari

### Sol Panel — Malzeme Listesi
- 8 malzeme kart listesi (QListWidget veya QVBoxLayout)
- Her kart: renk karesi, ad, Z, yogunluk
- Tiklandiginda detay karti acilir (mu/rho mini grafik, tam ozellikler)
- Malzeme kartindan katmana surukle-birak atama

### Sag Panel — Katmanlar + Parametreler + Sonuclar
- Daraltilabilir (collapsible) bolumler:
  1. **Katmanlar:** Layer listesi, ekle/sil, drag-drop siralama
  2. **Parametreler:** Genislik, yukseklik, aciklik, SDD (QDoubleSpinBox)
  3. **Hizli Sonuclar:** Iletim %, HVL, TVL, kacak % (Phase 4'te doldurulur)

### Enerji Secici
- QSlider + QDoubleSpinBox birlesik widget
- kVp modu (80-300) / MeV modu (0.5-6.0) secimi
- Preset butonlari: Bagaj(80kVp), Kargo Dusuk(160kVp), Kargo Orta(320kVp), LINAC Dusuk(1MeV), LINAC Orta(3.5MeV), LINAC Yuksek(6MeV)

## Renk Paleti (Referans)

| Oge | Renk |
|-----|------|
| Canvas arka plan | #0F172A |
| Grid cizgileri (ince) | #1E293B |
| Grid cizgileri (kalin) | #334155 |
| Olcu etiketleri | #94A3B8 |
| Isin yolu cizgileri | #3B82F6 %40 |
| Secili katman highlight | #3B82F6 |
| Handle (normal) | #64748B |
| Handle (hover) | #3B82F6 |
| Stage arasi bosluk (gap) | #1E293B (kesikli cizgi) |
| Secili stage cercevesi   | #3B82F6               |

### Malzeme Renkleri:
- Pb: #5C6BC0 (koyu mavi)
- W: #FF7043 (turuncu)
- SS304: #78909C (gri)
- SS316: #90A4AE (acik gri)
- Bi: #AB47BC (mor)
- Al: #66BB6A (yesil)
- Cu: #EF5350 (kirmizi)
- Bronze: #FFA726 (amber)

## Kabul Kriterleri

- [ ] Canvas acilir, koyu tema arka plan gorunur
- [ ] Fan-beam, Pencil-beam, Slit sablonlari dogru ciziyor
- [ ] Zoom (fare tekerlegi) ve pan (surukle) calisiyor (%10-%1000)
- [ ] Izgara gorunur, aralik degistirilebilir (1/5/10/50mm)
- [ ] Cetvel gorunur (ust ve sol kenar)
- [ ] Govde boyutlari handle ile degistirilebilir
- [ ] Govde boyutlari Properties Panel'den sayisal giris ile degistirilebilir (senkron)
- [ ] Katman ekleme/silme calisiyor
- [ ] Katman malzeme secimi dropdown ile calisiyor
- [ ] Katman sirasi drag-drop ile degistirilebilir
- [ ] Her katman dogru renk koduyla canvas'ta gorunuyor
- [ ] Kaynak ve detektor suruklenebilir
- [ ] SDD olcu cizgisi otomatik guncelleniyor
- [ ] Isin yolu cizgileri sembolik olarak gorunuyor
- [ ] Enerji slider + preset butonlari calisiyor
- [ ] Malzeme paneli 8 malzemeyi listeliyor

## Notlar
- Bu fazda hesaplama yapilmaz — sadece gorsel editor
- "Hizli Sonuclar" paneli bos kalabilir (Phase 4'te doldurulur)
- Grafik alani (alt panel) bos kalabilir (Phase 5'te doldurulur)
- Canvas performansi: yeniden cizim < 16ms (60fps) hedefi
- QGraphicsItem.setFlag(ItemIsMovable) kullanarak surukleme
- QGraphicsItem.boundingRect() dogru tanimlanmalidir (zoom icin)

> **FRD Referans:** §4.1 (FR-1.1 – FR-1.5), §6 (UI/UX Gereksinimleri)
