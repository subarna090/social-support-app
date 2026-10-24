"""Credit report PDF (research R7) from a fictional bureau, including household members on file."""

from pathlib import Path

from reportlab.platypus import Paragraph, Spacer

from social_support.synthetic.documents.common import (
    RenderedDocument,
    build_pdf,
    money,
    styles,
    table,
)


def render_credit_report(shown: dict, path: Path) -> RenderedDocument:
    s = styles()
    story = [
        Paragraph(shown["bureau_name"], s["title"]),
        Paragraph(f"Consumer credit report, issued {shown['report_date']}", s["h2"]),
        Paragraph("Subject", s["h2"]),
        table(
            [
                ["Name", shown["full_name"]],
                ["Emirates ID", shown["emirates_id"]],
                ["Date of birth", shown["date_of_birth"]],
                ["Address on file", shown["address"]],
            ],
            [40, 140],
            header=False,
        ),
        Paragraph("Household members on file", s["h2"]),
    ]
    members = shown["household_members"]
    if members:
        rows = [["Name", "Relationship", "Age"]]
        rows += [[m["name"], m["relationship"].title(), str(m["age"])] for m in members]
        story.append(table(rows, [90, 50, 40]))
    else:
        story.append(Paragraph("None recorded.", s["body"]))
    story += [
        Paragraph("Credit score", s["h2"]),
        Paragraph(f"Score: <b>{shown['credit_score']}</b> (range 300-900)", s["body"]),
        Paragraph(f"Active defaults: {shown['active_credit_defaults']}", s["body"]),
        Paragraph("Accounts", s["h2"]),
    ]
    accounts = shown["accounts"]
    if accounts:
        rows = [["Lender", "Type", "Balance (AED)", "Status"]]
        rows += [
            [a["lender"], a["kind"].replace("_", " ").title(), money(a["balance_aed"]), a["status"]]
            for a in accounts
        ]
        story.append(table(rows, [70, 40, 35, 35]))
    else:
        story.append(Paragraph("No credit accounts.", s["body"]))
    story += [Spacer(1, 8), Paragraph("Fictional bureau. For testing only.", s["small"])]
    build_pdf(path, "Credit report", story)
    return RenderedDocument(path, shown)
