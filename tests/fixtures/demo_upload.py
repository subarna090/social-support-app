"""Helpers to upload a feature 004 demo pack through the API, as the UI does."""

import json
from pathlib import Path

URL = "/api/v1/applications/with-documents"
UPLOADS = {  # multipart field -> file in the pack, content type
    "bank_statement": ("bank_statement.pdf", "application/pdf"),
    "emirates_id_card": ("emirates_id.png", "image/png"),
    "resume": ("resume.pdf", "application/pdf"),
    "assets_liabilities": (
        "assets_liabilities.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "credit_report": ("credit_report.pdf", "application/pdf"),
}


def form_values(pack: Path) -> dict:
    return json.loads((pack / "form.json").read_text(encoding="utf-8"))["submission"]


def pack_files(pack: Path, replace: dict | None = None, omit: tuple = ()) -> dict:
    """Multipart files for ``pack``; ``replace`` maps a field to (filename, bytes, content type)."""
    files = {
        field: (name, (pack / name).read_bytes(), content_type)
        for field, (name, content_type) in UPLOADS.items()
        if field not in omit
    }
    files.update(replace or {})
    return files


def upload_pack(client, pack: Path, *, replace=None, omit=(), **form_overrides):
    data = {k: str(v) for k, v in (form_values(pack) | form_overrides).items()}
    return client.post(URL, data=data, files=pack_files(pack, replace, omit))
