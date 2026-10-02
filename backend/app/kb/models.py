"""
Q2 Knowledge Base — Data Models.

Pydantic models for the entire KB ingestion pipeline.
No business data is invented here — these are structural contracts.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class SourceType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    CSV = "csv"
    HTML = "html"
    TXT = "txt"
    IMAGE = "image"
    UNKNOWN = "unknown"


class ExtractionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ElementType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    TABLE_ROW = "table_row"
    FOOTER = "footer"
    HEADER = "header"
    NAVIGATION = "navigation"
    IMAGE = "image"
    UNKNOWN = "unknown"


class PIIAction(str, Enum):
    MASK = "mask"
    REDACT = "redact"
    KEEP_SAFE = "keep_safe"
    FLAG = "flag"


class PIIEntityType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    PERSON_NAME = "person_name"
    ADDRESS = "address"
    ACCOUNT_ID = "account_id"
    POLICY_ID = "policy_id"
    CUSTOMER_ID = "customer_id"


class ConflictSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DuplicateType(str, Enum):
    EXACT = "exact"
    NEAR = "near"


class ValidationFlag(str, Enum):
    CONFLICTING_VALUES = "conflicting_values"
    IMPOSSIBLE_DATE = "impossible_date"
    INVALID_NUMERIC = "invalid_numeric"
    MISSING_METADATA = "missing_metadata"
    INCONSISTENT_TERMINOLOGY = "inconsistent_terminology"
    MISSING_TABLE_FIELDS = "missing_table_fields"
    INVALID_RANGE = "invalid_range"
    DUPLICATE_VERSION = "duplicate_version"


# =============================================================================
# Source Registry
# =============================================================================

class SourceRecord(BaseModel):
    """Tracks every source document entering the pipeline."""
    source_id: str = Field(default_factory=lambda: f"src_{uuid4().hex[:8]}")
    filename: str
    source_type: SourceType
    uri: str = ""
    content_hash: str = ""
    version: str = "1.0"
    ingestion_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ExtractionStatus = ExtractionStatus.SUCCESS
    extraction_method: str = ""
    error_code: str = ""
    error_message: str = ""
    fallback_attempted: bool = False
    fallback_status: str = ""


# =============================================================================
# Extraction
# =============================================================================

class ExtractedElement(BaseModel):
    """A single extracted element from a source document."""
    element_id: str = Field(default_factory=lambda: f"elem_{uuid4().hex[:8]}")
    source_id: str
    element_type: ElementType
    text: str
    order: int = 0
    page_number: Optional[int] = None
    section: Optional[str] = None
    table_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedTable(BaseModel):
    """A structured table extracted from a source."""
    table_id: str = Field(default_factory=lambda: f"tbl_{uuid4().hex[:8]}")
    source_id: str
    columns: list[str]
    rows: list[list[str]]
    page_number: Optional[int] = None
    section: Optional[str] = None
    caption: Optional[str] = None

    def to_text(self) -> str:
        """Create retrieval-friendly text representation preserving structure."""
        lines = []
        if self.caption:
            lines.append(f"Table: {self.caption}")
        header = " | ".join(self.columns)
        lines.append(header)
        lines.append("-" * len(header))
        for row in self.rows:
            lines.append(" | ".join(row))
        return "\n".join(lines)


class ExtractionDiagnostics(BaseModel):
    """Quality diagnostics for extraction output."""
    total_characters: int = 0
    total_elements: int = 0
    pages_detected: int = 0
    tables_detected: int = 0
    repeated_pages: int = 0
    garbage_ratio: float = 0.0
    status: ExtractionStatus = ExtractionStatus.SUCCESS
    issues: list[str] = Field(default_factory=list)


class ExtractedDocument(BaseModel):
    """Complete extraction result from a single source."""
    source_id: str
    elements: list[ExtractedElement] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)
    diagnostics: ExtractionDiagnostics = Field(default_factory=ExtractionDiagnostics)
    raw_text: str = ""


# =============================================================================
# Cleaning
# =============================================================================

class CleanedDocument(BaseModel):
    """Document after cleaning pipeline."""
    source_id: str
    elements: list[ExtractedElement] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)
    removed_elements: list[ExtractedElement] = Field(default_factory=list)
    cleaning_log: list[str] = Field(default_factory=list)


# =============================================================================
# PII
# =============================================================================

class PIIEntity(BaseModel):
    """A detected PII entity."""
    entity_type: PIIEntityType
    start: int
    end: int
    text: str = ""  # Only for internal processing; never log this
    confidence: float = 1.0
    action: PIIAction = PIIAction.MASK


class PIIResult(BaseModel):
    """Result of PII processing on a document."""
    source_id: str
    original_content: str = ""  # Stored internally, never logged
    sanitized_content: str = ""
    entities_found: list[PIIEntity] = Field(default_factory=list)
    total_entities: int = 0


# =============================================================================
# Deduplication
# =============================================================================

class DuplicateRecord(BaseModel):
    """Records a duplicate relationship between two content pieces."""
    record_id: str = Field(default_factory=lambda: f"dup_{uuid4().hex[:8]}")
    canonical_record_id: str
    duplicate_record_id: str
    duplicate_type: DuplicateType
    similarity: float = 1.0
    threshold: float = 0.95


# =============================================================================
# Terminology
# =============================================================================

class TermEntry(BaseModel):
    """A terminology dictionary entry."""
    canonical_term: str
    aliases: list[str] = Field(default_factory=list)
    normalized_form: str = ""
    category: str = ""


# =============================================================================
# Source Validation
# =============================================================================

class ConflictRecord(BaseModel):
    """Records a detected conflict between sources."""
    conflict_id: str = Field(default_factory=lambda: f"conf_{uuid4().hex[:8]}")
    source_ids: list[str]
    field: str
    values: list[str]
    severity: ConflictSeverity = ConflictSeverity.MEDIUM
    status: str = "unresolved"
    description: str = ""


class ValidationResult(BaseModel):
    """Result of source validation."""
    source_id: str
    flags: list[ValidationFlag] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    is_valid: bool = True


# =============================================================================
# Normalized KB Record
# =============================================================================

class KBRecord(BaseModel):
    """The final normalized knowledge base record."""
    record_id: str = Field(default_factory=lambda: f"kb_{uuid4().hex[:8]}")
    title: str
    content: str
    category: str = ""
    subcategory: str = ""
    product: str = ""
    source_id: str = ""
    source_name: str = ""
    source_type: str = ""
    source_page: Optional[int] = None
    version: str = "1.0"
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    language: str = "en"
    pii: bool = False
    section: Optional[str] = None
    content_hash: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Lineage
    parent_document_id: Optional[str] = None
    element_ids: list[str] = Field(default_factory=list)
    table_ids: list[str] = Field(default_factory=list)
    duplicate_of: Optional[str] = None
    validation_flags: list[str] = Field(default_factory=list)

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of normalized content."""
        normalized = self.content.strip().lower()
        self.content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return self.content_hash


# =============================================================================
# Pipeline
# =============================================================================

class ProcessingReport(BaseModel):
    """Report generated by the full ingestion pipeline."""
    source_id: str
    source_filename: str
    status: ExtractionStatus
    records_created: int = 0
    elements_extracted: int = 0
    elements_cleaned: int = 0
    elements_removed: int = 0
    tables_found: int = 0
    duplicates_found: int = 0
    near_duplicates_found: int = 0
    pii_entities_found: int = 0
    conflicts_found: int = 0
    validation_flags: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    processing_time_ms: float = 0.0


def compute_sha256(content: bytes) -> str:
    """Compute SHA-256 hash of raw content."""
    return hashlib.sha256(content).hexdigest()
