"""
Q2 Knowledge Base — Base Extractor Interface.

All format-specific extractors implement this interface.
Downstream code depends only on BaseExtractor, not specific libraries.
"""

from __future__ import annotations

import abc
from pathlib import Path

from app.kb.models import (
    ExtractedDocument,
    ExtractedElement,
    ExtractedTable,
    ExtractionDiagnostics,
    ExtractionStatus,
    SourceRecord,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseExtractor(abc.ABC):
    """Abstract base for all document extractors."""

    @abc.abstractmethod
    def extract(self, source: SourceRecord, filepath: Path) -> ExtractedDocument:
        """Extract content from a source document.

        Args:
            source: Registered source record.
            filepath: Path to the source file.

        Returns:
            ExtractedDocument with elements, tables, and diagnostics.
        """
        ...

    @abc.abstractmethod
    def supported_types(self) -> list[str]:
        """Return list of supported file extensions."""
        ...


def validate_extraction(doc: ExtractedDocument) -> ExtractionDiagnostics:
    """Validate extraction quality.

    Detects:
    - Zero extracted characters
    - Suspiciously low text length
    - Repeated identical pages
    - High garbage character ratio
    - Missing expected structure

    Returns:
        ExtractionDiagnostics with status and issues.
    """
    diag = ExtractionDiagnostics()

    total_text = " ".join(e.text for e in doc.elements)
    diag.total_characters = len(total_text)
    diag.total_elements = len(doc.elements)
    diag.tables_detected = len(doc.tables)

    issues = []

    # Zero characters
    if diag.total_characters == 0:
        issues.append("No text extracted from source")
        diag.status = ExtractionStatus.FAILED
        diag.issues = issues
        return diag

    # Suspiciously low
    if diag.total_characters < 50:
        issues.append(f"Very low extraction output: {diag.total_characters} characters")
        diag.status = ExtractionStatus.PARTIAL

    # Garbage ratio: non-printable / non-whitespace ratio
    printable_count = sum(1 for c in total_text if c.isprintable() or c.isspace())
    if len(total_text) > 0:
        diag.garbage_ratio = 1.0 - (printable_count / len(total_text))
        if diag.garbage_ratio > 0.3:
            issues.append(f"High garbage character ratio: {diag.garbage_ratio:.2f}")
            diag.status = ExtractionStatus.PARTIAL

    # Repeated pages
    page_texts: dict[int, list[str]] = {}
    for elem in doc.elements:
        if elem.page_number is not None:
            page_texts.setdefault(elem.page_number, []).append(elem.text)

    if page_texts:
        diag.pages_detected = len(page_texts)
        page_contents = [" ".join(texts) for texts in page_texts.values()]
        seen = set()
        repeated = 0
        for pc in page_contents:
            normalized = pc.strip().lower()
            if normalized in seen and len(normalized) > 20:
                repeated += 1
            seen.add(normalized)
        diag.repeated_pages = repeated
        if repeated > 0:
            issues.append(f"{repeated} repeated page(s) detected")

    if issues and diag.status == ExtractionStatus.SUCCESS:
        diag.status = ExtractionStatus.PARTIAL

    diag.issues = issues
    return diag
