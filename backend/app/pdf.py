"""Server-side PDF in the same layout as the browser print packet (frontend/src/lib/export.ts printNode):
header (council, product), generated-at line, SIMULATED marker when bank data is shown, title, subtitle, body, footer.
Each page also carries "page x of y" and who exported it (role, not a personal number)."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import CondPageBreak, KeepTogether, LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from .nudge.clock import now_ist

NAVY, MUTED, LINE, SIM_BG, SIM_FG = colors.HexColor("#0f1f45"), colors.HexColor("#4b5874"), colors.HexColor("#d8dfea"), colors.HexColor("#fff4d6"), colors.HexColor("#7a4b00")
FOOT = "Printed from NIDHIVEDA. Bank channels in this build are simulated; this document is not an AICTE record."


def _font() -> tuple[str, str]:
    for reg, bold in (("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),):
        if Path(reg).exists() and Path(bold).exists():
            try:
                pdfmetrics.registerFont(TTFont("TLSans", reg))
                pdfmetrics.registerFont(TTFont("TLSans-Bold", bold))
                return "TLSans", "TLSans-Bold"
            except Exception:  # noqa: BLE001
                break
    return "Helvetica", "Helvetica-Bold"


FONT, BOLD = _font()
S_TITLE = ParagraphStyle("t", fontName=BOLD, fontSize=15, leading=19, textColor=NAVY, spaceAfter=2)
S_SUB = ParagraphStyle("s", fontName=FONT, fontSize=9, leading=12, textColor=MUTED, spaceAfter=6)
S_CELL = ParagraphStyle("c", fontName=FONT, fontSize=7.6, leading=9.4, textColor=colors.HexColor("#26334f"))
S_HEAD = ParagraphStyle("h", parent=S_CELL, fontName=BOLD, textColor=NAVY)
S_TEXT = ParagraphStyle("x", fontName=FONT, fontSize=9, leading=12.5, textColor=colors.HexColor("#26334f"), spaceAfter=4)
S_H2 = ParagraphStyle("h2", fontName=BOLD, fontSize=11, leading=14, textColor=NAVY, spaceBefore=8, spaceAfter=4)


class _Packet:
    def __init__(self, title: str, simulated: bool, exported_by: str):
        self.title, self.simulated, self.exported_by = title, simulated, exported_by
        self.generated = now_ist().strftime("%d %b %Y, %H:%M IST")

    def frame(self, canv, doc):
        w, h = doc.pagesize
        canv.saveState()
        canv.setFillColor(NAVY)
        canv.setFont(BOLD, 9.5)
        canv.drawString(doc.leftMargin, h - 14 * mm, "All India Council for Technical Education")
        canv.setFont(FONT, 8)
        canv.setFillColor(MUTED)
        canv.drawString(doc.leftMargin, h - 18 * mm, "NIDHIVEDA · Security Deposit & FDR Management Portal")
        canv.drawRightString(w - doc.rightMargin, h - 14 * mm, f"Generated {self.generated}")
        if self.simulated:
            tw = canv.stringWidth("SIMULATED bank data", BOLD, 7.5) + 8
            canv.setFillColor(SIM_BG)
            canv.setStrokeColor(colors.HexColor("#f0c060"))
            canv.roundRect(w - doc.rightMargin - tw, h - 21.2 * mm, tw, 4.6 * mm, 1.2 * mm, fill=1, stroke=1)
            canv.setFillColor(SIM_FG)
            canv.setFont(BOLD, 7.5)
            canv.drawRightString(w - doc.rightMargin - 4, h - 19.9 * mm, "SIMULATED bank data")
        canv.setStrokeColor(LINE)
        canv.line(doc.leftMargin, h - 23 * mm, w - doc.rightMargin, h - 23 * mm)
        canv.line(doc.leftMargin, 15 * mm, w - doc.rightMargin, 15 * mm)
        canv.setFont(FONT, 7)
        canv.setFillColor(MUTED)
        canv.drawString(doc.leftMargin, 11 * mm, FOOT)
        canv.drawString(doc.leftMargin, 7.5 * mm, f"Exported by {self.exported_by}")
        canv.drawRightString(w - doc.rightMargin, 7.5 * mm, f"Page {canv.getPageNumber()} of {getattr(doc, '_tl_pages', '?')}")
        canv.restoreState()


def _cell(v) -> Paragraph:
    return Paragraph(escape("" if v is None else str(v)), S_CELL)


def auto_widths(columns: list[str], rows: list[list], avail: float) -> list[float]:
    """Column widths proportional to typical content length (clamped), summing to the frame width."""
    weights = []
    for i, c in enumerate(columns):
        lens = sorted(len(str(r[i])) if i < len(r) and r[i] is not None else 0 for r in rows[:300]) or [0]
        typical = lens[int(len(lens) * 0.9) - 1] if len(lens) > 1 else lens[0]
        weights.append(min(max(typical, len(c), 4), 60))
    total = sum(weights)
    return [avail * w / total for w in weights]


def table(columns: list[str], rows: list[list], widths: list[float] | None = None) -> LongTable:
    data = [[Paragraph(escape(c), S_HEAD) for c in columns]] + [[_cell(v) for v in r[: len(columns)]] for r in rows]
    t = LongTable(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f6fb")), ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafbfd")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]))
    return t


def build(title: str, blocks: list, *, subtitle: str | None = None, simulated: bool = False, exported_by: str = "", wide: bool = False) -> bytes:
    """`blocks`: reportlab flowables or ("h2", text) / ("p", text) / ("table", columns, rows) tuples."""
    pk = _Packet(title, simulated, exported_by)
    size = landscape(A4) if wide else A4
    story = [Paragraph(escape(title), S_TITLE)]
    if subtitle:
        story.append(Paragraph(escape(subtitle), S_SUB))
    story.append(Spacer(1, 3 * mm))
    avail = size[0] - 28 * mm - 14   # frame padding (6 pt each side) and a 2 pt margin for rounding
    for b in blocks:
        if isinstance(b, tuple):
            if b[0] == "h2":
                story.append(Paragraph(escape(b[1]), S_H2))
            elif b[0] == "p":
                story.append(Paragraph(escape(b[1]), S_TEXT))
            elif b[0] == "table":
                # a table must not start where only its repeated header fits: reportlab cannot split it there
                story.append(CondPageBreak(30 * mm))
                story.append(table(b[1], b[2], auto_widths(b[1], b[2], avail)))
            elif b[0] == "kv":
                story.append(KeepTogether(table(["Field", "Value"], [[k, v] for k, v in b[1]], [55 * mm, avail - 55 * mm])))
        else:
            story.append(b)

    def render(pages: int | str) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=size, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=27 * mm, bottomMargin=19 * mm,
                                title=title, author="NIDHIVEDA", subject=("SIMULATED bank data. " if simulated else "") + (subtitle or ""),
                                creator="NIDHIVEDA")
        doc._tl_pages = pages
        doc.build(list(story), onFirstPage=pk.frame, onLaterPages=pk.frame)
        return buf.getvalue(), doc.page

    _, n = render("?")
    data, _ = render(n)
    return data


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M")
