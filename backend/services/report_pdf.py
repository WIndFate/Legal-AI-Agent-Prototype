from __future__ import annotations

import html
import os
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont


class ReportPdfRenderer:
    def __init__(self) -> None:
        self.latin_font = self._register_font(
            "ContractGuardLatin",
            ["/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"],
        )
        self.nepali_font = self._register_font(
            "ContractGuardNepali",
            ["/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"],
        )
        self.japanese_font = self._register_cid_font("HeiseiKakuGo-W5")
        self.simplified_chinese_font = self._register_cid_font("STSong-Light")
        self.traditional_chinese_font = self._register_cid_font("MSung-Light")
        self.korean_font = self._register_cid_font("HYGothic-Medium")

    @staticmethod
    def _register_font(name: str, candidates: list[str], subfont_index: int | None = None) -> str:
        for candidate in candidates:
            if os.path.exists(candidate):
                if name not in pdfmetrics.getRegisteredFontNames():
                    if subfont_index is None:
                        pdfmetrics.registerFont(TTFont(name, candidate))
                    else:
                        pdfmetrics.registerFont(TTFont(name, candidate, subfontIndex=subfont_index))
                return name
        return "Helvetica"

    @staticmethod
    def _register_cid_font(name: str) -> str:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont(name))
        return name

    def _font_name_for_language(self, language: str) -> str:
        if language == "ne" and self.nepali_font != "Helvetica":
            return self.nepali_font
        if language == "ja":
            return self.japanese_font
        if language == "zh-CN":
            return self.simplified_chinese_font
        if language == "zh-TW":
            return self.traditional_chinese_font
        if language == "ko":
            return self.korean_font
        return self.latin_font

    def _cjk_font_for_language(self, language: str) -> str:
        if language == "zh-CN":
            return self.simplified_chinese_font
        if language == "zh-TW":
            return self.traditional_chinese_font
        if language == "ko":
            return self.korean_font
        return self.japanese_font

    def build_pdf(
        self,
        *,
        order_id: str,
        language: str,
        created_at: str,
        expires_at: str,
        overall_risk_level: str,
        summary: str,
        clause_analyses: list[dict],
        high_risk_count: int,
        medium_risk_count: int,
        low_risk_count: int,
        total_clauses: int,
    ) -> bytes:
        font_name = self._font_name_for_language(language)
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=f"ContractGuard Report {order_id}",
            author="ContractGuard",
        )
        styles = getSampleStyleSheet()
        story = []
        cjk_font = self._cjk_font_for_language(language)

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontName=cjk_font,
            fontSize=18,
            leading=24,
            textColor=colors.HexColor("#1f3a5f"),
            spaceAfter=8,
            alignment=TA_LEFT,
        )
        body_style = ParagraphStyle(
            "ReportBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#171411"),
            spaceAfter=6,
        )
        meta_style = ParagraphStyle(
            "ReportMeta",
            parent=body_style,
            fontSize=8.8,
            leading=12,
            textColor=colors.HexColor("#6b7280"),
            spaceAfter=4,
        )
        section_style = ParagraphStyle(
            "ReportSection",
            parent=body_style,
            fontSize=11.5,
            leading=16,
            textColor=colors.HexColor("#1f3a5f"),
            spaceBefore=8,
            spaceAfter=4,
        )
        label_style = ParagraphStyle(
            "ReportLabel",
            parent=meta_style,
            fontName=font_name,
            fontSize=9.2,
            leading=13,
            textColor=colors.HexColor("#625b54"),
            spaceAfter=2,
        )

        story.append(Paragraph("ContractGuard", title_style))
        story.append(Paragraph(self._escape_text("Analysis Report"), meta_style))
        story.append(Paragraph(self._escape_text(summary), body_style))
        story.append(Spacer(1, 4))

        summary_table = Table(
            [
                [
                    self._kv_block("Order ID", order_id, body_style, label_style, font_name=font_name),
                    self._kv_block("Overall Risk", overall_risk_level, body_style, label_style, font_name=font_name),
                ],
                [
                    self._kv_block("Clauses", str(total_clauses), body_style, label_style, font_name=font_name),
                    self._kv_block(
                        "Risk Counts",
                        f"High {high_risk_count} / Medium {medium_risk_count} / Low {low_risk_count}",
                        body_style,
                        label_style,
                        font_name=font_name,
                    ),
                ],
                [
                    self._kv_block("Created", created_at, body_style, label_style, font_name=font_name),
                    self._kv_block("Expires", expires_at, body_style, label_style, font_name=font_name),
                ],
            ],
            colWidths=[89 * mm, 89 * mm],
            hAlign="LEFT",
        )
        summary_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#d9d2c7")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e7e1d7")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffdfa")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(summary_table)
        story.append(Spacer(1, 10))

        for index, clause in enumerate(clause_analyses, start=1):
            story.append(
                Paragraph(
                    self._escape_text(f"Finding #{index:02d} · {clause.get('clause_number', '')}"),
                    section_style,
                )
            )

            clause_rows = [
                [self._kv_block("Risk", clause.get("risk_level", ""), body_style, label_style, font_name=font_name)],
                [self._kv_block("Assessment", clause.get("risk_reason", ""), body_style, label_style, font_name=font_name)],
            ]

            suggestion = clause.get("suggestion")
            if suggestion:
                clause_rows.append([self._kv_block("Suggestion", suggestion, body_style, label_style, font_name=font_name)])

            referenced_law = clause.get("referenced_law")
            if referenced_law:
                clause_rows.append([self._kv_block("Referenced Law", referenced_law, body_style, label_style, font_name=cjk_font)])

            original_text = clause.get("original_text")
            if original_text:
                clause_rows.append([self._kv_block("Original Clause", original_text, body_style, label_style, font_name=cjk_font)])

            clause_table = Table(clause_rows, colWidths=[178 * mm], hAlign="LEFT")
            clause_table.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#dfd8ce")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#ece5dc")),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffdfa")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(clause_table)
            story.append(Spacer(1, 8))

        doc.build(story)
        return buffer.getvalue()

    @staticmethod
    def _escape_text(value: str) -> str:
        return html.escape(value or "").replace("\n", "<br/>")

    def _kv_block(
        self,
        label: str,
        value: str,
        body_style: ParagraphStyle,
        label_style: ParagraphStyle,
        *,
        font_name: str,
    ) -> Paragraph:
        label_html = f'<font color="#8a8178">{html.escape(label)}</font>'
        value_html = self._escape_text(value)
        return Paragraph(f"{label_html}<br/>{value_html}", self._clone_style(body_style, font_name))

    @staticmethod
    def _clone_style(base_style: ParagraphStyle, font_name: str) -> ParagraphStyle:
        return ParagraphStyle(
            name=f"{base_style.name}-{font_name}",
            parent=base_style,
            fontName=font_name,
        )


renderer = ReportPdfRenderer()
