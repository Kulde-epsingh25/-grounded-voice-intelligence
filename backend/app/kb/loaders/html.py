"""
Q2 Knowledge Base — HTML Extractor.
"""

from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.kb.loaders.base import BaseExtractor
from app.kb.models import (
    ExtractedDocument,
    ExtractedElement,
    ExtractedTable,
    ExtractionDiagnostics,
    ExtractionStatus,
    ElementType,
    SourceRecord,
)

logger = get_logger(__name__)

# Tags to treat as navigation/boilerplate
_NAV_TAGS = {"nav", "footer", "header", "aside", "script", "style", "noscript", "meta", "link"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class HTMLExtractor(BaseExtractor):
    """Extracts structured content from HTML files using BeautifulSoup."""

    def supported_types(self) -> list[str]:
        return [".html", ".htm"]

    def extract(self, source: SourceRecord, filepath: Path) -> ExtractedDocument:
        doc = ExtractedDocument(source_id=source.source_id)

        try:
            from bs4 import BeautifulSoup

            html_content = filepath.read_text(encoding="utf-8", errors="replace")
            soup = BeautifulSoup(html_content, "lxml")

            order = 0

            # Extract navigation elements separately (for cleaning awareness)
            for nav_tag in _NAV_TAGS:
                for nav in soup.find_all(nav_tag):
                    text = nav.get_text(separator=" ", strip=True)
                    if text:
                        element = ExtractedElement(
                            source_id=source.source_id,
                            element_type=ElementType.NAVIGATION,
                            text=text,
                            order=order,
                        )
                        doc.elements.append(element)
                        order += 1
                    nav.decompose()

            # Extract content elements in reading order with section attribution
            current_section = ""
            for tag in soup.find_all(list(_HEADING_TAGS) + ["table", "p", "li"]):
                if tag.name in _HEADING_TAGS:
                    text = tag.get_text(separator=" ", strip=True)
                    if text:
                        current_section = text
                        element = ExtractedElement(
                            source_id=source.source_id,
                            element_type=ElementType.HEADING,
                            text=text,
                            order=order,
                            section=current_section,
                        )
                        doc.elements.append(element)
                        order += 1
                elif tag.name == "table":
                    rows = tag.find_all("tr")
                    if not rows:
                        continue
                    columns = []
                    data_rows = []
                    for i, row in enumerate(rows):
                        cells = row.find_all(["th", "td"])
                        cell_texts = [c.get_text(separator=" ", strip=True) for c in cells]
                        if i == 0:
                            columns = cell_texts
                        else:
                            data_rows.append(cell_texts)

                    ext_table = ExtractedTable(
                        source_id=source.source_id,
                        columns=columns if columns else [f"col_{j}" for j in range(len(data_rows[0]) if data_rows else [])],
                        rows=data_rows,
                        section=current_section or None,
                    )
                    doc.tables.append(ext_table)

                    table_elem = ExtractedElement(
                        source_id=source.source_id,
                        element_type=ElementType.TABLE,
                        text=ext_table.to_text(),
                        order=order,
                        section=current_section or None,
                        table_id=ext_table.table_id,
                    )
                    doc.elements.append(table_elem)
                    order += 1
                elif tag.name in ["p", "li"]:
                    text = tag.get_text(separator=" ", strip=True)
                    if text and len(text) > 3:
                        etype = ElementType.LIST if tag.name == "li" else ElementType.PARAGRAPH
                        element = ExtractedElement(
                            source_id=source.source_id,
                            element_type=etype,
                            text=text,
                            order=order,
                            section=current_section or None,
                        )
                        doc.elements.append(element)
                        order += 1

            doc.raw_text = "\n\n".join(e.text for e in doc.elements)
            doc.diagnostics = ExtractionDiagnostics(
                total_characters=len(doc.raw_text),
                total_elements=len(doc.elements),
                tables_detected=len(doc.tables),
                status=ExtractionStatus.SUCCESS if doc.elements else ExtractionStatus.FAILED,
            )

        except Exception as e:
            logger.error("HTML extraction failed", extra={"extra_data": {"source_id": source.source_id, "error": str(e)}})
            doc.diagnostics = ExtractionDiagnostics(status=ExtractionStatus.FAILED, issues=[f"HTML error: {str(e)}"])

        return doc
