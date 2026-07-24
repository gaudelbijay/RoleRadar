"""Styled PDF output for jobSearch results."""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

NAVY = colors.HexColor("#14213D")
BLUE = colors.HexColor("#2563EB")
SKY = colors.HexColor("#EFF6FF")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#DCE4F2")
GREEN = colors.HexColor("#047857")
WHITE = colors.white


def _text(value) -> str:
    return escape(str(value or "Not disclosed"))


def _footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(0.55 * inch, 0.48 * inch, 8.0 * inch, 0.48 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.55 * inch, 0.3 * inch, "Job Search · Verified source listings")
    canvas.drawRightString(8.0 * inch, 0.3 * inch, f"Page {document.page}")
    canvas.restoreState()


def build_pdf(query: str, result: dict, output_path: str | Path) -> str:
    """Create a concise, styled, clickable PDF and return its path."""
    output_path = str(output_path)
    document = SimpleDocTemplate(
        output_path, pagesize=letter, rightMargin=0.55 * inch,
        leftMargin=0.55 * inch, topMargin=0.55 * inch, bottomMargin=0.62 * inch,
        title=f"Job Search — {query}",
    )
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "Title", parent=base["Title"], fontName="Helvetica-Bold",
        fontSize=25, leading=29, textColor=NAVY, alignment=TA_LEFT,
        spaceAfter=8,
    )
    subtitle = ParagraphStyle(
        "Subtitle", parent=base["BodyText"], fontSize=10.5, leading=15,
        textColor=MUTED, spaceAfter=12,
    )
    job_title = ParagraphStyle(
        "JobTitle", parent=base["Heading2"], fontName="Helvetica-Bold",
        fontSize=15, leading=19, textColor=NAVY, spaceAfter=3,
    )
    company = ParagraphStyle(
        "Company", parent=base["BodyText"], fontName="Helvetica-Bold",
        fontSize=11, leading=14, textColor=BLUE, spaceAfter=8,
    )
    label = ParagraphStyle(
        "Label", parent=base["BodyText"], fontName="Helvetica-Bold",
        fontSize=8.5, leading=11, textColor=MUTED,
    )
    body = ParagraphStyle(
        "Body", parent=base["BodyText"], fontSize=9.2, leading=13,
        textColor=INK, spaceAfter=4,
    )
    bullet = ParagraphStyle(
        "Bullet", parent=body, leftIndent=10, firstLineIndent=-7,
        bulletIndent=0, spaceAfter=2,
    )
    apply_style = ParagraphStyle(
        "Apply", parent=body, fontName="Helvetica-Bold", fontSize=10,
        textColor=WHITE, alignment=TA_CENTER,
    )

    jobs = result.get("jobs", [])
    location = ", ".join(
        part for part in [result.get("city"), result.get("country")] if part
    )
    story = [
        Paragraph("Job Search", title),
        Paragraph(
            f"<b>{_text(query)}</b><br/>"
            f"{_text(result.get('search_type', 'Jobs'))} · {_text(location)} · {_text(result.get('education'))} · minimum {result.get('minimum_salary', 0):,} in listing currency · "
            f"posted within {result.get('max_age_days')} days",
            subtitle,
        ),
    ]
    metrics = Table(
        [[
            Paragraph(f"<b>{result.get('fetched_count', 0)}</b><br/>scanned", body),
            Paragraph(f"<b>{len(jobs)}</b><br/>verified matches", body),
            Paragraph(f"<b>{result.get('max_age_days')}</b><br/>maximum days", body),
            Paragraph(("<b>Best fit</b><br/>personalized" if result.get("resume_personalized") else "<b>Newest</b><br/>shown first"), body),
        ]],
        colWidths=[1.82 * inch] * 4,
    )
    metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SKY),
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story += [metrics, Spacer(1, 16)]

    if not jobs:
        diagnostics = result.get("diagnostics", {})
        story += [
            Paragraph("No verified matches", job_title),
            Paragraph(
                "No connected source returned a listing that satisfied the selected "
                "role concepts, education, country, date, and age settings.",
                body,
            ),
            Paragraph(
                f"Missing concept: {diagnostics.get('missing_requested_concept', 0)} · "
                f"Country mismatch: {diagnostics.get('country_mismatch', 0)} · "
                f"Outside age: {diagnostics.get('outside_age_window', 0)} · "
                f"Salary unavailable: {diagnostics.get('salary_missing_or_unusable', 0)} · "
                f"Below salary: {diagnostics.get('salary_below_minimum', 0)}",
                subtitle,
            ),
        ]

    for index, job in enumerate(jobs, 1):
        requirements = job.get("requirements", [])[:6]
        experience = job.get("experience", [])[:4]
        url = _text(job.get("apply_url"))
        metadata = Table(
            [
                [
                    Paragraph("LOCATION", label),
                    Paragraph("POSTED", label),
                    Paragraph("SOURCE", label),
                ],
                [
                    Paragraph(_text(job.get("location")), body),
                    Paragraph(
                        f"{_text(job.get('published_iso'))}<br/>"
                        f"{job.get('age_days')} days ago", body,
                    ),
                    Paragraph(_text(job.get("source")), body),
                ],
            ],
            colWidths=[3.05 * inch, 1.65 * inch, 2.55 * inch],
        )
        metadata.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SKY),
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        salary = Table(
            [[
                Paragraph("COMPENSATION", label),
                Paragraph(_text(job.get("salary_display")), body),
            ]],
            colWidths=[1.2 * inch, 6.05 * inch],
        )
        salary.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ECFDF5")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#A7F3D0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        resume_fit = job.get("resume_fit")
        card = [
            Paragraph(f"{index:02d}  ·  {_text(job.get('title'))}", job_title),
            Paragraph(_text(job.get("company")), company),
            metadata, Spacer(1, 7), salary, Spacer(1, 8),
            *(
                [Paragraph(
                    f"<b>ESTIMATED RESUME FIT: {resume_fit['score']}%</b><br/>"
                    f"{_text(', '.join(resume_fit.get('matched_skills', [])[:8]) or 'Limited direct skill overlap')}",
                    body), Spacer(1, 7)] if resume_fit else []
            ),
            Paragraph("EXPERIENCE & EDUCATION", label),
        ]
        card.extend(
            Paragraph(f"• {_text(item)}", bullet) for item in experience
        )
        if not experience:
            card.append(Paragraph("Not explicitly stated.", body))
        card += [Spacer(1, 5), Paragraph("KEY REQUIREMENTS", label)]
        card.extend(
            Paragraph(f"• {_text(item)}", bullet) for item in requirements
        )
        if not requirements:
            card.append(Paragraph("No additional requirement extracted.", body))
        card += [
            Spacer(1, 5), Paragraph("ROLE SNAPSHOT", label),
            Paragraph(_text(job.get("role_overview", job.get("description", "")[:700])), body),
            Spacer(1, 6),
        ]
        apply_table = Table(
            [[Paragraph(
                f'<link href="{url}" color="white">OPEN ORIGINAL JOB &amp; APPLY →</link>',
                apply_style,
            )]],
            colWidths=[7.25 * inch],
        )
        apply_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BLUE),
            ("BOX", (0, 0), (-1, -1), 0, BLUE),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        card += [apply_table, Spacer(1, 16)]
        story.extend(card)

    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path
