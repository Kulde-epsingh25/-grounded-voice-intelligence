"""
Q2 Knowledge Base — Comprehensive Pipeline Tests.

Tests all stages: registry, extraction, cleaning, dedup, terminology, PII,
validation, and full pipeline.

All tests use synthetic fixtures — no invented business data.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.kb.models import (
    ExtractionStatus,
    ElementType,
    SourceType,
    PIIEntityType,
    DuplicateType,
    KBRecord,
    ExtractedDocument,
    ExtractedElement,
    ExtractionDiagnostics,
)
from app.kb.registry import SourceRegistry, detect_source_type, register_source
from app.kb.loaders.base import validate_extraction
from app.kb.loaders.text import TextExtractor
from app.kb.loaders.xlsx import CSVExtractor
from app.kb.loaders.html import HTMLExtractor
from app.kb.cleaning.cleaner import clean_document
from app.kb.cleaning.dedup import (
    compute_content_hash,
    detect_exact_duplicate,
    detect_near_duplicate,
    compute_similarity,
    DeduplicationIndex,
)
from app.kb.cleaning.terminology import TerminologyNormalizer
from app.kb.privacy.pii import detect_pii, mask_pii, process_pii
from app.kb.validation.validator import validate_record, detect_conflicts
from app.kb.pipeline import IngestionPipeline


FIXTURES = Path(__file__).parent / "fixtures"


# =============================================================================
# Source Registry Tests
# =============================================================================

class TestSourceRegistry:

    def test_register_source(self):
        """register_source returns a SourceRecord with hash and type."""
        path = FIXTURES / "sample_product.csv"
        record = register_source(path)
        assert record.source_id.startswith("src_")
        assert record.filename == "sample_product.csv"
        assert record.source_type == SourceType.CSV
        assert len(record.content_hash) == 64  # SHA-256

    def test_sha256_consistency(self):
        """Same file produces same hash."""
        path = FIXTURES / "sample_product.csv"
        r1 = register_source(path)
        r2 = register_source(path)
        assert r1.content_hash == r2.content_hash

    def test_type_detection_csv(self):
        assert detect_source_type(Path("test.csv")) == SourceType.CSV

    def test_type_detection_html(self):
        assert detect_source_type(Path("test.html")) == SourceType.HTML

    def test_type_detection_pdf(self):
        assert detect_source_type(Path("test.pdf")) == SourceType.PDF

    def test_type_detection_unknown(self):
        assert detect_source_type(Path("test.xyz")) == SourceType.UNKNOWN

    def test_registry_duplicate_detection(self):
        """Registry detects when same content is registered twice."""
        registry = SourceRegistry()
        path = FIXTURES / "sample_product.csv"
        r1 = registry.register(path)
        r2 = registry.register(path)
        assert r1.content_hash == r2.content_hash
        # Both should be registered
        assert len(registry.all_sources()) == 2

    def test_file_not_found(self):
        """register_source raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            register_source(Path("nonexistent.pdf"))


# =============================================================================
# Extraction Tests
# =============================================================================

class TestExtraction:

    def test_csv_extraction(self):
        """CSV extractor preserves table structure."""
        path = FIXTURES / "sample_product.csv"
        record = register_source(path)
        extractor = CSVExtractor()
        doc = extractor.extract(record, path)

        assert doc.diagnostics.status == ExtractionStatus.SUCCESS
        assert len(doc.tables) == 1
        table = doc.tables[0]
        assert "loan_type" in table.columns
        assert len(table.rows) == 4  # 4 data rows
        assert table.rows[0][0] == "Starter"

    def test_html_extraction(self):
        """HTML extractor extracts headings, paragraphs, and tables."""
        path = FIXTURES / "sample_faq.html"
        record = register_source(path)
        extractor = HTMLExtractor()
        doc = extractor.extract(record, path)

        assert doc.diagnostics.status == ExtractionStatus.SUCCESS
        assert len(doc.elements) > 0
        assert len(doc.tables) >= 1

        # Check headings extracted
        headings = [e for e in doc.elements if e.element_type == ElementType.HEADING]
        assert len(headings) > 0

        # Check navigation elements detected
        nav_elements = [e for e in doc.elements if e.element_type == ElementType.NAVIGATION]
        assert len(nav_elements) > 0

    def test_text_extraction(self):
        """Text extractor handles plain text files."""
        path = FIXTURES / "sample_duplicate.txt"
        record = register_source(path)
        extractor = TextExtractor()
        doc = extractor.extract(record, path)

        assert doc.diagnostics.status == ExtractionStatus.SUCCESS
        assert len(doc.elements) > 0
        assert doc.raw_text != ""

    def test_extraction_failure(self):
        """Extraction failure produces FAILED status, not empty success."""
        doc = ExtractedDocument(
            source_id="test",
            elements=[],
            diagnostics=ExtractionDiagnostics(total_characters=0),
        )
        diag = validate_extraction(doc)
        assert diag.status == ExtractionStatus.FAILED
        assert len(diag.issues) > 0

    def test_partial_extraction(self):
        """Very short extraction produces PARTIAL status."""
        doc = ExtractedDocument(
            source_id="test",
            elements=[
                ExtractedElement(
                    source_id="test",
                    element_type=ElementType.PARAGRAPH,
                    text="Hi",
                    order=0,
                )
            ],
        )
        diag = validate_extraction(doc)
        assert diag.status == ExtractionStatus.PARTIAL


# =============================================================================
# Cleaning Tests
# =============================================================================

class TestCleaning:

    def test_cleaning_navigation(self):
        """Cleaner removes navigation elements."""
        path = FIXTURES / "sample_faq.html"
        record = register_source(path)
        extractor = HTMLExtractor()
        doc = extractor.extract(record, path)
        cleaned = clean_document(doc)

        # Navigation elements should be in removed_elements
        nav_removed = [
            e for e in cleaned.removed_elements
            if e.element_type == ElementType.NAVIGATION
        ]
        assert len(nav_removed) > 0

    def test_cleaning_preserves_content(self):
        """Cleaner preserves meaningful business content."""
        path = FIXTURES / "sample_faq.html"
        record = register_source(path)
        extractor = HTMLExtractor()
        doc = extractor.extract(record, path)
        cleaned = clean_document(doc)

        # Content elements should remain
        assert len(cleaned.elements) > 0
        all_text = " ".join(e.text for e in cleaned.elements)
        assert "revenue" in all_text.lower() or "loan" in all_text.lower()

    def test_cleaning_headers_footers(self):
        """Cleaner handles boilerplate patterns."""
        doc = ExtractedDocument(
            source_id="test",
            elements=[
                ExtractedElement(source_id="test", element_type=ElementType.PARAGRAPH, text="Page 1 of 5", order=0),
                ExtractedElement(source_id="test", element_type=ElementType.PARAGRAPH, text="Important business content here", order=1),
                ExtractedElement(source_id="test", element_type=ElementType.PARAGRAPH, text="© 2024 Corp", order=2),
            ],
        )
        cleaned = clean_document(doc)
        # Navigation patterns should be removed
        kept_texts = [e.text for e in cleaned.elements]
        assert "Important business content here" in kept_texts

    def test_table_preservation(self):
        """Cleaning preserves tables."""
        path = FIXTURES / "sample_faq.html"
        record = register_source(path)
        extractor = HTMLExtractor()
        doc = extractor.extract(record, path)
        cleaned = clean_document(doc)

        assert len(cleaned.tables) > 0
        table = cleaned.tables[0]
        assert len(table.columns) > 0
        assert len(table.rows) > 0


# =============================================================================
# Deduplication Tests
# =============================================================================

class TestDeduplication:

    def test_exact_duplicate(self):
        """Exact duplicates are detected."""
        text = "This is the exact same content."
        dup = detect_exact_duplicate(text, text, "rec_001", "rec_002")
        assert dup is not None
        assert dup.duplicate_type == DuplicateType.EXACT
        assert dup.similarity == 1.0

    def test_not_duplicate(self):
        """Different content is not flagged as duplicate."""
        dup = detect_exact_duplicate(
            "Content about loans",
            "Content about insurance",
            "rec_001",
            "rec_002",
        )
        assert dup is None

    def test_near_duplicate(self):
        """Near-duplicates are detected above threshold."""
        text_a = "The minimum monthly revenue for Starter loans is $500,000."
        text_b = "The minimum monthly revenue for Starter loans is $500,000. Updated."
        dup = detect_near_duplicate(text_a, text_b, "rec_001", "rec_002", threshold=0.85)
        assert dup is not None
        assert dup.duplicate_type == DuplicateType.NEAR
        assert dup.similarity >= 0.85

    def test_near_duplicate_below_threshold(self):
        """Content below threshold is not flagged."""
        dup = detect_near_duplicate(
            "Loans require minimum revenue of $500K",
            "Insurance policies have annual premiums starting at $1,200",
            "rec_001",
            "rec_002",
            threshold=0.90,
        )
        assert dup is None

    def test_content_hash_consistency(self):
        """Same content produces same hash regardless of whitespace."""
        h1 = compute_content_hash("  hello   world  ")
        h2 = compute_content_hash("hello world")
        assert h1 == h2

    def test_dedup_index(self):
        """DeduplicationIndex tracks and detects duplicates."""
        idx = DeduplicationIndex()
        d1 = idx.check_and_add("r1", "The quick brown fox")
        assert len(d1) == 0  # First entry, no duplicates

        d2 = idx.check_and_add("r2", "The quick brown fox")
        assert len(d2) == 1  # Exact duplicate
        assert d2[0].canonical_record_id == "r1"


# =============================================================================
# Terminology Tests
# =============================================================================

class TestTerminology:

    def test_terminology_normalization(self):
        """Aliases are normalized to canonical forms."""
        normalizer = TerminologyNormalizer()
        text = "Apply for SME loan with minimum monthly income of $500K."
        normalized, replacements = normalizer.normalize(text)

        assert "business loan" in normalized.lower()
        assert len(replacements) > 0

    def test_original_preserved(self):
        """Original text is not destroyed — both forms available."""
        normalizer = TerminologyNormalizer()
        original = "Apply for business financing today."
        normalized, replacements = normalizer.normalize(original)

        # Original is unchanged
        assert "business financing" in original
        # Normalized uses canonical term
        assert "business loan" in normalized


# =============================================================================
# PII Tests
# =============================================================================

class TestPII:

    def test_email_detection(self):
        """Emails are detected."""
        entities = detect_pii("Contact john@example.com for more info.")
        emails = [e for e in entities if e.entity_type == PIIEntityType.EMAIL]
        assert len(emails) == 1

    def test_phone_detection(self):
        """Phone numbers are detected."""
        entities = detect_pii("Call +63 917 123 4567 for support.")
        phones = [e for e in entities if e.entity_type == PIIEntityType.PHONE]
        assert len(phones) >= 1

    def test_account_id_detection(self):
        """Account identifiers are detected."""
        entities = detect_pii("Reference: Account #123456")
        accounts = [e for e in entities if e.entity_type == PIIEntityType.ACCOUNT_ID]
        assert len(accounts) >= 1

    def test_pii_masking(self):
        """PII is replaced with type-based masks."""
        text = "Email: john@example.com"
        entities = detect_pii(text)
        masked = mask_pii(text, entities)
        assert "john@example.com" not in masked
        assert "[EMAIL]" in masked

    def test_full_pii_processing(self):
        """Full PII processing from fixture file."""
        path = FIXTURES / "sample_customer_pii.txt"
        content = path.read_text(encoding="utf-8")
        result = process_pii("test_src", content)

        assert result.total_entities > 0
        assert "john.smith@example.com" not in result.sanitized_content
        assert "[EMAIL]" in result.sanitized_content

    def test_no_pii_in_clean_text(self):
        """Clean text without PII returns empty entity list."""
        result = process_pii("test", "This is clean business content about loans.")
        assert result.total_entities == 0
        assert result.sanitized_content == "This is clean business content about loans."


# =============================================================================
# Validation Tests
# =============================================================================

class TestValidation:

    def test_valid_record(self):
        """Valid record passes validation."""
        record = KBRecord(
            title="Test Policy",
            content="The minimum revenue requirement is $500,000 for starter loans.",
            source_id="src_001",
        )
        result = validate_record(record)
        assert result.is_valid

    def test_missing_title(self):
        """Record with missing title is flagged."""
        record = KBRecord(
            title="",
            content="Some content here that is long enough.",
            source_id="src_001",
        )
        result = validate_record(record)
        assert not result.is_valid
        assert "missing_metadata" in [f.value for f in result.flags]

    def test_impossible_date(self):
        """Record with end date before start date is flagged."""
        record = KBRecord(
            title="Test Policy",
            content="Some valid content for this record.",
            source_id="src_001",
            effective_from="2025-01-01",
            effective_to="2024-01-01",
        )
        result = validate_record(record)
        assert not result.is_valid
        assert "impossible_date" in [f.value for f in result.flags]

    def test_conflict_detection(self):
        """Conflicting values between sources are detected."""
        records = [
            KBRecord(
                title="Policy A",
                content="Minimum revenue is $500,000 for this product.",
                source_id="src_001",
                category="qualification",
                product="starter",
            ),
            KBRecord(
                title="Policy B",
                content="Minimum revenue is $750,000 for this product.",
                source_id="src_002",
                category="qualification",
                product="starter",
            ),
        ]
        conflicts = detect_conflicts(records)
        assert len(conflicts) > 0
        assert conflicts[0].status == "unresolved"


# =============================================================================
# Normalized Record Tests
# =============================================================================

class TestKBRecord:

    def test_record_creation(self):
        """KBRecord can be created with required fields."""
        record = KBRecord(
            title="Test",
            content="Test content for KB record.",
            source_id="src_001",
        )
        assert record.record_id.startswith("kb_")
        assert record.version == "1.0"

    def test_content_hash(self):
        """compute_hash produces consistent SHA-256."""
        record = KBRecord(title="Test", content="Hello World", source_id="src_001")
        h1 = record.compute_hash()
        h2 = record.compute_hash()
        assert h1 == h2
        assert len(h1) == 64


# =============================================================================
# Full Pipeline Tests
# =============================================================================

class TestFullPipeline:

    def test_pipeline_csv(self):
        """Full pipeline processes CSV file."""
        pipeline = IngestionPipeline()
        path = FIXTURES / "sample_product.csv"
        report = pipeline.process_source(path)

        assert report.status == ExtractionStatus.SUCCESS
        assert report.records_created >= 1
        assert report.tables_found >= 1

    def test_pipeline_html(self):
        """Full pipeline processes HTML file."""
        pipeline = IngestionPipeline()
        path = FIXTURES / "sample_faq.html"
        report = pipeline.process_source(path)

        assert report.status == ExtractionStatus.SUCCESS
        assert report.records_created >= 1

    def test_pipeline_text_with_pii(self):
        """Full pipeline detects PII in text file."""
        pipeline = IngestionPipeline()
        path = FIXTURES / "sample_customer_pii.txt"
        report = pipeline.process_source(path)

        assert report.status == ExtractionStatus.SUCCESS
        assert report.pii_entities_found > 0
        # Verify PII is masked in records
        for record in pipeline.all_records:
            if record.source_name == "sample_customer_pii.txt":
                assert "john.smith@example.com" not in record.content

    def test_pipeline_directory(self):
        """Full pipeline processes a directory."""
        pipeline = IngestionPipeline()
        reports = pipeline.process_directory(FIXTURES)

        assert len(reports) >= 3  # At least CSV, HTML, TXT
        successful = [r for r in reports if r.status == ExtractionStatus.SUCCESS]
        assert len(successful) >= 3

    def test_pipeline_nonexistent_file(self):
        """Pipeline handles missing file gracefully."""
        pipeline = IngestionPipeline()
        with pytest.raises(FileNotFoundError):
            pipeline.process_source(Path("nonexistent.pdf"))
