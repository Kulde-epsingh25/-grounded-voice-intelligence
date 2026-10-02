"""
Q2 Knowledge Base — Source Registry.

Registers and tracks every source document entering the ingestion pipeline.
Uses SHA-256 for content identity.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from app.core.logging import get_logger
from app.kb.models import SourceRecord, SourceType, ExtractionStatus, compute_sha256

logger = get_logger(__name__)

# Map file extensions to SourceType
_EXTENSION_MAP: dict[str, SourceType] = {
    ".pdf": SourceType.PDF,
    ".docx": SourceType.DOCX,
    ".xlsx": SourceType.XLSX,
    ".csv": SourceType.CSV,
    ".html": SourceType.HTML,
    ".htm": SourceType.HTML,
    ".txt": SourceType.TXT,
    ".md": SourceType.TXT,
    ".png": SourceType.IMAGE,
    ".jpg": SourceType.IMAGE,
    ".jpeg": SourceType.IMAGE,
    ".tiff": SourceType.IMAGE,
    ".tif": SourceType.IMAGE,
    ".bmp": SourceType.IMAGE,
}


def detect_source_type(filepath: Path) -> SourceType:
    """Detect source type from file extension."""
    ext = filepath.suffix.lower()
    return _EXTENSION_MAP.get(ext, SourceType.UNKNOWN)


def register_source(filepath: Path) -> SourceRecord:
    """Register a source file and compute its content identity.

    Args:
        filepath: Path to the source file.

    Returns:
        SourceRecord with checksum and type detection.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Source file not found: {filepath}")

    content = filepath.read_bytes()
    content_hash = compute_sha256(content)
    source_type = detect_source_type(filepath)

    record = SourceRecord(
        filename=filepath.name,
        source_type=source_type,
        uri=str(filepath.resolve()),
        content_hash=content_hash,
        extraction_method=f"native_{source_type.value}",
    )

    logger.info(
        "Source registered",
        extra={"extra_data": {
            "source_id": record.source_id,
            "filename": record.filename,
            "source_type": record.source_type.value,
            "content_hash_prefix": content_hash[:12],
        }},
    )

    return record


class SourceRegistry:
    """In-memory registry of all registered sources."""

    def __init__(self) -> None:
        self._sources: dict[str, SourceRecord] = {}
        self._hash_index: dict[str, str] = {}  # hash -> source_id

    def register(self, filepath: Path) -> SourceRecord:
        """Register a source and check for duplicate content."""
        record = register_source(filepath)

        # Check if identical content already registered
        if record.content_hash in self._hash_index:
            existing_id = self._hash_index[record.content_hash]
            logger.info(
                "Duplicate source content detected",
                extra={"extra_data": {
                    "new_source_id": record.source_id,
                    "existing_source_id": existing_id,
                    "hash_prefix": record.content_hash[:12],
                }},
            )

        self._sources[record.source_id] = record
        self._hash_index[record.content_hash] = record.source_id
        return record

    def get(self, source_id: str) -> SourceRecord | None:
        return self._sources.get(source_id)

    def get_by_hash(self, content_hash: str) -> SourceRecord | None:
        sid = self._hash_index.get(content_hash)
        return self._sources.get(sid) if sid else None

    def all_sources(self) -> list[SourceRecord]:
        return list(self._sources.values())

    def update_status(
        self,
        source_id: str,
        status: ExtractionStatus,
        error_code: str = "",
        error_message: str = "",
    ) -> None:
        """Update source status after processing."""
        record = self._sources.get(source_id)
        if record:
            record.status = status
            record.error_code = error_code
            record.error_message = error_message
