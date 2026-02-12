"""PDF report generator — ReportLab multi-section report.

Generates A4 PDF with sections A–I:
  Cover, Geometry, Stages & Layers, Attenuation, Build-up,
  Beam Profile, Quality Metrics, Compton Analysis,
  Model Assumptions, Validation Summary.

Charts are passed as pre-rendered PNG bytes (no pyqtgraph/matplotlib import).

Reference: Phase-06 spec — FR-4.1.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.constants import APP_NAME, APP_VERSION
from app.models.compton import ComptonAnalysis
from app.models.geometry import CollimatorGeometry
from app.models.simulation import SimulationResult


# Colors
_DARK_BG = colors.HexColor("#1E293B")
_ACCENT = colors.HexColor("#3B82F6")
_HEADER_BG = colors.HexColor("#334155")
_TEXT = colors.HexColor("#F8FAFC")
_TEXT_SEC = colors.HexColor("#94A3B8")
_BORDER = colors.HexColor("#475569")


class PdfReportExporter:
    """Multi-section PDF report generator."""

    def __init__(self):
        self._styles = getSampleStyleSheet()
        self._add_custom_styles()

    def _add_custom_styles(self) -> None:
        """Add custom paragraph styles."""
        self._styles.add(ParagraphStyle(
            name="CoverTitle",
            fontSize=24, leading=30,
            textColor=_ACCENT, spaceAfter=12,
        ))
        self._styles.add(ParagraphStyle(
            name="CoverSubtitle",
            fontSize=14, leading=18,
            textColor=colors.gray, spaceAfter=6,
        ))
        self._styles.add(ParagraphStyle(
            name="SectionTitle",
            fontSize=16, leading=20,
            textColor=_ACCENT, spaceAfter=10, spaceBefore=12,
        ))
        self._styles.add(ParagraphStyle(
            name="SubSection",
            fontSize=12, leading=16,
            textColor=colors.black, spaceAfter=6, spaceBefore=8,
        ))
        self._styles.add(ParagraphStyle(
            name="BodyText2",
            fontSize=10, leading=14,
            textColor=colors.black, spaceAfter=4,
        ))

    def generate_report(
        self,
        geometry: CollimatorGeometry,
        simulation_result: SimulationResult | None = None,
        output_path: str = "report.pdf",
        include_sections: list[str] | None = None,
        chart_images: dict[str, bytes] | None = None,
        canvas_image: bytes | None = None,
        compton_result: ComptonAnalysis | None = None,
        validation_results: list[dict] | None = None,
    ) -> None:
        """Build and save PDF report.

        Args:
            geometry: The collimator design.
            simulation_result: Simulation data (None = skip E,F).
            output_path: File path for output PDF.
            include_sections: Section codes ["A".."I"].
            chart_images: Pre-rendered charts as {name: png_bytes}.
            canvas_image: Pre-rendered canvas screenshot bytes.
            compton_result: Compton analysis data (None = skip G).
            validation_results: Validation test dicts (None = skip I).
        """
        if include_sections is None:
            include_sections = ["A", "B", "C", "D", "E", "F"]
        if chart_images is None:
            chart_images = {}

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        story: list = []

        # Cover page
        story.extend(self._build_cover(geometry))

        if "A" in include_sections:
            story.append(PageBreak())
            story.extend(self._build_section_a(geometry, canvas_image))

        if "B" in include_sections:
            story.append(PageBreak())
            story.extend(self._build_section_b(geometry))

        if "C" in include_sections:
            story.append(PageBreak())
            story.extend(self._build_section_c(chart_images))

        if "D" in include_sections:
            story.extend(self._build_section_d(simulation_result))

        if "E" in include_sections and simulation_result:
            story.append(PageBreak())
            story.extend(self._build_section_e(simulation_result, chart_images))

        if "F" in include_sections and simulation_result:
            story.extend(self._build_section_f(simulation_result))

        if "G" in include_sections:
            story.append(PageBreak())
            story.extend(self._build_section_g(compton_result, chart_images))

        if "H" in include_sections:
            story.append(PageBreak())
            story.extend(self._build_section_h(simulation_result))

        if "I" in include_sections:
            story.append(PageBreak())
            story.extend(self._build_section_i(validation_results))

        doc.build(story, onFirstPage=self._add_footer, onLaterPages=self._add_footer)

    # ------------------------------------------------------------------
    # Cover
    # ------------------------------------------------------------------

    def _build_cover(self, geometry: CollimatorGeometry) -> list:
        """Page 1: Title and design overview."""
        story = [
            Spacer(1, 60 * mm),
            Paragraph(APP_NAME, self._styles["CoverTitle"]),
            Paragraph(f"Versiyon {APP_VERSION}", self._styles["CoverSubtitle"]),
            Spacer(1, 20 * mm),
            Paragraph(f"Tasarim: <b>{geometry.name}</b>", self._styles["CoverSubtitle"]),
            Paragraph(f"Kolimator Tipi: {geometry.type.value}", self._styles["CoverSubtitle"]),
            Paragraph(f"Stage Sayisi: {geometry.stage_count}", self._styles["CoverSubtitle"]),
            Spacer(1, 10 * mm),
            Paragraph(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}", self._styles["CoverSubtitle"]),
        ]
        return story

    # ------------------------------------------------------------------
    # Section A — Geometry Overview
    # ------------------------------------------------------------------

    def _build_section_a(
        self, geometry: CollimatorGeometry, canvas_image: bytes | None,
    ) -> list:
        story = [
            Paragraph("A — Geometri Ozeti", self._styles["SectionTitle"]),
        ]

        # Canvas screenshot
        if canvas_image:
            img = Image(BytesIO(canvas_image), width=160 * mm, height=90 * mm)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 6 * mm))

        # Parameter table
        src = geometry.source
        det = geometry.detector
        data = [
            ["Parametre", "Deger"],
            ["Kolimator Tipi", geometry.type.value],
            ["Stage Sayisi", str(geometry.stage_count)],
            ["Toplam Yukseklik", f"{geometry.total_height:.1f} mm"],
            ["Kaynak Pozisyon", f"({src.position.x:.1f}, {src.position.y:.1f}) mm"],
            ["Fokal Spot", f"{src.focal_spot_size:.2f} mm ({src.focal_spot_distribution.value})"],
            ["Detektor Pozisyon", f"({det.position.x:.1f}, {det.position.y:.1f}) mm"],
            ["Detektor Genislik", f"{det.width:.1f} mm"],
            ["SDD", f"{det.distance_from_source:.1f} mm"],
        ]
        table = Table(data, colWidths=[80 * mm, 80 * mm])
        table.setStyle(self._table_style())
        story.append(table)
        return story

    # ------------------------------------------------------------------
    # Section B — Stages & Layers
    # ------------------------------------------------------------------

    def _build_section_b(self, geometry: CollimatorGeometry) -> list:
        story = [
            Paragraph("B — Stage ve Katman Yapisi", self._styles["SectionTitle"]),
        ]

        for stage in geometry.stages:
            story.append(Paragraph(
                f"Stage {stage.order}: {stage.name or '(isimsiz)'} — {stage.purpose.value}",
                self._styles["SubSection"],
            ))

            stage_data = [
                ["Parametre", "Deger"],
                ["Dis Genislik", f"{stage.outer_width:.1f} mm"],
                ["Dis Yukseklik", f"{stage.outer_height:.1f} mm"],
                ["Gap (sonraki stage'e)", f"{stage.gap_after:.1f} mm"],
            ]

            # Aperture info
            ap = stage.aperture
            if ap.fan_angle is not None:
                stage_data.append(["Fan Acisi", f"{ap.fan_angle:.1f} derece"])
            if ap.fan_slit_width is not None:
                stage_data.append(["Yarik Genislik", f"{ap.fan_slit_width:.1f} mm"])

            table = Table(stage_data, colWidths=[80 * mm, 80 * mm])
            table.setStyle(self._table_style())
            story.append(table)
            story.append(Spacer(1, 4 * mm))

            # Layer table
            if stage.layers:
                layer_data = [["Sira", "Malzeme", "Kalinlik (mm)", "Amac"]]
                for layer in stage.layers:
                    mat_str = layer.material_id
                    if layer.is_composite:
                        mat_str += f" / {layer.inner_material_id}"
                    layer_data.append([
                        str(layer.order),
                        mat_str,
                        f"{layer.thickness:.2f}",
                        layer.purpose.value,
                    ])
                ltable = Table(layer_data, colWidths=[20 * mm, 50 * mm, 40 * mm, 50 * mm])
                ltable.setStyle(self._table_style())
                story.append(ltable)
                story.append(Spacer(1, 6 * mm))

        return story

    # ------------------------------------------------------------------
    # Section C — Attenuation Charts
    # ------------------------------------------------------------------

    def _build_section_c(self, chart_images: dict[str, bytes]) -> list:
        story = [
            Paragraph("C — Zayiflama Analizi", self._styles["SectionTitle"]),
        ]

        for key, label in [
            ("mu_rho", "Kutle Zayiflama Katsayisi (mu/rho vs Enerji)"),
            ("transmission", "Iletim vs Kalinlik"),
            ("hvl", "Yari Deger Kalinligi (HVL vs Enerji)"),
        ]:
            if key in chart_images:
                story.append(Paragraph(label, self._styles["SubSection"]))
                img = Image(BytesIO(chart_images[key]), width=150 * mm, height=80 * mm)
                img.hAlign = "CENTER"
                story.append(img)
                story.append(Spacer(1, 6 * mm))

        if not any(k in chart_images for k in ["mu_rho", "transmission", "hvl"]):
            story.append(Paragraph(
                "Grafik goruntuleri mevcut degil.", self._styles["BodyText2"],
            ))

        return story

    # ------------------------------------------------------------------
    # Section D — Build-up Analysis
    # ------------------------------------------------------------------

    def _build_section_d(self, result: SimulationResult | None) -> list:
        story = [
            Paragraph("D — Build-up Analizi", self._styles["SectionTitle"]),
        ]

        if result and result.include_buildup:
            story.append(Paragraph(
                "Simulasyon build-up faktoru dahil edilmistir (GP yontemi).",
                self._styles["BodyText2"],
            ))
        else:
            story.append(Paragraph(
                "Build-up analizi mevcut degil veya devre disi.",
                self._styles["BodyText2"],
            ))

        return story

    # ------------------------------------------------------------------
    # Section E — Beam Profile
    # ------------------------------------------------------------------

    def _build_section_e(
        self, result: SimulationResult, chart_images: dict[str, bytes],
    ) -> list:
        story = [
            Paragraph("E — Isin Profili", self._styles["SectionTitle"]),
        ]

        if "beam_profile" in chart_images:
            img = Image(BytesIO(chart_images["beam_profile"]), width=150 * mm, height=80 * mm)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 6 * mm))

        # Profile summary
        qm = result.quality_metrics
        data = [
            ["Metrik", "Deger"],
            ["Enerji", f"{result.energy_keV:.0f} keV"],
            ["Isin Sayisi", str(result.num_rays)],
            ["FWHM", f"{qm.fwhm_mm:.2f} mm"],
            ["Hesaplama Suresi", f"{result.elapsed_seconds:.2f} s"],
        ]
        table = Table(data, colWidths=[80 * mm, 80 * mm])
        table.setStyle(self._table_style())
        story.append(table)

        return story

    # ------------------------------------------------------------------
    # Section F — Quality Metrics
    # ------------------------------------------------------------------

    def _build_section_f(self, result: SimulationResult) -> list:
        story = [
            Spacer(1, 6 * mm),
            Paragraph("F — Kalite Metrikleri", self._styles["SectionTitle"]),
        ]

        qm = result.quality_metrics
        data = [
            ["Metrik", "Deger", "Birim", "Durum"],
        ]
        for m in qm.metrics:
            status_text = {
                "excellent": "Mukemmel",
                "acceptable": "Kabul Edilir",
                "poor": "Yetersiz",
            }.get(m.status.value, m.status.value)
            data.append([m.name, f"{m.value:.3f}", m.unit, status_text])

        # Add aggregate metrics
        data.extend([
            ["Penumbra (sol)", f"{qm.penumbra_left_mm:.2f}", "mm", ""],
            ["Penumbra (sag)", f"{qm.penumbra_right_mm:.2f}", "mm", ""],
            ["Flatness", f"{qm.flatness_pct:.2f}", "%", ""],
            ["Ortalama Sizinti", f"{qm.leakage_avg_pct:.3f}", "%", ""],
            ["Maks Sizinti", f"{qm.leakage_max_pct:.3f}", "%", ""],
            ["Kollimasyon Orani", f"{qm.collimation_ratio_dB:.1f}", "dB", ""],
        ])

        table = Table(data, colWidths=[50 * mm, 35 * mm, 25 * mm, 50 * mm])
        table.setStyle(self._table_style())
        story.append(table)

        # Pass/fail summary
        verdict = "TUM METRIKLER UYGUN" if qm.all_pass else "BAZI METRIKLER YETERSIZ"
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f"<b>Genel Sonuc: {verdict}</b>", self._styles["BodyText2"]))

        return story

    # ------------------------------------------------------------------
    # Section G — Compton Analysis
    # ------------------------------------------------------------------

    def _build_section_g(
        self,
        compton_result: ComptonAnalysis | None,
        chart_images: dict[str, bytes],
    ) -> list:
        story = [
            Paragraph("G — Compton Analizi", self._styles["SectionTitle"]),
        ]

        if compton_result is None:
            story.append(Paragraph(
                "Compton analizi verisi mevcut degil.",
                self._styles["BodyText2"],
            ))
            return story

        # Summary table
        data = [
            ["Parametre", "Deger"],
            ["Gelen Enerji", f"{compton_result.incident_energy_keV:.1f} keV"],
            ["Toplam Tesir Kesiti", f"{compton_result.total_cross_section:.4e} cm\u00B2"],
            ["SPR", f"{compton_result.scatter_to_primary_ratio:.4f}"],
        ]
        table = Table(data, colWidths=[80 * mm, 80 * mm])
        table.setStyle(self._table_style())
        story.append(table)
        story.append(Spacer(1, 6 * mm))

        # Chart images (if provided)
        for key, label in [
            ("compton_polar", "Klein-Nishina Polar Dagilim"),
            ("compton_spectrum", "Sacilma Enerji Spektrumu"),
            ("compton_spr", "SPR Profili"),
        ]:
            if key in chart_images:
                story.append(Paragraph(label, self._styles["SubSection"]))
                img = Image(BytesIO(chart_images[key]), width=150 * mm, height=80 * mm)
                img.hAlign = "CENTER"
                story.append(img)
                story.append(Spacer(1, 6 * mm))

        return story

    # ------------------------------------------------------------------
    # Section H — Model Assumptions & Warnings
    # ------------------------------------------------------------------

    def _build_section_h(self, result: SimulationResult | None) -> list:
        story = [
            Paragraph("H — Model Varsayimlari ve Uyarilar", self._styles["SectionTitle"]),
        ]

        # Physics models
        story.append(Paragraph("Fizik Modeli", self._styles["SubSection"]))
        models_data = [
            ["Model", "Aciklama"],
            ["Zayiflama", "Beer-Lambert (narrow-beam geometri)"],
            ["Veri Kaynagi", "NIST XCOM (log-log interpolasyon)"],
            ["Build-up", "GP (Geometric Progression) formulu"],
            ["Compton", "Klein-Nishina diferansiyel tesir kesiti"],
            ["Scatter", "Monte Carlo tek-sacilma yaklasimi"],
            ["Alisim", "Karisim kurali: (mu/rho)_alloy = SUM(w_i * (mu/rho)_i)"],
        ]
        table = Table(models_data, colWidths=[50 * mm, 110 * mm])
        table.setStyle(self._table_style())
        story.append(table)
        story.append(Spacer(1, 6 * mm))

        # Limitations
        story.append(Paragraph("Kisitlamalar", self._styles["SubSection"]))
        limits_data = [
            ["Kisitlama", "Detay"],
            ["Enerji Araligi", "1 keV \u2013 20 MeV"],
            ["Geometri", "2D kesit, simetri varsayimi"],
            ["Scatter", "Tek sacilma; coklu sacilma ihmal edilir"],
            ["Malzeme", "Homojen; karisim kurali (agirlikli oran)"],
            ["LINAC Modu", "MeV modunda bremsstrahlung spektrum yaklasimi"],
            ["Polarizasyon", "Ihmal edilir (non-polarize kaynak)"],
        ]
        table = Table(limits_data, colWidths=[50 * mm, 110 * mm])
        table.setStyle(self._table_style())
        story.append(table)
        story.append(Spacer(1, 6 * mm))

        # Simulation-specific notes
        if result:
            notes = []
            if result.include_buildup:
                notes.append("Build-up faktoru dahil edilmistir (GP yontemi).")
            else:
                notes.append("Build-up faktoru devre disidir.")
            if result.scatter_result:
                notes.append("Compton scatter simulasyonu dahil edilmistir.")
            else:
                notes.append("Compton scatter simulasyonu dahil edilmemistir.")
            for note in notes:
                story.append(Paragraph(f"\u2022 {note}", self._styles["BodyText2"]))

        return story

    # ------------------------------------------------------------------
    # Section I — Validation Summary
    # ------------------------------------------------------------------

    def _build_section_i(self, validation_results: list[dict] | None) -> list:
        story = [
            Paragraph("I — Dogrulama Ozeti", self._styles["SectionTitle"]),
        ]

        if not validation_results:
            story.append(Paragraph(
                "Dogrulama testi calistirilmamis.",
                self._styles["BodyText2"],
            ))
            return story

        data = [["Test ID", "Grup", "Bizim", "Referans", "Fark%", "Durum"]]
        for r in validation_results:
            status = r.get("status", "?")
            our = r.get("our_value", 0)
            ref = r.get("ref_value", 0)
            our_str = f"{our:.4g}" if isinstance(our, float) else str(our)
            ref_str = f"{ref:.4g}" if isinstance(ref, float) else str(ref)
            diff_str = f"{r.get('diff_pct', 0):.2f}" if "diff_pct" in r else ""
            data.append([
                r.get("test_id", ""),
                r.get("group", ""),
                our_str,
                ref_str,
                diff_str,
                status,
            ])

        table = Table(data, colWidths=[30 * mm, 25 * mm, 30 * mm, 30 * mm, 20 * mm, 25 * mm])
        table.setStyle(self._table_style())
        story.append(table)

        # Summary counts
        total = len(validation_results)
        passed = sum(1 for r in validation_results if r.get("status") == "PASS")
        failed = sum(1 for r in validation_results if r.get("status") == "FAIL")
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            f"<b>Toplam: {total} | Basarili: {passed} | Basarisiz: {failed}</b>",
            self._styles["BodyText2"],
        ))

        return story

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _table_style(self) -> TableStyle:
        """Standard table style for reports."""
        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ])

    @staticmethod
    def _add_footer(canvas, doc) -> None:
        """Add footer with page number and app info."""
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.gray)
        page_text = f"Sayfa {doc.page}"
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, page_text)
        canvas.drawString(
            20 * mm, 10 * mm,
            f"{APP_NAME} v{APP_VERSION} — {datetime.now().strftime('%Y-%m-%d')}",
        )
        canvas.restoreState()
