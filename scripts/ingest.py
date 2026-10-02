"""
Q2 Knowledge Base — CLI Ingestion Script.

Usage:
    python scripts/ingest.py data/raw/example.pdf
    python scripts/ingest.py data/raw/

Output includes: source, status, records_created, duplicates, PII, conflicts, errors.
No raw PII is printed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.logging import setup_logging
from app.kb.pipeline import IngestionPipeline


def main() -> None:
    setup_logging("INFO")

    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest.py <file_or_directory>")
        print("  python scripts/ingest.py data/raw/example.pdf")
        print("  python scripts/ingest.py data/raw/")
        sys.exit(1)

    target = Path(sys.argv[1])
    pipeline = IngestionPipeline()

    if target.is_dir():
        reports = pipeline.process_directory(target)
    elif target.is_file():
        reports = [pipeline.process_source(target)]
    else:
        print(f"Error: {target} not found")
        sys.exit(1)

    # Print summary (no raw PII)
    print("\n" + "=" * 60)
    print("INGESTION REPORT")
    print("=" * 60)

    for report in reports:
        print(f"\nSource: {report.source_filename}")
        print(f"  Status:           {report.status.value}")
        print(f"  Records created:  {report.records_created}")
        print(f"  Elements:         {report.elements_extracted} extracted -> {report.elements_cleaned} kept -> {report.elements_removed} removed")
        print(f"  Tables:           {report.tables_found}")
        print(f"  Duplicates:       {report.duplicates_found} exact, {report.near_duplicates_found} near")
        print(f"  PII entities:     {report.pii_entities_found}")
        print(f"  Conflicts:        {report.conflicts_found}")
        print(f"  Processing time:  {report.processing_time_ms:.1f} ms")

        if report.errors:
            print(f"  Errors:")
            for err in report.errors:
                print(f"    - {err}")

        if report.warnings:
            print(f"  Warnings:")
            for warn in report.warnings:
                print(f"    - {warn}")

        if report.validation_flags:
            print(f"  Validation flags:")
            for flag in report.validation_flags:
                print(f"    - {flag}")

    # Total summary
    print(f"\n{'-' * 60}")
    print(f"Total sources:   {len(reports)}")
    print(f"Total records:   {sum(r.records_created for r in reports)}")
    print(f"Total errors:    {sum(len(r.errors) for r in reports)}")

    # Save KB records
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    records_data = [r.model_dump(mode="json") for r in pipeline.all_records]
    output_file = output_dir / "kb_records.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(records_data, f, indent=2, default=str)
    print(f"\nRecords saved to: {output_file}")


if __name__ == "__main__":
    main()
