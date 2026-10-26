"""Hand-made broken uploads for feature 004 tests and the demo (spec edge cases)."""

from pathlib import Path


def broken_files(approve_pack: Path) -> dict[str, tuple[str, dict]]:
    """``{case: (field it replaces, multipart replacement)}``."""
    pdf = (approve_pack / "resume.pdf").read_bytes()
    return {
        "empty": ("bank_statement", {"bank_statement": ("empty.pdf", b"", "application/pdf")}),
        "truncated_pdf": (
            "credit_report",
            {"credit_report": ("cut.pdf", pdf[: len(pdf) // 3], "application/pdf")},
        ),
        "pdf_as_id_card": (
            "emirates_id_card",
            {"emirates_id_card": ("card.png", pdf, "image/png")},
        ),
        "over_10_mb": (
            "resume",
            {"resume": ("big.pdf", b"%PDF" + b"0" * (10 * 1024 * 1024 - 3), "application/pdf")},
        ),
    }
