"""
Q2 Knowledge Base — Source Citations.

Generates structured citations for retrieved knowledge chunks to guarantee
verifiable source lineage, section tracking, and version traceability.
"""

from __future__ import annotations

import re
from typing import Optional

from app.retrieval.models import Citation, KBChunk


class CitationBuilder:
    """Constructs and formats source citations for retrieval responses."""

    @staticmethod
    def build_citation(chunk: KBChunk, confidence: float = 1.0) -> Citation:
        """Create a Citation instance from a KBChunk."""
        snippet = chunk.content.strip().split("\n")[0]
        if len(snippet) > 160:
            snippet = snippet[:157] + "..."

        return Citation(
            source_id=chunk.source_id,
            source_name=chunk.source_name or chunk.title or "Unknown Source",
            record_id=chunk.record_id,
            chunk_id=chunk.chunk_id,
            section=chunk.section,
            source_page=chunk.source_page,
            version=chunk.version,
            content_hash=chunk.content_hash,
            confidence=round(confidence, 4),
            snippet=snippet,
        )

    @staticmethod
    def format_citation_tag(citation: Citation) -> str:
        """Format a compact inline citation tag."""
        parts = [f"Source: {citation.source_name}"]
        if citation.section:
            parts.append(f"Section: {citation.section}")
        if citation.source_page:
            parts.append(f"p. {citation.source_page}")
        parts.append(f"v{citation.version}")
        if citation.content_hash:
            parts.append(f"hash:{citation.content_hash[:8]}")
        return f"[{' | '.join(parts)}]"

    @classmethod
    def format_grounded_answer(
        cls,
        answer_text: str,
        citations: list[Citation],
        include_inline: bool = True,
    ) -> str:
        """Format answer text appended with explicit source citations."""
        if not citations:
            return answer_text

        formatted_lines = [answer_text.strip(), ""]
        if include_inline:
            formatted_lines.append("Sources:")
            for idx, cit in enumerate(citations, start=1):
                tag = cls.format_citation_tag(cit)
                formatted_lines.append(f"  [{idx}] {tag}")

        return "\n".join(formatted_lines)
