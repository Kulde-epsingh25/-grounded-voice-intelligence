"""
Q2 Knowledge Base — Plain Text Extractor.
"""

from __future__ import annotations

from pathlib import Path

from app.kb.loaders.base import BaseExtractor
from app.kb.models import (
    ExtractedDocument,
    ExtractedElement,
    ExtractionDiagnostics,
    ExtractionStatus,
    ElementType,
    SourceRecord,
)


class TextExtractor(BaseExtractor):
    """Extracts content from plain text files."""

    def supported_types(self) -> list[str]:
        return [".txt", ".md"]

    def extract(self, source: SourceRecord, filepath: Path) -> ExtractedDocument:
        doc = ExtractedDocument(source_id=source.source_id)

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")

            # Split into paragraphs on double newlines
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

            for i, para in enumerate(paragraphs):
                etype = ElementType.HEADING if para.startswith("#") else ElementType.PARAGRAPH
                element = ExtractedElement(
                    source_id=source.source_id,
                    element_type=etype,
                    text=para,
                    order=i,
                )
                doc.elements.append(element)

            doc.raw_text = text
            doc.diagnostics = ExtractionDiagnostics(
                total_characters=len(text),
                total_elements=len(doc.elements),
                status=ExtractionStatus.SUCCESS if doc.elements else ExtractionStatus.FAILED,
            )

        except Exception as e:
            doc.diagnostics = ExtractionDiagnostics(
                status=ExtractionStatus.FAILED,
                issues=[f"Text extraction error: {str(e)}"],
            )

        return doc


class OCRExtractor(BaseExtractor):
    """OCR fallback extractor interface.

    This is an abstraction. The actual OCR implementation is lightweight
    for this chunk. If OCR dependencies are unavailable, this returns
    a documented failure rather than silently producing empty output.
    """

    def supported_types(self) -> list[str]:
        return [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"]

    def extract(self, source: SourceRecord, filepath: Path) -> ExtractedDocument:
        doc = ExtractedDocument(source_id=source.source_id)

        # Attempt OCR if pytesseract is available
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(filepath)
            text = pytesseract.image_to_string(image)

            if text.strip():
                element = ExtractedElement(
                    source_id=source.source_id,
                    element_type=ElementType.PARAGRAPH,
                    text=text.strip(),
                    order=0,
                )
                doc.elements.append(element)
                doc.raw_text = text.strip()
                doc.diagnostics = ExtractionDiagnostics(
                    total_characters=len(text),
                    total_elements=1,
                    status=ExtractionStatus.SUCCESS,
                )
            else:
                doc.diagnostics = ExtractionDiagnostics(
                    status=ExtractionStatus.FAILED,
                    issues=["OCR produced no text output"],
                )

        except ImportError:
            # OCR dependency not available — documented failure, not silent skip
            doc.diagnostics = ExtractionDiagnostics(
                status=ExtractionStatus.FAILED,
                issues=[
                    "OCR dependencies (pytesseract, Pillow) not available. "
                    "Install them for image/scanned document support. "
                    "This is a documented limitation, not a silent failure."
                ],
            )

        except Exception as e:
            doc.diagnostics = ExtractionDiagnostics(
                status=ExtractionStatus.FAILED,
                issues=[f"OCR extraction error: {str(e)}"],
            )

        return doc
