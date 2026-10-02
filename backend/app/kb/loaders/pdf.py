"""
Q2 Knowledge Base — PDF Extractor.
"""

from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.kb.loaders.base import BaseExtractor
from app.kb.models import (
    ExtractedDocument,
    ExtractedElement,
    ExtractionDiagnostics,
    ExtractionStatus,
    ElementType,
    SourceRecord,
)

logger = get_logger(__name__)


class PDFExtractor(BaseExtractor):
    """Extracts text from PDF files using PyPDF2."""

    def supported_types(self) -> list[str]:
        return [".pdf"]

    def extract(self, source: SourceRecord, filepath: Path) -> ExtractedDocument:
        doc = ExtractedDocument(source_id=source.source_id)

        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(filepath))
            order = 0

            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    element = ExtractedElement(
                        source_id=source.source_id,
                        element_type=ElementType.PARAGRAPH,
                        text=text,
                        order=order,
                        page_number=page_num,
                    )
                    doc.elements.append(element)
                    order += 1

            doc.raw_text = "\n\n".join(e.text for e in doc.elements)

            # Build diagnostics
            diag = ExtractionDiagnostics(
                total_characters=len(doc.raw_text),
                total_elements=len(doc.elements),
                pages_detected=len(reader.pages),
                status=ExtractionStatus.SUCCESS if doc.elements else ExtractionStatus.FAILED,
            )
            if not doc.elements:
                diag.issues.append("No text extracted from PDF — may be scanned/image PDF")
            doc.diagnostics = diag

        except Exception as e:
            logger.error(
                "PDF extraction failed",
                extra={"extra_data": {
                    "source_id": source.source_id,
                    "error": str(e),
                }},
            )
            doc.diagnostics = ExtractionDiagnostics(
                status=ExtractionStatus.FAILED,
                issues=[f"PDF extraction error: {str(e)}"],
            )

        return doc
