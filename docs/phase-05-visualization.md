# Phase 5 — Gorsellestirme (Grafikler)

## Amac
pyqtgraph ve matplotlib tabanli tum grafik bilesenleri implement etmek. Isin profili, mu/rho karsilastirma, HVL/TVL, iletim vs kalinlik grafikleri ve Compton analiz grafikleri (Klein-Nishina polar plot, enerji spektrumu, aci-enerji haritasi).

## Kapsam & Bagimliliklar
- **Bagimlilik:** Phase 2 (fizik hesaplamalari), Phase 4 (simulasyon sonuclari)
- **Compton analitik grafikler** Phase 2'deki ComptonEngine sonuclarini kullanir
- **Isin profili grafigi** Phase 4'teki SimulationResult verisini kullanir

## Olusturulacak Dosyalar

```
app/ui/charts/
├── __init__.py
├── base_chart.py           # Ortak grafik widget (pyqtgraph tabanli)
├── beam_profile_chart.py   # Isin profili grafigi
├── attenuation_chart.py    # mu/rho vs enerji grafigi (log-log)
├── hvl_chart.py            # HVL vs enerji grafigi
├── transmission_chart.py   # Iletim vs kalinlik grafigi
├── klein_nishina_chart.py  # Klein-Nishina polar plot (matplotlib)
├── compton_energy_chart.py # Sacilmis foton enerji spektrumu
├── angle_energy_chart.py   # Aci vs enerji kaybi interaktif (dual-axis)
└── spr_chart.py            # Scatter-to-Primary Ratio profili (Phase 7'de doldurulur)
```

## Grafik Gereksinimleri

### FR-3.2 Isin Profili Grafigi (beam_profile_chart.py)
- **Teknoloji:** pyqtgraph PlotWidget
- **X ekseni:** Aci (derece) veya detektor pozisyonu (mm) — kullanici secimi
- **Y ekseni:** Normalize siddet (0-1) veya iletim orani (%)
- **Bolge gorsellestirme:**
  - Useful beam (yararli isin alani): acik mavi dolgu
  - Penumbra (yari golge): sari dolgu
  - Shielded region (zirhlenmis bolge): kirmizi dolgu
- **Interaktivite:** Hover tooltip, zoom, crosshair
- **Overlay:** Birden fazla enerji profili ayni grafikte
- **Build-up:** dahil/haric overlay (isteğe bagli)

### FR-3.3.1 mu/rho vs Enerji Grafigi (attenuation_chart.py)
- **Teknoloji:** pyqtgraph PlotWidget
- **Olcek:** log-log (her iki eksen logaritmik)
- **X ekseni:** Foton enerjisi (keV)
- **Y ekseni:** mu/rho (cm2/g)
- **Egriler:** Toplam + alt bilesenler ayri renklerde:
  - Toplam (coherent dahil): beyaz, kalin
  - Fotoelektrik: mavi
  - Compton: yesil
  - Cift uretimi: kirmizi
- **Karsilastirma modu:** Birden fazla malzemenin toplam mu/rho egrisi ayni grafikte

### FR-3.3.3 HVL vs Enerji Grafigi (hvl_chart.py)
- **Teknoloji:** pyqtgraph PlotWidget
- **X ekseni:** Foton enerjisi (keV), logaritmik
- **Y ekseni:** HVL (mm)
- **Egriler:** Farkli malzemeler icin HVL degisimi, her biri malzeme rengiyle

### FR-3.3.4 Iletim vs Kalinlik Grafigi (transmission_chart.py)
- **Teknoloji:** pyqtgraph PlotWidget
- **X ekseni:** Kalinlik (mm)
- **Y ekseni:** Iletim orani (0-1) veya (%), logaritmik opsiyonel
- **Egriler:** Secili enerjide farkli malzemeler

### FR-3.5.1 Klein-Nishina Polar Plot (klein_nishina_chart.py)
- **Teknoloji:** matplotlib polar axes, QWidget icine embed (FigureCanvasQTAgg)
- **Polar koordinat:** Sacilma acisi (0-180 derece) vs d_sigma/d_Omega (cm2/sr/elektron)
- **Gosterim:**
  - Klein-Nishina: kalin cizgi (enerji renginde)
  - Thomson (klasik limit): kesik cizgi (karsilastirma)
  - One sacilma (forward): acik mavi dolgu
  - Geriye sacilma (back): kirmizi dolgu
- **Interaktivite:** Enerji slider degistikce anlik guncelleme
- **Tooltip:** Her acida E', T, enerji kaybi orani

### FR-3.5.2 Compton Enerji Spektrumu (compton_energy_chart.py)
- **Teknoloji:** pyqtgraph PlotWidget
- **X ekseni:** Sacilmis foton enerjisi (keV)
- **Y ekseni:** Olasilik yogunlugu (d_sigma/dE)
- **Compton kenari:** Dikey cizgi ile isaretli
- **Ek egri:** Geri sekme elektron enerji spektrumu
- **Overlay:** Birden fazla gelen foton enerjisi karsilastirma

### FR-3.5.3 Aci vs Enerji Kaybi (angle_energy_chart.py)
- **Teknoloji:** pyqtgraph PlotWidget, dual-axis
- **X ekseni:** Sacilma acisi theta (0-180 derece)
- **Y1 ekseni (sol):** Sacilmis foton enerjisi E' (keV)
- **Y2 ekseni (sag):** Geri sekme elektron enerjisi T (keV)
- **Interaktivite:** Crosshair — fare pozisyonunda E', T, Delta_E/E0, Delta_lambda gosterimi
- **Slider:** Gelen foton enerjisi (E0) slider ile degistirilebilir
- **Preset butonlari:** 80keV, 160keV, 320keV, 1MeV, 3.5MeV, 6MeV

### SPR Profili (spr_chart.py)
- **Bu faz:** Placeholder olarak olusturulur, Phase 7'de doldurulur
- **X ekseni:** Detektor pozisyonu (mm)
- **Y ekseni:** SPR (Scatter-to-Primary Ratio)

## Base Chart Sinifi

```python
# app/ui/charts/base_chart.py
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout

class BaseChart(QWidget):
    def __init__(self, title: str = "", x_label: str = "", y_label: str = "",
                 log_x: bool = False, log_y: bool = False):
        ...
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#0F172A')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        # Axis labels, title
        # Dark theme colors

    def add_curve(self, x, y, name: str, color: str, width: int = 2): ...
    def clear_curves(self): ...
    def set_log_mode(self, x: bool, y: bool): ...
    def enable_crosshair(self): ...
    def add_region(self, x_min, x_max, color, alpha=0.2, label=""): ...
```

## Alt Panel Duzeni

```
+--------------------------------------------------------------------+
| [Isin Profili] [mu/rho] [HVL/TVL] [Iletim] [Compton] [KN] [SPR]  |
|                                                                     |
|                    GRAFIK ALANI                                      |
|              (Secili tab'a gore degisir)                            |
|                                                                     |
+--------------------------------------------------------------------+
```

QTabWidget ile tab'lar arasi gecis. Her tab bir grafik widget'i icerir.

## Renk Paleti (Grafikler icin)

- Arka plan: #0F172A
- Grid: #1E293B alpha=0.3
- Birincil egri: #3B82F6 (mavi)
- Ikincil egriler: malzeme renk kodlari
- Useful beam bolgesi: #3B82F6 alpha=0.2
- Penumbra bolgesi: #F59E0B alpha=0.2
- Shielded bolgesi: #EF4444 alpha=0.1
- Crosshair: #94A3B8

## Kabul Kriterleri

- [ ] Alt panelde QTabWidget ile tum tab'lar gorunur
- [ ] Isin profili grafigi dogru gosteriyor (aciklik/penumbra/zirhlama bolgesi)
- [ ] mu/rho grafigi log-log olcekte dogru (fotoelektrik/Compton/cift uretimi)
- [ ] Malzeme karsilastirma grafigi birden fazla malzemeyi dogru gosteriyor
- [ ] HVL vs enerji grafigi dogru
- [ ] Iletim vs kalinlik grafigi dogru
- [ ] Klein-Nishina polar plot matplotlib ile gorunuyor
- [ ] KN polar plot enerji slider ile anlik guncelleniyor
- [ ] Thomson limiti kesik cizgi ile gosteriliyor
- [ ] Compton enerji spektrumu grafigi dogru, Compton kenari isaret
- [ ] Aci vs enerji dual-axis grafik crosshair calisiyor
- [ ] Overlay (coklu enerji karsilastirma) tum grafiklerde calisiyor
- [ ] Hover tooltip degerler dogru gosteriyor
- [ ] Zoom calisiyor
- [ ] Grafikler koyu tema ile uyumlu

## Notlar
- pyqtgraph performans icin tercih edilir (realtime, OpenGL destegi)
- matplotlib yalnizca polar plot icin kullanilir (pyqtgraph polar destegi sinirli)
- matplotlib FigureCanvasQTAgg ile PyQt6'ya embed edilir
- Grafik verisi NumPy array olarak gelir (pyqtgraph uyumlu)
- Compton grafikleri Phase 2'deki ComptonEngine ile hesaplanir, bu fazda sadece gorsellestirme
- SPR grafigi Phase 7'ye kadar bos kalabilir (placeholder)

> **FRD Referans:** §4.3 (FR-3.2, FR-3.3, FR-3.5.1-3)
