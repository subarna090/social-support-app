"""Bank statement PDF (research R7). Draws exactly the transactions in the view (FR-005)."""

from datetime import date
from pathlib import Path

from reportlab.platypus import Paragraph, Spacer

from social_support.synthetic.documents.common import (
    RenderedDocument,
    build_pdf,
    money,
    month_label,
    styles,
    table,
)


def render_bank_statement(shown: dict, path: Path) -> RenderedDocument:
    s = styles()
    story = [
        Paragraph(shown["bank_name"], s["title"]),
        Paragraph("Account statement", s["h2"]),
        Paragraph(f"Account holder: {shown['account_holder']}", s["body"]),
        Paragraph(f"Address: {shown['address']}", s["body"]),
        Paragraph(f"Account number: {shown['account_number']}", s["body"]),
        Paragraph(
            f"Statement period: {month_label(shown['period_start'])} to "
            f"{month_label(shown['period_end'])} ({shown['statement_months']} months)",
            s["body"],
        ),
        Paragraph(f"Opening balance: {money(shown['opening_balance_aed'])} AED", s["body"]),
    ]
    for month in shown["months"]:
        rows = [["Date", "Description", "Credit (AED)", "Debit (AED)", "Balance (AED)"]]
        for t in month["transactions"]:
            rows.append(
                [
                    t["date"],
                    t["description"],
                    money(t["credit_aed"]) if t["credit_aed"] else "",
                    money(t["debit_aed"]) if t["debit_aed"] else "",
                    money(t["balance_aed"]),
                ]
            )
        story += [
            Spacer(1, 6),
            Paragraph(date.fromisoformat(month["month"]).strftime("%B %Y"), s["h2"]),
            table(rows, [22, 78, 26, 26, 28]),
            Paragraph(
                f"Total credits: {money(shown['monthly_income_credits_aed'])} AED. "
                f"Closing balance: {money(month['closing_balance_aed'])} AED.",
                s["small"],
            ),
        ]
    build_pdf(path, "Account statement", story)
    return RenderedDocument(path, shown)
