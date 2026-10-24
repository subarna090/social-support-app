"""Shared helpers for document renderers: synthetic marking, formatting, deterministic PDFs."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

MARKING = "SYNTHETIC – NOT A REAL DOCUMENT"


@dataclass(frozen=True)
class RenderedDocument:
    path: Path
    shown: dict  # every displayed field, canonical form; written to answer_key.documents
    field_boxes: dict[str, tuple[int, int, int, int]] | None = field(default=None)  # tests only


def money(value: Decimal | str) -> str:
    """Display form of an amount: ``6,000.00``."""
    return f"{Decimal(value):,.2f}"


def month_label(value: date | str) -> str:
    """Display form of a month: ``Oct 2026``."""
    day = date.fromisoformat(value) if isinstance(value, str) else value
    return day.strftime("%b %Y")


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=16, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=11, spaceBefore=8),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=9, leading=12),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=8, leading=10),
    }


def table(rows: list[list[str]], widths: list[float], header: bool = True) -> Table:
    t = Table(rows, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    commands = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF2")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(commands))
    return t


def _mark_page(canvas, doc) -> None:
    """Diagonal watermark plus a footer, on every page (FR-017)."""
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(colors.Color(0.85, 0.1, 0.1, alpha=0.18))
    canvas.setFont("Helvetica-Bold", 30)
    canvas.translate(width / 2, height / 2)
    canvas.rotate(35)
    canvas.drawCentredString(0, 0, MARKING)
    canvas.restoreState()
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#B00000"))
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(15 * mm, 10 * mm, MARKING)
    canvas.drawRightString(width - 15 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(path: Path, title: str, story: list) -> None:
    """Render with ``invariant=1`` so the same content always gives the same bytes (R5)."""
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        invariant=1,
        title=title,
        author="Synthetic data generator",
        creator="social-support-data",
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
    )
    doc.build(story, onFirstPage=_mark_page, onLaterPages=_mark_page)
