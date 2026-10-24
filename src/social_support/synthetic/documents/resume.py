"""Resume PDF (research R7): contact details, employment history, education and skills."""

from pathlib import Path

from reportlab.platypus import Paragraph

from social_support.synthetic.documents.common import (
    RenderedDocument,
    build_pdf,
    month_label,
    styles,
)


def render_resume(shown: dict, path: Path) -> RenderedDocument:
    s = styles()
    story = [
        Paragraph(shown["full_name"], s["title"]),
        Paragraph(f"{shown['email']} | {shown['phone']}", s["body"]),
        Paragraph(shown["address"], s["body"]),
        Paragraph("Summary", s["h2"]),
        Paragraph(
            "Reliable professional looking for stable employment and opportunities to grow."
            if shown["jobs"]
            else "Motivated candidate looking for a first role and training opportunities.",
            s["body"],
        ),
        Paragraph("Employment history", s["h2"]),
    ]
    if not shown["jobs"]:
        story.append(Paragraph("No employment history.", s["body"]))
    for job in shown["jobs"]:
        end = "Present" if job["end"] is None else month_label(job["end"])
        story.append(
            Paragraph(
                f"<b>{job['title']}</b>, {job['employer']} ({month_label(job['start'])} - {end})",
                s["body"],
            )
        )
    story += [
        Paragraph("Education", s["h2"]),
        Paragraph(f"{shown['university']}, graduated {shown['graduation_year']}", s["body"]),
        Paragraph("Skills", s["h2"]),
        Paragraph(", ".join(shown["skills"]), s["body"]),
    ]
    build_pdf(path, "Resume", story)
    return RenderedDocument(path, shown)
