"""
Q2 Knowledge Base — Full Ingestion Pipeline.

Orchestrates: register → detect → extract → validate → clean → dedup
→ terminology → PII → source validation → normalize → report.
"""

from __future__ import annotations

import time
from pathlib import Path

from app.core.logging import get_logger
from app.kb.models import (
    ExtractionStatus,
    KBRecord,
    ProcessingReport,
    SourceType,
)
from app.kb.registry import SourceRegistry, detect_source_type
from app.kb.loaders.base import BaseExtractor, validate_extraction
from app.kb.loaders.pdf import PDFExtractor
from app.kb.loaders.docx import DOCXExtractor
from app.kb.loaders.xlsx import XLSXExtractor, CSVExtractor
from app.kb.loaders.html import HTMLExtractor
from app.kb.loaders.text import TextExtractor, OCRExtractor
from app.kb.cleaning.cleaner import clean_document
from app.kb.cleaning.dedup import DeduplicationIndex
from app.kb.cleaning.terminology import TerminologyNormalizer
from app.kb.privacy.pii import process_pii
from app.kb.validation.validator import validate_record

logger = get_logger(__name__)

# Map source types to extractors
_EXTRACTORS: dict[SourceType, BaseExtractor] = {
    SourceType.PDF: PDFExtractor(),
    SourceType.DOCX: DOCXExtractor(),
    SourceType.XLSX: XLSXExtractor(),
    SourceType.CSV: CSVExtractor(),
    SourceType.HTML: HTMLExtractor(),
    SourceType.TXT: TextExtractor(),
    SourceType.IMAGE: OCRExtractor(),
}


class IngestionPipeline:
    """Complete Q2 ingestion pipeline.

    Pipeline order:
    1. Register source
    2. Detect type
    3. Extract
    4. Validate extraction
    5. Clean
    6. Deduplicate
    7. Normalize terminology
    8. PII processing
    9. Source validation
    10. Create normalized KB records
    11. Generate processing report
    """

    def __init__(self) -> None:
        self.registry = SourceRegistry()
        self.dedup_index = DeduplicationIndex()
        self.terminology = TerminologyNormalizer()
        self._records: list[KBRecord] = []
        self._reports: list[ProcessingReport] = []

    def process_source(self, filepath: Path) -> ProcessingReport:
        """Process a single source through the full pipeline.

        Args:
            filepath: Path to the source file.

        Returns:
            ProcessingReport with complete processing details.
        """
        start_time = time.time()

        # 1. Register
        source = self.registry.register(filepath)
        report = ProcessingReport(
            source_id=source.source_id,
            source_filename=source.filename,
            status=ExtractionStatus.SUCCESS,
        )

        try:
            # 2. Get extractor
            extractor = _EXTRACTORS.get(source.source_type)
            if not extractor:
                report.status = ExtractionStatus.FAILED
                report.errors.append(f"No extractor for type: {source.source_type.value}")
                self.registry.update_status(
                    source.source_id,
                    ExtractionStatus.FAILED,
                    error_code="no_extractor",
                    error_message=f"Unsupported source type: {source.source_type.value}",
                )
                return report

            # 3. Extract
            extracted = extractor.extract(source, filepath)
            report.elements_extracted = len(extracted.elements)
            report.tables_found = len(extracted.tables)

            # 4. Validate extraction
            diagnostics = validate_extraction(extracted)
            extracted.diagnostics = diagnostics

            if diagnostics.status == ExtractionStatus.FAILED:
                # Try OCR fallback for PDFs
                if source.source_type == SourceType.PDF:
                    source.fallback_attempted = True
                    logger.info("Attempting OCR fallback", extra={"extra_data": {"source_id": source.source_id}})
                    ocr = OCRExtractor()
                    ocr_result = ocr.extract(source, filepath)
                    if ocr_result.diagnostics.status != ExtractionStatus.FAILED:
                        extracted = ocr_result
                        source.fallback_status = "success"
                        report.warnings.append("Used OCR fallback")
                    else:
                        source.fallback_status = "failed"
                        report.status = ExtractionStatus.FAILED
                        report.errors.append("Primary extraction failed, OCR fallback also failed")
                        self.registry.update_status(source.source_id, ExtractionStatus.FAILED)
                        return report
                else:
                    report.status = ExtractionStatus.FAILED
                    report.errors.extend(diagnostics.issues)
                    self.registry.update_status(source.source_id, ExtractionStatus.FAILED)
                    return report

            if diagnostics.status == ExtractionStatus.PARTIAL:
                report.warnings.extend(diagnostics.issues)

            # 5. Clean
            cleaned = clean_document(extracted)
            report.elements_cleaned = len(cleaned.elements)
            report.elements_removed = len(cleaned.removed_elements)

            # 6–10. Create KB records from cleaned elements
            records = self._create_records(source, cleaned, report)

            report.records_created = len(records)
            self._records.extend(records)

        except Exception as e:
            report.status = ExtractionStatus.FAILED
            report.errors.append(f"Pipeline error: {str(e)}")
            logger.error(
                "Pipeline failed",
                extra={"extra_data": {
                    "source_id": source.source_id,
                    "error": str(e),
                }},
            )

        report.processing_time_ms = (time.time() - start_time) * 1000
        self._reports.append(report)

        logger.info(
            "Source processed",
            extra={"extra_data": {
                "source_id": source.source_id,
                "status": report.status.value,
                "records": report.records_created,
                "time_ms": round(report.processing_time_ms, 1),
            }},
        )

        return report

    def _create_records(self, source, cleaned, report) -> list[KBRecord]:
        """Create KB records from cleaned elements with dedup, terminology, PII, and validation."""
        records: list[KBRecord] = []

        # Group elements into logical sections
        current_section = ""
        section_content: list[str] = []
        element_ids: list[str] = []

        for element in cleaned.elements:
            if element.section and element.section != current_section:
                # Flush previous section
                if section_content:
                    record = self._build_record(
                        source, current_section, section_content, element_ids, report
                    )
                    if record:
                        records.append(record)
                current_section = element.section
                section_content = [element.text]
                element_ids = [element.element_id]
            else:
                section_content.append(element.text)
                element_ids.append(element.element_id)

        # Flush remaining
        if section_content:
            record = self._build_record(
                source, current_section, section_content, element_ids, report
            )
            if record:
                records.append(record)

        # If no sections were detected, create one record from all content
        if not records and cleaned.elements:
            all_text = "\n\n".join(e.text for e in cleaned.elements)
            all_ids = [e.element_id for e in cleaned.elements]
            record = self._build_record(
                source, source.filename, [all_text], all_ids, report
            )
            if record:
                records.append(record)

        return records

    def _build_record(
        self,
        source,
        title: str,
        content_parts: list[str],
        element_ids: list[str],
        report: ProcessingReport,
    ) -> KBRecord | None:
        """Build a single KB record with all processing steps."""
        content = "\n\n".join(content_parts)
        if not content.strip():
            return None

        # 7. Terminology normalization
        normalized_content, replacements = self.terminology.normalize(content)

        # 8. PII processing
        pii_result = process_pii(source.source_id, normalized_content)
        report.pii_entities_found += pii_result.total_entities

        # Create record
        record = KBRecord(
            title=title or source.filename,
            content=pii_result.sanitized_content,
            source_id=source.source_id,
            source_name=source.filename,
            source_type=source.source_type.value,
            pii=pii_result.total_entities > 0,
            element_ids=element_ids,
        )
        record.compute_hash()

        # 6. Deduplication
        dups = self.dedup_index.check_and_add(record.record_id, record.content)
        if dups:
            report.duplicates_found += len([d for d in dups if d.duplicate_type.value == "exact"])
            report.near_duplicates_found += len([d for d in dups if d.duplicate_type.value == "near"])
            record.duplicate_of = dups[0].canonical_record_id

        # 9. Source validation
        validation = validate_record(record)
        if not validation.is_valid:
            report.validation_flags.extend([f.value for f in validation.flags])
            record.validation_flags = [f.value for f in validation.flags]
            report.conflicts_found += len(validation.conflicts)

        return record

    def process_directory(self, directory: Path) -> list[ProcessingReport]:
        """Process all supported files in a directory.

        Args:
            directory: Path to directory containing source files.

        Returns:
            List of ProcessingReports.
        """
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        reports = []
        supported_extensions = set()
        for ext in _EXTRACTORS.values():
            supported_extensions.update(ext.supported_types())

        for filepath in sorted(directory.iterdir()):
            if filepath.is_file() and filepath.suffix.lower() in supported_extensions:
                report = self.process_source(filepath)
                reports.append(report)

        return reports

    @property
    def all_records(self) -> list[KBRecord]:
        return list(self._records)

    @property
    def all_reports(self) -> list[ProcessingReport]:
        return list(self._reports)
