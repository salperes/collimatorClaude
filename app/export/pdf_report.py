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
from app.core.i18n import t
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
            Paragraph(t("pdf.version", "Version {version}").format(version=APP_VERSION), self._styles["CoverSubtitle"]),
            Spacer(1, 20 * mm),
            Paragraph(t("pdf.design", "Design: <b>{name}</b>").format(name=geometry.name), self._styles["CoverSubtitle"]),
            Paragraph(t("pdf.collimator_type", "Collimator Type: {type}").format(type=geometry.type.value), self._styles["CoverSubtitle"]),
            Paragraph(t("pdf.stage_count", "Stage Count: {count}").format(count=geometry.stage_count), self._styles["CoverSubtitle"]),
            Spacer(1, 10 * mm),
            Paragraph(t("pdf.date", "Date: {date}").format(date=datetime.now().strftime('%Y-%m-%d %H:%M')), self._styles["CoverSubtitle"]),
        ]
        return story

    # ------------------------------------------------------------------
    # Section A — Geometry Overview
    # ------------------------------------------------------------------

    def _build_section_a(
        self, geometry: CollimatorGeometry, canvas_image: bytes | None,
    ) -> list:
        story = [
            Paragraph(t("pdf.sec_a", "A — Geometry Summary"), self._styles["SectionTitle"]),
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
            [t("pdf.col_parameter", "Parameter"), t("pdf.col_value", "Value")],
            [t("pdf.collimator_type_label", "Collimator Type"), geometry.type.value],
            [t("pdf.stage_count_label", "Stage Count"), str(geometry.stage_count)],
            [t("pdf.total_height", "Total Height"), f"{geometry.total_height:.1f} mm"],
            [t("pdf.source_position", "Source Position"), f"({src.position.x:.1f}, {src.position.y:.1f}) mm"],
            [t("pdf.focal_spot", "Focal Spot"), f"{src.focal_spot_size:.2f} mm ({src.focal_spot_distribution.value})"],
            [t("pdf.detector_position", "Detector Position"), f"({det.position.x:.1f}, {det.position.y:.1f}) mm"],
            [t("pdf.detector_width", "Detector Width"), f"{det.width:.1f} mm"],
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
            Paragraph(t("pdf.sec_b", "B — Stage & Layer Structure"), self._styles["SectionTitle"]),
        ]

        for stage in geometry.stages:
            unnamed = t("pdf.unnamed", "(unnamed)")
            story.append(Paragraph(
                f"Stage {stage.order}: {stage.name or unnamed} — {stage.purpose.value}",
                self._styles["SubSection"],
            ))

            stage_data = [
                [t("pdf.col_parameter", "Parameter"), t("pdf.col_value", "Value")],
                [t("pdf.width", "Width (W)"), f"{stage.outer_width:.1f} mm"],
                [t("pdf.thickness", "Thickness (T)"), f"{stage.outer_height:.1f} mm"],
                [t("pdf.y_position", "Y Position"), f"{stage.y_position:.1f} mm"],
                [t("pdf.x_offset", "X Offset"), f"{stage.x_offset:.1f} mm"],
                [t("pdf.material", "Material"), stage.material_id],
            ]

            # Aperture info
            ap = stage.aperture
            if ap.fan_angle is not None:
                stage_data.append([t("pdf.fan_angle", "Fan Angle"), f"{ap.fan_angle:.1f}°"])
            if ap.fan_slit_width is not None:
                stage_data.append([t("pdf.slit_width", "Slit Width"), f"{ap.fan_slit_width:.1f} mm"])

            table = Table(stage_data, colWidths=[80 * mm, 80 * mm])
            table.setStyle(self._table_style())
            story.append(table)
            story.append(Spacer(1, 6 * mm))

        return story

    # ------------------------------------------------------------------
    # Section C — Attenuation Charts
    # ------------------------------------------------------------------

    def _build_section_c(self, chart_images: dict[str, bytes]) -> list:
        story = [
            Paragraph(t("pdf.sec_c", "C — Attenuation Analysis"), self._styles["SectionTitle"]),
        ]

        for key, label in [
            ("mu_rho", t("pdf.chart_mu_rho", "Mass Attenuation Coefficient (μ/ρ vs Energy)")),
            ("transmission", t("pdf.chart_transmission", "Transmission vs Thickness")),
            ("hvl", t("pdf.chart_hvl", "Half-Value Layer (HVL vs Energy)")),
        ]:
            if key in chart_images:
                story.append(Paragraph(label, self._styles["SubSection"]))
                img = Image(BytesIO(chart_images[key]), width=150 * mm, height=80 * mm)
                img.hAlign = "CENTER"
                story.append(img)
                story.append(Spacer(1, 6 * mm))

        if not any(k in chart_images for k in ["mu_rho", "transmission", "hvl"]):
            story.append(Paragraph(
                t("pdf.no_chart_images", "Chart images not available."), self._styles["BodyText2"],
            ))

        return story

    # ------------------------------------------------------------------
    # Section D — Build-up Analysis
    # ------------------------------------------------------------------

    def _build_section_d(self, result: SimulationResult | None) -> list:
        story = [
            Paragraph(t("pdf.sec_d", "D — Build-up Analysis"), self._styles["SectionTitle"]),
        ]

        if result and result.include_buildup:
            story.append(Paragraph(
                t("pdf.buildup_included", "Simulation includes build-up factor (GP method)."),
                self._styles["BodyText2"],
            ))
        else:
            story.append(Paragraph(
                t("pdf.buildup_not_available", "Build-up analysis not available or disabled."),
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
            Paragraph(t("pdf.sec_e", "E — Beam Profile"), self._styles["SectionTitle"]),
        ]

        if "beam_profile" in chart_images:
            img = Image(BytesIO(chart_images["beam_profile"]), width=150 * mm, height=80 * mm)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 6 * mm))

        # Profile summary
        qm = result.quality_metrics
        data = [
            [t("pdf.col_metric", "Metric"), t("pdf.col_value", "Value")],
            [t("pdf.energy", "Energy"), f"{result.energy_keV:.0f} keV"],
            [t("pdf.ray_count", "Ray Count"), str(result.num_rays)],
            ["FWHM", f"{qm.fwhm_mm:.2f} mm"],
            [t("pdf.computation_time", "Computation Time"), f"{result.elapsed_seconds:.2f} s"],
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
            Paragraph(t("pdf.sec_f", "F — Quality Metrics"), self._styles["SectionTitle"]),
        ]

        qm = result.quality_metrics
        data = [
            [t("pdf.col_metric", "Metric"), t("pdf.col_value", "Value"), t("pdf.col_unit", "Unit"), t("pdf.col_status", "Status")],
        ]
        for m in qm.metrics:
            status_text = {
                "excellent": t("pdf.status_excellent", "Excellent"),
                "acceptable": t("pdf.status_acceptable", "Acceptable"),
                "poor": t("pdf.status_poor", "Poor"),
            }.get(m.status.value, m.status.value)
            data.append([m.name, f"{m.value:.3f}", m.unit, status_text])

        # Add aggregate metrics
        data.extend([
            [t("pdf.penumbra_left", "Penumbra (left)"), f"{qm.penumbra_left_mm:.2f}", "mm", ""],
            [t("pdf.penumbra_right", "Penumbra (right)"), f"{qm.penumbra_right_mm:.2f}", "mm", ""],
            [t("pdf.flatness", "Flatness"), f"{qm.flatness_pct:.2f}", "%", ""],
            [t("pdf.avg_leakage", "Average Leakage"), f"{qm.leakage_avg_pct:.3f}", "%", ""],
            [t("pdf.max_leakage", "Max Leakage"), f"{qm.leakage_max_pct:.3f}", "%", ""],
            [t("pdf.collimation_ratio", "Collimation Ratio"), f"{qm.collimation_ratio_dB:.1f}", "dB", ""],
        ])

        table = Table(data, colWidths=[50 * mm, 35 * mm, 25 * mm, 50 * mm])
        table.setStyle(self._table_style())
        story.append(table)

        # Pass/fail summary
        verdict = t("pdf.all_pass", "ALL METRICS PASS") if qm.all_pass else t("pdf.some_fail", "SOME METRICS FAIL")
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f"<b>{t('pdf.overall_result', 'Overall Result')}: {verdict}</b>", self._styles["BodyText2"]))

        # Dose rate summary (if computed)
        unatt = result.unattenuated_dose_rate_Gy_h
        if unatt > 0:
            import numpy as np
            from app.core.units import Gy_h_to_µSv_h as _gy_to_usv
            max_int = float(np.max(result.beam_profile.intensities)) if len(result.beam_profile.intensities) > 0 else 0.0
            max_dose = max_int * unatt
            story.append(Spacer(1, 6 * mm))
            story.append(Paragraph(
                t("pdf.dose_summary", "Dose Rate Summary"),
                self._styles["SectionTitle"],
            ))
            dose_data = [
                [t("pdf.col_parameter", "Parameter"), t("pdf.col_value", "Value")],
                [t("pdf.open_beam_gy", "Open Beam (Gy/h)"), f"{unatt:.4g}"],
                [t("pdf.open_beam_usv", "Open Beam (\u00b5Sv/h)"), f"{_gy_to_usv(unatt):.1f}"],
                [t("pdf.max_beam_gy", "Max Beam (Gy/h)"), f"{max_dose:.4g}"],
                [t("pdf.max_beam_usv", "Max Beam (\u00b5Sv/h)"), f"{_gy_to_usv(max_dose):.1f}"],
            ]
            dose_table = Table(dose_data, colWidths=[80 * mm, 60 * mm])
            dose_table.setStyle(self._table_style())
            story.append(dose_table)

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
            Paragraph(t("pdf.sec_g", "G — Compton Analysis"), self._styles["SectionTitle"]),
        ]

        if compton_result is None:
            story.append(Paragraph(
                t("pdf.compton_not_available", "Compton analysis data not available."),
                self._styles["BodyText2"],
            ))
            return story

        # Summary table
        data = [
            [t("pdf.col_parameter", "Parameter"), t("pdf.col_value", "Value")],
            [t("pdf.incident_energy", "Incident Energy"), f"{compton_result.incident_energy_keV:.1f} keV"],
            [t("pdf.total_cross_section", "Total Cross Section"), f"{compton_result.total_cross_section:.4e} cm\u00B2"],
            ["SPR", f"{compton_result.scatter_to_primary_ratio:.4f}"],
        ]
        table = Table(data, colWidths=[80 * mm, 80 * mm])
        table.setStyle(self._table_style())
        story.append(table)
        story.append(Spacer(1, 6 * mm))

        # Chart images (if provided)
        for key, label in [
            ("compton_polar", t("pdf.chart_kn_polar", "Klein-Nishina Polar Distribution")),
            ("compton_spectrum", t("pdf.chart_scatter_spectrum", "Scatter Energy Spectrum")),
            ("compton_spr", t("pdf.chart_spr", "SPR Profile")),
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
            Paragraph(t("pdf.sec_h", "H — Model Assumptions & Warnings"), self._styles["SectionTitle"]),
        ]

        # Physics models
        story.append(Paragraph(t("pdf.physics_model", "Physics Model"), self._styles["SubSection"]))
        models_data = [
            [t("pdf.col_model", "Model"), t("pdf.col_description", "Description")],
            [t("pdf.model_attenuation", "Attenuation"), t("pdf.model_attenuation_desc", "Beer-Lambert (narrow-beam geometry)")],
            [t("pdf.model_data_source", "Data Source"), t("pdf.model_data_source_desc", "NIST XCOM (log-log interpolation)")],
            ["Build-up", t("pdf.model_buildup_desc", "GP (Geometric Progression) formula")],
            ["Compton", t("pdf.model_compton_desc", "Klein-Nishina differential cross section")],
            ["Scatter", t("pdf.model_scatter_desc", "Monte Carlo single-scatter approximation")],
            [t("pdf.model_alloy", "Alloy"), t("pdf.model_alloy_desc", "Mixture rule: (μ/ρ)_alloy = SUM(w_i * (μ/ρ)_i)")],
        ]
        table = Table(models_data, colWidths=[50 * mm, 110 * mm])
        table.setStyle(self._table_style())
        story.append(table)
        story.append(Spacer(1, 6 * mm))

        # Limitations
        story.append(Paragraph(t("pdf.constraints", "Constraints"), self._styles["SubSection"]))
        limits_data = [
            [t("pdf.col_constraint", "Constraint"), t("pdf.col_detail", "Detail")],
            [t("pdf.constraint_energy_range", "Energy Range"), "1 keV \u2013 20 MeV"],
            [t("pdf.constraint_geometry", "Geometry"), t("pdf.constraint_geometry_desc", "2D cross-section, symmetry assumption")],
            ["Scatter", t("pdf.constraint_scatter_desc", "Single scatter; multiple scattering neglected")],
            [t("pdf.constraint_material", "Material"), t("pdf.constraint_material_desc", "Homogeneous; mixture rule (weighted fraction)")],
            [t("pdf.constraint_linac", "LINAC Mode"), t("pdf.constraint_linac_desc", "MeV mode bremsstrahlung spectrum approximation")],
            [t("pdf.constraint_polarization", "Polarization"), t("pdf.constraint_polarization_desc", "Neglected (non-polarized source)")],
        ]
        table = Table(limits_data, colWidths=[50 * mm, 110 * mm])
        table.setStyle(self._table_style())
        story.append(table)
        story.append(Spacer(1, 6 * mm))

        # Simulation-specific notes
        if result:
            notes = []
            if result.include_buildup:
                notes.append(t("pdf.note_buildup_on", "Build-up factor included (GP method)."))
            else:
                notes.append(t("pdf.note_buildup_off", "Build-up factor disabled."))
            if result.scatter_result:
                notes.append(t("pdf.note_scatter_on", "Compton scatter simulation included."))
            else:
                notes.append(t("pdf.note_scatter_off", "Compton scatter simulation not included."))
            for note in notes:
                story.append(Paragraph(f"\u2022 {note}", self._styles["BodyText2"]))

        return story

    # ------------------------------------------------------------------
    # Section I — Validation Summary
    # ------------------------------------------------------------------

    def _build_section_i(self, validation_results: list[dict] | None) -> list:
        story = [
            Paragraph(t("pdf.sec_i", "I — Validation Summary"), self._styles["SectionTitle"]),
        ]

        if not validation_results:
            story.append(Paragraph(
                t("pdf.no_validation", "No validation tests have been run."),
                self._styles["BodyText2"],
            ))
            return story

        data = [[
            t("pdf.col_test_id", "Test ID"),
            t("pdf.col_group", "Group"),
            t("pdf.col_ours", "Ours"),
            t("pdf.col_reference", "Reference"),
            t("pdf.col_diff_pct", "Diff%"),
            t("pdf.col_status", "Status"),
        ]]
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
            t("pdf.validation_summary", "<b>Total: {total} | Passed: {passed} | Failed: {failed}</b>").format(
                total=total, passed=passed, failed=failed,
            ),
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
        page_text = t("pdf.page_footer", "Page {page}").format(page=doc.page)
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, page_text)
        canvas.drawString(
            20 * mm, 10 * mm,
            f"{APP_NAME} v{APP_VERSION} — {datetime.now().strftime('%Y-%m-%d')}",
        )
        canvas.restoreState()
