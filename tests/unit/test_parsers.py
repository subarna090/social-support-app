"""T014: document parsers on text captured from the demo packs (feature 004, research R1-R4)."""

from datetime import date

import pytest

from social_support.domain.documents import DocumentType
from social_support.extraction import bank_statement, credit_report, emirates_id, resume

BANK_TEXT = """SYNTHETIC � NOT A REAL DOCUMENT
Page 1
 Desert Falcon Demo Bank
Account statement
Account holder: Hassan Ali Al Zaabi
Address: Apartment 703, Building 41, Street 14, Al Fajr Park, Ajman
Account number: DFDB 0000 24759674
Statement period: Jul 2026 to Sep 2026 (3 months)
Opening balance: 22,000.00 AED
July 2026
2026-07-01
Salary - Al Waha Engineering (Demo)
7,500.00
29,500.00
Total credits: 9,000.00 AED. Closing balance: 25,486.00 AED.
August 2026
Total credits: 9,000.00 AED. Closing balance: 28,102.00 AED.
September 2026
Total credits: 8,500.00 AED. Closing balance: 1,234,567.50 AED.
"""

CREDIT_TEXT = """ Demo Credit Information Bureau
Consumer credit report, issued 2026-10-01
Subject
Name
Hassan Ali Al Zaabi
Emirates ID
784-1985-0000903-4
Date of birth
1985-11-05
Address on file
Apartment 703, Building 41, Street 14, Al Fajr Park, Ajman
Household members on file
Name
Relationship
Age
Fatima Al Zaabi
Spouse
38
Credit score
Score: 690 (range 300-900)
Active defaults: 2
Accounts
"""

RESUME_TEXT = """ Mariam Saeed Al Hammadi
mariam.al.hammadi12@example.com | +971 50 000 0901
Apartment 1408, Building 22, Street 9, Al Waha District, Sharjah
Summary
Reliable professional looking for stable employment and opportunities to grow.
Employment history
Sales Associate, Palm Leaf Retail (Demo) (Feb 2025 - Present)
Receptionist, Blue Lagoon Hospitality (Demo) (Jun 2021 -
Nov 2024)
Education
Gulf Coast University (Demo), graduated 2009
Skills
Customer service, Point-of-sale systems, Inventory
control, Arabic and English
"""

OCR_LINES = [
    ("MOCKRESIDENTIDENTITYCARD", 0.99),
    ("SYNTHETIC", 1.0),
    ("Name", 1.0),
    ("Reem Al Suwaidi", 0.98),
    ("ID Number", 0.98),
    ("784-1981-0000001-1", 1.0),
    ("Nationality", 0.97),
    ("Emirati", 1.0),
    ("DateofBirth", 0.96),
    ("1981-05-14", 1.0),
    ("ExpiryDate", 1.0),
    ("2029-05-14", 1.0),
]


def test_bank_statement_averages_monthly_credits_and_keeps_last_closing_balance():
    doc = bank_statement.parse_text(BANK_TEXT)
    assert doc.document_type is DocumentType.BANK_STATEMENT and doc.ok
    assert doc.fields["account_holder"] == "Hassan Ali Al Zaabi"
    assert doc.fields["monthly_income_aed"] == "8833.33"  # (9000 + 9000 + 8500) / 3
    assert doc.fields["closing_balance_aed"] == "1234567.50"
    assert doc.fields["statement_months"] == "3"


def test_bank_statement_without_credit_lines_is_not_ok():
    doc = bank_statement.parse_text("Account holder: Someone\n")
    assert not doc.ok
    assert "monthly_income_aed" in doc.error


def test_credit_report_fields():
    doc = credit_report.parse_text(CREDIT_TEXT)
    assert doc.ok
    assert doc.fields == {
        "full_name": "Hassan Ali Al Zaabi",
        "emirates_id": "784-1985-0000903-4",
        "report_date": "2026-10-01",
        "address": "Apartment 703, Building 41, Street 14, Al Fajr Park, Ajman",
        "credit_score": "690",
        "active_credit_defaults": "2",
    }


def test_resume_jobs_skills_and_employment_window():
    doc = resume.parse_text(RESUME_TEXT, as_of=date(2026, 10, 1))
    assert doc.ok
    # Window Oct 2024 - Sep 2026: Oct-Nov 2024 (Receptionist) + Feb 2025 - Sep 2026 (20 months).
    assert doc.fields["months_employed_last_24"] == "22"
    # 20 months current + 42 months previous = 62 months.
    assert doc.fields["years_experience"] == "5.2"
    assert doc.fields["last_job_title"] == "Sales Associate"
    assert doc.fields["education"] == "Gulf Coast University (Demo), graduated 2009"
    assert doc.items["skills"] == (
        "Customer service",
        "Point-of-sale systems",
        "Inventory control",
        "Arabic and English",
    )
    assert doc.items["jobs"] == (
        "Sales Associate (Feb 2025 - Present)",
        "Receptionist (Jun 2021 - Nov 2024)",
    )


def test_resume_matches_the_generator_algorithm():
    from social_support.synthetic.profile import Job, months_employed_last_24

    jobs = (
        Job("A", "Sales Associate", date(2025, 2, 1), None),
        Job("B", "Receptionist", date(2021, 6, 1), date(2024, 11, 1)),
    )
    doc = resume.parse_text(RESUME_TEXT, as_of=date(2026, 10, 1))
    assert int(doc.fields["months_employed_last_24"]) == months_employed_last_24(
        jobs, date(2026, 10, 1)
    )


def test_resume_without_jobs_has_zero_months():
    text = "Employment history\nNo employment history.\nEducation\nX (Demo), graduated 2020\n"
    doc = resume.parse_text(text, as_of=date(2026, 10, 1))
    assert doc.ok
    assert doc.fields["months_employed_last_24"] == "0"
    assert doc.items["jobs"] == ()


def test_emirates_id_card_from_ocr_lines():
    doc = emirates_id.parse_ocr_lines(OCR_LINES, min_confidence=0.80)
    assert doc.ok
    assert doc.fields == {
        "full_name": "Reem Al Suwaidi",
        "emirates_id": "784-1981-0000001-1",
        "date_of_birth": "1981-05-14",
    }
    assert doc.confidence == {"full_name": 0.98, "emirates_id": 1.0, "date_of_birth": 1.0}


def test_emirates_id_number_is_found_without_hyphens():
    lines = [(t.replace("-", "") if t.startswith("784") else t, s) for t, s in OCR_LINES]
    doc = emirates_id.parse_ocr_lines(lines, min_confidence=0.80)
    assert doc.fields["emirates_id"] == "784-1981-0000001-1"


@pytest.mark.parametrize("score", [0.79, 0.5])
def test_low_confidence_required_field_makes_the_card_unreadable(score):
    lines = [(t, score if t == "Reem Al Suwaidi" else s) for t, s in OCR_LINES]
    doc = emirates_id.parse_ocr_lines(lines, min_confidence=0.80)
    assert not doc.ok
    assert "read with low confidence" in doc.error
    assert "full_name" in doc.error


def test_card_without_an_id_number_is_unreadable():
    lines = [(t, s) for t, s in OCR_LINES if not t.startswith("784")]
    doc = emirates_id.parse_ocr_lines(lines, min_confidence=0.80)
    assert not doc.ok
    assert "emirates_id" in doc.error
