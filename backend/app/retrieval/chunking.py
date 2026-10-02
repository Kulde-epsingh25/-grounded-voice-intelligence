"""
Q2 Knowledge Base — Section-Aware Chunking Strategy.

Splits documents into retrieval-friendly chunks while:
1. Respecting section and heading boundaries
2. Preserving table structures intact
3. Applying configurable chunk size and overlap
4. Carrying forward complete source lineage and metadata
"""

from __future__ import annotations

import re
from typing import Optional

from app.kb.models import KBRecord
from app.retrieval.models import KBChunk


class SectionChunker:
    """Section-aware document chunker."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = max(128, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, self.chunk_size // 2))

    def chunk_record(self, record: KBRecord) -> list[KBChunk]:
        """Split a KBRecord into one or more KBChunks."""
        content = record.content.strip()
        if not content:
            return []

        # If already small enough, return as single chunk
        if len(content) <= self.chunk_size:
            chunk = self._build_chunk(
                record=record,
                content=content,
                section=record.section or record.title,
                index=0,
                total=1,
            )
            return [chunk]

        # Check if content is primarily a table
        if self._is_table(content):
            # Try to keep table together or split by table rows
            raw_chunks = self._chunk_table(content)
        else:
            # Section and paragraph aware text chunking
            raw_chunks = self._chunk_text(content)

        if not raw_chunks:
            raw_chunks = [content]

        total = len(raw_chunks)
        chunks = []
        for idx, text in enumerate(raw_chunks):
            # Detect section heading if present in chunk
            section_match = re.search(r"^(?:#{1,4}\s+|Section:\s*)([^\n]+)", text, re.MULTILINE)
            sec = section_match.group(1).strip() if section_match else (record.section or record.title)
            chunk = self._build_chunk(
                record=record,
                content=text.strip(),
                section=sec,
                index=idx,
                total=total,
            )
            chunks.append(chunk)

        return chunks

    def chunk_records(self, records: list[KBRecord]) -> list[KBChunk]:
        """Chunk a list of KBRecords."""
        all_chunks = []
        for r in records:
            all_chunks.extend(self.chunk_record(r))
        return all_chunks

    def _chunk_text(self, text: str) -> list[str]:
        """Split text respecting headings, paragraphs, and sentence boundaries."""
        # 1. Split on major heading or section markers
        heading_split = re.split(r"(?:\n|^)(?=#{1,3}\s+[^\n]+)", text)
        sections = [s.strip() for s in heading_split if s.strip()]

        chunks: list[str] = []

        for sec in sections:
            if len(sec) <= self.chunk_size:
                chunks.append(sec)
                continue

            # 2. Split section into paragraphs
            paras = [p.strip() for p in re.split(r"\n\s*\n", sec) if p.strip()]
            current_chunk: list[str] = []
            current_len = 0

            for para in paras:
                para_len = len(para)
                if current_len + para_len + 2 <= self.chunk_size:
                    current_chunk.append(para)
                    current_len += para_len + 2
                else:
                    if current_chunk:
                        chunk_str = "\n\n".join(current_chunk)
                        chunks.append(chunk_str)
                        # Overlap: keep last paragraph if it fits
                        last_p = current_chunk[-1]
                        if len(last_p) < self.chunk_overlap:
                            current_chunk = [last_p, para]
                            current_len = len(last_p) + 2 + para_len
                        else:
                            current_chunk = [para]
                            current_len = para_len
                    else:
                        # Paragraph itself is longer than chunk_size -> sentence split
                        sub_chunks = self._chunk_long_paragraph(para)
                        chunks.extend(sub_chunks)
                        current_chunk = []
                        current_len = 0

            if current_chunk:
                chunks.append("\n\n".join(current_chunk))

        return chunks

    def _chunk_long_paragraph(self, para: str) -> list[str]:
        """Split long paragraph on sentences."""
        sentences = re.split(r"(?<=[.!?])\s+", para)
        chunks: list[str] = []
        curr: list[str] = []
        curr_len = 0

        for sent in sentences:
            s_len = len(sent)
            if curr_len + s_len + 1 <= self.chunk_size:
                curr.append(sent)
                curr_len += s_len + 1
            else:
                if curr:
                    chunks.append(" ".join(curr))
                curr = [sent]
                curr_len = s_len

        if curr:
            chunks.append(" ".join(curr))
        return chunks

    def _is_table(self, text: str) -> bool:
        """Heuristic to check if content is structured table."""
        pipe_lines = sum(1 for line in text.splitlines() if "|" in line)
        return pipe_lines >= 3

    def _chunk_table(self, content: str) -> list[str]:
        """Chunk a table keeping headers with each chunk."""
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if len(lines) <= 2:
            return [content]

        header_lines: list[str] = []
        data_rows: list[str] = []

        # Find header rows (containing | and optional separator ---)
        for i, line in enumerate(lines):
            if i < 2 and ("|" in line or "---" in line):
                header_lines.append(line)
            else:
                data_rows.append(line)

        header_str = "\n".join(header_lines) + "\n" if header_lines else ""
        chunks: list[str] = []
        current_rows: list[str] = []
        current_len = len(header_str)

        for row in data_rows:
            row_len = len(row) + 1
            if current_len + row_len <= self.chunk_size:
                current_rows.append(row)
                current_len += row_len
            else:
                if current_rows:
                    chunks.append(header_str + "\n".join(current_rows))
                current_rows = [row]
                current_len = len(header_str) + row_len

        if current_rows:
            chunks.append(header_str + "\n".join(current_rows))

        return chunks if chunks else [content]

    def _build_chunk(
        self,
        record: KBRecord,
        content: str,
        section: Optional[str],
        index: int,
        total: int,
    ) -> KBChunk:
        char_count = len(content)
        token_count = max(1, int(len(content.split()) * 1.3))

        return KBChunk(
            record_id=record.record_id,
            source_id=record.source_id,
            source_name=record.source_name,
            source_page=record.source_page,
            title=record.title,
            section=section,
            content=content,
            category=record.category,
            subcategory=record.subcategory,
            product=record.product,
            version=record.version,
            effective_from=record.effective_from,
            language=record.language,
            pii=record.pii,
            content_hash=record.content_hash,
            chunk_index=index,
            total_chunks=total,
            char_count=char_count,
            token_count=token_count,
            metadata={
                "parent_doc": record.parent_document_id,
                "duplicate_of": record.duplicate_of,
                "has_tables": len(record.table_ids) > 0,
                "market": record.subcategory if record.subcategory in ("PH", "ID") else record.category,
                "sector": record.product,
            },
        )
