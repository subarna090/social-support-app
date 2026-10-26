"""Storing uploaded documents on disk (feature 004). The database keeps the path and SHA-256."""

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from social_support.domain.documents import DocumentType

EXTENSIONS = {
    DocumentType.BANK_STATEMENT: ".pdf",
    DocumentType.RESUME: ".pdf",
    DocumentType.CREDIT_REPORT: ".pdf",
    DocumentType.ASSETS_LIABILITIES: ".xlsx",
}


@dataclass(frozen=True)
class Upload:
    document_type: DocumentType
    filename: str
    data: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()

    def stored_name(self) -> str:
        if self.document_type is DocumentType.EMIRATES_ID_CARD:
            suffix = ".jpg" if self.data.startswith(b"\xff\xd8\xff") else ".png"
        else:
            suffix = EXTENSIONS[self.document_type]
        return f"{self.document_type.value.lower()}{suffix}"


def stored_path(reference: str, upload: Upload) -> str:
    """Relative to ``UPLOAD_DIR``; the client's file name is never used in the path."""
    return str(PurePosixPath(reference) / upload.stored_name())


def store_files(upload_dir: Path, reference: str, uploads: list[Upload]) -> None:
    folder = upload_dir / reference
    folder.mkdir(parents=True, exist_ok=False)
    for upload in uploads:
        (upload_dir / stored_path(reference, upload)).write_bytes(upload.data)
