"""Bank statement PDF (research R7): income credits, fixed payments and everyday spending."""

import random
from datetime import date
from decimal import Decimal
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


def _months(period_start: date, count: int) -> list[date]:
    months, year, month = [], period_start.year, period_start.month
    for _ in range(count):
        months.append(date(year, month, 1))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def render_bank_statement(shown: dict, path: Path, rng: random.Random) -> RenderedDocument:
    s = styles()
    months = _months(date.fromisoformat(shown["period_start"]), shown["statement_months"])
    balance = Decimal(shown["opening_balance_aed"])
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
        Paragraph(f"Opening balance: {money(balance)} AED", s["body"]),
    ]
    for month in months:
        entries = [
            (1, c["description"], Decimal(c["amount_aed"]), None) for c in shown["income_credits"]
        ]
        entries += [
            (5, p["description"], None, Decimal(p["amount_aed"])) for p in shown["monthly_payments"]
        ]
        entries += [
            (10, "Utilities - Oasis Power and Water (Demo)", None, Decimal(rng.randint(250, 900))),
            (
                15,
                "Groceries - Spice Route Supermarket (Demo)",
                None,
                Decimal(rng.randint(300, 1500)),
            ),
            (25, "Groceries - Palm Leaf Retail (Demo)", None, Decimal(rng.randint(200, 1200))),
        ]
        rows = [["Date", "Description", "Credit (AED)", "Debit (AED)", "Balance (AED)"]]
        for day, description, credit, debit in entries:
            balance += (credit or 0) - (debit or 0)
            rows.append(
                [
                    date(month.year, month.month, day).isoformat(),
                    description,
                    money(credit) if credit else "",
                    money(debit) if debit else "",
                    money(balance),
                ]
            )
        story += [
            Spacer(1, 6),
            Paragraph(month.strftime("%B %Y"), s["h2"]),
            table(rows, [22, 78, 26, 26, 28]),
            Paragraph(
                f"Total credits: {money(shown['monthly_income_credits_aed'])} AED. "
                f"Closing balance: {money(balance)} AED.",
                s["small"],
            ),
        ]
    build_pdf(path, "Account statement", story)
    return RenderedDocument(path, shown)
