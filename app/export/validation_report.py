"""Validation PDF report generator — ReportLab A4 report.

Generates a formal cross-validation report with cover, summary,
and per-group result tables (V1-V6).

Reference: Phase-08 spec — V&V documentation.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.constants import APP_NAME, APP_VERSION

if TYPE_CHECKING:
    from app.core.validation_runner import ValidationSummary

# Colors
_ACCENT = colors.HexColor("#3B82F6")
_HEADER_BG = colors.HexColor("#334155")
_PASS_BG = colors.HexColor("#DCFCE7")
_FAIL_BG = colors.HexColor("#FEE2E2")
_SKIP_BG = colors.HexColor("#FEF9C3")
_PASS_TEXT = colors.HexColor("#166534")
_FAIL_TEXT = colors.HexColor("#991B1B")
_SKIP_TEXT = colors.HexColor("#854D0E")

# Group titles
_GROUP_NAMES = {
    "V1": "V1 — Malzeme Veritabani (mu/rho vs xraylib)",
    "V2": "V2 — Fizik Motoru (HVL/TVL/Beer-Lambert)",
    "V3": "V3 — Build-up Faktorleri (GP vs ANSI)",
    "V4": "V4 — Compton/Klein-Nishina (kinematics + sigma)",
    "V5": "V5 — KN Ornekleyici (istatistiksel)",
    "V6": "V6 — Isin Simulasyonu (analitik levha)",
}


class ValidationReportExporter:
    """Generates a validation PDF report from ValidationSummary."""

    def __init__(self):
        self._styles = getSampleStyleSheet()
        self._add_custom_styles()

    def _add_custom_styles(self) -> None:
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
            fontSize=14, leading=18,
            textColor=_ACCENT, spaceAfter=8, spaceBefore=10,
        ))
        self._styles.add(ParagraphStyle(
            name="BodyText2",
            fontSize=10, leading=14,
            textColor=colors.black, spaceAfter=4,
        ))

    def generate_report(
        self,
        summary: ValidationSummary,
        output_path: str,
    ) -> None:
        """Build and save validation PDF report.

        Args:
            summary: Validation run results.
            output_path: Output PDF file path.
        """
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        story: list = []
        story.extend(self._build_cover(summary))
        story.append(PageBreak())
        story.extend(self._build_summary(summary))
        story.append(Spacer(1, 6 * mm))
        story.extend(self._build_results_tables(summary))

        doc.build(story, onFirstPage=self._add_footer, onLaterPages=self._add_footer)

    # ------------------------------------------------------------------
    # Cover
    # ------------------------------------------------------------------

    def _build_cover(self, summary: ValidationSummary) -> list:
        story = [
            Spacer(1, 60 * mm),
            Paragraph("Fizik Motoru Dogrulama Raporu", self._styles["CoverTitle"]),
            Paragraph("Cross-Validation Report (V1-V6)", self._styles["CoverSubtitle"]),
            Spacer(1, 10 * mm),
            Paragraph(
                f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                self._styles["CoverSubtitle"],
            ),
            Paragraph(
                f"Uygulama: {APP_NAME} v{APP_VERSION}",
                self._styles["CoverSubtitle"],
            ),
            Paragraph(
                f"xraylib: {'v' + summary.xraylib_version if summary.xraylib_available else 'Yuklu degil'}",
                self._styles["CoverSubtitle"],
            ),
            Spacer(1, 20 * mm),
        ]

        # Big pass/fail indicator
        if summary.failed == 0:
            verdict = "TUM TESTLER BASARILI"
            verdict_color = _PASS_TEXT
        else:
            verdict = f"{summary.failed} TEST BASARISIZ"
            verdict_color = _FAIL_TEXT

        story.append(Paragraph(
            f'<font color="{verdict_color.hexval()}" size="18"><b>{verdict}</b></font>',
            self._styles["BodyText2"],
        ))
        story.append(Paragraph(
            f"Toplam: {summary.total} | Basarili: {summary.passed} | "
            f"Basarisiz: {summary.failed} | Atlanan: {summary.skipped} | "
            f"Sure: {summary.duration_s:.2f}s",
            self._styles["BodyText2"],
        ))
        return story

    # ------------------------------------------------------------------
    # Summary table
    # ------------------------------------------------------------------

    def _build_summary(self, summary: ValidationSummary) -> list:
        story = [
            Paragraph("Ozet", self._styles["SectionTitle"]),
        ]

        # Per-group summary
        groups = {}
        for r in summary.results:
            g = r.group
            if g not in groups:
                groups[g] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
            groups[g]["total"] += 1
            if r.skipped:
                groups[g]["skipped"] += 1
            elif r.passed:
                groups[g]["passed"] += 1
            else:
                groups[g]["failed"] += 1

        data = [["Grup", "Aciklama", "Toplam", "Basarili", "Basarisiz", "Atlanan"]]
        for gid in sorted(groups.keys()):
            g = groups[gid]
            data.append([
                gid,
                _GROUP_NAMES.get(gid, gid),
                str(g["total"]),
                str(g["passed"]),
                str(g["failed"]),
                str(g["skipped"]),
            ])

        table = Table(data, colWidths=[15 * mm, 85 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm])
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]
        # Color failed rows
        for i, gid in enumerate(sorted(groups.keys()), start=1):
            if groups[gid]["failed"] > 0:
                style_cmds.append(("BACKGROUND", (4, i), (4, i), _FAIL_BG))

        table.setStyle(TableStyle(style_cmds))
        story.append(table)
        return story

    # ------------------------------------------------------------------
    # Per-group detail tables
    # ------------------------------------------------------------------

    def _build_results_tables(self, summary: ValidationSummary) -> list:
        story = []

        # Group results by V1-V6
        by_group: dict[str, list] = {}
        for r in summary.results:
            by_group.setdefault(r.group, []).append(r)

        for gid in sorted(by_group.keys()):
            results = by_group[gid]
            title = _GROUP_NAMES.get(gid, gid)
            story.append(Paragraph(title, self._styles["SectionTitle"]))

            data = [["Test ID", "Bizim", "Referans", "Fark%", "Tolerans%", "Durum"]]
            row_colors = []

            for r in results:
                if r.skipped:
                    status = "SKIP"
                    row_colors.append(_SKIP_BG)
                elif r.passed:
                    status = "PASS"
                    row_colors.append(_PASS_BG)
                else:
                    status = "FAIL"
                    row_colors.append(_FAIL_BG)

                ours_s = self._fmt(r.our_value)
                ref_s = self._fmt(r.ref_value)
                diff_s = f"{r.diff_pct:.2f}" if not r.skipped else "-"
                tol_s = f"{r.tolerance_pct:.1f}" if r.tolerance_pct > 0 else "exact"

                data.append([r.test_id, ours_s, ref_s, diff_s, tol_s, status])

            col_widths = [48 * mm, 25 * mm, 25 * mm, 18 * mm, 18 * mm, 16 * mm]
            table = Table(data, colWidths=col_widths)

            style_cmds = [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (5, 0), (5, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ]

            for i, bg in enumerate(row_colors, start=1):
                style_cmds.append(("BACKGROUND", (5, i), (5, i), bg))

            table.setStyle(TableStyle(style_cmds))
            story.append(table)
            story.append(Spacer(1, 4 * mm))

        return story

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt(val: float) -> str:
        if val == 0:
            return "0"
        if abs(val) < 0.001 or abs(val) > 1e4:
            return f"{val:.4e}"
        return f"{val:.4f}"

    @staticmethod
    def _add_footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.gray)
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Sayfa {doc.page}")
        canvas.drawString(
            20 * mm, 10 * mm,
            f"{APP_NAME} v{APP_VERSION} — {datetime.now().strftime('%Y-%m-%d')}",
        )
        canvas.restoreState()
