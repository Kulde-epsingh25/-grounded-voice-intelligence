"""Domain terminology dictionaries with canonical mappings and normalization for PH and ID markets."""
from __future__ import annotations

import re
from typing import Optional
from app.localization.models import (
    Language,
    Market,
    Sector,
    TerminologyItem,
)

PH_TERMINOLOGY_LIST: list[TerminologyItem] = [
    TerminologyItem(
        canonical_concept="premium",
        term="premium",
        market=Market.PH,
        language=Language.TAGLISH,
        domain=Sector.BANCASSURANCE,
        allowed_variants=["hulog", "bayad", "monthly premium", "annual premium", "premiums"],
        notes="Commonly referred to directly as 'premium' in Taglish or 'hulog'/'bayad' in conversational Tagalog.",
    ),
    TerminologyItem(
        canonical_concept="policy",
        term="policy",
        market=Market.PH,
        language=Language.TAGLISH,
        domain=Sector.BANCASSURANCE,
        allowed_variants=["polisiya", "plan", "insurance plan", "policy plan"],
        notes="In Taglish, 'policy' is preferred over formal Tagalog 'polisiya' in bank partner settings.",
    ),
    TerminologyItem(
        canonical_concept="beneficiary",
        term="beneficiary",
        market=Market.PH,
        language=Language.TAGLISH,
        domain=Sector.BANCASSURANCE,
        allowed_variants=["makakatanggap", "benepisyaryo", "dependent", "designated heir"],
        notes="Usually kept in English 'beneficiary' during bancassurance consultations with Tagalog explanation.",
    ),
    TerminologyItem(
        canonical_concept="rider",
        term="rider",
        market=Market.PH,
        language=Language.TAGLISH,
        domain=Sector.BANCASSURANCE,
        allowed_variants=["add-on", "additional benefit", "dagdag coverage", "supplementary benefit"],
        notes="Insurance add-on coverage such as critical illness or accidental disability.",
    ),
    TerminologyItem(
        canonical_concept="lapse",
        term="lapse",
        market=Market.PH,
        language=Language.TAGLISH,
        domain=Sector.BANCASSURANCE,
        allowed_variants=["mawalan ng bisa", "maputol ang coverage", "lapsed", "inactive policy"],
        notes="Policy lapse is explained as 'maputol ang protection' to avoid overly legalistic jargon.",
    ),
    TerminologyItem(
        canonical_concept="coverage",
        term="coverage",
        market=Market.PH,
        language=Language.TAGLISH,
        domain=Sector.BANCASSURANCE,
        allowed_variants=["proteksyon", "sum assured", "insurance coverage", "sakop"],
        notes="Both 'coverage' and 'proteksyon' are used naturally in Taglish bancassurance dialogues.",
    ),
    TerminologyItem(
        canonical_concept="bank_referral",
        term="bank referral",
        market=Market.PH,
        language=Language.TAGLISH,
        domain=Sector.BANCASSURANCE,
        allowed_variants=["referral sa branch", "endorsement", "branch endorsement", "partner bank"],
        notes="Bancassurance warm handoff from branch teller/relationship manager to insurance financial advisor.",
    ),
    TerminologyItem(
        canonical_concept="grace_period",
        term="grace period",
        market=Market.PH,
        language=Language.TAGLISH,
        domain=Sector.BANCASSURANCE,
        allowed_variants=["palugit", "31-day grace period", "extension para magbayad"],
        notes="Typically 31 calendar days to pay overdue premium before policy lapses.",
    ),
]

ID_TERMINOLOGY_LIST: list[TerminologyItem] = [
    TerminologyItem(
        canonical_concept="installment",
        term="cicilan",
        market=Market.ID,
        language=Language.ID_FORMAL,
        domain=Sector.MULTIFINANCE,
        allowed_variants=["angsuran", "pembayaran berkala", "cicil", "cicilannya"],
        notes="'Cicilan' is standard colloquial and formal consumer finance vocabulary; 'angsuran' is formal legal.",
    ),
    TerminologyItem(
        canonical_concept="tenor",
        term="tenor",
        market=Market.ID,
        language=Language.ID_FORMAL,
        domain=Sector.MULTIFINANCE,
        allowed_variants=["jangka waktu", "periode kredit", "durasi pembiayaan", "bulan"],
        notes="'Tenor' is the standard industry English loanword accepted across Indonesian financial services.",
    ),
    TerminologyItem(
        canonical_concept="late_penalty",
        term="denda",
        market=Market.ID,
        language=Language.ID_FORMAL,
        domain=Sector.MULTIFINANCE,
        allowed_variants=["denda keterlambatan", "pinalti", "biaya denda", "denda per hari"],
        notes="Daily penalty fee for late installment payment after the due date.",
    ),
    TerminologyItem(
        canonical_concept="down_payment",
        term="DP",
        market=Market.ID,
        language=Language.ID_FORMAL,
        domain=Sector.MULTIFINANCE,
        allowed_variants=["uang muka", "down payment", "DP-nya", "dp"],
        notes="Almost universally called 'DP' (pronounced /de-pe/) in consumer automobile and cash loans.",
    ),
    TerminologyItem(
        canonical_concept="due_date",
        term="jatuh tempo",
        market=Market.ID,
        language=Language.ID_FORMAL,
        domain=Sector.MULTIFINANCE,
        allowed_variants=["tanggal jatuh tempo", "tenggat waktu", "batas bayar", "jatuh temponya"],
        notes="The fixed monthly date by which the installment must be credited without incurring penalty.",
    ),
    TerminologyItem(
        canonical_concept="installment_formal",
        term="angsuran",
        market=Market.ID,
        language=Language.ID_FORMAL,
        domain=Sector.MULTIFINANCE,
        allowed_variants=["cicilan", "angsuran bulanan", "pembayaran angsuran"],
        notes="Formal term used in financial agreements and official customer statements.",
    ),
    TerminologyItem(
        canonical_concept="financing",
        term="pembiayaan",
        market=Market.ID,
        language=Language.ID_FORMAL,
        domain=Sector.MULTIFINANCE,
        allowed_variants=["kredit", "pinjaman", "multifinance", "fasilitas dana"],
        notes="OJK-standard regulatory term for non-bank multifinance loans.",
    ),
    TerminologyItem(
        canonical_concept="early_payoff",
        term="pelunasan dipercepat",
        market=Market.ID,
        language=Language.ID_FORMAL,
        domain=Sector.MULTIFINANCE,
        allowed_variants=["pelunasan awal", "prepayment", "tutup pinjaman", "lunas duluan"],
        notes="Paying off the remaining principal ahead of schedule, usually subject to administration fees.",
    ),
]


class TerminologyDictionary:
    """Market-specific terminology dictionary with normalization and concept retrieval."""

    def __init__(self, market: Market, items: list[TerminologyItem]):
        self.market = market
        self.items = items
        self._term_to_item: dict[str, TerminologyItem] = {}
        self._concept_to_item: dict[str, TerminologyItem] = {}

        for item in items:
            self._term_to_item[item.term.lower()] = item
            self._concept_to_item[item.canonical_concept.lower()] = item

        for item in items:
            for variant in item.allowed_variants:
                var_key = variant.lower()
                if var_key not in self._term_to_item:
                    self._term_to_item[var_key] = item

    def get_by_term(self, term: str) -> Optional[TerminologyItem]:
        """Look up canonical item by exact term or variant."""
        return self._term_to_item.get(term.lower().strip())

    def get_by_concept(self, concept: str) -> Optional[TerminologyItem]:
        """Look up canonical item by canonical concept key."""
        return self._concept_to_item.get(concept.lower().strip())

    def find_terms_in_text(self, text: str) -> list[TerminologyItem]:
        """Identify all domain terminology occurrences in an utterance."""
        lower = text.lower()
        matched: list[TerminologyItem] = []
        seen_concepts = set()

        for term_str, item in self._term_to_item.items():
            # Match word boundary
            pattern = rf"\b{re.escape(term_str)}\b"
            if re.search(pattern, lower):
                if item.canonical_concept not in seen_concepts:
                    matched.append(item)
                    seen_concepts.add(item.canonical_concept)

        return matched

    def normalize_text(self, text: str) -> str:
        """Replace slang or non-canonical variations with recognized standard domain term."""
        normalized = text
        for term_str, item in self._term_to_item.items():
            if term_str != item.term.lower():
                pattern = rf"\b{re.escape(term_str)}\b"
                normalized = re.sub(pattern, item.term, normalized, flags=re.IGNORECASE)
        return normalized


# Singleton registries
PH_TERMINOLOGY = TerminologyDictionary(Market.PH, PH_TERMINOLOGY_LIST)
ID_TERMINOLOGY = TerminologyDictionary(Market.ID, ID_TERMINOLOGY_LIST)
