"""Exportación de incidentes a CSV (compatible con Excel) y PDF (reportlab)."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from app.api.schemas import IncidentOut
from app.db.models import ActionTaken
from app.domain.categories import LABEL_ES, MACRO_LABEL_ES

ACTION_ES = {
    ActionTaken.DELETED_WARNED: "Borrado y advertencia",
    ActionTaken.DELETED_BANNED: "Borrado y expulsión",
    ActionTaken.DELETED_CRISIS_SUPPORT: "Borrado y apoyo en crisis",
    ActionTaken.LOGGED_ONLY: "Solo registrado",
}
HEADERS = ["ID", "Fecha", "Grupo", "ID grupo", "Usuario", "ID usuario", "Macrocategoría", "Categoría",
           "Toxicidad", "Crisis", "Acción", "Respuesta del autor", "Mensaje"]


def _esc(text: str) -> str:
    """reportlab interpreta etiquetas en Paragraph: un nombre con '<' rompería el PDF."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe_cell(value: object) -> object:
    """Evita inyección de fórmulas al abrir el CSV en Excel (=, +, -, @ al inicio)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _fmt(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")


def to_csv(rows: list[IncidentOut], tz_name: str) -> bytes:
    tz = ZoneInfo(tz_name)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADERS)
    for r in rows:
        writer.writerow([_safe_cell(v) for v in [
            r.id, _fmt(r.created_at, tz), r.group_title, r.group_id, r.user_display, r.user_id,
            MACRO_LABEL_ES[r.macro_category], LABEL_ES[r.category], f"{r.toxicity_score:.3f}",
            f"{r.crisis_score:.3f}", ACTION_ES[r.action], r.user_response.value if r.user_response else "",
            r.message_text,
        ]])
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM para que Excel respete acentos


def _footer(canvas: object, doc: object) -> None:
    c = canvas  # type: ignore[assignment]
    c.saveState()  # type: ignore[attr-defined]
    c.setFont("Helvetica", 7.5)  # type: ignore[attr-defined]
    c.setFillColor(colors.HexColor("#5b6472"))  # type: ignore[attr-defined]
    c.drawString(14 * mm, 9 * mm, "Centinela — reporte de moderación")  # type: ignore[attr-defined]
    c.drawRightString(landscape(A4)[0] - 14 * mm, 9 * mm, f"Página {doc.page}")  # type: ignore[attr-defined]
    c.restoreState()  # type: ignore[attr-defined]


def to_pdf(rows: list[IncidentOut], *, title: str, filters_desc: str, tz_name: str) -> bytes:
    tz = ZoneInfo(tz_name)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=14 * mm, bottomMargin=16 * mm, title=title, author="Centinela")
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontName="Times-Bold", fontSize=18, alignment=0,
                        textColor=colors.HexColor("#1b2a41"), spaceAfter=4)
    meta = ParagraphStyle("meta", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#5b6472"))
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7.4, leading=9)

    total = len(rows)
    crisis = sum(1 for r in rows if r.macro_category.value == "crisis")
    mean = (sum(r.toxicity_score for r in rows if r.macro_category.value != "crisis")
            / max(1, total - crisis))
    story: list[object] = [
        Paragraph(_esc(title), h1),
        Paragraph(_esc(f"Generado el {datetime.now(tz).strftime('%d/%m/%Y %H:%M')} ({tz_name}). {filters_desc}"), meta),
        Paragraph(f"Incidentes: <b>{total}</b>. Alertas de crisis: <b>{crisis}</b>. "
                  f"Toxicidad media (sin crisis): <b>{mean:.2f}</b>.", meta),
        Spacer(1, 6 * mm),
    ]
    data: list[list[object]] = [["Fecha", "Grupo", "Usuario", "Categoría", "Tox.", "Acción", "Mensaje"]]
    for r in rows:
        text = r.message_text if len(r.message_text) < 280 else r.message_text[:277] + "..."
        data.append([
            _fmt(r.created_at, tz), Paragraph(_esc(r.group_title), cell), Paragraph(_esc(r.user_display), cell),
            Paragraph(LABEL_ES[r.category], cell), f"{r.toxicity_score:.2f}", Paragraph(ACTION_ES[r.action], cell),
            Paragraph(_esc(text), cell),
        ])
    table = LongTable(data, repeatRows=1,
                      colWidths=[26 * mm, 38 * mm, 32 * mm, 32 * mm, 13 * mm, 32 * mm, None])
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.8),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 7.4),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1b2a41")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#1b2a41")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#d5d9e0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (4, 1), (4, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)  # type: ignore[arg-type]
    return buf.getvalue()
